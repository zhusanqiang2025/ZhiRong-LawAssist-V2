# backend/app/services/knowledge_base/unified_service.py
"""
统一知识服务 - 多源聚合检索（优化版）

实现三个核心优化：
1. Rerank 重排序机制：使用 BGE-Reranker 二次打分
2. 异步并发搜索：使用 asyncio.gather 并发检索
3. 意图识别：搜索前确定检索范围和优化查询
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base_interface import (
    BaseKnowledgeStore,
    KnowledgeItem,
    KnowledgeSearchResult,
    SearchIntent
)
from .local_legal_kb import get_local_legal_kb

logger = logging.getLogger(__name__)


# ==================== 统一知识服务 ====================

class UnifiedKnowledgeService:
    """
    统一知识服务 - 多源聚合检索（优化版）

    优化特性：
    1. 意图识别：搜索前确定检索范围和优化查询
    2. 并发搜索：所有知识库同时检索（asyncio.gather）
    3. Rerank 重排序：使用 BGE-Reranker 二次打分，提升结果质量
    """

    def __init__(self):
        """初始化统一知识服务"""
        # 按优先级排序的知识库列表
        self.stores: List[BaseKnowledgeStore] = []

        # Rerank 客户端（延迟初始化）
        self._reranker = None

        # 结果缓存（简单实现，可后续升级为 Redis）
        self._cache: Dict[str, tuple[list, datetime]] = {}
        self._cache_ttl = 3600  # 缓存1小时

        # 注册默认知识库
        self._register_default_stores()

        logger.info("[统一知识服务] 初始化完成")

    def _register_default_stores(self):
        """注册默认知识库"""
        # 注册本地法律知识库
        local_kb = get_local_legal_kb()
        self.register_store(local_kb)

    @property
    def reranker(self):
        """延迟初始化 Reranker 客户端"""
        if self._reranker is None:
            try:
                from app.services.contract_generation.rag.bge_client import get_bge_reranker_client
                self._reranker = get_bge_reranker_client()
                logger.info("[统一知识服务] BGE-Reranker 初始化成功")
            except ImportError:
                logger.warning("[统一知识服务] BGE-Reranker 不可用，将跳过重排序")
            except Exception as e:
                logger.warning(f"[统一知识服务] BGE-Reranker 初始化失败: {e}")
        return self._reranker

    def register_store(self, store: BaseKnowledgeStore):
        """
        注册知识库

        Args:
            store: 知识库实例
        """
        # 检查是否已注册
        if any(s.name == store.name for s in self.stores):
            logger.warning(f"[统一知识服务] 知识库 '{store.name}' 已注册，跳过")
            return

        self.stores.append(store)
        # 按优先级排序
        self.stores.sort(key=lambda x: x.priority)
        logger.info(f"[统一知识服务] 注册知识库: {store.name} (优先级: {store.priority})")

    async def search(
        self,
        query: str,
        domain: str = "",
        limit: int = 5,
        enabled_stores: Optional[List[str]] = None
    ) -> KnowledgeSearchResult:
        """
        多源并发搜索 + Rerank 重排序（优化版）

        策略：
        1. 意图识别：确定检索范围和优化查询（优化三）
        2. 并发搜索：所有知识库同时检索（优化二）
        3. 汇总结果：取各库 Top N
        4. Rerank 重排序：使用 BGE-Reranker 二次打分（优化一）
        5. 返回 Top K

        性能优化：
        - 并发搜索：延迟由最慢的库决定，而非累加
        - 结果缓存：相同查询复用结果
        - 超时控制：单个库超时不影响其他库

        Args:
            query: 搜索查询
            domain: 法律领域（可选）
            limit: 返回结果数量
            enabled_stores: 启用的知识库列表（可选）

        Returns:
            搜索结果
        """
        # 检查缓存
        cache_key = f"{query}_{domain}_{limit}_{enabled_stores}"
        if cache_key in self._cache:
            cached_items, cached_time = self._cache[cache_key]
            if (datetime.now() - cached_time).seconds < self._cache_ttl:
                logger.info(f"[统一知识服务] 使用缓存结果: {cache_key}")
                return KnowledgeSearchResult(
                    query=query,
                    items=cached_items,
                    total=len(cached_items)
                )

        # 步骤1：意图识别（优化三）
        search_intent = await self._detect_intent(query, domain)
        logger.info(f"[统一知识服务] 搜索意图: domain={search_intent.target_domains}, query='{search_intent.optimized_query}'")

        # 步骤2：筛选启用的知识库
        active_stores = [
            store for store in self.stores
            if (not enabled_stores or store.name in enabled_stores)
            and store.is_available()
        ]

        if not active_stores:
            logger.warning("[统一知识服务] 没有可用的知识库")
            return KnowledgeSearchResult(query=query, items=[], total=0, search_intent=search_intent)

        logger.info(f"[统一知识服务] 启用的知识库: {[s.name for s in active_stores]}")

        # 步骤3：并发搜索（优化二）
        # 各库取 Top N（N > limit，为 Rerank 提供候选）
        top_n_per_store = max(10, limit * 2)

        search_tasks = [
            store.search(
                query=search_intent.optimized_query,
                domain=domain,
                limit=top_n_per_store
            )
            for store in active_stores
        ]

        # 并发执行，超时控制
        try:
            results_list = await asyncio.wait_for(
                asyncio.gather(*search_tasks, return_exceptions=True),
                timeout=30  # 总超时30秒
            )
        except asyncio.TimeoutError:
            logger.error("[统一知识服务] 搜索超时（30秒）")
            return KnowledgeSearchResult(query=query, items=[], total=0, search_intent=search_intent)

        # 步骤4：汇总结果
        all_candidates = []
        for i, result in enumerate(results_list):
            if isinstance(result, Exception):
                logger.warning(f"[统一知识服务] 知识库 {active_stores[i].name} 搜索失败: {result}")
                continue

            # 添加来源标识
            for item in result:
                item.source_store = active_stores[i].name
                all_candidates.append(item)

        if not all_candidates:
            logger.info("[统一知识服务] 所有知识库均无结果")
            return KnowledgeSearchResult(query=query, items=[], total=0, search_intent=search_intent)

        logger.info(f"[统一知识服务] 汇总 {len(all_candidates)} 个候选结果")

        # 步骤5：Rerank 重排序（优化一）
        if len(all_candidates) > limit and self.reranker is not None:
            try:
                all_candidates = await self._rerank_results(
                    query=query,
                    candidates=all_candidates,
                    top_k=limit
                )
                logger.info(f"[统一知识服务] Rerank 重排序完成，返回 Top {len(all_candidates)}")
            except Exception as e:
                logger.warning(f"[统一知识服务] Rerank 重排序失败: {e}，使用原始排序")
                all_candidates = all_candidates[:limit]
        else:
            all_candidates = all_candidates[:limit]

        # 缓存结果
        self._cache[cache_key] = (all_candidates, datetime.now())

        return KnowledgeSearchResult(
            query=query,
            items=all_candidates,
            total=len(all_candidates),
            search_intent=search_intent
        )

    async def _detect_intent(self, query: str, domain: str) -> SearchIntent:
        """
        意图识别（优化三）

        确定检索范围和优化查询

        Args:
            query: 原始查询
            domain: 法律领域

        Returns:
            搜索意图
        """
        # 简化版意图识别（可后续升级为 LLM 分类）
        intent = SearchIntent(
            original_query=query,
            optimized_query=query,
            target_domains=[domain] if domain else [],
            confidence=1.0
        )

        # 根据查询内容确定目标知识库
        query_lower = query.lower()

        # 合同相关 → 优先合同知识库
        if any(kw in query_lower for kw in ["合同", "协议", "违约", "解除", "条款"]):
            intent.target_domains = ["合同法", "民法典·合同编"]
            intent.optimized_query = f"{query} 民法典 合同编"

        # 劳动相关 → 优先劳动法知识库
        elif any(kw in query_lower for kw in ["劳动", "工资", "工伤", "仲裁", "解除劳动关系"]):
            intent.target_domains = ["劳动法", "劳动争议"]
            intent.optimized_query = f"{query} 劳动争议调解仲裁法"

        # 公司相关 → 优先公司法知识库
        elif any(kw in query_lower for kw in ["公司", "股东", "股权", "董事会", "破产"]):
            intent.target_domains = ["公司法", "破产法"]
            intent.optimized_query = f"{query} 公司法"

        # 已指定 domain，则直接使用
        elif domain:
            intent.target_domains = [domain]
            # 根据领域优化查询
            if "合同" in domain:
                intent.optimized_query = f"{query} 民法典 合同编"
            elif "劳动" in domain:
                intent.optimized_query = f"{query} 劳动争议调解仲裁法"

        return intent

    async def _rerank_results(
        self,
        query: str,
        candidates: List[KnowledgeItem],
        top_k: int = 5
    ) -> List[KnowledgeItem]:
        """
        使用 BGE-Reranker 进行重排序（优化一）

        Args:
            query: 原始查询
            candidates: 候选结果列表
            top_k: 返回前 K 个

        Returns:
            重排序后的结果
        """
        try:
            # 准备文档列表和查询
            docs = [item.content for item in candidates]

            # 调用 Reranker
            rerank_results = await self.reranker.rerank(
                query=query,
                documents=docs,
                top_n=top_k
            )

            # 根据重排序结果重新排序
            reranked_map = {
                result.index: result.score
                for result in rerank_results
            }

            # 按新分数排序
            sorted_candidates = sorted(
                candidates,
                key=lambda x: reranked_map.get(candidates.index(x), 0),
                reverse=True
            )

            logger.info(f"[Rerank] 从 {len(candidates)} 个候选中重排序出 Top {top_k}")
            return sorted_candidates[:top_k]

        except Exception as e:
            logger.warning(f"[Rerank] 重排序失败: {e}，使用原始排序")
            return candidates[:top_k]

    async def get_by_id(self, item_id: str, store_name: Optional[str] = None) -> Optional[KnowledgeItem]:
        """
        通过 ID 获取知识

        Args:
            item_id: 知识条目 ID
            store_name: 知识库名称（可选，如果指定则只在该库中查找）

        Returns:
            知识条目，如果不存在则返回 None
        """
        # 如果指定了知识库，只在该库中查找
        if store_name:
            for store in self.stores:
                if store.name == store_name:
                    return await store.get_by_id(item_id)
            return None

        # 在所有知识库中查找
        for store in self.stores:
            item = await store.get_by_id(item_id)
            if item:
                return item

        return None

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查所有知识库

        Returns:
            健康状态信息
        """
        health_info = {
            "total_stores": len(self.stores),
            "available_stores": 0,
            "stores": []
        }

        for store in self.stores:
            store_health = await store.health_check()
            health_info["stores"].append(store_health)
            if store_health["available"]:
                health_info["available_stores"] += 1

        return health_info


