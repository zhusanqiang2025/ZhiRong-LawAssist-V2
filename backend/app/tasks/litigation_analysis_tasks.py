# backend/app/tasks/litigation_analysis_tasks.py
"""
案件分析后台任务

处理案件分析的异步执行（Celery版本）
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.litigation_analysis import LitigationAnalysisSession
from app.models.task import Task
from app.schemas.litigation_analysis import AnalysisStatusEnum
from app.services.litigation_analysis.workflow import run_litigation_analysis_workflow
from app.tasks.celery_app import celery_app
from app.tasks.base_task import DatabaseTask
import uuid

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="tasks.litigation_analysis",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=1800,  # 30分钟软超时
)
def litigation_analysis_task(
    self,
    session_id: str,
    user_input: str,
    document_paths: list = None,
    case_package_id: Optional[str] = None,
    case_type: Optional[str] = None,
    case_position: Optional[str] = None,
    analysis_mode: str = "multi",
    selected_model: Optional[str] = None
):
    """
    案件分析Celery任务

    Args:
        self: Celery任务实例
        session_id: 会话ID
        user_input: 用户输入
        document_paths: 文档路径列表
        case_package_id: 案件包ID
        case_type: 案件类型
        case_position: 案件立场
        analysis_mode: 分析模式 ("single" 或 "multi")
        selected_model: 单模型模式下指定的模型

    Returns:
        dict: 任务执行结果
    """
    task_id = self.request.id
    document_paths = document_paths or []
    db = SessionLocal()

    try:
        # 检查任务是否已存在（防止重复提交）
        existing_task = db.query(Task).filter(Task.celery_task_id == task_id).first()
        if existing_task:
            logger.info(f"[{task_id}] 任务已存在，跳过创建: {existing_task.id}")
            task = existing_task
        else:
            # 创建数据库任务记录
            task = Task(
                id=str(uuid.uuid4()),
                celery_task_id=task_id,
                user_demand=user_input,
                status="processing",
                task_type="litigation_analysis",
                queue_name="medium_priority",
                started_at=datetime.now(timezone.utc),
                task_params={
                    "session_id": session_id,
                    "user_input": user_input,
                    "document_paths": document_paths,
                    "case_package_id": case_package_id,
                    "case_type": case_type,
                    "case_position": case_position,
                    "analysis_mode": analysis_mode,
                    "selected_model": selected_model
                }
            )
            db.add(task)
            db.commit()

        logger.info(f"[{task_id}] 案件分析任务开始 (模式: {analysis_mode})")

        # 初始化进度
        self.update_progress(
            progress=0,
            current_node="init",
            message="案件分析任务开始"
        )

        # 获取会话
        session = db.query(LitigationAnalysisSession).filter(
            LitigationAnalysisSession.session_id == session_id
        ).first()

        if not session:
            logger.error(f"[{session_id}] 会话不存在")
            raise ValueError(f"会话 {session_id} 不存在")

        # 更新状态为分析中
        session.status = AnalysisStatusEnum.ANALYZING.value
        db.commit()

        # 更新进度：开始分析
        self.update_progress(
            progress=10,
            current_node="analyzing",
            message="正在分析案件..."
        )

        # 执行工作流
        try:
            result = asyncio.run(run_litigation_analysis_workflow(
                session_id=session_id,
                user_input=user_input,
                document_paths=document_paths,
                case_package_id=case_package_id,
                case_type=case_type,
                case_position=case_position,
                analysis_scenario="pre_litigation",  # 默认场景：起诉前评估
                preorganized_case=None,               # 无预整理数据
                analysis_mode=analysis_mode,
                selected_model=selected_model
            ))

            # 更新进度：分析完成
            self.update_progress(
                progress=90,
                current_node="finalizing",
                message="正在生成报告..."
            )

            # 更新结果到会话表
            session.status = AnalysisStatusEnum.COMPLETED.value
            session.case_summary = result.get("case_summary")
            session.case_strength = result.get("case_strength")
            session.evidence_assessment = result.get("evidence_analysis")
            session.timeline_events = result.get("timeline")
            session.evidence_chain = result.get("evidence_chain")
            session.strategies = result.get("strategies")
            session.model_results = result.get("model_results")
            session.report_md = result.get("final_report")
            session.report_json = result.get("report_json")
            session.selected_model = result.get("model_results", {}).get("selected")
            session.completed_at = datetime.now(timezone.utc)

            db.commit()

            # 更新进度：完成
            self.update_progress(
                progress=100,
                current_node="completed",
                message="案件分析完成"
            )

            logger.info(f"[{session_id}] 案件分析完成")

            # 返回结果
            return {
                "status": "completed",
                "session_id": session_id,
                "result": result
            }

        except Exception as e:
            logger.error(f"[{session_id}] 工作流执行失败: {e}")
            session.status = AnalysisStatusEnum.FAILED.value
            db.commit()
            raise

    except Exception as e:
        logger.error(f"[{task_id}] 案件分析失败: {e}")

        # 更新会话状态为失败
        try:
            session = db.query(LitigationAnalysisSession).filter(
                LitigationAnalysisSession.session_id == session_id
            ).first()
            if session:
                session.status = AnalysisStatusEnum.FAILED.value
                db.commit()
        except Exception as session_error:
            logger.error(f"更新会话状态失败: {session_error}")

        # 重新抛出异常，让Celery处理重试
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()
