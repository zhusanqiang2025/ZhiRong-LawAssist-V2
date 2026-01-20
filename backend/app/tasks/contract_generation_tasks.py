# backend/app/tasks/contract_generation_tasks.py
"""
合同生成 Celery 任务定义

将异步的合同生成工作流封装为 Celery 任务，支持：
1. 异步执行（解决 HTTP 超时问题）
2. 进度实时推送 (WebSocket)
3. 自动重试机制
4. 运行在高优先级队列
5. 【新增】数据库持久化集成
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from celery import shared_task
from app.tasks.base_task import DatabaseTask
from app.tasks.progress import TaskProgress, send_task_notification
from app.services.contract_generation.workflow import generate_contract_simple
# 【新增】数据库相关导入
from app.database import SessionLocal
from app.crud.task import task as crud_task

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.contract_generation.generate",
    queue="high_priority",  # 指定高优先级队列
    acks_late=True,         # 任务完成后确认，防止丢失
    max_retries=3,          # 最大重试次数
    default_retry_delay=60  # 重试延迟(秒)
)
def task_generate_contract(
    self,
    user_input: str,
    uploaded_files: List[str],
    pre_analysis_result: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    planning_mode: Optional[str] = "single_model",  # 【新增】
    owner_id: Optional[int] = None,  # 【新增】用于数据库记录
    skip_template: Optional[bool] = False,  # 【新增】是否跳过模板匹配
    confirmed_modification_termination_info: Optional[Dict[str, Any]] = None  # 【新增】Step 2 确认的变更/解除信息
):
    """
    Celery 任务：执行合同生成工作流

    Args:
        user_input: 用户需求描述
        uploaded_files: 上传的文件路径列表
        pre_analysis_result: 前端缓存的分析结果（用于跳过重复分析）
        session_id: 会话 ID
        planning_mode: 规划模式（"single_model" 或 "multi_model"）【新增】
        owner_id: 用户ID（用于数据库记录）【新增】
        skip_template: 是否跳过模板匹配【新增】
        confirmed_modification_termination_info: Step 2 确认的变更/解除信息【新增】
    """
    celery_task_id = self.request.id
    progress = TaskProgress(celery_task_id)

    # 【新增】创建数据库会话
    db = SessionLocal()
    task_record = None

    logger.info(f"[Celery] 开始执行合同生成任务: {celery_task_id}, planning_mode={planning_mode}, skip_template={skip_template}")

    try:
        # 【新增】1. 创建任务记录
        if owner_id:
            task_record = crud_task.create_contract_generation_task(
                db=db,
                owner_id=owner_id,
                user_input=user_input,
                planning_mode=planning_mode or "single_model",
                uploaded_files=uploaded_files,
                session_id=session_id,
                status="running",
                celery_task_id=celery_task_id
            )
            logger.info(f"[Celery] 创建任务记录: {task_record.id}")

        # 2. 报告初始化状态
        progress.report(10, "任务已启动，正在初始化智能生成引擎...", "initializing")

        # 【新增】3. 更新任务进度
        if task_record:
            crud_task.update_contract_generation_progress(
                db=db,
                task_id=task_record.id,
                progress=10.0,
                status="processing"
            )

        # 4. 准备运行环境
        # 由于 Celery Worker 是同步运行的，而 core logic 是 async 的
        # 我们需要创建一个新的事件循环来运行 async 代码
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            progress.report(30, "正在进行深度法律分析与合同起草 (预计耗时 1-3 分钟)...", "processing")

            # 【新增】5. 更新任务进度
            if task_record:
                crud_task.update_contract_generation_progress(
                    db=db,
                    task_id=task_record.id,
                    progress=30.0
                )

            # 6. 执行核心工作流 (同步等待异步结果)
            result = loop.run_until_complete(
                generate_contract_simple(
                    user_input=user_input,
                    uploaded_files=uploaded_files,
                    pre_analysis_result=pre_analysis_result,
                    planning_mode=planning_mode or "single_model",
                    skip_template=skip_template or False,  # 【新增】传递 skip_template
                    confirmed_modification_termination_info=confirmed_modification_termination_info  # 【新增】传递确认信息
                )
            )

            # 7. 处理结果
            if result.get("success"):
                # 【新增】保存融合报告
                if task_record and result.get("synthesis_report"):
                    crud_task.save_synthesis_report(
                        db=db,
                        task_id=task_record.id,
                        synthesis_report=result["synthesis_report"]
                    )

                # 【新增】标记任务完成
                if task_record:
                    crud_task.update_contract_generation_progress(
                        db=db,
                        task_id=task_record.id,
                        progress=100.0,
                        status="completed",
                        result_data={
                            "generated_contracts": result.get("contracts", []),
                            "processing_type": result.get("processing_type"),
                            "synthesis_report": result.get("synthesis_report"),
                            "contract_plan": result.get("contract_plan")
                        }
                    )

                # 成功完成
                progress.report(100, "合同生成完成", "completed", {
                    "contracts": result.get("contracts", []),
                    "processing_type": result.get("processing_type"),
                    "clarification_questions": result.get("clarification_questions", []),
                    # 【新增】多模型融合报告
                    "synthesis_report": result.get("synthesis_report"),
                    "contract_plan": result.get("contract_plan")
                })

                # 【新增】发送完成通知到 WebSocket（task_completed 类型）
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        send_task_notification(
                            task_id=celery_task_id,
                            notification_type="completed",
                            message="合同生成完成",
                            data={
                                "contracts": result.get("contracts", []),
                                "processing_type": result.get("processing_type"),
                                "clarification_questions": result.get("clarification_questions", []),
                                "synthesis_report": result.get("synthesis_report"),
                                "contract_plan": result.get("contract_plan")
                            }
                        )
                    )
                except Exception as notify_error:
                    logger.error(f"[Celery] 发送完成通知失败: {notify_error}")

                logger.info(f"[Celery] 任务 {celery_task_id} 执行成功")
                return result
            else:
                # 【新增】标记任务失败
                if task_record:
                    crud_task.update_contract_generation_progress(
                        db=db,
                        task_id=task_record.id,
                        status="failed"
                    )

                # 逻辑失败（如 LLM 报错）
                error_msg = result.get("error", "未知生成错误")
                logger.error(f"[Celery] 任务逻辑失败: {error_msg}")
                progress.report(100, f"生成失败: {error_msg}", "failed")

                # 【新增】发送失败通知到 WebSocket
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        send_task_notification(
                            task_id=celery_task_id,
                            notification_type="failed",
                            message=f"生成失败: {error_msg}",
                            data={"error": error_msg}
                        )
                    )
                except Exception as notify_error:
                    logger.error(f"[Celery] 发送失败通知失败: {notify_error}")

                # 可以选择抛出异常触发重试，或者直接标记失败
                # 这里选择抛出异常以便记录到 Flower
                raise Exception(error_msg)

        finally:
            # 清理事件循环
            loop.close()

    except Exception as e:
        logger.error(f"[Celery] 任务 {celery_task_id} 发生异常: {str(e)}", exc_info=True)

        # 【新增】标记任务失败
        if task_record:
            try:
                crud_task.update_contract_generation_progress(
                    db=db,
                    task_id=task_record.id,
                    status="failed"
                )
            except Exception as db_error:
                logger.error(f"[Celery] 更新失败状态时出错: {db_error}")

        # 报告失败状态
        progress.report(100, f"系统异常: {str(e)}", "failed")

        # 【新增】发送失败通知到 WebSocket
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(
                send_task_notification(
                    task_id=celery_task_id,
                    notification_type="failed",
                    message=f"系统异常: {str(e)}",
                    data={"error": str(e)}
                )
            )
        except Exception as notify_error:
            logger.error(f"[Celery] 发送失败通知失败: {notify_error}")

        # 触发自动重试 (捕获所有未处理的异常)
        # exc=e 会保留原始堆栈信息
        raise self.retry(exc=e)

    finally:
        # 【新增】确保关闭数据库会话
        if db:
            db.close()
            logger.debug(f"[Celery] 数据库会话已关闭")