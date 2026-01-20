# backend/app/tasks/progress.py
"""
任务进度追踪工具

提供任务进度更新到数据库和WebSocket的功能
使用 Redis Pub/Sub 实现跨进程通信
"""

from app.database import SessionLocal
from app.models.task import Task as TaskModel
from datetime import datetime, timezone
import logging
import json
import os
import redis

logger = logging.getLogger(__name__)

# 创建 Redis 连接用于 Pub/Sub
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# WebSocket 进度频道前缀
PROGRESS_CHANNEL_PREFIX = "task_progress:"


async def update_progress(
    task_id: str,
    progress: float,
    current_node: str = "",
    message: str = "",
    node_progress: dict = None
):
    """
    更新任务进度到数据库和WebSocket

    Args:
        task_id: 任务ID
        progress: 总体进度（0-100）
        current_node: 当前节点名称
        message: 进度消息
        node_progress: 各节点进度详情
    """
    db = SessionLocal()
    try:
        # 更新数据库
        task = db.query(TaskModel).filter(
            TaskModel.celery_task_id == task_id
        ).first()

        if task:
            task.progress = progress
            task.current_node = current_node

            # 更新节点进度
            if node_progress:
                if not task.node_progress:
                    task.node_progress = {}
                task.node_progress.update(node_progress)

            # 计算预计剩余时间
            if progress > 0 and task.started_at:
                elapsed = (datetime.now(timezone.utc) - task.started_at).total_seconds()
                estimated_remaining = int(elapsed * (100 - progress) / progress)
                task.estimated_time_remaining = estimated_remaining

            task.updated_at = datetime.now(timezone.utc)
            db.commit()

        # 发布到 Redis Pub/Sub（Backend 会监听并转发到 WebSocket）
        channel_name = f"{PROGRESS_CHANNEL_PREFIX}{task_id}"
        progress_data = {
            "type": "task_progress",
            "data": {
                "task_id": task_id,
                "progress": progress,
                "current_node": current_node,
                "message": message,
                "node_progress": node_progress,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        redis_client.publish(channel_name, json.dumps(progress_data))
        logger.info(f"[Redis Pub] 进度已发布到频道 {channel_name}: {progress}% - {message}")

    except Exception as e:
        logger.error(f"Failed to update progress: {e}", exc_info=True)
    finally:
        db.close()


async def send_task_notification(
    task_id: str,
    notification_type: str,
    message: str,
    data: dict = None
):
    """
    发送任务通知到WebSocket

    Args:
        task_id: 任务ID
        notification_type: 通知类型（completed, failed, warning等）
        message: 通知消息
        data: 附加数据
    """
    try:
        # 映射通知类型到前端期望的消息类型
        message_type_map = {
            "completed": "task_completed",
            "failed": "task_error",
            "error": "task_error",
            "warning": "task_progress",
            "info": "task_progress"
        }

        msg_type = message_type_map.get(notification_type, "task_progress")

        # 发布到 Redis Pub/Sub
        channel_name = f"{PROGRESS_CHANNEL_PREFIX}{task_id}"
        notification_data = {
            "type": msg_type,
            "data": {
                "task_id": task_id,
                "notification_type": notification_type,
                "message": message,
                "result": data or {},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        redis_client.publish(channel_name, json.dumps(notification_data))
        logger.info(f"[Redis Pub] 通知已发布到频道 {channel_name}: {notification_type}")

    except Exception as e:
        logger.error(f"Failed to send notification: {e}", exc_info=True)


def calculate_node_progress(completed_nodes: list, total_nodes: list) -> dict:
    """
    计算各节点进度

    Args:
        completed_nodes: 已完成的节点列表
        total_nodes: 所有节点列表

    Returns:
        节点进度字典
    """
    node_progress = {}
    total = len(total_nodes)

    for i, node in enumerate(total_nodes):
        if node in completed_nodes:
            node_progress[node] = 100
        else:
            # 计算当前节点的进度（基于已完成节点数）
            completed_count = len(completed_nodes)
            if completed_count > 0 and completed_count <= total:
                # 简单的线性进度计算
                node_progress[node] = 0
            else:
                node_progress[node] = 0

    return node_progress


def calculate_overall_progress(node_progress: dict, node_weights: dict = None) -> float:
    """
    计算总体进度

    Args:
        node_progress: 各节点进度字典
        node_weights: 各节点权重字典（可选）

    Returns:
        总体进度（0-100）
    """
    if not node_progress:
        return 0.0

    # 如果没有提供权重，使用平均权重
    if not node_weights:
        node_weights = {node: 1.0 for node in node_progress.keys()}

    total_weight = sum(node_weights.values())
    weighted_progress = 0.0

    for node, progress in node_progress.items():
        weight = node_weights.get(node, 1.0)
        weighted_progress += (progress * weight) / total_weight

    return round(weighted_progress, 2)


class ProgressTracker:
    """
    进度追踪器类

    用于在任务执行过程中追踪和更新进度
    """

    def __init__(self, task_id: str, total_steps: int, db_session=None):
        """
        初始化进度追踪器

        Args:
            task_id: 任务ID
            total_steps: 总步骤数
            db_session: 数据库会话（可选）
        """
        self.task_id = task_id
        self.total_steps = total_steps
        self.current_step = 0
        self.db = db_session or SessionLocal()
        self.node_progress = {}

    async def update(
        self,
        step: int,
        node_name: str,
        message: str,
        node_progress: dict = None
    ):
        """
        更新进度

        Args:
            step: 当前步骤
            node_name: 节点名称
            message: 进度消息
            node_progress: 节点进度详情
        """
        self.current_step = step

        # 计算总体进度
        progress = (step / self.total_steps) * 100

        # 更新节点进度
        if node_progress:
            self.node_progress.update(node_progress)

        # 调用进度更新函数
        await update_progress(
            task_id=self.task_id,
            progress=progress,
            current_node=node_name,
            message=message,
            node_progress=self.node_progress
        )

    async def complete(self, message: str = "任务完成"):
        """标记任务完成"""
        await update_progress(
            task_id=self.task_id,
            progress=100.0,
            current_node="completed",
            message=message,
            node_progress=self.node_progress
        )

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()


class TaskProgress:
    """
    任务进度报告类（用于Celery任务）

    提供简化的进度报告接口
    """

    def __init__(self, task_id: str):
        """
        初始化任务进度报告器

        Args:
            task_id: Celery任务ID
        """
        self.task_id = task_id

    def report(self, progress: float, message: str, status: str, data: dict = None):
        """
        报告任务进度

        Args:
            progress: 进度百分比（0-100）
            message: 进度消息
            status: 当前状态（initializing, processing, completed, failed等）
            data: 附加数据
        """
        import asyncio
        try:
            # 尝试获取现有事件循环
            loop = asyncio.get_event_loop()
            # 检查循环是否已关闭
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            # 如果没有事件循环或循环已关闭，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            # 运行异步进度更新
            loop.run_until_complete(
                update_progress(
                    task_id=self.task_id,
                    progress=progress,
                    current_node=status,
                    message=message,
                    node_progress=data
                )
            )
        finally:
            # 如果是新创建的循环，确保关闭它
            # 但不要关闭可能被外部使用的循环
            if not loop.is_running() and not loop.is_closed():
                # 只在循环是我们自己创建的情况下关闭
                # 这里保守一点，不关闭循环，让 Python GC 处理
                pass
