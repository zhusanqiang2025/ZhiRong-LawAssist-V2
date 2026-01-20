# backend/app/services/legal_features/hybrid_template_retriever.py
"""
混合模板检索服务

结合分类映射和RAG向量检索，提供更精准的模板推荐。

检索策略：
1. 分类检索（快速）：通过用户输入关键词，匹配分类-特征映射库
2. 特征检索（精准）：通过 RequirementAnalyzer 分析特征，反向匹配分类
3. 向量检索（语义）：使用RAG向量检索，匹配模板内容

三种方式结果融合，返回最优推荐。
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from app.services.contract_generation.rag.template_retriever import (
    TemplateRetriever,
    RetrievedTemplate,
    TemplateSearchResult
)
from app.services.legal_features.category_feature_mapping import (
    CategoryFeatureLibrary,
    CategoryFeatureMapping,
    V2Features,
    get_category_feature_library
)
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """混合检索结果"""
    # 检索到的模板列表
    templates: List[RetrievedTemplate]

    # 推荐的分类（用于前端展示）
    recommended_category: Optional[str] = None
    recommended_subcategory: Optional[str] = None

    # 匹配到的特征（用于前端展示）
    matched_features: Optional[Dict] = None

    # 检索来源统计
    category_score: float = 0.0  # 分类匹配分数
    feature_score: float = 0.0  # 特征匹配分数
    vector_score: float = 0.0  # 向量匹配分数

    # 匹配原因（向用户解释）
    match_explanation: str = ""

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "templates": [t.to_dict() for t in self.templates],
            "recommended_category": self.recommended_category,
            "recommended_subcategory": self.recommended_subcategory,
            "matched_features": self.matched_features,
            "scores": {
                "category": self.category_score,
                "feature": self.feature_score,
                "vector": self.vector_score
            },
            "match_explanation": self.match_explanation
        }


class HybridTemplateRetriever:
    """
    混合模板检索器

    整合三种检索方式：
    1. 分类关键词检索（快速定位）
    2. RequirementAnalyzer 特征分析（精准匹配）
    3. RAG向量语义检索（内容匹配）

    综合三种结果，返回最优推荐。
    """

    def __init__(
        self,
        vector_retriever: Optional[TemplateRetriever] = None,
        llm: Optional[ChatOpenAI] = None
    ):
        """
        初始化混合检索器

        Args:
            vector_retriever: 向量检索器（RAG）
            llm: 用于特征分析的 LLM 实例
        """
        self.vector_retriever = vector_retriever or TemplateRetriever()
        self.llm = llm
        self._requirement_analyzer = None
        self.category_library = get_category_feature_library()

        logger.info("[HybridTemplateRetriever] 初始化完成")

    def _get_requirement_analyzer(self):
        """获取 RequirementAnalyzer 实例（延迟初始化）"""
        if self._requirement_analyzer is None and self.llm:
            from app.services.contract_generation.agents.requirement_analyzer import RequirementAnalyzer
            self._requirement_analyzer = RequirementAnalyzer(self.llm)
        return self._requirement_analyzer

    def retrieve(
        self,
        user_query: str,
        user_id: Optional[int] = None,
        top_k: int = 5,
        enable_feature_extraction: bool = True
    ) -> HybridSearchResult:
        """
        混合检索：综合三种检索方式

        Args:
            user_query: 用户查询
            user_id: 用户ID
            top_k: 返回结果数量
            enable_feature_extraction: 是否启用特征提取（较慢）

        Returns:
            HybridSearchResult: 混合检索结果
        """
        logger.info(f"[HybridTemplateRetriever] 开始混合检索: '{user_query}'")

        # ========== 第一步：分类关键词检索（快速） ==========
        category_mappings = self._category_search(user_query)
        category_score = len(category_mappings) > 0

        logger.info(f"[HybridTemplateRetriever] 分类检索找到 {len(category_mappings)} 个匹配")

        # ========== 第二步：特征提取与反向检索（精准） ==========
        feature_mappings = []
        matched_features = None

        if enable_feature_extraction:
            analyzer = self._get_requirement_analyzer()
            if analyzer:
                try:
                    # 使用 RequirementAnalyzer 分析
                    analysis_result = analyzer.analyze(user_query)

                    # 提取法律特征
                    legal_features = analysis_result.get("legal_features", {})

                    if legal_features:
                        # 转换为 V2 特征格式
                        matched_features = {
                            "transaction_nature": legal_features.get("transaction_nature", "service_delivery"),
                            "contract_object": legal_features.get("contract_object", "ip"),
                            "complexity": "standard_commercial",  # 默认中等复杂度
                            "stance": legal_features.get("stance", "neutral"),
                        }

                        # 使用提取的特征反向搜索分类
                        feature_mappings = self._feature_search(matched_features)

                        logger.info(f"[HybridTemplateRetriever] 特征检索找到 {len(feature_mappings)} 个匹配")
                        logger.info(f"[HybridTemplateRetriever] 提取的特征: {matched_features}")

                except Exception as e:
                    logger.error(f"[HybridTemplateRetriever] 特征提取失败: {e}")

        feature_score = len(feature_mappings) > 0

        # ========== 第三步：RAG向量语义检索（兜底） ==========
        # 如果前两步都没有结果，或者需要更多候选，使用向量检索
        use_vector_search = (
            len(category_mappings) == 0 or
            len(feature_mappings) == 0 or
            top_k > max(len(category_mappings), len(feature_mappings))
        )

        vector_result = None
        if use_vector_search:
            # 构建category过滤器
            category_filter = None
            if category_mappings:
                category_filter = category_mappings[0].category

            vector_result = self.vector_retriever.retrieve(
                query=user_query,
                user_id=user_id,
                category=category_filter,
                top_k=top_k,
                use_rerank=True
            )

            logger.info(f"[HybridTemplateRetriever] 向量检索找到 {len(vector_result.templates)} 个模板")

        vector_score = len(vector_result.templates) > 0 if vector_result else 0

        # ========== 第四步：结果融合 ==========
        final_result = self._merge_results(
            category_mappings=category_mappings,
            feature_mappings=feature_mappings,
            vector_result=vector_result,
            user_id=user_id,
            top_k=top_k
        )

        # ========== 第五步：生成推荐信息 ==========
        self._populate_recommendation(
            result=final_result,
            category_mappings=category_mappings,
            feature_mappings=feature_mappings,
            matched_features=matched_features
        )

        # 设置分数
        final_result.category_score = float(category_score)
        final_result.feature_score = float(feature_score)
        final_result.vector_score = float(vector_score)

        logger.info(f"[HybridTemplateRetriever] 检索完成，返回 {len(final_result.templates)} 个模板")

        return final_result

    def _category_search(self, query: str) -> List[CategoryFeatureMapping]:
        """分类关键词搜索"""
        return self.category_library.search_by_keywords(query)

    def _feature_search(self, features: Dict) -> List[CategoryFeatureMapping]:
        """V2特征反向搜索"""
        return self.category_library.search_by_features(
            transaction_nature=features.get("transaction_nature"),
            contract_object=features.get("contract_object"),
            complexity=features.get("complexity"),
            stance=features.get("stance")
        )

    def _merge_results(
        self,
        category_mappings: List[CategoryFeatureMapping],
        feature_mappings: List[CategoryFeatureMapping],
        vector_result: Optional[TemplateSearchResult],
        user_id: Optional[int],
        top_k: int
    ) -> HybridSearchResult:
        """
        融合三种检索结果

        优先级：特征匹配 > 分类匹配 > 向量相似度
        """
        template_scores = {}  # {template_id: (template, score)}

        # 1. 特征匹配的模板（最高优先级）
        for mapping in feature_mappings:
            # TODO: 从数据库获取该分类下的实际模板
            # 这里简化处理，给该分类加分
            pass

        # 2. 分类匹配的模板（次优先级）
        for mapping in category_mappings:
            # TODO: 从数据库获取该分类下的实际模板
            pass

        # 3. 向量检索的模板（兜底）
        if vector_result:
            for template in vector_result.templates:
                if template.id not in template_scores:
                    # 基础分数：向量相似度 * 0.3
                    base_score = template.final_score * 0.3

                    # 如果匹配分类，额外加分
                    for mapping in category_mappings:
                        if template.category == mapping.category:
                            base_score += 0.5
                            break

                    template_scores[template.id] = (template, base_score)

        # 排序并取Top-K
        sorted_templates = sorted(
            template_scores.values(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        final_templates = [t for t, s in sorted_templates]

        return HybridSearchResult(templates=final_templates)

    def _populate_recommendation(
        self,
        result: HybridSearchResult,
        category_mappings: List[CategoryFeatureMapping],
        feature_mappings: List[CategoryFeatureMapping],
        matched_features: Optional[Dict]
    ):
        """填充推荐信息和解释"""

        # 推荐分类（优先使用特征匹配的分类）
        if feature_mappings:
            result.recommended_category = feature_mappings[0].category
            result.recommended_subcategory = feature_mappings[0].subcategory
        elif category_mappings:
            result.recommended_category = category_mappings[0].category
            result.recommended_subcategory = category_mappings[0].subcategory

        # 生成匹配解释
        explanations = []

        if feature_mappings:
            mapping = feature_mappings[0]
            explanations.append(f"根据法律特征分析，推荐使用【{mapping.category}】")
            if matched_features:
                explanations.append(
                    f"识别特征：{matched_features.get('transaction_nature', '')} / "
                    f"{matched_features.get('contract_object', '')}"
                )

        if category_mappings:
            mapping = category_mappings[0]
            explanations.append(f"关键词匹配【{mapping.category}】")

        if result.templates:
            top_template = result.templates[0]
            if top_template.match_reason:
                explanations.append(f"匹配模板：{top_template.match_reason}")

        result.match_explanation = "；".join(explanations)


# ==================== 单例模式 ====================

_hybrid_retriever_instance: Optional[HybridTemplateRetriever] = None


def get_hybrid_retriever() -> HybridTemplateRetriever:
    """获取混合检索器单例"""
    global _hybrid_retriever_instance
    if _hybrid_retriever_instance is None:
        _hybrid_retriever_instance = HybridTemplateRetriever()
    return _hybrid_retriever_instance
