# backend/app/models/task.py (v3.0 - 支持进度追踪)
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_demand = Column(Text, nullable=True)
    analysis_report = Column(Text, nullable=True)
    final_document = Column(Text, nullable=True)
    status = Column(String, default="pending")
    doc_type = Column(String, nullable=True)
    result = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="tasks")

    # === 进度追踪字段 ===

    # 总体进度百分比 (0-100)
    progress = Column(Float, default=0.0, nullable=False)

    # 当前执行节点名称
    current_node = Column(String, nullable=True)

    # 各节点详细进度信息 JSON格式: {"节点名": {"status": "pending|processing|completed|failed", "progress": 0-100, "message": "描述", "started_at": "时间"}}
    node_progress = Column(JSON, nullable=True)

    # 工作流步骤信息 JSON格式: [{"name": "节点名", "order": 1, "estimated_time": 30, "status": "pending", "progress": 0}]
    workflow_steps = Column(JSON, nullable=True)

    # 预计剩余时间（秒）
    estimated_time_remaining = Column(Integer, nullable=True)

    # 处理开始时间
    started_at = Column(DateTime(timezone=True), nullable=True)

    # 处理完成时间
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 重试次数
    retry_count = Column(Integer, default=0)

    # 处理优先级
    priority = Column(Integer, default=5)  # 1-10, 数字越小优先级越高

    # ==================== Celery 集成字段 ====================

    # Celery任务ID
    celery_task_id = Column(String(255), nullable=True, unique=True, index=True)

    # Worker名称
    worker_name = Column(String(255), nullable=True)

    # 队列名称
    queue_name = Column(String(100), nullable=True)

    # 任务类型（用于任务路由）
    task_type = Column(String(100), nullable=True, index=True)

    # 最后重试时间
    last_retry_at = Column(DateTime(timezone=True), nullable=True)

    # 任务参数（JSON格式存储）
    task_params = Column(JSON, nullable=True)

    # 结果数据（JSON格式存储）
    result_data = Column(JSON, nullable=True)