# backend/app/services/contract_generation/rag/__init__.py
"""
RAG (Retrieval Augmented Generation) 模块

提供合同模板的向量化索引、检索和增强生成功能。
"""
from .bge_client import BGEClient, get_bge_client, EmbeddingResult, RerankResult

# 可选导入 ChromaDB (在 Python 3.14 + pydantic v2 环境下可能不可用)
try:
    from .vector_store import TemplateVectorStore, get_vector_store, DocumentSearchResult
    _chromadb_available = True
except (ImportError, Exception) as e:
    # ChromaDB 导入失败,仅使用 pgvector
    TemplateVectorStore = None
    get_vector_store = None
    DocumentSearchResult = None
    _chromadb_available = False

# pgvector 是推荐方案,始终可用
from .pgvector_store import PgVectorStore, get_pgvector_store

from .template_indexer import TemplateIndexer, get_template_indexer
from .template_retriever import TemplateRetriever, get_template_retriever, RetrievedTemplate

__all__ = [
    # BGE 客户端
    "BGEClient",
    "get_bge_client",
    "EmbeddingResult",
    "RerankResult",

    # 向量存储 (ChromaDB - 可选)
    "TemplateVectorStore",
    "get_vector_store",
    "DocumentSearchResult",

    # 向量存储 (pgvector - 推荐)
    "PgVectorStore",
    "get_pgvector_store",

    # 模板索引
    "TemplateIndexer",
    "get_template_indexer",

    # 模板检索
    "TemplateRetriever",
    "get_template_retriever",
    "RetrievedTemplate",
]
