# backend/app/services/task_manager.py (修复版)

import redis
import uuid
import json
from ..core.config import settings

class TaskManager:
    def __init__(self, host, port, db):
        # 使用连接池以提高性能和可靠性
        self.pool = redis.ConnectionPool(host=host, port=port, db=db, decode_responses=True)
        
    def _get_connection(self):
        """从连接池获取一个连接。"""
        return redis.Redis(connection_pool=self.pool)

    def create_task(self) -> str:
        """创建一个新的任务，并返回任务ID。任务永久有效。"""
        task_id = str(uuid.uuid4())
        r = self._get_connection()
        initial_data = {"status": "pending", "result": ""}
        # [修复] 移除 ex=3600，使任务永久有效
        r.set(f"task:{task_id}", json.dumps(initial_data))
        return task_id

    def get_task(self, task_id: str) -> dict | None:
        """获取任务状态和结果。"""
        r = self._get_connection()
        task_data = r.get(f"task:{task_id}")
        if task_data:
            task = json.loads(task_data)
            # 确保 result 字段总是存在，避免前端出错
            if "result" not in task or task["result"] is None:
                task["result"] = ""
            return task
        return None

    def update_task(self, task_id: str, data: dict):
        """
        以原子方式更新任务数据。
        使用 WATCH/MULTI/EXEC 事务来防止并发写入冲突。
        """
        r = self._get_connection()
        task_key = f"task:{task_id}"
        
        with r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(task_key)
                    current_task_data_str = pipe.get(task_key)
                    if not current_task_data_str:
                        # 如果任务在WATCH之后被删除，则中止操作
                        return

                    current_task_data = json.loads(current_task_data_str)
                    current_task_data.update(data)
                    
                    pipe.multi()
                    # [修复] 移除 ex=3600，确保更新后任务不会重新设置过期时间
                    pipe.set(task_key, json.dumps(current_task_data))
                    pipe.execute()
                    break # 成功执行，退出循环
                except redis.exceptions.WatchError:
                    # 键被修改，重试整个事务
                    continue

# 创建全局 task_manager 实例
task_manager = TaskManager(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB
)