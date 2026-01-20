# backend/app/models/contract_review_task.py
"""
合同审查任务历史模型

用于记录每次审查任务的详细信息,支持任务状态追踪和断点续传
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class ContractReviewTask(Base):
    """
    合同审查任务历史表

    功能:
    - 记录每次审查任务的详细信息
    - 支持任务状态追踪 (pending/running/paused/completed/failed)
    - 支持断点续传
    - 支持历史查询
    """
    __tablename__ = "contract_review_tasks"

    # ========== 基本信息 ==========
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contract_docs.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ========== 任务配置 ==========
    task_type = Column(String(32), default="review", comment="任务类型: review/generation/other")
    stance = Column(String(16), nullable=True, comment="审查立场: 甲方/乙方")
    use_custom_rules = Column(Boolean, default=False, comment="是否使用自定义规则")
    use_langgraph = Column(Boolean, default=True, comment="是否使用LangGraph系统")
    transaction_structures = Column(JSON, nullable=True, comment="用户选择的交易结构列表")

    # ========== 任务状态 ==========
    status = Column(String(32), default="pending", index=True, comment="""
        状态枚举:
        - pending: 等待执行
        - running: 执行中
        - paused: 已暂停
        - completed: 已完成
        - failed: 执行失败
        - cancelled: 已取消
    """)

    # ========== 任务数据 ==========
    metadata_info = Column(JSON, nullable=True, comment="审查时的元数据")
    result_summary = Column(JSON, nullable=True, comment="审查结果摘要")
    error_message = Column(Text, nullable=True, comment="错误信息")

    # ========== Celery集成 ==========
    celery_task_id = Column(String(255), nullable=True, index=True, comment="Celery任务ID")

    # ========== 时间戳 ==========
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # ========== 关系 ==========
    # 注意：明确指定 foreign_keys，因为 ContractDoc 中还有 current_review_task_id
    contract = relationship(
        "ContractDoc",
        foreign_keys=[contract_id],
        back_populates="review_tasks"
    )
    # user = relationship("User", back_populates="review_tasks")  # 如果User模型有back_populates

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "user_id": self.user_id,
            "task_type": self.task_type,
            "status": self.status,
            "stance": self.stance,
            "use_custom_rules": self.use_custom_rules,
            "use_langgraph": self.use_langgraph,
            "transaction_structures": self.transaction_structures,
            "result_summary": self.result_summary,
            "error_message": self.error_message,
            "celery_task_id": self.celery_task_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<ContractReviewTask id={self.id} status={self.status} contract_id={self.contract_id}>"
