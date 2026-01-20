# backend/app/services/contract_generation/rag/vector_store.py
"""
向量数据库服务

使用 Chroma 作为向量数据库，存储和检索合同模板的嵌入向量。
与公司 BGE-M3 服务集成，支持自定义嵌入函数。
"""
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.core.config import settings
from .bge_client import BGEClient, get_bge_client

logger = logging.getLogger(__name__)


# ==================== 自定义嵌入函数 ====================

class BGEEmbeddingFunction(EmbeddingFunction):
    """
    Chroma 自定义嵌入函数，使用公司 BGE-M3 服务
    """

    def __init__(self, bge_client: Optional[BGEClient] = None):
        """
        初始化嵌入函数

        Args:
            bge_client: BGE 客户端，默认使用全局单例
        """
        self.bge_client = bge_client or get_bge_client()

    def __call__(self, texts: Documents) -> Embeddings:
        """
        将文本列表转换为嵌入向量列表

        Args:
            texts: 文本列表

        Returns:
            Embeddings: 嵌入向量列表（二维列表）
        """
        # 使用同步方法获取嵌入
        results = self.bge_client.embed_batch(texts)
        embeddings = [result.embedding for result in results]
        return embeddings


# ==================== 向量存储服务 ====================

@dataclass
class DocumentSearchResult:
    """文档搜索结果"""
    id: str  # 文档 ID
    text: str  # 文档内容
    metadata: Dict[str, Any]  # 元数据
    similarity: float  # 相似度分数


