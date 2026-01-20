# backend/app/api/v1/endpoints/legal_features_management.py
"""
法律特征管理 API

提供分类-特征映射的管理和查询接口。
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.legal_features import (
    get_category_feature_library,
    CategoryFeatureMapping,
    V2Features,
    TransactionNature,
    ContractObject,
    Complexity,
    Stance
)

router = APIRouter(
    prefix="/legal-features",
    tags=["Legal Features Management"]
)


# ==================== 请求/响应模型 ====================

class CategoryFeatureResponse(BaseModel):
    """分类-特征映射响应"""
    category: str
    subcategory: Optional[str]
    v2_features: dict
    primary_contract_type: str
    keywords: List[str]
    aliases: List[str]
    usage_scenario: str


class FeatureQueryRequest(BaseModel):
    """特征查询请求"""
    transaction_nature: Optional[str] = None
    contract_object: Optional[str] = None
    complexity: Optional[str] = None
    stance: Optional[str] = None


class CategoryRecommendationResponse(BaseModel):
    """分类推荐响应"""
    category: str
    subcategory: Optional[str]
    v2_features: dict
    confidence: float
    match_reason: str


# ==================== API 端点 ====================

@router.get("/mappings", response_model=List[CategoryFeatureResponse])
async def get_all_mappings():
    """
    获取所有分类-特征映射

    返回系统中配置的所有合同分类及其对应的V2法律特征。
    """
    library = get_category_feature_library()
    mappings = list(library._mappings.values())

    return [
        CategoryFeatureResponse(
            category=m.category,
            subcategory=m.subcategory,
            v2_features=m.v2_features.to_dict(),
            primary_contract_type=m.primary_contract_type,
            keywords=m.keywords,
            aliases=m.aliases,
            usage_scenario=m.usage_scenario
        )
        for m in mappings
    ]


@router.get("/mappings/{category}", response_model=CategoryFeatureResponse)
async def get_mapping_by_category(
    category: str,
    subcategory: Optional[str] = None
):
    """
    根据分类获取特征映射

    Args:
        category: 一级分类（如"买卖合同"）
        subcategory: 二级分类（如"设备买卖"，可选）
    """
    library = get_category_feature_library()
    mapping = library.get_mapping(category, subcategory)

    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"未找到分类映射: {category}{' > ' + subcategory if subcategory else ''}"
        )

    return CategoryFeatureResponse(
        category=mapping.category,
        subcategory=mapping.subcategory,
        v2_features=mapping.v2_features.to_dict(),
        primary_contract_type=mapping.primary_contract_type,
        keywords=mapping.keywords,
        aliases=mapping.aliases,
        usage_scenario=mapping.usage_scenario
    )


@router.get("/categories", response_model=List[str])
async def get_all_categories():
    """
    获取所有一级分类

    返回系统中配置的所有合同一级分类列表。
    """
    library = get_category_feature_library()
    return library.get_all_categories()


@router.get("/categories/{category}/subcategories", response_model=List[str])
async def get_subcategories(category: str):
    """
    获取指定分类的所有子分类

    Args:
        category: 一级分类名称
    """
    library = get_category_feature_library()
    subcategories = library.get_subcategories(category)

    if not subcategories:
        raise HTTPException(
            status_code=404,
            detail=f"分类 '{category}' 没有子分类"
        )

    return subcategories


@router.post("/search-by-keywords", response_model=List[CategoryFeatureResponse])
async def search_by_keywords(query: str):
    """
    根据关键词搜索分类

    当用户输入"房屋买卖"时，系统会匹配到"房屋买卖"子分类。

    Args:
        query: 查询关键词
    """
    library = get_category_feature_library()
    mappings = library.search_by_keywords(query)

    return [
        CategoryFeatureResponse(
            category=m.category,
            subcategory=m.subcategory,
            v2_features=m.v2_features.to_dict(),
            primary_contract_type=m.primary_contract_type,
            keywords=m.keywords,
            aliases=m.aliases,
            usage_scenario=m.usage_scenario
        )
        for m in mappings[:5]  # 返回前5个结果
    ]


@router.post("/search-by-features", response_model=List[CategoryFeatureResponse])
async def search_by_features(request: FeatureQueryRequest):
    """
    根据V2特征反向搜索分类

    当通过LLM提取到用户需求的V2特征后，可以使用此接口反向推荐合适的分类。

    例如：
    - 交易性质="转移所有权" + 标的="不动产" → 推荐"房屋买卖"
    - 交易性质="提供服务" + 标的="工程" → 推荐"工程施工"
    """
    library = get_category_feature_library()
    mappings = library.search_by_features(
        transaction_nature=request.transaction_nature,
        contract_object=request.contract_object,
        complexity=request.complexity,
        stance=request.stance
    )

    return [
        CategoryFeatureResponse(
            category=m.category,
            subcategory=m.subcategory,
            v2_features=m.v2_features.to_dict(),
            primary_contract_type=m.primary_contract_type,
            keywords=m.keywords,
            aliases=m.aliases,
            usage_scenario=m.usage_scenario
        )
        for m in mappings[:5]
    ]


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "legal-features",
        "version": "1.0.0"
    }
