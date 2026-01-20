# backend/app/services/contract_generation/rag/template_retriever.py
"""
模板检索服务

负责根据用户需求检索相关的合同模板。
结合向量检索和重排序，提供精准的模板匹配。

支持两种向量存储后端:
- ChromaDB (传统,需要额外依赖)
- PostgreSQL pgvector (推荐,统一数据存储)
"""
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.contract_template import ContractTemplate

# 可选导入 ChromaDB (在 Python 3.14 + pydantic v2 环境下可能不可用)
try:
    from .vector_store import TemplateVectorStore, get_vector_store, DocumentSearchResult
    _chromadb_available = True
except (ImportError, Exception):
    TemplateVectorStore = None
    get_vector_store = None
    DocumentSearchResult = None
    _chromadb_available = False

from .pgvector_store import PgVectorStore, get_pgvector_store  # 新增: pgvector支持
from .bge_client import BGEClient, get_bge_client, RerankResult
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedTemplate:
    """
    检索到的模板

    包含模板信息和匹配分数。
    """
    # 模板基本信息
    id: str
    name: str
    category: str
    subcategory: Optional[str]
    description: Optional[str]
    file_url: str
    file_name: str

    # 权限信息
    is_public: bool
    owner_id: Optional[int]

    # 统计信息
    download_count: int
    rating: float

    # 匹配信息
    similarity_score: float  # 向量相似度 (0-1)
    rerank_score: Optional[float] = None  # 重排序分数 (0-1)
    final_score: float = 0.0  # 最终分数（综合考虑）

    # 元数据
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    jurisdiction: Optional[str] = None
    language: str = "zh-CN"

    # 匹配原因（用于向用户解释）
    match_reason: Optional[str] = None

    def __post_init__(self):
        """计算最终分数"""
        if self.final_score == 0.0:
            # 综合向量相似度和重排序分数
            if self.rerank_score is not None:
                # 重排序分数权重更高（更精准）
                self.final_score = (
                    self.similarity_score * 0.3 +
                    self.rerank_score * 0.7
                )
            else:
                self.final_score = self.similarity_score

    @classmethod
    def from_search_result(cls, result: DocumentSearchResult) -> "RetrievedTemplate":
        """从向量搜索结果创建 RetrievedTemplate"""
        metadata = result.metadata

        return cls(
            id=result.id,
            name=metadata.get("name", ""),
            category=metadata.get("category", ""),
            subcategory=metadata.get("subcategory") or None,
            description=metadata.get("description") or None,
            file_url=metadata.get("file_url", ""),
            file_name=metadata.get("file_name", ""),
            is_public=metadata.get("is_public", True),
            owner_id=metadata.get("owner_id") or None,
            download_count=metadata.get("download_count", 0),
            rating=metadata.get("rating", 0.0),
            similarity_score=result.similarity,
            tags=metadata.get("tags", []),
            keywords=metadata.get("keywords", []),
            jurisdiction=metadata.get("jurisdiction") or None,
            language=metadata.get("language", "zh-CN"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "file_url": self.file_url,
            "file_name": self.file_name,
            "is_public": self.is_public,
            "owner_id": self.owner_id,
            "download_count": self.download_count,
            "rating": self.rating,
            "similarity_score": self.similarity_score,
            "rerank_score": self.rerank_score,
            "final_score": self.final_score,
            "tags": self.tags,
            "keywords": self.keywords,
            "jurisdiction": self.jurisdiction,
            "language": self.language,
            "match_reason": self.match_reason,
        }


@dataclass
class TemplateSearchResult:
    """
    模板搜索结果

    包含检索到的模板列表和搜索元数据。
    """
    templates: List[RetrievedTemplate]
    query: str
    total_count: int
    search_time_ms: int

    # 搜索统计
    vector_search_count: int = 0  # 向量检索返回的数量
    rerank_count: int = 0  # 重排序的数量

    def get_top_k(self, k: int) -> List[RetrievedTemplate]:
        """获取前 k 个结果"""
        return self.templates[:k]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "templates": [t.to_dict() for t in self.templates],
            "query": self.query,
            "total_count": self.total_count,
            "search_time_ms": self.search_time_ms,
            "vector_search_count": self.vector_search_count,
            "rerank_count": self.rerank_count,
        }


