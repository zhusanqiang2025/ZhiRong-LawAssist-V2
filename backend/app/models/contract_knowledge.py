# backend/app/models/contract_knowledge.py
"""
合同法律特征知识图谱数据库模型
"""
from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class ContractKnowledgeType(Base):
    """合同法律特征知识图谱表

    存储127种合同类型的完整法律特征定义
    """
    __tablename__ = "contract_knowledge_types"

    id = Column(Integer, primary_key=True, index=True)

    # ==================== 合同基本信息 ====================
    name = Column(String(255), nullable=False, unique=True, index=True, comment="合同类型名称")
    aliases = Column(JSON, comment="别名列表")
    category = Column(String(100), index=True, comment="一级分类")
    subcategory = Column(String(100), index=True, comment="二级分类")

    # ==================== 法律特征字段 ====================
    transaction_nature = Column(String(100), index=True, comment="交易性质")
    contract_object = Column(String(100), index=True, comment="合同标的")
    stance = Column(String(50), index=True, comment="立场")
    consideration_type = Column(String(50), comment="交易对价类型")
    consideration_detail = Column(Text, comment="交易对价详情")
    transaction_characteristics = Column(Text, comment="交易特征")
    usage_scenario = Column(Text, comment="使用场景")
    legal_basis = Column(JSON, comment="法律依据列表")

    # ==================== 扩展字段 ====================
    recommended_template_ids = Column(JSON, comment="推荐模板ID列表")
    meta_info = Column(JSON, comment="扩展元数据")

    # ==================== 状态控制 ====================
    is_active = Column(Boolean, default=True, index=True, comment="是否启用")
    is_system = Column(Boolean, default=False, comment="是否为系统预定义")

    # ==================== 审计字段 ====================
    creator_id = Column(Integer, comment="创建者ID")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def __repr__(self):
        return f"<ContractKnowledgeType {self.name}>"

    def to_dict(self) -> dict:
        """转换为字典格式（兼容原有JSON结构）"""
        return {
            "id": self.id,
            "name": self.name,
            "aliases": self.aliases or [],
            "category": self.category or "",
            "subcategory": self.subcategory or "",
            "legal_features": {
                "transaction_nature": self.transaction_nature,
                "contract_object": self.contract_object,
                "stance": self.stance,
                "consideration_type": self.consideration_type,
                "consideration_detail": self.consideration_detail or "",
                "transaction_characteristics": self.transaction_characteristics or "",
                "usage_scenario": self.usage_scenario or "",
                "legal_basis": self.legal_basis or []
            },
            "recommended_template_ids": self.recommended_template_ids or [],
            "is_active": self.is_active,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
