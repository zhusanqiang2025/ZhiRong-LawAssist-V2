# backend/app/api/v1/endpoints/search.py
"""
全局搜索API端点
支持搜索功能模块、历史任务、法律知识
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.task import Task
from app.models.contract_knowledge import ContractKnowledgeType
from app.crud import task as crud_task

router = APIRouter()


# ==================== 数据模型 ====================

class SearchResultItem(BaseModel):
    """搜索结果项"""
    id: str
    type: str  # 'module', 'task', 'legal'
    title: str
    description: str
    category: Optional[str] = None
    url: Optional[str] = None


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str
    total: int
    results: List[SearchResultItem]
    facets: Dict[str, int]  # 各类型结果数量


# ==================== 功能模块索引（硬编码） ====================

MODULES_INDEX = [
    {
        "id": "consultation",
        "type": "module",
        "title": "智能咨询",
        "description": "资深律师为您提供专业的法律咨询服务",
        "keywords": ["咨询", "问答", "律师", "专业咨询", "法律咨询"],
        "category": "咨询类",
        "url": "/consultation"
    },
    {
        "id": "risk-analysis",
        "type": "module",
        "title": "风险评估",
        "description": "深度分析法律文件，识别潜在风险点",
        "keywords": ["风险", "评估", "分析", "审查", "风险分析"],
        "category": "咨询类",
        "url": "/risk-analysis"
    },
    {
        "id": "contract-generation",
        "type": "module",
        "title": "合同生成",
        "description": "智能生成各类法律合同文件",
        "keywords": ["合同", "生成", "起草", "撰写", "合同生成"],
        "category": "文书类",
        "url": "/contract-generation"
    },
    {
        "id": "contract-review",
        "type": "module",
        "title": "合同审查",
        "description": "专业审查合同条款，提供修改建议",
        "keywords": ["审查", "合同", "条款", "修改", "合同审查"],
        "category": "文书类",
        "url": "/contract-review"
    },
    {
        "id": "smart-chat",
        "type": "module",
        "title": "智能对话",
        "description": "AI助手在线解答法律问题",
        "keywords": ["对话", "聊天", "问答", "AI", "智能对话"],
        "category": "咨询类",
        "url": "/smart-chat"
    },
    {
        "id": "guidance",
        "type": "module",
        "title": "智能引导",
        "description": "智能分析需求，推荐最佳解决方案",
        "keywords": ["引导", "推荐", "方案", "智能引导"],
        "category": "咨询类",
        "url": "/guidance"
    },
    {
        "id": "case-analysis",
        "type": "module",
        "title": "案件分析",
        "description": "分析案件情况，评估胜诉可能性",
        "keywords": ["案件", "分析", "诉讼", "胜诉", "案件分析"],
        "category": "诉讼类",
        "url": "/case-analysis"
    },
    {
        "id": "cost-calculation",
        "type": "module",
        "title": "费用计算",
        "description": "计算诉讼费用、律师费等",
        "keywords": ["费用", "计算", "成本", "报价", "费用计算"],
        "category": "工具类",
        "url": "/cost-calculation"
    },
    {
        "id": "template-library",
        "type": "module",
        "title": "模板库",
        "description": "海量法律文书模板",
        "keywords": ["模板", "库", "文档", "范本", "模板库"],
        "category": "资源类",
        "url": "/templates"
    },
]


# ==================== 搜索端点 ====================

@router.get("/global", response_model=SearchResponse)
def global_search(
    query: str = Query(..., min_length=1, description="搜索关键词"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    types: Optional[str] = Query(None, description="结果类型过滤，逗号分隔：module,task,legal")
) -> SearchResponse:
    """
    全局搜索接口

    搜索范围：功能模块、历史任务、法律知识（合同知识图谱）

    Args:
        query: 搜索关键词
        db: 数据库会话
        current_user: 当前登录用户
        types: 可选的类型过滤（逗号分隔）

    Returns:
        搜索结果，包含分面统计
    """
    results = []
    facets = {"module": 0, "task": 0, "legal": 0}

    # 解析类型过滤
    type_filter = None
    if types:
        type_filter = set(t.strip() for t in types.split(','))

    # 1. 搜索功能模块
    if not type_filter or 'module' in type_filter:
        module_results = _search_modules(query)
        results.extend(module_results)
        facets["module"] = len(module_results)

    # 2. 搜索历史任务
    if not type_filter or 'task' in type_filter:
        task_results = _search_tasks(query, db, current_user)
        results.extend(task_results)
        facets["task"] = len(task_results)

    # 3. 搜索法律知识（合同知识图谱）
    if not type_filter or 'legal' in type_filter:
        legal_results = _search_legal_articles(query, db)
        results.extend(legal_results)
        facets["legal"] = len(legal_results)

    return SearchResponse(
        query=query,
        total=len(results),
        results=results,
        facets=facets
    )


# ==================== 搜索辅助函数 ====================

def _search_modules(query: str) -> List[SearchResultItem]:
    """搜索功能模块"""
    results = []
    query_lower = query.lower()

    for module in MODULES_INDEX:
        # 匹配标题、描述、关键词
        if (query_lower in module["title"].lower() or
            query_lower in module["description"].lower() or
            any(query_lower in kw.lower() for kw in module["keywords"])):
            results.append(SearchResultItem(
                id=module["id"],
                type=module["type"],
                title=module["title"],
                description=module["description"],
                category=module["category"],
                url=module["url"]
            ))

    return results


def _search_tasks(query: str, db: Session, user: User) -> List[SearchResultItem]:
    """搜索历史任务"""
    tasks = crud_task.task.get_tasks_by_owner(db, owner_id=user.id, skip=0, limit=50)
    results = []
    query_lower = query.lower()

    for task in tasks:
        # 匹配标题、用户需求
        title = task.doc_type or task.user_demand or "未命名任务"
        if (query_lower in title.lower() or
            (task.user_demand and query_lower in task.user_demand.lower())):
            results.append(SearchResultItem(
                id=str(task.id),
                type="task",
                title=_truncate_title(title, 30),
                description=task.user_demand or "无描述",
                url=f"/result/{task.id}",
                category="历史任务"
            ))

    return results[:10]  # 限制返回数量


def _search_legal_articles(query: str, db: Session) -> List[SearchResultItem]:
    """搜索法律知识（合同知识图谱）"""
    results = []
    query_lower = query.lower()

    # 搜索合同知识库
    knowledge_items = db.query(ContractKnowledgeType).filter(
        ContractKnowledgeType.is_active == True
    ).all()

    for item in knowledge_items:
        # 匹配合同名称、别名、类别
        name_match = query_lower in item.name.lower()
        alias_match = any(query_lower in alias.lower() for alias in (item.aliases or []))
        category_match = item.category and query_lower in item.category.lower()
        legal_basis_match = _search_in_legal_basis(query_lower, item.legal_basis)

        if name_match or alias_match or category_match or legal_basis_match:
            results.append(SearchResultItem(
                id=f"legal_{item.id}",
                type="legal",
                title=item.name,
                description=f"{item.category or ''} - {item.subcategory or ''}",
                url=f"/knowledge/{item.id}",
                category="法律知识"
            ))

    return results[:10]  # 限制返回数量


def _search_in_legal_basis(query: str, legal_basis: Optional[List]) -> bool:
    """在法律依据中搜索"""
    if not legal_basis:
        return False

    for basis in legal_basis:
        if isinstance(basis, dict) and "law_name" in basis:
            if query in basis["law_name"].lower():
                return True
        elif isinstance(basis, str) and query in basis.lower():
            return True

    return False


def _truncate_title(title: str, max_length: int) -> str:
    """截断标题"""
    if len(title) > max_length:
        return title[:max_length - 3] + "..."
    return title
