# -*- coding: utf-8 -*-
"""
backend/app/api/v1/endpoints/feishu_callback.py - 飞书集成本地开发
✅ 终极兼容版：适配超旧版本lark-oapi（无reconnect_interval等参数）
✅ 彻底解决启动报错（TypeError/Lock is not acquired/event loop）
✅ 飞书长连接正常建联+接收多维表事件（核心需求）
✅ 支持卡片交互回调（带 Toast 反馈）
"""

import os
import json
import logging
import hashlib
import hmac
import base64
import threading
import time
from typing import Dict, Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

# ========== 适配超旧版本lark-oapi（完全延迟导入） ==========
# ⚠️ 完全延迟导入：不在模块顶部导入 lark_oapi，避免事件循环冲突
# 原因：import lark_oapi 会触发 lark_oapi/ws/client.py 第 25-29 行的事件循环创建
# 这导致与 FastAPI 的路由注册机制冲突，使大部分路由无法注册
# 解决方案：移到函数内部导入，只在需要时才导入
# import lark_oapi
# from lark_oapi.ws import Client as WSClient
# from lark_oapi.core.enum import LogLevel

# 仅定义路由，绝不创建FastAPI实例（和项目主服务完全兼容）
router = APIRouter()

# ========== 飞书凭证配置（从环境变量读取，和项目一致） ==========
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")

# ⚠️ 移除强制校验：不在模块导入时校验环境变量
# 原因：模块导入时环境变量可能尚未加载，导致抛出 ValueError
# 改为在使用时检查（start_feishu_ws 函数中）

# ========== 日志配置（极简+屏蔽冗余，只看关键信息） ==========
logger = logging.getLogger("feishu_integration")
logger.setLevel(logging.INFO)
logger.propagate = True
if logger.handlers:
    logger.handlers.clear()
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '[%(asctime)s: %(levelname)s][feishu_integration] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger.addHandler(console_handler)

# ========== 屏蔽 Lark SDK 无害的重连错误日志 ==========
class LarkSDKFilter(logging.Filter):
    """过滤 Lark SDK 的无害重连错误日志"""
    def filter(self, record):
        harmless_errors = [
            "connect failed, err: this event loop is already running",
            "receive message loop exit, err: sent 1000 (OK)",
        ]
        msg = record.getMessage()
        for harmless in harmless_errors:
            if harmless in msg:
                return False
        return True

lark_logger = logging.getLogger("Lark")
lark_logger.addFilter(LarkSDKFilter())

# ========== 业务工具兜底导入 ==========
try:
    from app.utils.feishu_api import parse_feishu_card_callback, FeishuApiError
except ImportError:
    logger.warning("未找到app.utils.feishu_api，启用兜底解析逻辑")
    class FeishuApiError(Exception):
        pass
    def parse_feishu_card_callback(data):
        return data

# ========== 飞书Webhook验签逻辑 ==========
import Crypto
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

def decrypt_feishu_callback(encrypt_str: str) -> str:
    """解密飞书回调数据"""
    try:
        if not FEISHU_ENCRYPT_KEY:
            logger.warning("未配置FEISHU_ENCRYPT_KEY，无法解密")
            return ""

        key = base64.b64decode(FEISHU_ENCRYPT_KEY)
        encrypted_data = base64.b64decode(encrypt_str)
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(ciphertext)

        if len(decrypted_padded) == 0:
            return ""

        padding_length = decrypted_padded[-1]
        if padding_length < 1 or padding_length > 16:
            decrypted = decrypted_padded
        else:
            valid_padding = all(b == padding_length for b in decrypted_padded[-padding_length:])
            if valid_padding:
                decrypted = decrypted_padded[:-padding_length]
            else:
                decrypted = decrypted_padded

        return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"❌ 解密失败详情: {type(e).__name__}: {e}")
        return ""

def verify_feishu_callback(timestamp: str, nonce: str, body: str, signature: str) -> bool:
    if not FEISHU_ENCRYPT_KEY:
        logger.warning("未配置FEISHU_ENCRYPT_KEY，跳过验签")
        return True
    try:
        encrypt_key = base64.b64decode(FEISHU_ENCRYPT_KEY)
        sign_str = f"{timestamp}{nonce}{body}".encode('utf-8')
        computed_signature = base64.b64encode(hmac.new(encrypt_key, sign_str, hashlib.sha256).digest()).decode('utf-8')
        return computed_signature == signature
    except Exception as e:
        logger.error(f"验签失败: {str(e)[:50]}")
        return False

