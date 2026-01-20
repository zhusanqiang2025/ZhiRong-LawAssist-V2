# backend/app/services/legal_features/__init__.py
"""
法律特征服务模块

提供合同分类与法律特征的映射、检索、推荐功能。
"""
from .category_feature_mapping import (
    CategoryFeatureLibrary,
    CategoryFeatureMapping,
    V2Features,
    TransactionNature,
    ContractObject,
    Complexity,
    Stance,
    get_category_feature_library
)

from .hybrid_template_retriever import (
    HybridTemplateRetriever,
    HybridSearchResult,
    get_hybrid_retriever
)

__all__ = [
    # 分类特征映射
    "CategoryFeatureLibrary",
    "CategoryFeatureMapping",
    "V2Features",
    "TransactionNature",
    "ContractObject",
    "Complexity",
    "Stance",
    "get_category_feature_library",

    # 混合检索
    "HybridTemplateRetriever",
    "HybridSearchResult",
    "get_hybrid_retriever",
]
