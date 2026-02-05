# -*- coding: utf-8 -*-
"""
backend/app/tasks/feishu_review_tasks.py - 飞书合同审查集成任务

通过 Celery 异步处理飞书文件下载和审查模块启动：
1. 接收飞书文件标识
2. 下载飞书文件到临时目录
3. 调用审查模块上传接口
4. 启动深度审查
5. 清理临时文件
6. [新增] 监听审查状态并回写结果
"""

import os
import tempfile
import time
import logging
import json
import requests
from typing import Optional

from celery import shared_task
from celery.result import AsyncResult  # [新增] 用于监听任务状态
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==================== 日志配置 ====================
logger = logging.getLogger("feishu_integration.review")
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '[%(asctime)s: %(levelname)s][feishu_review] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(console_handler)

# ==================== 配置 ====================
# 审查模块 API 地址
REVIEW_API_BASE = os.getenv("REVIEW_API_BASE", "http://localhost:8000")
REVIEW_UPLOAD_URL = f"{REVIEW_API_BASE}/api/v1/contract-review/upload"

# JWT Token
SYSTEM_SERVICE_EMAIL = os.getenv("SYSTEM_SERVICE_EMAIL", "")
SYSTEM_SERVICE_PASSWORD = os.getenv("SYSTEM_SERVICE_PASSWORD", "")

# 临时文件目录
TEMP_DIR = tempfile.gettempdir()

# 飞书多维表配置 (监控任务需要)
FEISHU_BITABLE_APP_TOKEN = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
FEISHU_BITABLE_TABLE_ID = os.getenv("FEISHU_BITABLE_TABLE_ID", "")

# 飞书卡片回调 URL
# 优先使用显式配置的 FEISHU_CARD_CALLBACK_URL，否则使用 BACKEND_PUBLIC_URL
FEISHU_CARD_CALLBACK_URL = os.getenv(
    "FEISHU_CARD_CALLBACK_URL",
    os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000") + "/api/v1/feishu/callback/position"
)