class TemplateRetriever:
    """
    模板检索服务 (使用pgvector)

    结合向量检索和重排序，提供精准的模板匹配。
    """

    def __init__(
        self,
        vector_store: Optional[Union[TemplateVectorStore, PgVectorStore]] = None,  # 支持两种存储
        bge_client: Optional[BGEClient] = None
    ):
        """
        初始化模板检索器

        Args:
            vector_store: 向量存储实例，默认使用pgvector单例
            bge_client: BGE 客户端实例，默认使用全局单例
        """
        # 优先使用pgvector,如果不可用则回退到ChromaDB
        if vector_store is None:
            try:
                from app.database import SessionLocal
                db = SessionLocal()
                # 测试pgvector是否可用
                test_store = get_pgvector_store()
                test_store.get_stats(db)
                db.close()
                vector_store = test_store
                logger.info("TemplateRetriever initialized (using pgvector)")
            except Exception as e:
                logger.warning(f"pgvector不可用,回退到ChromaDB: {e}")
                vector_store = get_vector_store()
                logger.info("TemplateRetriever initialized (using ChromaDB fallback)")

        self.vector_store = vector_store
        self.bge_client = bge_client or get_bge_client()
        logger.info("TemplateRetriever initialized")

    # ==================== 核心检索逻辑 ====================

    def retrieve(
        self,
        query: str,
        user_id: Optional[int] = None,
        category: Optional[str] = None,
        top_k: int = 5,
        use_rerank: bool = True,
        rerank_top_n: int = 20  # 先检索 20 个，再重排序
    ) -> TemplateSearchResult:
        """
        根据用户需求检索相关模板

        检索流程：
        1. 向量检索：从公共模板和用户私有模板中检索
        2. 重排序：使用 BGE-Reranker 对结果进行精准排序
        3. 过滤：根据用户权限过滤结果

        Args:
            query: 用户查询文本
            user_id: 当前用户 ID（用于检索私有模板）
            category: 类别过滤
            top_k: 返回结果数量
            use_rerank: 是否使用重排序
            rerank_top_n: 重排序前的候选数量

        Returns:
            TemplateSearchResult: 检索结果
        """
        start_time = datetime.now()

        logger.info(f"Retrieving templates for query: '{query}' (user={user_id}, category={category})")

        # 检测vector_store类型并调用相应方法
        if isinstance(self.vector_store, PgVectorStore):
            # 使用pgvector
            logger.info("Using pgvector for retrieval")
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                vector_results = self.vector_store.search(
                    db=db,
                    query=query,
                    top_k=rerank_top_n if use_rerank else top_k,
                    user_id=user_id,
                    category_filter=category
                )

                # 转换pgvector结果为RetrievedTemplate格式
                candidates = []
                for result in vector_results:
                    # 从metadata创建RetrievedTemplate
                    template = RetrievedTemplate(
                        id=result.id,
                        name=result.metadata["name"],
                        category=result.metadata["category"],
                        subcategory=result.metadata.get("subcategory"),
                        description=result.metadata.get("description"),
                        file_url=result.metadata["file_url"],
                        file_name=result.metadata["file_name"],
                        is_public=result.metadata["is_public"],
                        owner_id=result.metadata.get("owner_id"),
                        download_count=result.metadata.get("download_count", 0),
                        rating=result.metadata.get("rating", 0.0),
                        similarity_score=result.similarity,
                        tags=result.metadata.get("tags", []),
                        keywords=result.metadata.get("keywords", []),
                        jurisdiction=result.metadata.get("jurisdiction"),
                        language=result.metadata.get("language", "zh-CN"),
                    )
                    candidates.append(template)

                db.close()
            except Exception as e:
                logger.error(f"pgvector search failed: {e}")
                db.close()
                candidates = []

        else:
            # 使用ChromaDB
            logger.info("Using ChromaDB for retrieval")
            vector_results = self.vector_store.search_multi_collection(
                query=query,
                top_k=rerank_top_n if use_rerank else top_k,
                user_id=user_id,
                include_public=True,
                include_private=(user_id is not None),
                category_filter=category
            )

            # 转换为 RetrievedTemplate
            candidates = [RetrievedTemplate.from_search_result(r) for r in vector_results]

        logger.info(f"Vector search returned {len(candidates)} candidates")

        if not candidates:
            return TemplateSearchResult(
                templates=[],
                query=query,
                total_count=0,
                search_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                vector_search_count=0
            )

        # 第二步：重排序（可选）
        if use_rerank and len(candidates) > 1:
            candidates = self._rerank_candidates(query, candidates)
            logger.info(f"Reranked {len(candidates)} candidates")
        else:
            # 按相似度排序
            candidates.sort(key=lambda x: x.final_score, reverse=True)

        # 第二步半：关键词匹配提升（重要！）
        # 如果模板名称包含查询关键词，大幅提升其排名
        candidates = self._boost_keyword_matches(query, candidates)
        logger.info(f"Applied keyword matching boost")

        # 第三步：权限过滤
        filtered_templates = self._filter_by_permission(candidates, user_id)

        # 第四步：返回前 top_k 个
        final_results = filtered_templates[:top_k]

        # 生成匹配原因
        for template in final_results:
            template.match_reason = self._generate_match_reason(query, template)

        search_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        result = TemplateSearchResult(
            templates=final_results,
            query=query,
            total_count=len(filtered_templates),
            search_time_ms=search_time_ms,
            vector_search_count=len(vector_results),
            rerank_count=len(candidates) if use_rerank else 0
        )

        logger.info(f"Retrieval completed: {len(final_results)} results in {search_time_ms}ms")

        return result

    def _rerank_candidates(
        self,
        query: str,
        candidates: List[RetrievedTemplate]
    ) -> List[RetrievedTemplate]:
        """
        使用 BGE-Reranker 对候选模板进行重排序

        Args:
            query: 用户查询
            candidates: 候选模板列表

        Returns:
            List[RetrievedTemplate]: 重排序后的模板列表
        """
        try:
            # 准备重排序文档
            # 使用模板名称 + 描述 + 类别作为重排序内容
            documents = []
            for template in candidates:
                parts = [template.name]
                if template.description:
                    parts.append(template.description)
                if template.subcategory:
                    parts.append(template.subcategory)
                documents.append(" | ".join(parts))

            # 调用重排序 API
            rerank_results = self.bge_client.rerank(
                query=query,
                documents=documents,
                top_n=None  # 返回全部结果
            )

            # 更新候选模板的重排序分数
            for rerank_result in rerank_results:
                idx = rerank_result.index
                if idx < len(candidates):
                    candidates[idx].rerank_score = rerank_result.relevance_score

            # 重新计算最终分数并排序
            candidates.sort(key=lambda x: x.final_score, reverse=True)

            return candidates

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # 重排序失败时，返回原始顺序（按向量相似度）
            return candidates

    def _boost_keyword_matches(
        self,
        query: str,
        candidates: List[RetrievedTemplate]
    ) -> List[RetrievedTemplate]:
        """
        关键词匹配提升

        如果模板名称或关键词包含查询词，大幅提升其排名。
        这可以弥补向量检索的不足，确保精确匹配的模板排在前面。

        Args:
            query: 用户查询
            candidates: 候选模板列表

        Returns:
            List[RetrievedTemplate]: 提升后的模板列表
        """
        # 提取查询中的关键词（去掉常见停用词）
        query_lower = query.lower()
        keywords = [k for k in query_lower.split() if len(k) > 1]

        # 对每个候选模板进行检查
        for template in candidates:
            name_lower = template.name.lower()

            # 检查模板名称是否包含查询关键词
            keyword_match_count = 0
            matched_keywords = []

            for keyword in keywords:
                if keyword in name_lower:
                    keyword_match_count += 1
                    matched_keywords.append(keyword)

            # 如果有关键词匹配，大幅提升分数
            if keyword_match_count > 0:
                # 提升幅度：
                # - 完全匹配（所有关键词都在）：+2.0
                # - 部分匹配：+0.5 * 匹配数量
                boost = 0.5 * keyword_match_count
                if keyword_match_count == len(keywords):
                    boost = 2.0

                template.final_score += boost
                logger.debug(f"Keyword boost: '{template.name}' +{boost:.2f} (matched: {matched_keywords})")

        # 重新排序
        candidates.sort(key=lambda x: x.final_score, reverse=True)

        return candidates

    def _filter_by_permission(
        self,
        templates: List[RetrievedTemplate],
        user_id: Optional[int]
    ) -> List[RetrievedTemplate]:
        """
        根据用户权限过滤模板

        规则：
        - 公共模板：所有用户可见
        - 私有模板：仅所有者可见

        Args:
            templates: 候选模板列表
            user_id: 当前用户 ID

        Returns:
            List[RetrievedTemplate]: 过滤后的模板列表
        """
        filtered = []

        for template in templates:
            if template.is_public:
                # 公共模板，所有人可见
                filtered.append(template)
            elif template.owner_id == user_id:
                # 用户的私有模板
                filtered.append(template)
            else:
                # 其他用户的私有模板，不可见
                logger.debug(f"Filtered out private template {template.id} (owner={template.owner_id})")

        return filtered

    def _generate_match_reason(
        self,
        query: str,
        template: RetrievedTemplate
    ) -> str:
        """
        生成模板匹配原因（用于向用户解释为什么推荐这个模板）

        Args:
            query: 用户查询
            template: 匹配的模板

        Returns:
            str: 匹配原因
        """
        reasons = []

        # 类别匹配
        if template.category and template.category.lower() in query.lower():
            reasons.append(f"属于'{template.category}'类别")

        # 关键词匹配
        if template.keywords:
            matched_keywords = [
                kw for kw in template.keywords
                if kw.lower() in query.lower()
            ]
            if matched_keywords:
                reasons.append(f"包含关键词：{', '.join(matched_keywords)}")

        # 高评分
        if template.rating >= 4.0:
            reasons.append(f"用户评分 {template.rating:.1f} 分")

        # 高下载量
        if template.download_count >= 100:
            reasons.append(f"已被下载 {template.download_count} 次")

        # 默认原因
        if not reasons:
            reasons.append("与您的需求语义相似")

        return "；".join(reasons)

    # ==================== 高级检索 ====================

    def retrieve_by_category(
        self,
        category: str,
        user_id: Optional[int] = None,
        subcategory: Optional[str] = None,
        top_k: int = 10
    ) -> TemplateSearchResult:
        """
        按类别检索模板

        Args:
            category: 类别名称
            user_id: 当前用户 ID
            subcategory: 子类别（可选）
            top_k: 返回结果数量

        Returns:
            TemplateSearchResult: 检索结果
        """
        # 构造查询文本
        if subcategory:
            query = f"{category} {subcategory}"
        else:
            query = category

        return self.retrieve(
            query=query,
            user_id=user_id,
            category=category,
            top_k=top_k,
            use_rerank=False  # 类别检索不需要重排序
        )

    def retrieve_similar_template(
        self,
        template_id: str,
        user_id: Optional[int] = None,
        top_k: int = 5
    ) -> TemplateSearchResult:
        """
        检索与指定模板相似的其他模板

        Args:
            template_id: 参考模板 ID
            user_id: 当前用户 ID
            top_k: 返回结果数量

        Returns:
            TemplateSearchResult: 相似模板列表
        """
        # TODO: 实现相似模板检索
        # 可以通过获取模板内容，然后以其作为查询进行检索
        raise NotImplementedError("Similar template retrieval not yet implemented")

    def retrieve_multi_query(
        self,
        queries: List[str],
        user_id: Optional[int] = None,
        category: Optional[str] = None,
        top_k: int = 5
    ) -> TemplateSearchResult:
        """
        多查询检索（合并多个查询的结果）

        Args:
            queries: 查询列表
            user_id: 当前用户 ID
            category: 类别过滤
            top_k: 返回结果数量

        Returns:
            TemplateSearchResult: 合并后的检索结果
        """
        all_templates = {}  # 使用 dict 去重（key = template_id）

        for query in queries:
            result = self.retrieve(
                query=query,
                user_id=user_id,
                category=category,
                top_k=top_k * 2,  # 获取更多候选
                use_rerank=False
            )

            # 合并结果
            for template in result.templates:
                if template.id not in all_templates:
                    all_templates[template.id] = template
                else:
                    # 如果已存在，更新分数（取最大值）
                    existing = all_templates[template.id]
                    if template.final_score > existing.final_score:
                        all_templates[template.id] = template

        # 按分数排序
        merged_templates = sorted(
            all_templates.values(),
            key=lambda x: x.final_score,
            reverse=True
        )[:top_k]

        return TemplateSearchResult(
            templates=merged_templates,
            query=" | ".join(queries),
            total_count=len(merged_templates),
            search_time_ms=0,
        )

    # ==================== 辅助方法 ====================

    def get_template_by_id(
        self,
        template_id: str,
        db: Session
    ) -> Optional[RetrievedTemplate]:
        """
        从数据库获取模板详情

        Args:
            template_id: 模板 ID
            db: 数据库会话

        Returns:
            Optional[RetrievedTemplate]: 模板信息
        """
        template = db.query(ContractTemplate).filter(
            ContractTemplate.id == template_id
        ).first()

        if not template:
            return None

        return RetrievedTemplate(
            id=template.id,
            name=template.name,
            category=template.category,
            subcategory=template.subcategory,
            description=template.description,
            file_url=template.file_url,
            file_name=template.file_name,
            is_public=template.is_public,
            owner_id=template.owner_id,
            download_count=template.download_count,
            rating=template.rating,
            similarity_score=0.0,  # 无相似度
            tags=template.tags or [],
            keywords=template.keywords or [],
            jurisdiction=template.jurisdiction,
            language=template.language,
        )


# ==================== 单例模式 ====================

_template_retriever_instance: Optional[TemplateRetriever] = None


def get_template_retriever() -> TemplateRetriever:
    """
    获取模板检索器单例

    Returns:
        TemplateRetriever: 模板检索器实例
    """
    global _template_retriever_instance
    if _template_retriever_instance is None:
        _template_retriever_instance = TemplateRetriever()
    return _template_retriever_instance
