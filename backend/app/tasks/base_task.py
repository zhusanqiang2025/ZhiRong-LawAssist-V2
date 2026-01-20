# backend/app/tasks/base_task.py
"""
Celery任务基类

提供数据库持久化、任务状态更新、失败处理等功能
"""

from celery import Task
from app.database import SessionLocal
from app.models.task import Task as TaskModel
from app.tasks.progress import update_progress
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """
    带数据库持久化的任务基类

    功能：
    1. 自动管理数据库连接
    2. 任务成功/失败钩子
    3. 自动更新任务状态到数据库
    4. 进度追踪支持
    """

    _db = None

    @property
    def db(self):
        """获取数据库会话（延迟初始化）"""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """任务完成后关闭数据库连接"""
        if self._db is not None:
            self._db.close()
            self._db = None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        任务失败处理

        Args:
            exc: 异常对象
            task_id: Celery任务ID
            args: 任务参数
            kwargs: 任务关键字参数
            einfo: 异常信息
        """
        logger.error(f"Task {task_id} failed: {exc}", exc_info=True)

        # 更新数据库状态
        try:
            task = self.db.query(TaskModel).filter(
                TaskModel.celery_task_id == task_id
            ).first()

            if task:
                task.status = "failed"
                task.error_message = str(exc)
                task.retry_count = self.request.retries
                task.completed_at = datetime.now(timezone.utc)

                # 如果有重试次数且未达到最大重试次数，标记为重试中
                if self.request.retries < self.max_retries:
                    task.status = "retrying"
                    task.last_retry_at = datetime.now(timezone.utc)

                self.db.commit()
                logger.info(f"Task {task_id} status updated to: {task.status}")
        except Exception as e:
            logger.error(f"Failed to update task status in database: {e}")

    def on_success(self, retval, task_id, args, kwargs):
        """
        任务成功处理

        Args:
            retval: 任务返回值
            task_id: Celery任务ID
            args: 任务参数
            kwargs: 任务关键字参数
        """
        logger.info(f"Task {task_id} completed successfully")

        # 更新数据库状态
        try:
            task = self.db.query(TaskModel).filter(
                TaskModel.celery_task_id == task_id
            ).first()

            if task:
                task.status = "completed"
                task.progress = 100.0
                task.completed_at = datetime.now(timezone.utc)

                # 如果返回值是字典，提取结果
                if isinstance(retval, dict):
                    task.analysis_report = retval.get("report")
                    task.final_document = retval.get("document")
                    task.result_data = retval.get("result")

                self.db.commit()
                logger.info(f"Task {task_id} marked as completed in database")
        except Exception as e:
            logger.error(f"Failed to update task status in database: {e}")

    def update_progress(
        self,
        progress: float,
        current_node: str = "",
        message: str = "",
        node_progress: dict = None
    ):
        """
        更新任务进度（便捷方法）

        Args:
            progress: 总体进度（0-100）
            current_node: 当前节点名称
            message: 进度消息
            node_progress: 各节点进度详情
        """
        task_id = self.request.id

        # 使用asyncio运行异步进度更新
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(update_progress(
            task_id=task_id,
            progress=progress,
            current_node=current_node,
            message=message,
            node_progress=node_progress
        ))


class WebSocketProgressTask(DatabaseTask):
    """
    支持WebSocket进度推送的任务基类

    继承自DatabaseTask，额外提供：
    1. 自动WebSocket进度推送
    2. 断线重连支持
    3. 进度历史记录
    """

    def update_progress(
        self,
        progress: float,
        current_node: str = "",
        message: str = "",
        node_progress: dict = None
    ):
        """
        更新任务进度并推送到WebSocket

        Args:
            progress: 总体进度（0-100）
            current_node: 当前节点名称
            message: 进度消息
            node_progress: 各节点进度详情
        """
        task_id = self.request.id

        # 调用父类方法更新进度
        super().update_progress(progress, current_node, message, node_progress)

        # 记录进度历史（可选）
        try:
            task = self.db.query(TaskModel).filter(
                TaskModel.celery_task_id == task_id
            ).first()

            if task and node_progress:
                # 更新节点进度
                if not task.node_progress:
                    task.node_progress = {}
                task.node_progress.update(node_progress)
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update progress history: {e}")