def get_review_token() -> Optional[str]:
    """获取审查模块的 JWT Token"""
    try:
        url = f"{REVIEW_API_BASE}/api/v1/auth/login"
        payload = {
            "username": SYSTEM_SERVICE_EMAIL,
            "password": SYSTEM_SERVICE_PASSWORD
        }
        # 使用表单数据格式
        response = requests.post(url, data=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            logger.error(f"❌ 获取 JWT Token 失败 | 状态码: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"❌ 获取 JWT Token 异常: {e}")
        return None


@shared_task(name="app.tasks.feishu_review_tasks.process_feishu_contract_review")
def process_feishu_contract_review(file_key: str, temp_record_id: str, reviewer_open_id: str = ""):
    """处理飞书合同审查：下载 -> 上传"""
    logger.info(f"🚀 [步骤1] 开始处理飞书合同审查 | 文件标识: {file_key}")
    
    try:
        from app.utils.feishu_api import download_feishu_file, update_feishu_bitable_record
        
        # 0. 更新状态为处理中
        update_feishu_bitable_record(temp_record_id, {"审查状态": "文件预处理中"})
    except ImportError as e:
        logger.error(f"❌ 无法导入飞书 API: {e}")
        return {"status": "error"}

    temp_file_path = os.path.join(TEMP_DIR, f"feishu_{file_key}.docx")

    try:
        # 1. 下载飞书文件
        download_success = download_feishu_file(file_key, temp_file_path, temp_record_id)
        if not download_success:
            update_feishu_bitable_record(temp_record_id, {"审查状态": "失败", "失败原因": "文件下载失败"})
            return {"status": "error"}

        # 2. 上传到审查模块
        token = get_review_token()
        if not token:
            update_feishu_bitable_record(temp_record_id, {"审查状态": "失败", "失败原因": "系统鉴权失败"})
            return {"status": "error"}

        headers = {"Authorization": f"Bearer {token}"}
        # 使用 BACKEND_PUBLIC_URL 作为回调地址（公网可访问）
        callback_url = f"{os.getenv('BACKEND_PUBLIC_URL', 'http://localhost:8000')}/api/v1/feishu/callback/review-metadata"

        with open(temp_file_path, 'rb') as f:
            files = {'file': (f"{file_key}.docx", f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
            data = {
                'auto_extract_metadata': 'true',
                'callback_url': callback_url,
                'feishu_record_id': temp_record_id,
                'feishu_file_key': file_key,
                'reviewer_open_id': reviewer_open_id
            }
            upload_response = requests.post(REVIEW_UPLOAD_URL, headers=headers, files=files, data=data, timeout=60)

        if upload_response.status_code != 200:
            logger.error(f"❌ 上传失败: {upload_response.text[:200]}")
            update_feishu_bitable_record(temp_record_id, {"审查状态": "失败", "失败原因": f"上传失败:{upload_response.status_code}"})
            return {"status": "error"}

        upload_data = upload_response.json()
        contract_id = upload_data.get("id") or upload_data.get("contract_id")
        
        # 3. 清理
        try:
            os.remove(temp_file_path)
        except:
            pass

        return {"status": "success", "data": {"contract_id": contract_id}}

    except Exception as e:
        logger.error(f"❌ 处理异常: {e}", exc_info=True)
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass
        return {"status": "error"}


@shared_task(name="app.tasks.feishu_review_tasks.process_metadata_extracted")
def process_metadata_extracted(contract_id: int, metadata: dict, feishu_record_id: str, feishu_file_key: str, reviewer_open_id: str = ""):
    """处理元数据提取完成：存储 feishu 信息 -> 回写 + 发送【交互卡片】"""
    import threading
    logger.info(f"🚀 [步骤2] 处理元数据提取完成 | contract_id: {contract_id}")

    results = {"update_success": False, "card_sent": False, "db_update_success": False}

    # ========== 新增：存储 feishu 信息到 ContractDoc ==========
    def update_contract_doc():
        try:
            from app.database import SessionLocal
            from app.models.contract import ContractDoc

            db = SessionLocal()
            try:
                contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
                if contract:
                    # 在 metadata_info 中存储 feishu 相关信息
                    # 确保 metadata_info 是字典类型
                    current_metadata = contract.metadata_info
                    if not current_metadata:
                        contract.metadata_info = {}
                    elif not isinstance(current_metadata, dict):
                        # 如果 metadata_info 不是字典，记录警告并重新初始化
                        logger.warning(f"⚠️ ContractDoc {contract_id} 的 metadata_info 类型异常: {type(current_metadata)}，重新初始化")
                        contract.metadata_info = {}

                    # 更新 feishu 信息（保留原有数据）
                    contract.metadata_info.update({
                        "feishu_record_id": feishu_record_id,
                        "feishu_file_key": feishu_file_key,
                        "reviewer_open_id": reviewer_open_id
                    })

                    db.commit()
                    results["db_update_success"] = True
                    logger.info(f"✅ Feishu 信息已存储到 ContractDoc {contract_id} | record_id: {feishu_record_id}")
                else:
                    logger.warning(f"⚠️ 未找到合同记录: {contract_id}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"❌ 更新 ContractDoc 失败: {e}", exc_info=True)

    # 并行任务1：更新 ContractDoc（新增）
    # 并行任务2：回写多维表
    # 并行任务3：发送交互卡片

    def update_bitable():
        try:
            from app.utils.feishu_api import update_feishu_bitable_record
            update_data = {
                "系统合同 ID": str(contract_id),
                "合同名称": metadata.get("contract_name", "未命名合同"),
                "提取的元数据": json.dumps(metadata, ensure_ascii=False)[:1000],
                "审查状态": "选择立场"
            }
            results["update_success"] = update_feishu_bitable_record(feishu_record_id, update_data)
            if results["update_success"]:
                logger.info("✅ 元数据回写成功")
        except Exception as e:
            logger.error(f"❌ 回写异常: {e}")

    # 并行任务2：发送交互卡片（修改为发送按钮）
    def send_stance_card():
        try:
            from app.utils.feishu_api import send_feishu_card_message, get_user_open_id_by_name
            
            target_id = reviewer_open_id or os.getenv("DEFAULT_REVIEWER_OPEN_ID", "")
            
            # 尝试姓名转换
            if target_id and not (target_id.startswith("ou_") or target_id.startswith("on_")):
                target_id = get_user_open_id_by_name(target_id)
            
            if not target_id:
                logger.warning("⚠️ 无有效审查人ID，跳过发送消息")
                return

            # 构造元数据摘要
            metadata_summary = json.dumps(metadata, ensure_ascii=False)[:300]
            contract_name = metadata.get('contract_name', '未命名合同')

            # ==================== 构造飞书交互卡片 ====================
            card_content = {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "template": "blue",
                    "title": {
                        "content": "⚖️ 合同审查 - 请确认立场",
                        "tag": "plain_text"
                    }
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "content": f"**合同名称**: {contract_name}\n**元数据摘要**: {metadata_summary}...",
                            "tag": "lark_md"
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "div",
                        "text": {
                            "content": "请点击下方按钮选择审查立场：",
                            "tag": "plain_text"
                        }
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "content": "我是甲方",
                                    "tag": "plain_text"
                                },
                                "type": "primary",
                                "value": {
                                    # 这些 value 会被回传给您的 /callback/position 接口
                                    "stance": "甲方",
                                    "contract_id": str(contract_id),
                                    "feishu_record_id": feishu_record_id
                                }
                            },
                            {
                                "tag": "button",
                                "text": {
                                    "content": "我是乙方",
                                    "tag": "plain_text"
                                },
                                "type": "primary",
                                "value": {
                                    "stance": "乙方",
                                    "contract_id": str(contract_id),
                                    "feishu_record_id": feishu_record_id
                                }
                            },
                            {
                                "tag": "button",
                                "text": {
                                    "content": "保持中立",
                                    "tag": "plain_text"
                                },
                                "type": "default",
                                "value": {
                                    "stance": "中立",
                                    "contract_id": str(contract_id),
                                    "feishu_record_id": feishu_record_id
                                }
                            }
                        ]
                    }
                ]
            }
            # ========================================================

            logger.info(f"📌 准备发送交互卡片至: {target_id}")
            if send_feishu_card_message(target_id, card_content):
                results["card_sent"] = True
                logger.info(f"✅ 立场选择卡片已发送")
            else:
                logger.error(f"❌ 卡片发送失败")

        except Exception as e:
            logger.error(f"❌ 发送消息异常: {e}", exc_info=True)

    # 并行执行
    t0 = threading.Thread(target=update_contract_doc)
    t1 = threading.Thread(target=update_bitable)
    t2 = threading.Thread(target=send_stance_card)
    t0.start(); t1.start(); t2.start()
    t0.join(); t1.join(); t2.join()

    return {"status": "success", "data": results}


