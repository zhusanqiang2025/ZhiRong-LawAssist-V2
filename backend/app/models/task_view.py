# backend/app/models/task_view.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class TaskViewRecord(Base):
    """任务查看记录表

    用于追踪用户是否已查看任务结果，支持任务保持功能
    """
    __tablename__ = "task_view_records"

    id = Column(Integer, primary_key=True, index=True)

    # 关联的任务ID
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)

    # 关联的用户ID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 是否已查看结果
    has_viewed_result = Column(Boolean, default=False, nullable=False)

    # 首次查看时间
    first_viewed_at = Column(DateTime(timezone=True), nullable=True)

    # 最后查看时间
    last_viewed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 查看次数
    view_count = Column(Integer, default=0, nullable=False)

    # 创建时间
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<TaskViewRecord(task_id={self.task_id}, user_id={self.user_id}, has_viewed={self.has_viewed_result})>"
