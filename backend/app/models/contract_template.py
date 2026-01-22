# backend/app/models/contract_template.py
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
# from pgvector.sqlalchemy import Vector  # 向量数据库支持 - 暂时注释
import uuid

from app.database import Base

class ContractTemplate(Base):
    """合同模板数据模型 (v3.0 - RAG增强 + 知识图谱集成)

    注意：
    - 集成 pgvector 支持语义搜索 (embedding字段)
    - 保留旧字段用于 API 向后兼容
    """
    __tablename__ = "contract_templates"

    # ==================== 基础信息 ====================
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, index=True, comment="模板唯一标识(UUID)")
    name = Column(String(255), nullable=False, index=True, comment="模板名称")

    # 模板变体字段
    version_type = Column(String(50), default="标准版", comment="版本类型：标准版/简化版/详细版")
    stance_tendency = Column(String(50), default="中立", comment="立场倾向：甲方/乙方/中立")
    detailed_usage_scenario = Column(Text, comment="详细使用场景说明")

    category = Column(String(100), nullable=False, index=True, comment="模板分类")
    subcategory = Column(String(100), comment="模板子分类")
    description = Column(Text, comment="模板描述")

    # 搜索与标签
    keywords = Column(JSON, comment="搜索关键字列表")
    tags = Column(JSON, comment="标签列表")
    content_summary = Column(Text, comment="模板内容摘要(AI生成)")

    # ==================== 文件信息 ====================
    file_url = Column(String(500), nullable=False, comment="Markdown文件系统路径")
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_size = Column(Integer, default=0, comment="文件大小（字节）")
    file_type = Column(String(50), default="docx", comment="文件类型")
    preview_url = Column(String(500), comment="预览图片URL")

    # ==================== 权限与状态 ====================
    # True = 公开模版 (所有人可查); False = 私有模版
    is_public = Column(Boolean, default=False, index=True, comment="是否公开")
    
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="所有者ID")
    owner = relationship("User", back_populates="contract_templates")

    download_count = Column(Integer, default=0, comment="下载次数")
    rating = Column(Float, default=0.0, comment="用户评分")
    rating_count = Column(Integer, default=0, comment="评分人数")
    status = Column(String(20), default="active", comment="状态：active/inactive/archived")

    # ==================== ⚠️ 兼容性字段 (Deprecated) ====================
    # 注意：API 代码目前仍会写入这些字段以保持兼容性，请勿删除。
    # 核心逻辑已逐渐迁移至 metadata_info 中的 knowledge_graph_link。

    # V2 四维法律特征
    transaction_nature = Column(String(100), index=True, comment="[V2兼容] 交易性质")
    contract_object = Column(String(100), index=True, comment="[V2兼容] 合同标的")
    stance = Column(String(50), index=True, comment="[V2兼容] 总体立场")
    complexity = Column(String(50), comment="[V2兼容] 复杂度")

    # V2+ 扩展特征
    transaction_consideration = Column(String(200), comment="[V2兼容] 交易对价")
    transaction_characteristics = Column(Text, comment="[V2兼容] 交易特征")

    # 结构锚点
    primary_contract_type = Column(String(100), nullable=True, index=True, comment="[V2兼容] 主合同类型")
    secondary_types = Column(JSON, comment="[V2兼容] 次级类型")
    delivery_model = Column(String(50), nullable=True, comment="[V2兼容] 交付模型")
    payment_model = Column(String(50), comment="[V2兼容] 付款模型")
    industry_tags = Column(JSON, comment="[V2兼容] 行业标签")
    allowed_party_models = Column(JSON, comment="[V2兼容] 允许的主体模型")
    risk_level = Column(String(20), index=True, comment="[V2兼容] 风险等级")

    # ==================== ✅ V3 核心扩展字段 ====================
    
    is_recommended = Column(Boolean, default=False, index=True, comment="是否为推荐模板")

    # 扩展元数据（核心）
    # 存储：source_file_url, knowledge_graph_link, extract_note 等
    metadata_info = Column(JSON, default={}, comment="V3扩展元数据")

    # 业务属性
    is_featured = Column(Boolean, default=False, comment="是否为精选模板")
    is_free = Column(Boolean, default=True, comment="是否免费")
    language = Column(String(10), default="zh-CN", comment="模板语言")
    jurisdiction = Column(String(50), default="中国大陆", comment="适用司法管辖区")
    usage_scenario = Column(Text, comment="使用场景说明")

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    # ==================== 🤖 向量搜索字段 (RAG) ====================
    # 对应 BGE-M3 模型维度 (1024)
    # 注意：需要数据库已安装 pgvector 扩展
    # 暂时注释以支持无 pgvector 环境的部署
    # from pgvector.sqlalchemy import Vector
    # embedding = Column(
    #     Vector(1024),
    #     nullable=True,
    #     comment="内容向量嵌入(1024维)"
    # )
    embedding = Column(JSON, nullable=True, comment="内容向量嵌入(临时使用JSON存储)")
    embedding_updated_at = Column(DateTime(timezone=True), nullable=True, comment="向量最后更新时间")
    embedding_text_hash = Column(String(64), nullable=True, comment="向量源文本哈希")

    class Meta:
        verbose_name = "合同模板"
        verbose_name_plural = "合同模板"

    def to_dict(self):
        """转换为字典格式"""
        # 处理向量数据，防止序列化错误
        embedding_val = None
        if self.embedding is not None:
            # 如果是 numpy 数组或 vector 对象，转换为 list
            if hasattr(self.embedding, 'tolist'):
                embedding_val = self.embedding.tolist()
            else:
                embedding_val = list(self.embedding)

        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "version_type": self.version_type,
            "stance_tendency": self.stance_tendency,
            "detailed_usage_scenario": self.detailed_usage_scenario,
            
            # 文件与统计
            "file_url": self.file_url,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "is_public": self.is_public,
            "owner_id": self.owner_id,
            "download_count": self.download_count,
            "rating": self.rating,
            "status": self.status,
            
            # 兼容性字段
            "transaction_nature": self.transaction_nature,
            "contract_object": self.contract_object,
            "stance": self.stance,
            "risk_level": self.risk_level,
            "primary_contract_type": self.primary_contract_type,
            "industry_tags": self.industry_tags or [],
            
            # V3 字段
            "is_recommended": self.is_recommended,
            "metadata_info": self.metadata_info or {},
            "usage_scenario": self.usage_scenario,
            
            # 向量 (通常不直接返回给前端，除非调试)
            # "embedding": embedding_val, 
            
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<ContractTemplate(id={self.id}, name={self.name}, public={self.is_public})>"