@shared_task(name="app.tasks.feishu_review_tasks.process_stance_selected")
def process_stance_selected(stance: str, contract_id: int, feishu_record_id: str):
    """
    处理立场选择：回写 -> 启动审查 -> 启动监控
    """
    logger.info(f"🚀 [步骤3] 处理立场选择 | 立场: {stance}")

    try:
        from app.utils.feishu_api import update_feishu_bitable_record

        # 1. 回写状态
        update_feishu_bitable_record(feishu_record_id, {
            "选择的立场": stance,
            "审查状态": "审查中"
        })

        # 2. 启动深度审查
        token = get_review_token()
        if not token:
            raise Exception("无法获取系统 Token")

        deep_review_url = f"{REVIEW_API_BASE}/api/v1/contract-review/{contract_id}/deep-review"
        headers = {"Authorization": f"Bearer {token}"}
        data = {
            'stance': stance,
            'use_celery': 'true',
            'use_langgraph': 'true'
        }

        logger.info(f"📌 调用审查 API: {deep_review_url}")
        response = requests.post(deep_review_url, headers=headers, data=data, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"API调用失败: {response.text}")

        resp_data = response.json()
        system_task_id = resp_data.get("celery_task_id")
        logger.info(f"✅ 深度审查任务已启动 | Task ID: {system_task_id}")

        # 3. 启动监控任务 (延迟 10s 后开始)
        if system_task_id:
            logger.info(f"🚀 [步骤4] 启动审查状态监控...")
            monitor_review_status.apply_async(
                args=[system_task_id, feishu_record_id, str(contract_id)],
                countdown=10
            )

        return {"status": "success", "task_id": system_task_id}

    except Exception as e:
        logger.error(f"❌ 处理立场选择异常: {e}", exc_info=True)
        # 尝试回写错误
        try:
            update_feishu_bitable_record(feishu_record_id, {
                "审查状态": "失败", 
                "失败原因": str(e)[:200]
            })
        except:
            pass
        return {"status": "error", "message": str(e)}