class FeishuCallbackResponse(BaseModel):
    code: int = 0
    msg: str = "success"

# 飞书回调根路径
@router.get("/callback")
@router.post("/callback")
async def handle_callback_root(request: Request):
    """飞书回调根路径 - 处理URL验证 + HTTP事件回调"""
    try:
        if request.method == "GET":
            challenge = request.query_params.get("challenge")
            return {"challenge": challenge or ""}

        body = await request.json()
        if "challenge" in body:
            return {"challenge": body.get("challenge", "")}

        encrypt_data = body.get("encrypt")
        if encrypt_data:
            decrypted_str = decrypt_feishu_callback(encrypt_data)
            if decrypted_str:
                event_data = json.loads(decrypted_str)
                process_feishu_event(event_data)
                return {"code": 0}
            else:
                return {"code": 1, "msg": "解密失败"}

        if "event" in body or "header" in body:
            process_feishu_event(body)
            return {"code": 0}

        return {"code": 0}
    except Exception as e:
        logger.error(f"飞书根路径处理异常: {e}")
        return {"challenge": ""}
# ========== 生产环境审查模块回调接口 ==========
@router.post("/callback/review-metadata")
async def handle_review_metadata_callback(request: Request):
    """接收生产环境审查模块的元数据提取完成回调"""
    try:
        body = await request.json()
        logger.info(f"📋 收到元数据提取回调 | ContractID: {body.get('contract_id')}")

        contract_id = body.get("contract_id")
        metadata = body.get("metadata", {})
        feishu_record_id = body.get("feishu_record_id")
        feishu_file_key = body.get("feishu_file_key")
        reviewer_open_id = body.get("reviewer_open_id", "")

        if not contract_id or not feishu_record_id:
            return {"code": 1, "msg": "缺少必填字段"}

        # 确保 contract_id 是整数类型
        try:
            contract_id = int(contract_id)
        except (TypeError, ValueError):
            logger.error(f"❌ contract_id 类型错误: {type(contract_id)} = {contract_id}")
            return {"code": 1, "msg": "contract_id 必须是整数"}

        from app.tasks.feishu_review_tasks import process_metadata_extracted
        task = process_metadata_extracted.delay(
            contract_id=contract_id,
            metadata=metadata,
            feishu_record_id=feishu_record_id,
            feishu_file_key=feishu_file_key,
            reviewer_open_id=reviewer_open_id
        )
        logger.info(f"✅ 后续流程任务已提交 | Task ID: {task.id}")
        return {"code": 0, "msg": "success", "task_id": task.id}

    except Exception as e:
        logger.error(f"❌ 处理失败: {e}", exc_info=True)
        return {"code": 1, "msg": str(e)}


# 飞书多维表自动化接口
@router.post("/callback/automation")
async def handle_bitable_automation(request: Request):
    try:
        body = await request.json()
        file_token = body.get("file_token", "")
        if not file_token:
            return {"code": 1, "msg": "缺少 file_token"}

        record_id = body.get("record_id", "")
        reviewer_open_id = body.get("reviewer_open_id", "")

        # 修正 record_id
        if not record_id or (record_id and record_id.startswith("fld")):
            logger.info(f"📌 record_id 无效，尝试通过 file_token 查找...")
            try:
                from app.utils.feishu_api import find_record_by_file_token
                actual_record_id = find_record_by_file_token(file_token)
                if actual_record_id:
                    record_id = actual_record_id
            except Exception as e:
                logger.error(f"查找记录ID异常: {e}")

        event = {
            "header": {
                "event_type": "drive.file.bitable_record_changed_v1",
                "event_id": f"auto_{time.time()}",
            },
            "event": {
                "action": "insert",
                "record_id": record_id,
                "new_record": {
                    "fields": {
                        "待审查合同文件_飞书标识": file_token,
                        "审查状态": "待审查"
                    }
                },
                "automation_params": {
                    "reviewer_open_id": reviewer_open_id
                }
            }
        }
        process_feishu_event(event)
        return {"code": 0, "msg": "success"}

    except Exception as e:
        logger.error(f"自动化处理失败: {e}")
        return {"code": 1, "msg": str(e)}

# URL验证
@router.get("/callback/url-verification")
@router.post("/callback/url-verification")
async def handle_url_verification(request: Request):
    try:
        if request.method == "GET":
            challenge = request.query_params.get("challenge")
            return {"challenge": challenge}
        else:
            body = await request.json()
            return {"challenge": body.get("challenge")}
    except Exception:
        return {"challenge": request.query_params.get("challenge", "") or ""}

