# backend/app/api/websocket.py
"""
WebSocket 连接管理器

用于实时推送风险分析进度到前端

关键改进：使用 asyncio.Queue + asyncio.Event 解决并发问题
- queue 用于存储消息
- event 用于通知有新消息，避免 queue.get() 阻塞问题
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict
import logging
import asyncio

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 存储每个 session_id 对应的消息队列
        self.message_queues: Dict[str, asyncio.Queue] = {}
        # 存储每个 session_id 对应的 WebSocket 对象（仅用于连接管理）
        self.active_connections: Dict[str, WebSocket] = {}
        # 存储每个 session_id 对应的事件（用于通知有新消息）
        self.queue_events: Dict[str, asyncio.Event] = {}
        # 【新增】缓存每个任务的最新进度消息（用于新连接时立即发送）
        self.latest_messages: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """接受并存储 WebSocket 连接，创建消息队列

        Args:
            websocket: WebSocket 对象
            session_id: 会话 ID
        """
        await websocket.accept()
        self.active_connections[session_id] = websocket
        # 为每个连接创建一个消息队列
        self.message_queues[session_id] = asyncio.Queue()
        # 创建一个事件用于通知
        self.queue_events[session_id] = asyncio.Event()
        queue_id = id(self.message_queues[session_id])
        logger.info(f"WebSocket 连接建立: {session_id}, 队列ID: {queue_id}")

    async def disconnect(self, websocket_id: str):
        """移除 WebSocket 连接和消息队列"""
        if websocket_id in self.active_connections:
            del self.active_connections[websocket_id]
        if websocket_id in self.message_queues:
            del self.message_queues[websocket_id]
        if websocket_id in self.queue_events:
            del self.queue_events[websocket_id]
        # 【新增】可选择保留缓存，以便重连时获取（这里保留缓存）
        # 如果需要清理缓存，取消注释下面这行：
        # if websocket_id in self.latest_messages:
        #     del self.latest_messages[websocket_id]
        logger.info(f"WebSocket 连接断开: {websocket_id}")

    def is_connected(self, session_id: str) -> bool:
        """检查会话是否有活跃连接"""
        return session_id in self.active_connections

    async def send_progress(self, websocket_id: str, data: dict):
        """向指定连接的队列中放入进度数据（带连接检查）"""
        if not self.is_connected(websocket_id):
            return False

        if websocket_id in self.message_queues:
            try:
                queue = self.message_queues[websocket_id]
                queue_id = id(queue)
                queue_size_before = queue.qsize()
                logger.info(f"[Manager] 准备发送到 {websocket_id}, 队列ID: {queue_id}, 队列大小(放入前): {queue_size_before}")
                logger.info(f"[Manager] 消息类型: {data.get('type')}")

                # 【新增】缓存最新消息（支持 task_progress 和 task_completed）
                if data.get('type') in ['task_progress', 'task_completed', 'task_error', 'task_status']:
                    self.latest_messages[websocket_id] = data
                    logger.debug(f"[Manager] 已缓存最新消息: {websocket_id}, type={data.get('type')}")

                # 将消息放入队列
                await queue.put(data)

                # 触发事件通知有新消息
                if websocket_id in self.queue_events:
                    self.queue_events[websocket_id].set()
                    logger.info(f"[Manager] 🔥 事件已触发: {websocket_id}")

                queue_size_after = queue.qsize()
                logger.info(f"[Manager] 消息已放入队列: {websocket_id}, 队列ID: {queue_id}, 队列大小(放入后): {queue_size_after}")
            except Exception as e:
                logger.error(f"[Manager] 发送进度失败: {e}", exc_info=True)
                logger.error(f"[Manager] 错误类型: {type(e).__name__}")
                logger.error(f"[Manager] 错误详情: {str(e)}")
                self.disconnect(websocket_id)
        else:
            logger.warning(f"[Manager] WebSocket 连接不存在: {websocket_id}")
            logger.info(f"[Manager] 当前活跃连接: {list(self.active_connections.keys())}")

    async def get_message(self, websocket_id: str, timeout: float = 1.0):
        """
        从队列中获取消息（供 WebSocket 端点使用）

        Args:
            websocket_id: 会话 ID
            timeout: 超时时间（秒）

        Returns:
            消息数据或 None（超时）
        """
        if websocket_id not in self.message_queues:
            return None

        queue = self.message_queues[websocket_id]
        queue_id = id(queue)

        # 直接等待队列，如果有消息立即返回，否则超时
        try:
            message = await asyncio.wait_for(queue.get(), timeout=timeout)
            queue_size_after = queue.qsize()
            logger.info(f"[Manager.get_message] ✅ 获取到消息: {websocket_id}, 队列ID: {queue_id}, type: {message.get('type') if message else 'None'}, 队列大小(取出后): {queue_size_after}")
            return message
        except asyncio.TimeoutError:
            # 超时是正常情况（队列为空），使用 debug 级别
            logger.debug(f"[Manager.get_message] ⏱️ 超时: {websocket_id}, 队列ID: {queue_id}")
            return None

    def get_latest_message(self, websocket_id: str) -> dict | None:
        """
        获取缓存的最新消息（供新连接时使用）

        Args:
            websocket_id: 会话 ID

        Returns:
            最新消息或 None
        """
        return self.latest_messages.get(websocket_id)

    async def broadcast(self, data: dict):
        """向所有活跃连接广播数据"""
        disconnected = []
        for websocket_id, connection in self.active_connections.items():
            try:
                await self.send_progress(websocket_id, data)
            except Exception as e:
                logger.error(f"广播失败 {websocket_id}: {e}")
                disconnected.append(websocket_id)

        # 清理断开的连接
        for websocket_id in disconnected:
            await self.disconnect(websocket_id)

    def get_connection_count(self) -> int:
        """获取当前活跃连接数"""
        return len(self.active_connections)


# 创建全局连接管理器实例
manager = ConnectionManager()