@shared_task(bind=True, max_retries=120, name="app.tasks.feishu_review_tasks.monitor_review_status")
def monitor_review_status(self, system_task_id: str, feishu_record_id: str, contract_id: str):
    """
    [新增] 监听深度审查任务状态 (轮询机制)
    每 30 秒检查一次，最多检查 1 小时
    """
    try:
        # 获取任务状态
        result = AsyncResult(system_task_id)
        state = result.state

        logger.info(f"🔍 [监控] 任务状态: {state} | ID: {system_task_id}")

        if state == 'SUCCESS':
            logger.info(f"✅ 审查任务完成: {system_task_id}")
            
            # 解析结果路径
            result_data = result.result
            file_path = None
            if isinstance(result_data, dict):
                # 兼容不同的返回结构
                file_path = result_data.get("file_path") or \
                            result_data.get("data", {}).get("file_path") or \
                            result_data.get("result_file_path")
            elif isinstance(result_data, str):
                file_path = result_data

            _handle_review_completion(feishu_record_id, file_path, contract_id)
            
        elif state == 'FAILURE':
            error_msg = str(result.result)
            logger.error(f"❌ 审查任务失败: {error_msg}")
            _handle_review_failure(feishu_record_id, error_msg)
            
        elif state in ['PENDING', 'STARTED', 'RETRY']:
            # 继续等待，30秒后重试
            raise self.retry(countdown=30)
            
        else:
            # 未知状态也重试
            raise self.retry(countdown=30)

    except Exception as e:
        # 如果是 retry 抛出的异常，直接抛出
        if "Retry" in str(type(e)):
            raise e
        logger.error(f"❌ 监控任务异常: {e}", exc_info=True)
        # 异常情况下也重试，防止监控中断
        raise self.retry(countdown=60)