class TemplateVectorStore:
    """
    合同模板向量存储服务

    基于 Chroma，提供模板的索引、存储和检索功能。
    """

    # 集合名称
    COLLECTION_PUBLIC = "contract_templates_public"
    COLLECTION_PRIVATE_PREFIX = "contract_templates_user_"

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        bge_client: Optional[BGEClient] = None
    ):
        """
        初始化向量存储服务

        Args:
            persist_dir: Chroma 持久化目录，默认从配置读取
            bge_client: BGE 客户端实例
        """
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR

        # 确保持久化目录存在
        os.makedirs(self.persist_dir, exist_ok=True)

        # 创建 BGE 嵌入函数
        self.embedding_function = BGEEmbeddingFunction(bge_client)

        # 初始化 Chroma 客户端
        self._chroma_client: Optional[chromadb.ClientAPI] = None

        logger.info(f"TemplateVectorStore initialized with persist_dir: {self.persist_dir}")

    @property
    def client(self) -> chromadb.ClientAPI:
        """获取 Chroma 客户端（懒加载）"""
        if self._chroma_client is None:
            # 使用新的 ChromaDB API
            self._chroma_client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=chromadb.Settings(
                    anonymized_telemetry=False,
                )
            )
            logger.info("Chroma client initialized")
        return self._chroma_client

    def _get_collection_name(self, user_id: Optional[int] = None, is_public: bool = True) -> str:
        """
        获取集合名称

        Args:
            user_id: 用户 ID，用于私有模板集合
            is_public: 是否为公共模板

        Returns:
            str: 集合名称
        """
        if is_public:
            return self.COLLECTION_PUBLIC
        else:
            if user_id is None:
                raise ValueError("user_id is required for private collections")
            return f"{self.COLLECTION_PRIVATE_PREFIX}{user_id}"

    def _get_or_create_collection(
        self,
        user_id: Optional[int] = None,
        is_public: bool = True
    ) -> chromadb.Collection:
        """
        获取或创建集合

        Args:
            user_id: 用户 ID
            is_public: 是否为公共模板

        Returns:
            chromadb.Collection: Chroma 集合对象
        """
        collection_name = self._get_collection_name(user_id, is_public)

        try:
            # 尝试获取现有集合
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            logger.debug(f"Retrieved existing collection: {collection_name}")
        except Exception:
            # 集合不存在，创建新集合
            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "Contract templates" + (" (public)" if is_public else f" (user_{user_id})")}
            )
            logger.info(f"Created new collection: {collection_name}")

        return collection

    # ==================== 索引和存储 ====================

    def add_template(
        self,
        template_id: str,
        text: str,
        metadata: Dict[str, Any],
        user_id: Optional[int] = None,
        is_public: bool = True
    ) -> None:
        """
        添加单个模板到向量存储

        Args:
            template_id: 模板唯一标识
            text: 模板文本内容（用于嵌入）
            metadata: 模板元数据（类别、标签、文件名等）
            user_id: 用户 ID（私有模板必需）
            is_public: 是否为公共模板
        """
        collection = self._get_or_create_collection(user_id, is_public)

        # 添加到集合
        collection.add(
            ids=[template_id],
            documents=[text],
            metadatas=[metadata]
        )

        logger.debug(f"Added template {template_id} to {collection.name}")

    def add_templates_batch(
        self,
        templates: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        is_public: bool = True
    ) -> None:
        """
        批量添加模板到向量存储

        Args:
            templates: 模板列表，每个模板包含:
                - id: 模板唯一标识
                - text: 模板文本内容
                - metadata: 模板元数据
            user_id: 用户 ID
            is_public: 是否为公共模板
        """
        if not templates:
            return

        collection = self._get_or_create_collection(user_id, is_public)

        # 准备批量数据
        ids = [t["id"] for t in templates]
        documents = [t["text"] for t in templates]
        metadatas = [t["metadata"] for t in templates]

        # 批量添加
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        logger.info(f"Added {len(templates)} templates to {collection.name}")

    def update_template(
        self,
        template_id: str,
        text: str,
        metadata: Dict[str, Any],
        user_id: Optional[int] = None,
        is_public: bool = True
    ) -> None:
        """
        更新已有模板

        Args:
            template_id: 模板唯一标识
            text: 新的模板文本内容
            metadata: 新的模板元数据
            user_id: 用户 ID
            is_public: 是否为公共模板
        """
        collection = self._get_or_create_collection(user_id, is_public)

        collection.update(
            ids=[template_id],
            documents=[text],
            metadatas=[metadata]
        )

        logger.debug(f"Updated template {template_id} in {collection.name}")

    def delete_template(
        self,
        template_id: str,
        user_id: Optional[int] = None,
        is_public: bool = True
    ) -> None:
        """
        从向量存储中删除模板

        Args:
            template_id: 模板唯一标识
            user_id: 用户 ID
            is_public: 是否为公共模板
        """
        collection = self._get_or_create_collection(user_id, is_public)

        collection.delete(ids=[template_id])

        logger.debug(f"Deleted template {template_id} from {collection.name}")

    def delete_user_collection(self, user_id: int) -> None:
        """
        删除用户的整个私有集合（用于用户删除或清理）

        Args:
            user_id: 用户 ID
        """
        collection_name = self._get_collection_name(user_id, is_public=False)

        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Failed to delete collection {collection_name}: {e}")

    # ==================== 检索 ====================

    def search(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[int] = None,
        is_public: bool = True,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> List[DocumentSearchResult]:
        """
        在向量存储中搜索相似模板

        Args:
            query: 查询文本
            top_k: 返回结果数量
            user_id: 用户 ID（搜索私有模板时需要）
            is_public: 是否搜索公共模板
            where: 元数据过滤条件（Chroma where 过滤器语法）
            where_document: 文档内容过滤条件

        Returns:
            List[DocumentSearchResult]: 搜索结果列表，按相似度降序排序
        """
        collection = self._get_or_create_collection(user_id, is_public)

        # 执行查询
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
            where_document=where_document
        )

        # 转换结果
        search_results = []
        if results["ids"] and len(results["ids"]) > 0 and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                # ChromaDB 默认使用 L2 距离（欧氏距离），需要转换为相似度
                # 距离越小越相似，所以用 1/(1+distance) 来得到 [0,1] 范围的相似度
                distance = results["distances"][0][i] if results["distances"] else 0.0
                # 使用负距离作为相似度排序依据（距离越小，负值越大，排序越靠前）
                similarity = -distance  # 保持排序顺序：更小的距离 = 更大的相似度

                search_results.append(DocumentSearchResult(
                    id=results["ids"][0][i],
                    text=results["documents"][0][i],
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    similarity=similarity
                ))

        logger.debug(f"Search returned {len(search_results)} results from {collection.name}")
        return search_results

    def search_multi_collection(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[int] = None,
        include_public: bool = True,
        include_private: bool = True,
        category_filter: Optional[str] = None
    ) -> List[DocumentSearchResult]:
        """
        跨多个集合搜索（公共 + 私有）

        Args:
            query: 查询文本
            top_k: 每个集合返回的结果数量
            user_id: 用户 ID（搜索私有模板时需要）
            include_public: 是否包含公共模板
            include_private: 是否包含私有模板
            category_filter: 类别过滤

        Returns:
            List[DocumentSearchResult]: 合并后的搜索结果列表
        """
        all_results = []

        # 搜索公共模板
        if include_public:
            where = {"category": category_filter} if category_filter else None
            public_results = self.search(
                query=query,
                top_k=top_k,
                is_public=True,
                where=where
            )
            all_results.extend(public_results)

        # 搜索私有模板
        if include_private and user_id is not None:
            where = {"category": category_filter} if category_filter else None
            private_results = self.search(
                query=query,
                top_k=top_k,
                user_id=user_id,
                is_public=False,
                where=where
            )
            all_results.extend(private_results)

        # 按相似度排序
        all_results.sort(key=lambda x: x.similarity, reverse=True)

        # 返回前 top_k * 2 结果（给重排序留空间）
        return all_results[:top_k * 2]

    # ==================== 维护和管理 ====================

    def get_collection_stats(self, user_id: Optional[int] = None, is_public: bool = True) -> Dict[str, Any]:
        """
        获取集合统计信息

        Args:
            user_id: 用户 ID
            is_public: 是否为公共模板

        Returns:
            Dict[str, Any]: 包含 count, metadata 等信息
        """
        collection = self._get_or_create_collection(user_id, is_public)

        count = collection.count()

        return {
            "name": collection.name,
            "count": count,
            "metadata": collection.metadata
        }

    def list_all_collections(self) -> List[Dict[str, Any]]:
        """
        列出所有集合

        Returns:
            List[Dict[str, Any]]: 集合信息列表
        """
        collections = self.client.list_collections()

        return [
            {
                "name": col.name,
                "count": col.count(),
                "metadata": col.metadata
            }
            for col in collections
        ]

    def clear_collection(self, user_id: Optional[int] = None, is_public: bool = True) -> None:
        """
        清空集合（谨慎使用！）

        Args:
            user_id: 用户 ID
            is_public: 是否为公共模板
        """
        collection_name = self._get_collection_name(user_id, is_public)

        try:
            self.client.delete_collection(name=collection_name)
            logger.warning(f"Cleared collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection {collection_name}: {e}")

    def persist(self) -> None:
        """
        持久化向量存储（确保数据写入磁盘）
        """
        # Chroma 在 duckdb+parquet 模式下会自动持久化
        # 这里可以添加额外的刷新逻辑（如果需要）
        logger.debug("Vector store persisted")


# ==================== 单例模式 ====================

_vector_store_instance: Optional[TemplateVectorStore] = None


def get_vector_store() -> TemplateVectorStore:
    """
    获取向量存储服务单例

    Returns:
        TemplateVectorStore: 向量存储服务实例
    """
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = TemplateVectorStore()
    return _vector_store_instance
