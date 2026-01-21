# backend/app/api/v1/endpoints/admin.py
"""
管理员相关 API 端点

提供系统统计、用户管理、JSON 审查规则管理等功能
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List

from app.database import get_db
from app.models.user import User
from app.models.task import Task
from app.models.contract_template import ContractTemplate
from app.models.rule import ReviewRule  # ✅ 从 contract.py 移动到独立的 rule.py
from app.schemas import (
    RuleCreate,
    RuleUpdate,
    UniversalRulesOut,
    FeatureRuleOut,
    StanceRuleOut
)
from app.api.deps import get_current_user
from app.services.review_rules_service import review_rules_service
from datetime import datetime, timedelta
from app.api.websocket import manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 系统统计 API ====================

@router.get("/stats")
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取系统统计信息 - 增强版
    包含用户统计、任务统计、模板统计和趋势数据
    仅管理员可访问
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    # 用户统计
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.is_admin == True).count()

    # 任务统计
    total_tasks = db.query(Task).count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    in_progress_tasks = db.query(Task).filter(Task.status == "processing").count()
    completed_tasks = db.query(Task).filter(Task.status == "completed").count()
    failed_tasks = db.query(Task).filter(Task.status == "failed").count()

    # 今日任务统计
    today = datetime.now().date()
    tasks_created_today = db.query(Task).filter(
        func.date(Task.created_at) == today
    ).count()

    # 任务类型分布
    task_types = db.query(Task.task_type, func.count(Task.id)).group_by(Task.task_type).all()
    task_type_distribution = {ttype: count for ttype, count in task_types if ttype}

    # 实时在线用户（通过 WebSocket manager）
    online_users = manager.get_connection_count()

    # 模板统计
    total_templates = db.query(ContractTemplate).filter(
        ContractTemplate.status == "active"
    ).count()
    total_downloads = db.query(func.sum(ContractTemplate.download_count)).scalar() or 0

    # 最近7天任务趋势数据
    trend_data = []
    for i in range(6, -1, -1):
        target_date = datetime.now().date() - timedelta(days=i)
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date, datetime.max.time())
        count = db.query(Task).filter(
            Task.created_at >= day_start,
            Task.created_at <= day_end
        ).count()
        trend_data.append({"date": target_date.isoformat(), "count": count})

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "admins": admin_users,
            "online": online_users
        },
        "tasks": {
            "total": total_tasks,
            "pending": pending_tasks,
            "in_progress": in_progress_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
            "created_today": tasks_created_today,
            "by_type": task_type_distribution,
            "trend_7days": trend_data
        },
        "templates": {
            "total": total_templates,
            "total_downloads": total_downloads
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/users")
async def get_user_list(
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户列表

    仅管理员可访问
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    # 查询用户总数
    total_count = db.query(User).count()

    # 分页查询用户
    users = db.query(User).offset((page - 1) * size).limit(size).all()

    # 构造返回数据
    user_list = []
    for user in users:
        # 统计每个用户的模板数量
        template_count = db.query(ContractTemplate).filter(
            ContractTemplate.owner_id == user.id
        ).count()

        user_list.append({
            "id": user.id,
            "email": user.email,
            "is_admin": user.is_admin,
            "template_count": template_count,
            "task_count": 0,  # 如果有任务表的话可以统计
            "download_count": 0,  # 简化版
            "last_active": None,  # User模型暂无此字段
            "created_at": None  # User模型暂无此字段
        })

    return {
        "items": user_list,
        "total": total_count,
        "page": page,
        "size": size
    }


# ==================== JSON 审查规则管理 API ====================

@router.get("/rules/config")
async def get_rules_config(
    current_user: User = Depends(get_current_user)
):
    """
    获取完整的规则配置

    所有用户可查看
    """
    rules = review_rules_service.get_all_rules()
    return {
        "version": rules.get("version"),
        "description": rules.get("description"),
        "_comment": rules.get("_comment", "")
    }


@router.get("/rules/universal", response_model=UniversalRulesOut)
async def get_universal_rules(
    current_user: User = Depends(get_current_user)
):
    """
    获取通用基础规则

    所有用户可查看
    """
    return review_rules_service.get_universal_rules()


@router.get("/rules/feature", response_model=List[FeatureRuleOut])
async def get_feature_rules(
    feature_type: Optional[str] = None,
    feature_value: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    获取特征规则

    参数:
    - feature_type: 特征类型（交易性质/合同标的）
    - feature_value: 特征值（如：转移所有权/不动产）

    所有用户可查看
    """
    return review_rules_service.get_feature_rules(feature_type, feature_value)


