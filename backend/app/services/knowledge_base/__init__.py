# backend/app/services/knowledge_base/__init__.py
"""
统一知识库服务层

支持多源知识库：
- 本地法律知识库
- 飞书知识库
- 未来可扩展：Confluence、Notion 等
"""

from .base_interface import BaseKnowledgeStore, KnowledgeItem, KnowledgeSearchResult, SearchIntent
from .unified_service import UnifiedKnowledgeService, get_unified_kb_service
from .local_legal_kb import LocalLegalKnowledgeBase, get_local_legal_kb
from .feishu_kb import FeishuKnowledgeBase, create_feishu_kb_from_config
from .deduplication import KnowledgeDeduplicator, get_deduplicator, DuplicateInfo

__all__ = [
    # 基类接口
    "BaseKnowledgeStore",
    "KnowledgeItem",
    "KnowledgeSearchResult",
    "SearchIntent",

    # 统一服务
    "UnifiedKnowledgeService",
    "get_unified_kb_service",

    # 本地知识库
    "LocalLegalKnowledgeBase",
    "get_local_legal_kb",

    # 飞书知识库
    "FeishuKnowledgeBase",
    "create_feishu_kb_from_config",

    # 去重服务
    "KnowledgeDeduplicator",
    "get_deduplicator",
    "DuplicateInfo",
]
