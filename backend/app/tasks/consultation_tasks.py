# backend/app/tasks/consultation_tasks.py
"""
智能咨询 Celery 任务

支持异步执行和进度保存，与HTTP请求解耦

批准条件：Celery任务使用独立数据库会话（避免跨线程错误）
"""
import logging
from typing import Optional, Dict, Any
from celery import shared_task
from app.tasks.base_task import DatabaseTask

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.consultation.run",
    queue="high_priority",
    max_retries=2,
    default_retry_delay=30
)
def task_run_consultation(
    self,
    session_id: str,
    question: str,
    context: Dict[str, Any],
    user_id: int,
    user_confirmed: bool = False,
    selected_suggested_questions: Optional[list] = None,
    previous_specialist_output: Optional[Dict[str, Any]] = None,
    saved_classification: Optional[Dict[str, Any]] = None
):
    """
    执行法律咨询任务（后台运行）

    与HTTP请求解耦，确保用户关闭页面后任务继续执行

    批准条件：使用独立数据库会话（通过DatabaseTask base）
    """
    import asyncio
    from app.database import SessionLocal  # 独立的数据库会话
    from app.services.consultation.session_service import ConsultationSessionService
    from app.services.consultation.graph import run_legal_consultation

    task_id = self.request.id
    logger.info(f"[Consultation Task] 启动任务: {task_id}, session_id={session_id}")

    # 【批准条件】使用独立的数据库会话（避免跨线程错误）
    db = SessionLocal()
    session_service = ConsultationSessionService(db=db)

    try:
        # 1. 立即保存初始状态
        asyncio.run(session_service.initialize_session(session_id, question, user_id))

        # 2. 执行工作流
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            consultation_result, final_report = loop.run_until_complete(
                run_legal_consultation(
                    question=question,
                    context=context,
                    conversation_history=None,
                    user_confirmed=user_confirmed,
                    selected_suggested_questions=selected_suggested_questions,
                    is_follow_up=False,  # 【修复】用户确认阶段不是后续追问，应从律师助理节点开始
                    session_id=session_id,
                    previous_specialist_output=previous_specialist_output,
                    saved_classification=saved_classification,
                    user_id=user_id
                )
            )

            # 3. 保存结果（使用独立会话）
            if consultation_result:
                # 【新增】详细日志：打印字段实际值
                logger.info(f"[Consultation Task] consultation_result 字段值:")
                logger.info(f"[Consultation Task] - analysis = '{consultation_result.analysis}' (type: {type(consultation_result.analysis).__name__})")
                logger.info(f"[Consultation Task] - advice = '{consultation_result.advice}' (type: {type(consultation_result.advice).__name__})")
                logger.info(f"[Consultation Task] - action_steps = {consultation_result.action_steps} (type: {type(consultation_result.action_steps).__name__})")
                logger.info(f"[Consultation Task] - classification_result = {consultation_result.classification_result is not None}")

                # 判断工作流执行状态：
                # - 如果有 classification_result 但没有 specialist 输出 → 助理节点完成，等待用户确认
                # - 如果有 specialist 输出 → 专业律师节点已完成
                has_specialist_output = bool(
                    consultation_result.analysis or
                    consultation_result.advice or
                    consultation_result.action_steps
                )
                has_classification = bool(consultation_result.classification_result)

                logger.info(f"[Consultation Task] 判断结果: has_specialist_output={has_specialist_output}, has_classification={has_classification}")

                if has_classification and not has_specialist_output:
                    # 【修复】助理节点完成，等待用户确认
                    # 保存 classification 到 session_state，供前端轮询获取
                    logger.info(f"[Consultation Task] -> 进入助理完成分支，保存 status=active, current_phase=waiting_confirmation")
                    asyncio.run(session_service.update_session(
                        session_id=session_id,
                        status="active",  # 【修复】使用正确的status值
                        current_phase="waiting_confirmation",  # 【新增】更新当前阶段
                        classification=consultation_result.classification_result,
                        is_in_specialist_mode=False,
                        user_decision="pending"  # 【新增】等待用户决策
                    ))
                    logger.info(f"[Consultation Task] 助理节点完成，等待用户确认: {session_id}")
                elif has_specialist_output:
                    logger.info(f"[Consultation Task] -> 进入专业律师完成分支，保存 specialist_output")
                    # 专业律师节点完成
                    # 使用 save_session 完整保存所有状态，避免多次调用导致状态不一致
                    asyncio.run(session_service.save_session(
                        session_id=session_id,
                        current_phase="completed",
                        is_in_specialist_mode=True,
                        specialist_output={
                            "legal_analysis": consultation_result.analysis,
                            "legal_advice": consultation_result.advice,
                            "risk_warning": consultation_result.risk_warning,
                            "action_steps": consultation_result.action_steps
                        },
                        classification=consultation_result.classification_result,
                        question=question,
                        user_id=user_id,
                        user_decision="confirmed"
                    ))
                    logger.info(f"[Consultation Task] 专业律师节点完成: {session_id}")
                else:
                    # 只有 classification 且已被标记为确认状态（用户确认后的第二阶段）
                    asyncio.run(session_service.update_session(
                        session_id=session_id,
                        status="active",  # 【修复】使用正确的status值
                        current_phase="completed",  # 【新增】更新当前阶段
                        classification=consultation_result.classification_result,
                        user_decision="confirmed"  # 【新增】用户已确认
                    ))
                    logger.info(f"[Consultation Task] 任务完成: {session_id}")
        finally:
            # 确保事件循环被清理
            loop.close()
    finally:
        # 确保数据库会话被关闭
        db.close()