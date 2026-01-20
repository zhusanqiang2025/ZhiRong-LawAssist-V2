# backend/app/models/user.py (v3.0 - 增加权限控制)
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # <<< 新增: 用户权限标识 >>>
    # True = 管理员 (可上传公开模版，管理所有模版)
    # False = 普通用户 (仅上传私有模版，仅管理自己的模版)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

    # <<< 新增: 手机号字段 >>>
    # 可选字段，支持国际号码格式
    phone = Column(String(20), unique=True, index=True, nullable=True, comment='手机号')

    # 关系定义
    tasks = relationship("Task", back_populates="owner")
    # 反向关联合同模版
    contract_templates = relationship("ContractTemplate", back_populates="owner")
    # 反向关联知识库配置
    knowledge_base_configs = relationship("KnowledgeBaseConfig", back_populates="user")
    # 反向关联模块偏好设置
    module_preferences = relationship("UserModulePreference", back_populates="user")
    # 反向关联知识库文档
    knowledge_documents = relationship("KnowledgeDocument", back_populates="user")