@router.get("/rules/stance", response_model=List[StanceRuleOut])
async def get_stance_rules(
    party: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    获取立场规则

    参数:
    - party: 立场（party_a/party_b）

    所有用户可查看
    """
    return review_rules_service.get_stance_rules(party)


@router.post("/rules/universal")
async def add_universal_rule(
    category: str,
    instruction: str,
    current_user: User = Depends(get_current_user)
):
    """
    添加通用规则

    参数:
    - category: 规则分类（如：形式质量、定义一致性、争议解决等）
    - instruction: 规则指令

    权限：仅管理员可添加系统通用规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可添加通用规则")

    rule_id = review_rules_service.add_universal_rule(category, instruction)
    return {
        "success": True,
        "rule_id": rule_id,
        "message": f"通用规则 {rule_id} 已添加"
    }


@router.post("/rules/feature")
async def add_feature_rule(
    feature_type: str,
    feature_value: str,
    focus: str,
    instruction: str,
    current_user: User = Depends(get_current_user)
):
    """
    添加特征规则

    参数:
    - feature_type: 特征类型（交易性质/合同标的）
    - feature_value: 特征值（如：转移所有权/不动产）
    - focus: 关注点
    - instruction: 规则指令

    权限：仅管理员可添加系统特征规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可添加特征规则")

    review_rules_service.add_feature_rule(feature_type, feature_value, focus, instruction)
    return {
        "success": True,
        "message": f"特征规则已添加到 {feature_type}-{feature_value}"
    }


@router.post("/rules/stance")
async def add_stance_rule(
    party: str,
    focus: str,
    instruction: str,
    current_user: User = Depends(get_current_user)
):
    """
    添加立场规则

    参数:
    - party: 立场（party_a/party_b）
    - focus: 关注点
    - instruction: 规则指令

    权限：仅管理员可添加系统立场规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可添加立场规则")

    review_rules_service.add_stance_rule(party, focus, instruction)
    return {
        "success": True,
        "message": f"立场规则已添加到 {party}"
    }


@router.put("/rules/universal/{rule_id}")
async def update_universal_rule(
    rule_id: str,
    category: Optional[str] = None,
    instruction: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    更新通用规则

    参数:
    - rule_id: 规则ID（如：U01）
    - category: 新的规则分类
    - instruction: 新的规则指令

    权限：仅管理员可修改系统规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可修改系统规则")

    try:
        review_rules_service.update_universal_rule(rule_id, category, instruction)
        return {
            "success": True,
            "message": f"通用规则 {rule_id} 已更新"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/rules/feature")
async def update_feature_rule(
    feature_type: str,
    feature_value: str,
    index: int,
    focus: Optional[str] = None,
    instruction: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    更新特征规则

    参数:
    - feature_type: 特征类型
    - feature_value: 特征值
    - index: 规则索引（从0开始）
    - focus: 新的关注点
    - instruction: 新的规则指令

    权限：仅管理员可修改系统规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可修改系统规则")

    try:
        review_rules_service.update_feature_rule(feature_type, feature_value, index, focus, instruction)
        return {
            "success": True,
            "message": f"特征规则已更新"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/rules/stance")
async def update_stance_rule(
    party: str,
    index: int,
    focus: Optional[str] = None,
    instruction: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    更新立场规则

    参数:
    - party: 立场（party_a/party_b）
    - index: 规则索引（从0开始）
    - focus: 新的关注点
    - instruction: 新的规则指令

    权限：仅管理员可修改系统规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可修改系统规则")

    try:
        review_rules_service.update_stance_rule(party, index, focus, instruction)
        return {
            "success": True,
            "message": f"立场规则已更新"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/rules/universal/{rule_id}")
async def delete_universal_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    删除通用规则

    参数:
    - rule_id: 规则ID（如：U01）

    权限：仅管理员可删除系统规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可删除系统规则")

    try:
        review_rules_service.delete_universal_rule(rule_id)
        return {
            "success": True,
            "message": f"通用规则 {rule_id} 已删除"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/rules/feature")
async def delete_feature_rule(
    feature_type: str,
    feature_value: str,
    index: int,
    current_user: User = Depends(get_current_user)
):
    """
    删除特征规则

    参数:
    - feature_type: 特征类型
    - feature_value: 特征值
    - index: 规则索引（从0开始）

    权限：仅管理员可删除系统规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可删除系统规则")

    try:
        review_rules_service.delete_feature_rule(feature_type, feature_value, index)
        return {
            "success": True,
            "message": f"特征规则已删除"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/rules/stance")
async def delete_stance_rule(
    party: str,
    index: int,
    current_user: User = Depends(get_current_user)
):
    """
    删除立场规则

    参数:
    - party: 立场（party_a/party_b）
    - index: 规则索引（从0开始）

    权限：仅管理员可删除系统规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可删除系统规则")

    try:
        review_rules_service.delete_stance_rule(party, index)
        return {
            "success": True,
            "message": f"立场规则已删除"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/rules/reload")
async def reload_rules(
    current_user: User = Depends(get_current_user)
):
    """
    重新加载规则文件

    权限：仅管理员可执行
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    # 重新加载规则文件
    rules = review_rules_service.get_all_rules()
    return {
        "success": True,
        "message": "规则文件已重新加载",
        "version": rules.get("version"),
        "description": rules.get("description")
    }


@router.post("/rules/migrate-from-json")
async def migrate_json_rules_to_db(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    将 JSON 规则文件迁移到数据库

    权限：仅管理员可执行
    会清除现有的系统规则，然后从 JSON 文件导入新的规则
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    import json
    import os
    from datetime import datetime

    # 加载 JSON 规则文件
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rule_file_path = os.path.join(current_dir, "config", "review_rules.json")

    if not os.path.exists(rule_file_path):
        raise HTTPException(status_code=404, detail=f"规则文件不存在: {rule_file_path}")

    try:
        with open(rule_file_path, 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取规则文件失败: {str(e)}")

    # 清除现有系统规则
    existing_count = db.query(ReviewRule).filter(ReviewRule.is_system == True).count()
    if existing_count > 0:
        db.query(ReviewRule).filter(ReviewRule.is_system == True).delete()
        db.commit()

    created_count = 0

    # 迁移通用规则
    universal_rules = rules_data.get("universal_rules", {}).get("rules", [])
    for rule in universal_rules:
        existing = db.query(ReviewRule).filter(
            ReviewRule.name == f"[通用] {rule['id']}"
        ).first()

        if not existing:
            new_rule = ReviewRule(
                name=f"[通用] {rule['id']}",
                description=f"{rule['category']} - {rules_data['universal_rules']['description']}",
                content=rule['instruction'],
                rule_category="universal",
                priority=10 + int(rule['id'][1:]),
                is_system=True,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(new_rule)
            created_count += 1

    # 迁移特征规则
    feature_rules = rules_data.get("feature_rules", {})
    priority = 100
    for feature_type, feature_values in feature_rules.items():
        if feature_type == "description":
            continue
        for feature_value, rules in feature_values.items():
            for rule in rules:
                rule_name = f"[{feature_type}] {feature_value} - {rule['focus']}"
                existing = db.query(ReviewRule).filter(ReviewRule.name == rule_name).first()
                if not existing:
                    content = f"**{feature_type}**: {feature_value}\n**关注点**: {rule['focus']}\n**审查指令**: {rule['instruction']}"
                    new_rule = ReviewRule(
                        name=rule_name,
                        description=f"{feature_type}为'{feature_value}'时的{rule['focus']}审查要点",
                        content=content,
                        rule_category="feature",
                        priority=priority,
                        is_system=True,
                        is_active=True,
                        created_at=datetime.utcnow()
                    )
                    db.add(new_rule)
                    created_count += 1
                    priority += 1

    # 迁移立场规则
    stance_rules = rules_data.get("stance_rules", {})
    priority = 200
    for party, party_data in stance_rules.items():
        if party == "description":
            continue
        role_definition = party_data.get("role_definition", "")
        rules = party_data.get("rules", [])
        for rule in rules:
            rule_name = f"[立场-{party}] {rule['focus']}"
            existing = db.query(ReviewRule).filter(ReviewRule.name == rule_name).first()
            if not existing:
                content = f"**立场**: {party}\n**角色定义**: {role_definition}\n**关注点**: {rule['focus']}\n**审查指令**: {rule['instruction']}"
                new_rule = ReviewRule(
                    name=rule_name,
                    description=f"{role_definition}的{rule['focus']}审查要点",
                    content=content,
                    rule_category="stance",
                    priority=priority,
                    is_system=True,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(new_rule)
                created_count += 1
                priority += 1

    db.commit()

    # 统计
    total_rules = db.query(ReviewRule).count()
    system_rules = db.query(ReviewRule).filter(ReviewRule.is_system == True).count()

    return {
        "success": True,
        "message": f"迁移完成！共创建 {created_count} 条系统规则",
        "stats": {
            "total_rules": total_rules,
            "system_rules": system_rules,
            "created_rules": created_count,
            "cleared_rules": existing_count
        },
        "version": rules_data.get("version"),
        "description": rules_data.get("description")
    }


# ==================== 数据库审查规则管理 API (Database CRUD) ====================

@router.get("/rules")
async def get_rules_from_db(
    rule_category: Optional[str] = None,
    is_system: Optional[bool] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从数据库获取审查规则列表（支持分页和过滤）

    参数:
    - rule_category: 规则类型
    - is_system: 是否为系统规则
    - is_active: 是否启用
    - page: 页码（从1开始）
    - size: 每页数量

    所有用户可查看
    """
    # 构建查询
    query = db.query(ReviewRule)

    if rule_category:
        query = query.filter(ReviewRule.rule_category == rule_category)
    if is_system is not None:
        query = query.filter(ReviewRule.is_system == is_system)
    if is_active is not None:
        query = query.filter(ReviewRule.is_active == is_active)

    # 统计总数
    total_count = query.count()

    # 分页查询，按优先级排序
    rules = query.order_by(ReviewRule.priority.asc(), ReviewRule.id.asc()).offset((page - 1) * size).limit(size).all()

    # 转换为字典格式
    items = []
    for rule in rules:
        items.append({
            "id": rule.id,
            "name": rule.name,
            "description": rule.description,
            "content": rule.content,
            "rule_category": rule.rule_category,
            "priority": rule.priority,
            "is_system": rule.is_system,
            "is_active": rule.is_active,
            "creator_id": rule.creator_id,
            "created_at": rule.created_at.isoformat() if rule.created_at else None
        })

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "size": size
    }


@router.get("/rules/{rule_id}")
async def get_rule_by_id(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据ID获取单个规则详情

    所有用户可查看
    """
    rule = db.query(ReviewRule).filter(ReviewRule.id == rule_id).first()

    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 ID {rule_id} 不存在")

    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "content": rule.content,
        "rule_category": rule.rule_category,
        "priority": rule.priority,
        "is_system": rule.is_system,
        "is_active": rule.is_active,
        "creator_id": rule.creator_id,
        "created_at": rule.created_at.isoformat() if rule.created_at else None
    }


@router.post("/rules")
async def create_rule(
    rule_data: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建新的审查规则

    参数:
    - rule_data: 规则创建数据（请求体）

    权限：所有用户可创建自定义规则
    """
    # 验证 rule_category
    valid_categories = ["universal", "feature", "stance", "custom"]
    if rule_data.rule_category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"无效的规则类型: {rule_data.rule_category}。有效值为: {', '.join(valid_categories)}"
        )

    # 只有管理员可以创建系统规则
    if rule_data.rule_category in ["universal", "feature", "stance"] and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可创建系统规则")

    # 创建规则
    new_rule = ReviewRule(
        name=rule_data.name,
        description=rule_data.description,
        content=rule_data.content,
        rule_category=rule_data.rule_category,
        priority=rule_data.priority,
        is_active=rule_data.is_active,
        is_system=(rule_data.rule_category in ["universal", "feature", "stance"]),
        creator_id=current_user.id
    )

    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)

    logger.info(f"用户 {current_user.email} 创建了规则: {rule_data.name} (ID: {new_rule.id})")

    return {
        "id": new_rule.id,
        "name": new_rule.name,
        "description": new_rule.description,
        "content": new_rule.content,
        "rule_category": new_rule.rule_category,
        "priority": new_rule.priority,
        "is_system": new_rule.is_system,
        "is_active": new_rule.is_active,
        "creator_id": new_rule.creator_id,
        "created_at": new_rule.created_at.isoformat() if new_rule.created_at else None,
        "message": "规则创建成功"
    }


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    name: Optional[str] = None,
    content: Optional[str] = None,
    description: Optional[str] = None,
    rule_category: Optional[str] = None,
    priority: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新审查规则

    参数:
    - rule_id: 规则ID
    - name: 新的规则名称（可选）
    - content: 新的规则内容（可选）
    - description: 新的规则描述（可选）
    - rule_category: 新的规则类型（可选）
    - priority: 新的优先级（可选）
    - is_active: 新的启用状态（可选）

    权限：
    - 自定义规则：创建者可修改
    - 系统规则：仅管理员可修改
    """
    rule = db.query(ReviewRule).filter(ReviewRule.id == rule_id).first()

    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 ID {rule_id} 不存在")

    # 权限检查
    if rule.is_system and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可修改系统规则")

    if not rule.is_system and rule.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可修改自己的自定义规则")

    # 更新字段
    if name is not None:
        rule.name = name
    if content is not None:
        rule.content = content
    if description is not None:
        rule.description = description
    if rule_category is not None:
        valid_categories = ["universal", "feature", "stance", "custom"]
        if rule_category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"无效的规则类型: {rule_category}。有效值为: {', '.join(valid_categories)}"
            )
        rule.rule_category = rule_category
    if priority is not None:
        rule.priority = priority
    if is_active is not None:
        rule.is_active = is_active

    db.commit()
    db.refresh(rule)

    logger.info(f"用户 {current_user.email} 更新了规则: {rule.name} (ID: {rule.id})")

    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "content": rule.content,
        "rule_category": rule.rule_category,
        "priority": rule.priority,
        "is_system": rule.is_system,
        "is_active": rule.is_active,
        "creator_id": rule.creator_id,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "message": "规则更新成功"
    }


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除审查规则

    权限：
    - 自定义规则：创建者可删除
    - 系统规则：仅管理员可删除
    """
    logger.info(f"删除规则请求: rule_id={rule_id}, user={current_user.email}, is_admin={current_user.is_admin}")

    rule = db.query(ReviewRule).filter(ReviewRule.id == rule_id).first()

    if not rule:
        logger.error(f"规则不存在: rule_id={rule_id}")
        raise HTTPException(status_code=404, detail=f"规则 ID {rule_id} 不存在")

    logger.info(f"找到规则: id={rule.id}, name={rule.name}, is_system={rule.is_system}, creator_id={rule.creator_id}")

    # 权限检查
    if rule.is_system and not current_user.is_admin:
        logger.error(f"权限拒绝: 非管理员尝试删除系统规则")
        raise HTTPException(status_code=403, detail="仅管理员可删除系统规则")

    if not rule.is_system and rule.creator_id != current_user.id:
        logger.error(f"权限拒绝: 非创建者尝试删除自定义规则")
        raise HTTPException(status_code=403, detail="仅创建者可删除自己的自定义规则")

    rule_name = rule.name
    db.delete(rule)
    db.commit()

    # 验证删除
    deleted_rule = db.query(ReviewRule).filter(ReviewRule.id == rule_id).first()
    if deleted_rule:
        logger.error(f"删除失败: 规则仍然存在于数据库中")
    else:
        logger.info(f"删除成功: 规则已从数据库中移除")

    logger.info(f"用户 {current_user.email} 删除了规则: {rule_name} (ID: {rule_id})")

    return {
        "message": f"规则 '{rule_name}' 已删除",
        "deleted_rule_id": rule_id
    }


@router.put("/rules/{rule_id}/toggle")
async def toggle_rule_status(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    切换规则启用/禁用状态

    权限：
    - 自定义规则：创建者可切换
    - 系统规则：仅管理员可切换
    """
    rule = db.query(ReviewRule).filter(ReviewRule.id == rule_id).first()

    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 ID {rule_id} 不存在")

    # 权限检查
    if rule.is_system and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可修改系统规则")

    if not rule.is_system and rule.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可修改自己的自定义规则")

    # 切换状态
    rule.is_active = not rule.is_active
    db.commit()
    db.refresh(rule)

    logger.info(f"用户 {current_user.email} 切换了规则状态: {rule.name} (ID: {rule.id}) -> {rule.is_active}")

    return {
        "id": rule.id,
        "is_active": rule.is_active,
        "message": f"规则已{'启用' if rule.is_active else '禁用'}"
    }
