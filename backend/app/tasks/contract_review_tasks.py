# backend/app/tasks/contract_review_tasks.py
"""
合同审查 Celery 任务

用于异步执行合同审查,支持任务历史管理、暂停、恢复等功能
"""

import logging
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.contract_review_task import ContractReviewTask
from app.models.contract import ContractDoc, ContractStatus
from app.services.langgraph_review_service import LangGraphReviewService
from app.services.contract_review_service import ContractReviewService
from app.tasks.celery_app import celery_app
from app.tasks.base_task import DatabaseTask

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="tasks.perform_contract_review",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=1800,  # 30分钟软超时
)
def perform_contract_review(
    self,
    task_id: int,
    contract_id: int,
    user_id: int,
    stance: str = "甲方",
    use_custom_rules: bool = False,
    use_langgraph: bool = True,
    transaction_structures: list = None
):
    """
    执行合同审查任务 (Celery异步任务)

    Args:
        task_id: ContractReviewTask记录ID
        contract_id: 合同ID
        user_id: 用户ID
        stance: 审查立场 (甲方/乙方)
        use_custom_rules: 是否使用自定义规则
        use_langgraph: 是否使用LangGraph系统
        transaction_structures: 交易结构列表

    Returns:
        bool: 任务是否成功
    """
    db = SessionLocal()

    try:
        # 1️⃣ 更新任务状态为running
        task = db.query(ContractReviewTask).filter(
            ContractReviewTask.id == task_id
        ).first()

        if not task:
            logger.error(f"任务不存在: task_id={task_id}")
            return False

        task.status = "running"
        task.started_at = datetime.utcnow()
        task.celery_task_id = self.request.id
        db.commit()

        logger.info(f"开始执行审查任务: task_id={task_id}, contract_id={contract_id}")

        # 准备元数据
        metadata = task.metadata_info or {}

        # 2️⃣ 选择审查系统并执行
        if use_langgraph:
            # ⭐ 修复：LangGraph 服务使用异步方法，需要在同步任务中运行
            service = LangGraphReviewService(db)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success = loop.run_until_complete(
                    service.run_deep_review(
                        contract_id=contract_id,
                        stance=stance,
                        updated_metadata=metadata,
                        enable_custom_rules=use_custom_rules,
                        user_id=user_id,
                        transaction_structures=transaction_structures
                    )
                )
            finally:
                loop.close()
        else:
            # ContractReviewService 使用同步方法
            service = ContractReviewService(db)
            success = service.run_deep_review(
                contract_id=contract_id,
                stance=stance,
                updated_metadata=metadata,
                enable_custom_rules=use_custom_rules,
                user_id=user_id,
                transaction_structures=transaction_structures
            )

        # 3️⃣ 更新任务状态
        if success:
            task.status = "completed"
            task.completed_at = datetime.utcnow()

            # 保存结果摘要
            contract = db.query(ContractDoc).filter(
                ContractDoc.id == contract_id
            ).first()

            if contract:
                review_items_count = len(contract.review_items)

                # 按严重程度统计
                severity_counts = {
                    "Critical": 0,
                    "High": 0,
                    "Medium": 0,
                    "Low": 0
                }

                for item in contract.review_items:
                    severity = item.severity or "Medium"
                    if severity in severity_counts:
                        severity_counts[severity] += 1

                task.result_summary = {
                    "total_items": review_items_count,
                    "by_severity": severity_counts
                }

            logger.info(f"审查任务完成: task_id={task_id}, 发现 {review_items_count} 个风险点")
        else:
            task.status = "failed"
            task.error_message = "审查执行失败"
            logger.error(f"审查任务失败: task_id={task_id}")

        db.commit()
        return success

    except Exception as e:
        logger.exception(f"审查任务异常: task_id={task_id}, error={str(e)}")

        # 更新任务状态为failed
        if 'task' in locals():
            task.status = "failed"
            task.error_message = str(e)
            db.commit()

        return False

    finally:
        db.close()


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="tasks.resume_contract_review",
    max_retries=3,
    default_retry_delay=60
)
def resume_contract_review(task_id: int):
    """
    恢复暂停的审查任务

    Args:
        task_id: ContractReviewTask记录ID

    Returns:
        bool: 任务是否成功
    """
    db = SessionLocal()

    try:
        task = db.query(ContractReviewTask).filter(
            ContractReviewTask.id == task_id
        ).first()

        if not task or task.status != "paused":
            logger.error(f"任务无法恢复: task_id={task_id}, status={task.status if task else None}")
            return False

        # 重新执行任务
        return perform_contract_review(
            task_id=task.id,
            contract_id=task.contract_id,
            user_id=task.user_id,
            stance=task.stance,
            use_custom_rules=task.use_custom_rules,
            use_langgraph=task.use_langgraph,
            transaction_structures=task.transaction_structures
        )

    finally:
        db.close()


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="tasks.cleanup_old_tasks"
)
def cleanup_old_tasks(self, days: int = 30):
    """
    清理旧的已完成任务记录

    Args:
        days: 保留天数,默认30天

    Returns:
        int: 删除的任务数量
    """
    db = SessionLocal()

    try:
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # 删除旧的已完成/失败任务
        deleted_count = db.query(ContractReviewTask).filter(
            ContractReviewTask.status.in_(["completed", "failed"]),
            ContractReviewTask.created_at < cutoff_date
        ).delete()

        db.commit()

        logger.info(f"清理旧任务完成: 删除了 {deleted_count} 条记录 (保留 {days} 天)")

        return deleted_count

    except Exception as e:
        logger.exception(f"清理旧任务失败: {str(e)}")
        db.rollback()
        return 0

    finally:
        db.close()