def _handle_review_completion(record_id: str, file_path: str, contract_id: str = None):
    """
    内部函数：处理审查完成 (回写状态 + 审查意见 + 发送卡片通知)

    参数:
        record_id: 飞书多维表记录ID
        file_path: 审查结果文件路径（保留兼容，但不再使用）
        contract_id: 系统合同ID
    """
    try:
        from app.utils.feishu_api import update_feishu_bitable_record, send_feishu_card_message, get_bitable_record_simple
        from app.database import SessionLocal
        from app.models.contract import ContractDoc, ContractReviewItem

        # 1. 获取审查结果数据
        review_summary = ""
        review_items_count = 0
        if contract_id:
            db = SessionLocal()
            try:
                contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
                if contract:
                    review_items = contract.review_items
                    review_items_count = len(review_items)

                    if review_items:
                        # 生成审查意见摘要（前5条）
                        summary_lines = []
                        for idx, item in enumerate(review_items[:5], 1):
                            severity_emoji = {
                                "Critical": "🔴",
                                "High": "🟠",
                                "Medium": "🟡",
                                "Low": "🟢"
                            }.get(item.severity, "⚪")

                            summary_lines.append(
                                f"{idx}. {severity_emoji} [{item.issue_type}]\n"
                                f"   原文：{item.quote[:50]}...\n"
                                f"   建议：{item.suggestion[:80]}..."
                            )

                        review_summary = "\n\n".join(summary_lines)

                        if len(review_items) > 5:
                            review_summary += f"\n\n... 还有 {len(review_items) - 5} 条审查意见"
            finally:
                db.close()

        # 2. 回写多维表状态和审查意见
        fields = {
            "审查状态": "AI审查完成"
        }

        # 如果有审查意见，添加到回写字段
        if review_summary:
            fields["审查意见"] = review_summary

        update_feishu_bitable_record(record_id, fields)
        logger.info(f"✅ 状态和审查意见已回写至多维表: {record_id} -> AI审查完成，共{review_items_count}条意见")

        # 3. 发送卡片通知 - 包含审查结果页面链接
        try:
            # 获取记录详情以找到审查人
            record_data = get_bitable_record_simple(record_id)
            if not record_data:
                logger.warning(f"⚠️ 无法获取记录详情: {record_id}")
                return

            # 提取审查人信息
            fields_data = record_data.get("fields", {})
            reviewer_field = fields_data.get("审查人", {})
            reviewer_list = reviewer_field.get("reviewer", []) if isinstance(reviewer_field, dict) else reviewer_field

            # 合同名称
            contract_name = fields_data.get("合同名称", "") or "未命名合同"

            # 构造审查结果页面URL
            # 前端是通过后端静态文件服务提供的，所以使用 BACKEND_PUBLIC_URL
            backend_public_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
            review_url = f"{backend_public_url}/contract/review/{contract_id}?feishu_record_id={record_id}"

            # 构造飞书卡片内容
            card_content = {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "content": "📋 合同审查已完成",
                        "tag": "plain_text"
                    },
                    "template": "green"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**合同名称**\n{contract_name}\n\n**审查结果**\nAI 审查已完成，共发现若干风险点和修改建议。\n\n请点击下方按钮查看详细审查结果。"
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "content": "查看审查结果",
                                    "tag": "plain_text"
                                },
                                "type": "primary",
                                "url": review_url
                            },
                            {
                                "tag": "button",
                                "text": {
                                    "content": "前往多维表",
                                    "tag": "plain_text"
                                },
                                "type": "default",
                                "url": f"{backend_public_url}/bitable/{record_id}"
                            }
                        ]
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "plain_text",
                            "content": "💡 提示：您可以根据审查意见对合同条款进行修改"
                        }
                    }
                ]
            }

            # 发送卡片通知给审查人
            if reviewer_list:
                for reviewer in reviewer_list:
                    reviewer_open_id = reviewer.get("id", "") or reviewer.get("open_id", "")
                    if reviewer_open_id:
                        success = send_feishu_card_message(reviewer_open_id, card_content)
                        if success:
                            logger.info(f"✅ 已发送审查完成卡片通知给审查人: {reviewer_open_id[:20]}...")
                        else:
                            logger.error(f"❌ 发送卡片通知失败: {reviewer_open_id[:20]}...")
            else:
                logger.warning(f"⚠️ 未找到审查人，跳过通知发送")

        except Exception as e:
            logger.error(f"❌ 发送卡片通知失败: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"❌ 结果处理失败: {e}")
        _handle_review_failure(record_id, f"结果回写失败: {str(e)}")


def _handle_review_failure(record_id: str, error_msg: str):
    """内部函数：处理审查失败"""
    try:
        from app.utils.feishu_api import update_feishu_bitable_record
        update_feishu_bitable_record(record_id, {
            "审查状态": "失败", 
            "失败原因": str(error_msg)[:200]
        })
    except Exception as e:
        logger.error(f"❌ 更新失败状态异常: {e}")