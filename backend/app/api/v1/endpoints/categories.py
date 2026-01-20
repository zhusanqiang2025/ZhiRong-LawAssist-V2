# backend/app/api/v1/endpoints/categories.py
"""
合同分类管理 API (V3 动态版)

功能：
1. 提供分类树形结构，支持无限层级。
2. 动态统计每个分类下的模板数量（用于覆盖率仪表盘）。
3. 支持管理员对分类进行增删改查。
"""
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel

from app.database import get_db
from app.models.category import Category
from app.models.contract_template import ContractTemplate
from app.models.user import User
from app.api.deps import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== Pydantic Schemas ====================

class CategoryBase(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True
    meta_info: Optional[Dict[str, Any]] = {}

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    meta_info: Optional[Dict[str, Any]] = None

class CategoryTreeItem(CategoryBase):
    id: int
    template_count: int = 0  # 核心字段：该分类下的模板数量
    children: List['CategoryTreeItem'] = []

    class Config:
        from_attributes = True

# ==================== 辅助函数 ====================

def get_template_counts(db: Session) -> Dict[str, int]:
    """
    聚合查询：统计每个分类名称对应的模板数量
    逻辑：
    1. 统计 primary_contract_type (对应二级分类)
    2. 统计 subcategory (对应三级分类)
    3. 统计 category (对应一级分类，兼容旧数据)
    """
    stats = {}

    # 1. 统计 primary_contract_type (主要匹配二级分类)
    q1 = db.query(
        ContractTemplate.primary_contract_type, 
        func.count(ContractTemplate.id)
    ).filter(
        ContractTemplate.status == 'active'
    ).group_by(ContractTemplate.primary_contract_type).all()

    for name, count in q1:
        if name:
            stats[name] = stats.get(name, 0) + count

    # 2. 统计 subcategory (主要匹配三级分类)
    q2 = db.query(
        ContractTemplate.subcategory, 
        func.count(ContractTemplate.id)
    ).filter(
        ContractTemplate.status == 'active'
    ).group_by(ContractTemplate.subcategory).all()

    for name, count in q2:
        if name:
            stats[name] = stats.get(name, 0) + count
            
    # 3. 统计 category (兼容旧数据/一级分类)
    q3 = db.query(
        ContractTemplate.category, 
        func.count(ContractTemplate.id)
    ).filter(
        ContractTemplate.status == 'active'
    ).group_by(ContractTemplate.category).all()
    
    for name, count in q3:
        if name:
            # 避免重复累计 (如果 category 和 primary_type 一样)
            if name not in stats:
                stats[name] = count

    return stats

# ==================== API Endpoints ====================

@router.get("/", response_model=Dict[str, Any])
async def get_primary_contract_types(db: Session = Depends(get_db)):
    """
    获取13种标准合同类型列表（向后兼容）

    用于管理员后台的"合同分类配置"页面
    """
    # 13种标准合同类型（硬编码，符合民法典合同编）
    PRIMARY_CONTRACT_TYPES = [
        {"name": "买卖合同", "value": "买卖合同"},
        {"name": "建设工程合同", "value": "建设工程合同"},
        {"name": "承揽合同", "value": "承揽合同"},
        {"name": "租赁合同", "value": "租赁合同"},
        {"name": "融资租赁合同", "value": "融资租赁合同"},
        {"name": "保理合同", "value": "保理合同"},
        {"name": "供用电、水、气、热力合同", "value": "供用电、水、气、热力合同"},
        {"name": "赠与合同", "value": "赠与合同"},
        {"name": "借款合同", "value": "借款合同"},
        {"name": "保证合同", "value": "保证合同"},
        {"name": "租赁合同", "value": "租赁合同"},
        {"name": "运输合同", "value": "运输合同"},
        {"name": "技术合同", "value": "技术合同"},
    ]

    # 统计每种类型的模板数量
    stats = {}
    for pt in PRIMARY_CONTRACT_TYPES:
        count = db.query(ContractTemplate).filter(
            ContractTemplate.primary_contract_type == pt["value"],
            ContractTemplate.status == 'active'
        ).count()
        stats[pt["value"]] = count

    return {
        "categories": PRIMARY_CONTRACT_TYPES,
        "total": len(PRIMARY_CONTRACT_TYPES),
        "stats": stats
    }


@router.get("/tree", response_model=List[CategoryTreeItem])
async def get_category_tree(
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """
    获取分类树（带模板统计）
    
    用于：
    1. 用户端的侧边栏菜单
    2. 管理员端的分类管理页面
    3. 管理员端的合同覆盖率索引
    """
    # 1. 获取所有分类
    query = db.query(Category)
    if not include_inactive:
        query = query.filter(Category.is_active == True)
    
    all_categories = query.order_by(Category.sort_order).all()
    
    # 2. 获取统计数据
    stats_map = get_template_counts(db)

    # 3. 递归构建树
    def build_tree(parent_id):
        nodes = [c for c in all_categories if c.parent_id == parent_id]
        tree = []
        for node in nodes:
            children = build_tree(node.id)
            
            # 计算当前节点的模板数
            # 逻辑：自身名字匹配数 + 子节点总数
            # 例如："买卖合同"的数 = 自己名下的模板 + 子类(动产买卖)的模板
            own_count = stats_map.get(node.name, 0)
            
            # 简单的去重逻辑：如果子节点的模板也被归类到了父节点，不重复加
            # 但在这里，为了展示覆盖率，我们采用"累加"逻辑，让父级显示总盘子
            child_total = sum(c.template_count for c in children)
            
            # 如果是叶子节点，就看 own_count
            # 如果是父节点，且 own_count 很小（说明模板都挂在子类上了），就用 child_total
            total_count = max(own_count, child_total)
            
            # 构造 Pydantic 模型
            item = CategoryTreeItem(
                id=node.id,
                name=node.name,
                code=node.code,
                description=node.description,
                parent_id=node.parent_id,
                sort_order=node.sort_order,
                is_active=node.is_active,
                meta_info=node.meta_info,
                template_count=total_count,
                children=children
            )
            tree.append(item)
        return tree

    return build_tree(None)


@router.post("/", response_model=CategoryTreeItem)
async def create_category(
    category_in: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    新增分类 (仅管理员)
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")

    # 检查重名
    existing = db.query(Category).filter(
        Category.name == category_in.name,
        Category.parent_id == category_in.parent_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="同级分类下已存在该名称")

    new_category = Category(
        name=category_in.name,
        code=category_in.code,
        description=category_in.description,
        parent_id=category_in.parent_id,
        sort_order=category_in.sort_order,
        is_active=category_in.is_active,
        meta_info=category_in.meta_info
    )
    
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    
    # 转换响应格式 (空children)
    return CategoryTreeItem(
        id=new_category.id,
        name=new_category.name,
        code=new_category.code,
        description=new_category.description,
        parent_id=new_category.parent_id,
        sort_order=new_category.sort_order,
        is_active=new_category.is_active,
        meta_info=new_category.meta_info,
        template_count=0,
        children=[]
    )


@router.put("/{category_id}", response_model=CategoryTreeItem)
async def update_category(
    category_id: int,
    category_in: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新分类 (仅管理员)
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    update_data = category_in.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    
    # 简单返回，不递归计算 children 和 count 以节省性能
    return CategoryTreeItem(
        id=category.id,
        name=category.name,
        code=category.code,
        description=category.description,
        parent_id=category.parent_id,
        sort_order=category.sort_order,
        is_active=category.is_active,
        meta_info=category.meta_info,
        template_count=0, # 更新时暂不重新计算
        children=[]
    )


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除分类 (仅管理员)
    注意：如果有子分类，也会被级联删除（Model中配置了cascade）
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    # 检查是否有子分类
    has_children = db.query(Category).filter(Category.parent_id == category_id).first()
    if has_children:
        raise HTTPException(status_code=400, detail="该分类下存在子分类，请先删除子分类")

    db.delete(category)
    db.commit()

    return {"message": "分类已删除"}