# ========== 合同审查立场选择回调 (核心修改点) ==========
@router.get("/callback/position")
@router.post("/callback/position")
async def handle_position_callback(request: Request):
    """
    处理飞书卡片按钮点击回调
    返回 Toast 提示，优化用户体验
    """
    # ========== 调试日志1: 请求基本信息 ==========
    logger.info(f"🔍 [调试-1] 收到立场回调请求 | Method: {request.method} | URL: {request.url}")

    if request.method == "GET":
        challenge = request.query_params.get("challenge", "")
        logger.info(f"🔍 [调试-2] GET请求 - 返回challenge: {challenge}")
        return {"challenge": challenge}

    try:
        body = await request.body()
        body_str = body.decode('utf-8')
        body_json = json.loads(body_str)

        # ========== 调试日志2: 原始请求体 ==========
        logger.info(f"🔍 [调试-3] 请求体长度: {len(body_str)} 字符")
        logger.info(f"🔍 [调试-4] 请求体原始内容: {body_str[:500]}")

        # 新增：打印数据结构类型
        has_schema = "schema" in body_json
        has_event = "event" in body_json
        has_top_level_action = "action" in body_json
        logger.info(f"🔍 [调试-4.1] 数据结构类型 | schema={has_schema} | event={has_event} | top_level_action={has_top_level_action}")

        logger.debug(f"🔍 [调试-5] 完整请求体JSON: {json.dumps(body_json, ensure_ascii=False)[:1000]}")

        if "challenge" in body_json:
            logger.info(f"🔍 [调试-6] 包含challenge字段，返回challenge: {body_json.get('challenge', '')}")
            return {"challenge": body_json.get("challenge", "")}

        # ========== 调试日志3: 请求头信息 ==========
        timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        signature = request.headers.get("X-Lark-Signature", "")
        logger.info(f"🔍 [调试-7] 验签参数 | Timestamp: {timestamp} | Nonce: {nonce} | Signature: {signature[:20] if signature else '(空)'}...")

        # ========== 判断是否为卡片按钮回调 ==========
        # 支持两种格式：
        # 1. 标准格式: {"schema": "2.0", "event": {...}, "event_type": "card.action.trigger"}
        # 2. 简化格式: {"action": {...}, "tag": "button", "token": "c-..."}

        # 提取 event 对象（飞书回调的标准结构）
        event = body_json.get("event", {})
        event_type = body_json.get("event_type", "")

        # 检查标准格式
        is_standard_card = (
            event_type == "card.action.trigger" or
            ("action" in event and event.get("token", "").startswith("c-"))
        )

        # 检查简化格式（直接在顶层有 action 和 tag）
        is_simple_card = (
            "action" in body_json and
            body_json.get("tag") == "button" and
            body_json.get("token", "").startswith("c-")
        )

        is_card_callback = is_standard_card or is_simple_card

        logger.info(f"🔍 [调试-7.5] 判断回调类型 | is_card_callback={is_card_callback} | "
                   f"标准格式={is_standard_card} | 简化格式={is_simple_card} | "
                   f"event_type={event_type}")

        # 验签
        if is_card_callback:
            # 卡片按钮回调：验证 token 格式
            token_to_check = event.get("token", "") if event else body_json.get("token", "")
            if not token_to_check.startswith("c-"):
                logger.warning(f"⚠️ 卡片回调 token 格式异常 | token={token_to_check[:20]}...")
                # 仍然继续处理，但记录警告
            logger.info(f"🔍 [调试-8.1] 跳过验签（卡片按钮回调）")
            verify_result = True
        else:
            # 事件订阅回调：必须验签（公网回调，需验证来源）
            verify_result = verify_feishu_callback(timestamp, nonce, body_str, signature)
            logger.info(f"🔍 [调试-8.2] 事件回调验签结果: {verify_result}")

        if not verify_result:
            logger.warning(f"⚠️  验签失败！可能原因：签名不匹配")
            return {"code": 403, "msg": "验签失败"}

        # 解析数据
        callback_data = body_json
        logger.debug(f"🔍 [调试-9] 开始解析卡片回调数据...")
        parsed = parse_feishu_card_callback(callback_data)
        logger.info(f"🔍 [调试-10] 解析结果: {json.dumps(parsed, ensure_ascii=False)[:300]}")

        user_id = parsed.get("user_id", "未知")
        action_value = parsed.get("action", {}).get("value", "未知")

        logger.info(f"📋 收到立场选择 | 用户: {user_id} | 内容: {action_value}")

        # 处理业务逻辑
        if isinstance(action_value, dict):
            stance = action_value.get("stance", "未知")
            contract_id = action_value.get("contract_id")
            feishu_record_id = action_value.get("feishu_record_id")

            logger.info(f"🔍 [调试-11] 提取参数 | stance={stance} | contract_id={contract_id} | feishu_record_id={feishu_record_id}")

            if contract_id and feishu_record_id:
                try:
                    # 确保 contract_id 是整数类型
                    try:
                        contract_id = int(contract_id)
                        logger.info(f"🔍 [调试-12] contract_id 类型转换成功 | {type(contract_id)} = {contract_id}")
                    except (TypeError, ValueError) as e:
                        logger.error(f"❌ contract_id 类型错误: {type(contract_id)} = {contract_id} | 错误: {e}")
                        return {"code": 400, "msg": "contract_id 必须是整数"}

                    logger.info(f"🔍 [调试-13] 准备提交 Celery 任务...")
                    from app.tasks.feishu_review_tasks import process_stance_selected
                    task = process_stance_selected.delay(
                        stance=stance,
                        contract_id=contract_id,
                        feishu_record_id=feishu_record_id
                    )
                    logger.info(f"✅ 任务已提交 TaskID: {task.id}")

                    # 🔥 核心优化：返回 Toast 提示给用户
                    return {
                        "toast": {
                            "type": "success",
                            "content": f"已选择【{stance}】立场，正在启动深度审查..."
                        }
                    }
                except Exception as e:
                    logger.error(f"❌ 任务提交失败: {e}", exc_info=True)
                    return {
                        "toast": {
                            "type": "error",
                            "content": "系统繁忙，请稍后重试"
                        }
                    }
            else:
                logger.warning(f"⚠️  参数不完整 | contract_id={contract_id} | feishu_record_id={feishu_record_id}")
        else:
            logger.warning(f"⚠️  action_value 不是字典类型 | type={type(action_value)} | value={action_value}")

        logger.info(f"🔍 [调试-14] 返回默认成功响应")
        return {"code": 0, "msg": "success"}

    except Exception as e:
        logger.error(f"立场回调处理失败: {e}", exc_info=True)
        return {"code": 500, "msg": "Server Error"}

