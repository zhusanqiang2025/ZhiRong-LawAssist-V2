# backend/app/api/v1/endpoints/contract_knowledge_graph_db.py
"""
合同法律特征知识图谱 API（数据库版本）

提供合同类型-法律特征的查询和管理接口。
数据存储在 PostgreSQL 数据库中，而非 JSON 文件。
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models.contract_knowledge import ContractKnowledgeType
from app.services.common.contract_knowledge_db_service import contract_knowledge_db_service

router = APIRouter(
    prefix="/knowledge-graph",
    tags=["Contract Knowledge Graph"]
)

logger = logging.getLogger(__name__)


# ==================== 请求/响应模型 ====================

class ContractTypeInfo(BaseModel):
    """合同类型信息"""
    name: str
    aliases: List[str]
    category: str
    subcategory: Optional[str] = None
    legal_features: dict
    recommended_template_ids: List[str]


class ContractTypeListResponse(BaseModel):
    """合同类型列表响应"""
    contract_types: List[ContractTypeInfo]
    total_count: int


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str


class CreateContractTypeRequest(BaseModel):
    """创建合同类型请求"""
    name: str
    aliases: List[str] = []
    category: str
    subcategory: Optional[str] = None
    legal_features: Dict[str, Any]
    recommended_template_ids: List[str] = []


class UpdateContractTypeRequest(BaseModel):
    """更新合同类型请求"""
    name: Optional[str] = None
    aliases: Optional[List[str]] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    legal_features: Optional[Dict[str, Any]] = None
    recommended_template_ids: Optional[List[str]] = None


# ==================== 查询接口 ====================

@router.get("/contract-types", response_model=ContractTypeListResponse)
async def get_all_contract_types():
    """
    获取所有合同类型及其法律特征

    返回系统中配置的所有合同类型，包括完整的法律特征定义。
    """
    try:
        definitions = contract_knowledge_db_service.get_all()

        return ContractTypeListResponse(
            contract_types=[
                ContractTypeInfo(
                    name=d["name"],
                    aliases=d["aliases"],
                    category=d["category"],
                    subcategory=d["subcategory"],
                    legal_features=d["legal_features"],
                    recommended_template_ids=d["recommended_template_ids"]
                )
                for d in definitions
            ],
            total_count=len(definitions)
        )
    except Exception as e:
        logger.error(f"获取合同类型列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取合同类型列表失败: {str(e)}")


@router.get("/contract-types/{contract_name}", response_model=ContractTypeInfo)
async def get_contract_type_by_name(contract_name: str):
    """
    根据合同名称获取法律特征

    Args:
        contract_name: 合同类型名称，如"不动产买卖合同"
    """
    definition = contract_knowledge_db_service.get_by_name(contract_name)

    if not definition:
        raise HTTPException(
            status_code=404,
            detail=f"未找到合同类型: {contract_name}"
        )

    return ContractTypeInfo(
        name=definition["name"],
        aliases=definition["aliases"],
        category=definition["category"],
        subcategory=definition["subcategory"],
        legal_features=definition["legal_features"],
        recommended_template_ids=definition["recommended_template_ids"]
    )


@router.post("/search-by-keywords", response_model=ContractTypeListResponse)
async def search_contract_types_by_keywords(request: SearchRequest):
    """
    根据关键词搜索合同类型

    当用户输入"房屋买卖"时，系统会匹配到"不动产买卖合同"并返回完整的法律特征。

    Args:
        request: 包含query字段的搜索请求
    """
    try:
        results = contract_knowledge_db_service.search_by_keywords(request.query)

        return ContractTypeListResponse(
            contract_types=[
                ContractTypeInfo(
                    name=d["name"],
                    aliases=d["aliases"],
                    category=d["category"],
                    subcategory=d["subcategory"],
                    legal_features=d["legal_features"],
                    recommended_template_ids=d["recommended_template_ids"]
                )
                for d in results
            ],
            total_count=len(results)
        )
    except Exception as e:
        logger.error(f"搜索合同类型失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/categories/{category}/contract-types", response_model=ContractTypeListResponse)
async def get_contract_types_by_category(
    category: str,
    subcategory: Optional[str] = None
):
    """
    根据分类获取合同类型

    Args:
        category: 一级分类，如"买卖合同"
        subcategory: 二级分类（可选），如"不动产买卖"
    """
    try:
        definitions = contract_knowledge_db_service.get_by_category(category, subcategory)

        if not definitions:
            raise HTTPException(
                status_code=404,
                detail=f"分类 '{category}'{' > ' + subcategory if subcategory else ''}' 下没有合同类型"
            )

        return ContractTypeListResponse(
            contract_types=[
                ContractTypeInfo(
                    name=d["name"],
                    aliases=d["aliases"],
                    category=d["category"],
                    subcategory=d["subcategory"],
                    legal_features=d["legal_features"],
                    recommended_template_ids=d["recommended_template_ids"]
                )
                for d in definitions
            ],
            total_count=len(definitions)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分类合同类型失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取分类合同类型失败: {str(e)}")


@router.get("/legal-features/{contract_name}")
async def get_legal_features_by_contract_name(contract_name: str):
    """
    根据合同名称获取法律特征（简化接口）

    当用户选择合同类型时，直接返回其法律特征，用于自动填充表单。

    Args:
        contract_name: 合同类型名称
    """
    definition = contract_knowledge_db_service.get_by_name(contract_name)

    if not definition or not definition.get("legal_features"):
        raise HTTPException(
            status_code=404,
            detail=f"未找到合同类型 '{contract_name}' 或其法律特征"
        )

    return definition["legal_features"]


@router.get("/health")
async def health_check():
    """健康检查"""
    count = contract_knowledge_db_service.count()
    return {
        "status": "healthy",
        "service": "contract-knowledge-graph",
        "version": "2.0.0",
        "storage": "database",
        "contract_types_count": count
    }


# ==================== 管理接口 ====================

@router.post("/admin/contract-types")
async def create_contract_type(
    request: CreateContractTypeRequest,
    db: Session = Depends(get_db)
):
    """
    创建新的合同类型定义（管理员）

    Args:
        request: 合同类型定义
    """
    try:
        # 检查是否已存在
        existing = db.query(ContractKnowledgeType).filter(
            ContractKnowledgeType.name == request.name
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"合同类型 '{request.name}' 已存在"
            )

        # 创建新记录
        features = request.legal_features
        knowledge_type = ContractKnowledgeType(
            name=request.name,
            aliases=request.aliases,
            category=request.category,
            subcategory=request.subcategory,

            # 法律特征
            transaction_nature=features.get("transaction_nature"),
            contract_object=features.get("contract_object"),
            stance=features.get("stance"),
            consideration_type=features.get("consideration_type"),
            consideration_detail=features.get("consideration_detail"),
            transaction_characteristics=features.get("transaction_characteristics"),
            usage_scenario=features.get("usage_scenario"),
            legal_basis=features.get("legal_basis", []),

            # 扩展字段
            recommended_template_ids=request.recommended_template_ids,

            # 状态
            is_active=True,
            is_system=False
        )

        db.add(knowledge_type)
        db.commit()
        db.refresh(knowledge_type)

        return {
            "message": "创建成功",
            "contract_type": knowledge_type.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建合同类型失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.put("/admin/contract-types/{contract_name}")
async def update_contract_type(
    contract_name: str,
    request: UpdateContractTypeRequest,
    db: Session = Depends(get_db)
):
    """
    更新合同类型定义（管理员）

    Args:
        contract_name: 原合同名称
        request: 更新数据
    """
    try:
        record = db.query(ContractKnowledgeType).filter(
            ContractKnowledgeType.name == contract_name
        ).first()

        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"未找到合同类型 '{contract_name}'"
            )

        # 更新字段
        if request.name is not None and request.name != contract_name:
            # 检查新名称是否已存在
            existing = db.query(ContractKnowledgeType).filter(
                ContractKnowledgeType.name == request.name
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"合同类型 '{request.name}' 已存在")
            record.name = request.name

        if request.aliases is not None:
            record.aliases = request.aliases
        if request.category is not None:
            record.category = request.category
        if request.subcategory is not None:
            record.subcategory = request.subcategory
        if request.recommended_template_ids is not None:
            record.recommended_template_ids = request.recommended_template_ids

        # 更新法律特征
        if request.legal_features is not None:
            features = request.legal_features
            record.transaction_nature = features.get("transaction_nature", record.transaction_nature)
            record.contract_object = features.get("contract_object", record.contract_object)
            record.stance = features.get("stance", record.stance)
            record.consideration_type = features.get("consideration_type", record.consideration_type)
            record.consideration_detail = features.get("consideration_detail", record.consideration_detail)
            record.transaction_characteristics = features.get("transaction_characteristics", record.transaction_characteristics)
            record.usage_scenario = features.get("usage_scenario", record.usage_scenario)
            record.legal_basis = features.get("legal_basis", record.legal_basis)

        db.commit()
        db.refresh(record)

        return {
            "message": "更新成功",
            "contract_type": record.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新合同类型失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/admin/contract-types/{contract_name}")
async def delete_contract_type(
    contract_name: str,
    db: Session = Depends(get_db)
):
    """
    删除合同类型定义（管理员）

    Args:
        contract_name: 合同类型名称
    """
    try:
        record = db.query(ContractKnowledgeType).filter(
            ContractKnowledgeType.name == contract_name
        ).first()

        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"未找到合同类型 '{contract_name}'"
            )

        db.delete(record)
        db.commit()

        return {
            "message": "删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除合同类型失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/admin/export")
async def export_knowledge_graph(db: Session = Depends(get_db)):
    """
    导出知识图谱数据（用于备份）

    Returns:
        JSON 格式的知识图谱数据
    """
    try:
        records = db.query(ContractKnowledgeType).filter(
            ContractKnowledgeType.is_active == True
        ).all()

        export_data = {
            "contract_types": [r.to_dict() for r in records],
            "total_count": len(records),
            "exported_at": None
        }

        return export_data
    except Exception as e:
        logger.error(f"导出知识图谱失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