# ==================== 单例 ====================

_service_instance: Optional[UnifiedKnowledgeService] = None


def get_unified_kb_service() -> UnifiedKnowledgeService:
    """获取统一知识服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = UnifiedKnowledgeService()
        logger.info("[统一知识服务] 创建单例实例")
    return _service_instance


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import asyncio

    async def test_unified_service():
        """测试统一知识服务"""
        service = get_unified_kb_service()

        # 测试1：基本搜索
        print("=" * 80)
        print("测试1：基本搜索 - 合同违约")
        print("=" * 80)
        result = await service.search("合同违约怎么办", domain="合同法", limit=3)
        print(f"找到 {result.total} 条结果")
        for item in result.items:
            print(f"- {item.title} (来源: {item.source})")
            print(f"  {item.content[:80]}...")
            print()

        # 测试2：意图识别
        print()
        print("=" * 80)
        print("测试2：意图识别 - 劳动争议")
        print("=" * 80)
        result = await service.search("公司不给我发工资", limit=3)
        print(f"搜索意图: {result.search_intent.optimized_query}")
        print(f"目标领域: {result.search_intent.target_domains}")
        print(f"找到 {result.total} 条结果")
        for item in result.items:
            print(f"- {item.title} (来源: {item.source})")
            print()

        # 测试3：健康检查
        print()
        print("=" * 80)
        print("测试3：健康检查")
        print("=" * 80)
        health = await service.health_check()
        print(f"知识库总数: {health['total_stores']}")
        print(f"可用知识库: {health['available_stores']}")
        for store in health["stores"]:
            status = "✓" if store["available"] else "✗"
            print(f"  {status} {store['name']} (优先级: {store['priority']})")

    asyncio.run(test_unified_service())
