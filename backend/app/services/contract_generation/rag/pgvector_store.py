# backend/app/services/contract_generation/rag/pgvector_store.py
"""
PostgreSQL pgvector 向量存储服务

替代ChromaDB,直接在PostgreSQL中存储和检索向量。
"""
import logging
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from sqlalchemy.sql import select

from app.models.contract_template import ContractTemplate
from .bge_client import BGEClient, get_bge_client

logger = logging.getLogger(__name__)


@dataclass
class DocumentSearchResult:
    """文档搜索结果"""
    id: str  # 文档 ID
    text: str  # 文档内容
    metadata: Dict[str, Any]  # 元数据
    similarity: float  # 相似度分数 (余弦相似度)
    distance: float = 0.0  # 距离 (用于排序)


class PgVectorStore:
    """
    PostgreSQL pgvector 向量存储服务

    直接在PostgreSQL中存储和检索向量,无需额外的向量数据库。
    """

    def __init__(self, bge_client: Optional[BGEClient] = None):
        """
        初始化向量存储服务

        Args:
            bge_client: BGE 客户端实例
        """
        self.bge_client = bge_client or get_bge_client()
        logger.info("PgVectorStore initialized")

    # ==================== 向量生成 ====================

    def _generate_embedding(self, text: str) -> List[float]:
        """
        生成文本的向量嵌入

        Args:
            text: 输入文本

        Returns:
            List[float]: 向量 (1024维)
        """
        result = self.bge_client.embed(text)
        return result.embedding

    def _compute_text_hash(self, text: str) -> str:
        """
        计算文本的SHA256哈希

        Args:
            text: 输入文本

        Returns:
            str: 十六进制哈希值
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    # ==================== 单个模板操作 ====================

    def add_template(
        self,
        db: Session,
        template_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        为模板添加向量嵌入

        Args:
            db: 数据库会话
            template_id: 模板ID
            text: 用于生成向量的文本
            metadata: 元数据 (可选,用于调试)

        Returns:
            bool: 是否成功
        """
        try:
            # 生成向量
            embedding = self._generate_embedding(text)
            text_hash = self._compute_text_hash(text)

            # 更新数据库
            template = db.query(ContractTemplate).filter(
                ContractTemplate.id == template_id
            ).first()

            if not template:
                logger.error(f"Template not found: {template_id}")
                return False

            # 更新向量字段
            template.embedding = embedding
            template.embedding_updated_at = datetime.utcnow()
            template.embedding_text_hash = text_hash

            db.commit()
            logger.info(f"Added embedding for template {template_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to add embedding for template {template_id}: {e}")
            db.rollback()
            return False

    def update_template(
        self,
        db: Session,
        template_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新模板的向量嵌入

        Args:
            db: 数据库会话
            template_id: 模板ID
            text: 新的文本内容
            metadata: 元数据

        Returns:
            bool: 是否成功
        """
        return self.add_template(db, template_id, text, metadata)

    def delete_template(
        self,
        db: Session,
        template_id: str
    ) -> bool:
        """
        删除模板的向量嵌入 (置空)

        Args:
            db: 数据库会话
            template_id: 模板ID

        Returns:
            bool: 是否成功
        """
        try:
            template = db.query(ContractTemplate).filter(
                ContractTemplate.id == template_id
            ).first()

            if not template:
                return False

            # 置空向量
            template.embedding = None
            template.embedding_updated_at = None
            template.embedding_text_hash = None

            db.commit()
            logger.info(f"Deleted embedding for template {template_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete embedding for template {template_id}: {e}")
            db.rollback()
            return False

    # ==================== 批量操作 ====================

    def add_templates_batch(
        self,
        db: Session,
        templates: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> Dict[str, int]:
        """
        批量添加向量嵌入

        Args:
            db: 数据库会话
            templates: 模板列表 [{"id": ..., "text": ...}, ...]
            batch_size: 批处理大小

        Returns:
            Dict: 统计信息
        """
        success_count = 0
        failed_count = 0

        logger.info(f"Starting batch embedding generation for {len(templates)} templates")

        for i in range(0, len(templates), batch_size):
            batch = templates[i:i + batch_size]

            for template_data in batch:
                template_id = template_data["id"]
                text = template_data["text"]

                if self.add_template(db, template_id, text):
                    success_count += 1
                else:
                    failed_count += 1

        logger.info(f"Batch embedding completed: {success_count} succeeded, {failed_count} failed")

        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(templates)
        }

    # ==================== 向量检索 ====================

    def search(
        self,
        db: Session,
        query: str,
        top_k: int = 5,
        user_id: Optional[int] = None,
        category_filter: Optional[str] = None,
        is_public: Optional[bool] = None
    ) -> List[DocumentSearchResult]:
        """
        向量相似度搜索

        Args:
            db: 数据库会话
            query: 查询文本
            top_k: 返回结果数量
            user_id: 用户ID (用于权限过滤)
            category_filter: 类别过滤
            is_public: 是否为公共模板

        Returns:
            List[DocumentSearchResult]: 搜索结果
        """
        try:
            # 生成查询向量
            query_embedding = self._generate_embedding(query)

            # 构建基础查询 - 使用原生SQL以支持pgvector的cosine_distance
            # 余弦相似度 = 1 - 余弦距离
            sql_query = text("""
                SELECT
                    id,
                    name,
                    category,
                    subcategory,
                    description,
                    file_url,
                    file_name,
                    is_public,
                    owner_id,
                    download_count,
                    rating,
                    tags,
                    keywords,
                    jurisdiction,
                    language,
                    1 - (embedding <=> :query_embedding) AS similarity
                FROM contract_templates
                WHERE embedding IS NOT NULL
                  AND status = 'active'
                :category_filter
                :is_public_filter
                :user_filter
                ORDER BY similarity DESC
                LIMIT :top_k
            """)

            # 构建过滤条件
            params = {
                "query_embedding": str(query_embedding),
                "top_k": top_k
            }

            # 添加类别过滤
            if category_filter:
                sql_query = sql_query.bindparams(
                    category_filter=text("AND category = :category")
                )
                params["category"] = category_filter
            else:
                sql_query = sql_query.bindparams(
                    category_filter=text("")
                )

            # 添加is_public过滤
            if is_public is not None:
                sql_query = sql_query.bindparams(
                    is_public_filter=text("AND is_public = :is_public")
                )
                params["is_public"] = is_public
            else:
                sql_query = sql_query.bindparams(
                    is_public_filter=text("")
                )

            # 添加用户权限过滤
            if user_id is not None:
                sql_query = sql_query.bindparams(
                    user_filter=text("AND (is_public = true OR owner_id = :user_id)")
                )
                params["user_id"] = user_id
            else:
                sql_query = sql_query.bindparams(
                    user_filter=text("")
                )

            # 执行查询
            result = db.execute(sql_query, params)
            rows = result.fetchall()

            # 转换为DocumentSearchResult
            search_results = []
            for row in rows:
                search_results.append(DocumentSearchResult(
                    id=row[0],  # id
                    text="",  # 文本内容按需加载
                    metadata={
                        "name": row[1],  # name
                        "category": row[2],  # category
                        "subcategory": row[3],  # subcategory
                        "description": row[4] or "",  # description
                        "file_url": row[5],  # file_url
                        "file_name": row[6],  # file_name
                        "is_public": row[7],  # is_public
                        "owner_id": row[8],  # owner_id
                        "download_count": row[9],  # download_count
                        "rating": row[10],  # rating
                        "tags": row[11] or [],  # tags
                        "keywords": row[12] or [],  # keywords
                        "jurisdiction": row[13] or "",  # jurisdiction
                        "language": row[14] or "zh-CN",  # language
                    },
                    similarity=float(row[16]),  # similarity
                    distance=1 - float(row[16])  # 余弦距离
                ))

            logger.info(f"Vector search returned {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Vector search failed: {e}", exc_info=True)
            return []

    # ==================== 维护和统计 ====================

    def get_stats(self, db: Session) -> Dict[str, Any]:
        """
        获取向量存储统计信息

        Args:
            db: 数据库会话

        Returns:
            Dict: 统计信息
        """
        try:
            total = db.query(func.count(ContractTemplate.id)).filter(
                ContractTemplate.status == "active"
            ).scalar()

            indexed = db.query(func.count(ContractTemplate.id)).filter(
                ContractTemplate.embedding.isnot(None),
                ContractTemplate.status == "active"
            ).scalar()

            return {
                "total_templates": total,
                "indexed_templates": indexed,
                "coverage": f"{(indexed / total * 100):.1f}%" if total > 0 else "N/A"
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "total_templates": 0,
                "indexed_templates": 0,
                "coverage": "Error"
            }


# ==================== 单例模式 ====================

_pgvector_store_instance: Optional[PgVectorStore] = None


def get_pgvector_store() -> PgVectorStore:
    """
    获取向量存储服务单例

    Returns:
        PgVectorStore: 向量存储服务实例
    """
    global _pgvector_store_instance
    if _pgvector_store_instance is None:
        _pgvector_store_instance = PgVectorStore()
    return _pgvector_store_instance