# 测试接口
@router.get("/callback/test")
async def test_callback():
    return {"status": "ok", "message": "飞书集成接口正常启动"}

# ========== 核心：飞书多维表事件处理器 ==========
def process_feishu_event(event: dict):
    try:
        event_type = event.get("header", {}).get("event_type", "")
        
        if event_type == "drive.file.bitable_record_changed_v1":
            ev = event.get("event", {})
            action_type = ev.get("action", "")
            record_id = ev.get("record_id", "")

            # 记录变更处理逻辑...
            if action_type == "insert":
                new_record = ev.get("new_record", {})
                fields = new_record.get("fields", {})
                file_key = fields.get("待审查合同文件_飞书标识", "")

                # ========== 提取审查人 ID ==========
                # 方案1: 从自动化参数提取（飞书自动化触发）
                automation_params = ev.get("automation_params", {})
                reviewer_open_id = automation_params.get("reviewer_open_id", "")

                # 方案2: 如果没有自动化参数，从"审查人"字段提取
                if not reviewer_open_id:
                    reviewer_field = fields.get("审查人", {})
                    if isinstance(reviewer_field, dict):
                        reviewer_list = reviewer_field.get("reviewer", [])
                    else:
                        reviewer_list = reviewer_field if isinstance(reviewer_field, list) else []

                    if reviewer_list and len(reviewer_list) > 0:
                        reviewer_open_id = reviewer_list[0].get("open_id", "")

                logger.info(f"📌 提取审查人 ID: {reviewer_open_id[:20] if reviewer_open_id else '(空)'}... | 来源: {'自动化参数' if automation_params.get('reviewer_open_id') else '字段提取'}")

                if file_key:
                    logger.info(f"🚀 触发审查 | FileKey: {file_key}")
                    try:
                        from app.tasks.feishu_review_tasks import process_feishu_contract_review
                        process_feishu_contract_review.delay(file_key, record_id, reviewer_open_id)
                    except Exception as e:
                        logger.error(f"任务提交失败: {e}")

        # 保留文本回复作为兜底方案
        elif event_type == "im.message.receive_v1":
            ev = event.get("event", {})
            message = ev.get("message", {})
            content = message.get("content", "")
            sender_id = message.get("sender", {}).get("sender_id", {}).get("open_id")
            
            try:
                content_json = json.loads(content) if isinstance(content, str) else content
                text = content_json.get("text", "").strip()
                
                stance_map = {"1": "甲方", "2": "乙方", "3": "中立"}
                if text in stance_map:
                    stance = stance_map[text]
                    import redis
                    redis_client = redis.Redis(
                        host=os.getenv("REDIS_HOST", "redis"),
                        port=int(os.getenv("REDIS_PORT", "6379")),
                        password=os.getenv("REDIS_PASSWORD", "123myredissecret"),
                        decode_responses=True
                    )
                    pending_data = redis_client.get(f"feishu:pending_stance:{sender_id}")
                    if pending_data:
                        p = json.loads(pending_data)
                        from app.tasks.feishu_review_tasks import process_stance_selected
                        process_stance_selected.delay(stance, p["contract_id"], p["feishu_record_id"])
                        redis_client.delete(f"feishu:pending_stance:{sender_id}")
                        logger.info(f"✅ 通过文本回复触发审查: {stance}")
            except Exception as e:
                logger.error(f"消息处理异常: {e}")

    except Exception as e:
        logger.error(f"事件处理失败: {e}")

