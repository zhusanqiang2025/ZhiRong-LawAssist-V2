# backend/app/models/rule.py
"""
审查规则模型 (v3.2 - 修正版)
逻辑定义:
1. 规则分为两大类: 系统级规则 (is_system=True) 和 用户自定义规则 (is_system=False)
2. 系统级规则细分为三类 (rule_category):
   - universal: 通用规则 (对所有合同生效)
   - feature:   特征规则 (仅对特定分类生效，依赖 apply_to_category_ids)
   - stance:    立场规则 (仅对特定分类+特定立场生效，依赖 apply_to_category_ids + target_stance)
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class ReviewRule(Base):
    __tablename__ = "contract_review_rules"

    # ========== 1. 基础信息 ==========
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True, comment="规则名称")
    description = Column(String(255), nullable=True, comment="规则简述")
    content = Column(Text, nullable=False, comment="具体的Prompt/指令内容")
    
    # ========== 2. 第一层级：来源分类 (系统 vs 自定义) ==========
    # True = 系统级规则 (管理员维护); False = 用户自定义规则 (用户维护)
    is_system = Column(Boolean, default=False, index=True, comment="是否为系统规则")
    
    # 如果是自定义规则，必须记录是谁创建的
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID(自定义规则用)")
    
    # ========== 3. 第二层级：系统级类型 & 动态挂载 ==========
    # 类型枚举: 'universal'(通用), 'feature'(特征), 'stance'(立场), 'custom'(自定义)
    # 注意：自定义规则此处通常默认为 'custom'
    rule_category = Column(String(20), nullable=False, default="custom", comment="规则子类型")

    # 【关键字段】适用分类 ID 列表
    # 场景: 
    # 1. rule_category='feature' -> 必须填，表示该规则属于哪些合同分类 (如 [101, 102])
    # 2. rule_category='stance'  -> 必须填，同上
    # 3. rule_category='universal' -> 为空 (表示全适用)
    apply_to_category_ids = Column(JSON, nullable=True, comment="适用分类ID列表 (JSON Array)")

    # 【关键字段】目标立场
    # 场景: 仅当 rule_category='stance' 时填写 (如 'buyer', 'seller')
    target_stance = Column(String(20), nullable=True, comment="适用立场: buyer/seller/neutral")

    # ========== 4. 管理属性 ==========
    priority = Column(Integer, default=0, comment="优先级(数字越小越优先)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_system": self.is_system,         # 第一层级
            "rule_category": self.rule_category, # 第二层级
            "apply_to_category_ids": self.apply_to_category_ids or [],
            "target_stance": self.target_stance,
            "priority": self.priority,
            "is_active": self.is_active,
            "creator_id": self.creator_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }