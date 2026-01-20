# backend/app/models/consultation_history.py
"""
对话历史记录模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class ConsultationHistory(Base):
    """对话历史记录表"""
    __tablename__ = "consultation_history"

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    session_id = Column(String(64), unique=True, index=True, nullable=False, comment="会话ID")

    # 会话元数据
    title = Column(String(200), nullable=False, comment="会话标题")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    # 消息数据（JSON格式存储）
    messages = Column(JSON, nullable=False, comment="消息列表")
    message_count = Column(Integer, default=0, comment="消息数量")

    # 会话状态
    status = Column(SQLEnum('active', 'archived', name='consultation_status'), default='active', comment="会话状态")

    # 额外数据
    specialist_type = Column(String(50), comment="专业律师类型")
    classification = Column(JSON, comment="分类结果")

    # 关系
    # user = relationship("User", back_populates="consultation_history")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "messages": self.messages,
            "message_count": self.message_count,
            "status": self.status,
            "specialist_type": self.specialist_type,
            "classification": self.classification
        }

    class Config:
        orm_mode = True