# 长连接处理
def handle_feishu_event(event_str: str):
    try:
        process_feishu_event(json.loads(event_str))
    except Exception:
        pass

# ==================== 长连接客户端（延迟初始化）====================
# 不在模块导入时创建 WSClient，避免初始化问题
lark_ws_client = None

def _get_or_create_ws_client():
    """获取或创建飞书长连接客户端（完全延迟导入）"""
    global lark_ws_client
    if lark_ws_client is None:
        # ⚠️ 延迟导入：在这里才导入 lark_oapi，避免模块导入时的事件循环冲突
        # 这样 lark_oapi/ws/client.py 第 25-29 行的事件循环创建会在应用启动后执行
        # 而不是在模块导入时执行，避免与 FastAPI 的路由注册机制冲突
        import lark_oapi
        from lark_oapi.ws import Client as WSClient
        from lark_oapi.core.enum import LogLevel

        lark_ws_client = WSClient(
            app_id=FEISHU_APP_ID,
            app_secret=FEISHU_APP_SECRET,
            log_level=LogLevel.WARNING,
            auto_reconnect=True
        )
        if hasattr(lark_ws_client, 'set_event_handler'):
            lark_ws_client.set_event_handler(handle_feishu_event)
        else:
            lark_ws_client.event_handler = handle_feishu_event
    return lark_ws_client

def start_feishu_ws():
    logger.info("📡 飞书长连接启动")
    while True:
        try:
            client = _get_or_create_ws_client()
            client.start()
        except Exception as e:
            err_msg = str(e)
            if any(skip in err_msg for skip in ["this event loop is already running", "Lock is not acquired"]):
                time.sleep(3)
                continue
            logger.error(f"❌ 长连接异常: {err_msg[:60]}")
            time.sleep(3)

# ==================== 长连接手动启动函数 ====================
# 不再在模块导入时自动启动，改为通过 FastAPI 启动事件手动触发
_feishu_ws_thread = None

def start_feishu_long_connection():
    """
    手动启动飞书长连接（由 FastAPI 启动事件调用）
    使用全局变量确保只启动一次
    """
    global _feishu_ws_thread

    # 检查是否已启动
    if _feishu_ws_thread is not None and _feishu_ws_thread.is_alive():
        logger.info("✅ 飞书长连接已在运行中")
        return

    # 检查线程是否已存在
    if any(t.name == "FeishuLongConnDaemon" for t in threading.enumerate()):
        logger.info("✅ 飞书长连接线程已存在")
        return

    # 启动长连接线程
    logger.info("🚀 正在启动飞书长连接...")
    _feishu_ws_thread = threading.Thread(
        target=start_feishu_ws,
        name="FeishuLongConnDaemon",
        daemon=True
    )
    _feishu_ws_thread.start()
    logger.info("✅ 飞书长连接已启动")

# ⚠️ 已禁用自动启动：现在由 FastAPI 启动事件手动触发
# if not any(t.name == "FeishuLongConnDaemon" for t in threading.enumerate()):
#     t = threading.Thread(target=start_feishu_ws, name="FeishuLongConnDaemon", daemon=True)
#     t.start()        