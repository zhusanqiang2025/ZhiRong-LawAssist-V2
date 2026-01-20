# backend/app/models/category.py (v2.1 - 适配 categories.json)
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship, backref
from app.database import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    
    # 核心字段
    name = Column(String(100), index=True, nullable=False, comment="分类名称")
    code = Column(String(50), index=True, nullable=True, comment="分类编码 (如 '1', '1-1')")
    description = Column(Text, nullable=True, comment="分类描述")
    
    # 层级关系
    parent_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    sort_order = Column(Integer, default=0, comment="排序权重")
    
    # 扩展属性 (关键升级)
    # 用于存储 categories.json 中的 contract_type, industry, usage_scene, jurisdiction
    meta_info = Column(JSON, default={}, comment="扩展元数据")
    
    is_active = Column(Boolean, default=True, comment="是否启用")
    
    # 自关联
    children = relationship("Category", 
        backref=backref('parent', remote_side=[id]),
        cascade="all, delete-orphan",
        order_by="Category.sort_order" # 自动按顺序加载子级
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "parent_id": self.parent_id,
            "meta_info": self.meta_info,
            "children": [c.to_dict() for c in self.children] if self.children else []
        }