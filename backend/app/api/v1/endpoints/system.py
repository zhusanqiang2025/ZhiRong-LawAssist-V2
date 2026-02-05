# backend/app/api/v1/endpoints/system.py
import os
import logging
import json
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.api import deps
from app.models.user import User
from app.models.category import Category
from app.models.rule import ReviewRule
from app.models.contract_knowledge import ContractKnowledgeType
from app.models.risk_analysis import RiskRulePackage
from app.models.litigation_analysis import LitigationCasePackage
from app.database import SessionLocal, get_db
from fastapi.responses import Response
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()

# ... (保留原有的 admin-status, ensure-admin 等接口，为了篇幅省略，请保留它们) ...
# 请保留 check_admin_status, ensure_admin_user, auto_ensure_admin 这三个函数

@router.get("/admin-status")
def check_admin_status() -> Any:
    # ... (保持原样)
    return {"message": "请保留原有的 check_admin_status 代码"}

@router.post("/ensure-admin")
def ensure_admin_user() -> Any:
    # ... (保持原样)
    return {"message": "请保留原有的 ensure_admin_user 代码"}

# =====================================================================
# 📦 数据迁移专用接口 (Export / Import)
# =====================================================================

@router.get("/data/export")
def export_system_data(
    module: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    【本地开发环境使用】导出核心系统数据为 JSON
    包含: Categories, ReviewRules, KnowledgeGraph, RiskPackages, LitigationPackages

    参数:
    - module: 可选，指定导出的模块
      - None 或 'all': 导出所有数据
      - 'categories': 仅导出分类数据
      - 'knowledge': 仅导出知识图谱
      - 'rules': 仅导出审查规则
      - 'risk': 仅导出风险评估规则包
      - 'litigation': 仅导出案件分析规则包
    """
    data = {
        "version": "2.0",
        "exported_at": datetime.now().isoformat(),
        "categories": [],
        "knowledge_types": [],
        "review_rules": [],
        "risk_packages": [],
        "litigation_packages": []
    }

    # 按模块导出
    if module in [None, "all", "categories"]:
        # 1. 导出分类 (按 ID 排序，保证父子关系)
        categories = db.query(Category).order_by(Category.id).all()
        for c in categories:
            data["categories"].append({
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "parent_id": c.parent_id,
                "sort_order": c.sort_order,
                "is_active": c.is_active,
                "meta_info": c.meta_info
            })

    if module in [None, "all", "knowledge"]:
        # 2. 导出知识图谱
        knowledges = db.query(ContractKnowledgeType).all()
        for k in knowledges:
            data["knowledge_types"].append(k.to_dict())

    if module in [None, "all", "rules"]:
        # 3. 导出审查规则
        rules = db.query(ReviewRule).all()
        for r in rules:
            rule_dict = r.to_dict()
            # 补充 to_dict 可能缺失的字段，确保完整恢复
            rule_dict.update({
                "content": r.content,
                "apply_to_category_ids": r.apply_to_category_ids,
                "target_stance": r.target_stance,
                "rule_category": r.rule_category,
                "is_system": r.is_system
            })
            data["review_rules"].append(rule_dict)

    if module in [None, "all", "risk"]:
        # 4. 导出风险规则包
        packages = db.query(RiskRulePackage).all()
        for p in packages:
            data["risk_packages"].append({
                "package_id": p.package_id,
                "package_name": p.package_name,
                "package_category": p.package_category,
                "description": p.description,
                "applicable_scenarios": p.applicable_scenarios,
                "target_entities": p.target_entities,
                "rules": p.rules,
                "is_active": p.is_active,
                "is_system": p.is_system,
                "version": p.version
            })

    if module in [None, "all", "litigation"]:
        # 5. 导出案件分析规则包
        litigation_packages = db.query(LitigationCasePackage).all()
        for lp in litigation_packages:
            data["litigation_packages"].append({
                "package_id": lp.package_id,
                "package_name": lp.package_name,
                "package_category": lp.package_category,
                "case_type": lp.case_type,
                "description": lp.description,
                "applicable_positions": lp.applicable_positions,
                "target_documents": lp.target_documents,
                "rules": lp.rules,
                "is_active": lp.is_active,
                "is_system": lp.is_system,
                "version": lp.version
            })

    return data


@router.post("/data/import")
async def import_system_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    【生产环境使用】上传 JSON 文件并初始化数据库
    注意：此操作会 清空 现有的分类、规则和知识图谱数据！

    支持两种格式：
    - v1.0: 旧版本格式 {version: "1.0", backup_time: "...", data: {rules: [...]}}
    - v2.0: 新版本格式 {version: "2.0", exported_at: "...", risk_packages: [...], ...}
    """
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的 JSON 文件: {e}")

    # 检测版本并转换格式
    version = data.get("version", "2.0")

    # 处理旧版本格式 (v1.0)
    if version == "1.0":
        logger.info("[Import] 检测到旧版本格式 (v1.0)，正在转换...")
        # 旧版本格式: {version: "1.0", backup_time: "...", data: {rules: [...]}}
        # 转换为新版本格式
        old_data = data.get("data", {})

        # 如果旧文件中包含风险规则 (data.rules)，转换为风险包格式
        if "rules" in old_data:
            old_rules = old_data["rules"]
            # 按场景类型分组规则
            rules_by_scene = {}
            for rule in old_rules:
                scene_type = rule.get("scene_type", "general")
                if scene_type not in rules_by_scene:
                    rules_by_scene[scene_type] = []
                rules_by_scene[scene_type].append(rule)

            # 转换为风险包格式
            risk_packages = []
            for scene_type, rules in rules_by_scene.items():
                # 使用第一个规则的名称来创建包名
                first_rule = rules[0]
                package_name = {
                    "equity_penetration": "股权穿透风险分析包",
                    "contract_risk": "合同风险分析包",
                    "tax_risk": "税务风险分析包",
                    "compliance_review": "合规审查分析包",
                    "related_party": "关联交易风险分析包",
                    "asset_securitization": "资产证券化风险分析包",
                    "capital_increase": "增资扩股风险分析包",
                    "equity_transfer": "股权转让风险分析包",
                    "shareholders_agreement": "股东协议风险分析包",
                    "joint_stock_restriction": "股份限售风险分析包",
                    "general": "通用风险分析包"
                }.get(scene_type, f"{scene_type}风险分析包")

                package_category = {
                    "equity_penetration": "equity_risk",
                    "contract_risk": "contract_risk",
                    "tax_risk": "tax_risk",
                    "compliance_review": "compliance",
                    "related_party": "transaction_risk",
                    "asset_securitization": "finance_risk",
                    "capital_increase": "equity_risk",
                    "equity_transfer": "equity_risk",
                    "shareholders_agreement": "corporate_governance",
                    "joint_stock_restriction": "equity_risk",
                    "general": "general"
                }.get(scene_type, "general")

                # 将旧规则转换为包内规则格式
                package_rules = []
                for rule in rules:
                    package_rules.append({
                        "rule_id": f"RULE_{rule.get('id', '')}",
                        "rule_name": rule.get("name", ""),
                        "rule_prompt": rule.get("content", ""),
                        "risk_type": rule.get("risk_type", "general"),
                        "priority": rule.get("priority", 5),
                        "default_risk_level": rule.get("default_risk_level", "medium"),
                        "keywords": rule.get("keywords", [])
                    })

                risk_packages.append({
                    "package_id": f"{scene_type}_risk_package",
                    "package_name": package_name,
                    "package_category": package_category,
                    "description": f"从旧版本数据导入的 {package_name}",
                    "applicable_scenarios": [scene_type],
                    "target_entities": ["company", "shareholder"],
                    "rules": package_rules,
                    "is_active": True,
                    "is_system": True,
                    "version": "1.0"
                })

            # 更新数据结构为新版本格式
            data = {
                "version": "2.0",
                "exported_at": data.get("backup_time", datetime.now().isoformat()),
                "categories": data.get("categories", []),
                "knowledge_types": data.get("knowledge_types", []),
                "review_rules": data.get("review_rules", []),
                "risk_packages": risk_packages,
                "litigation_packages": data.get("litigation_packages", [])
            }
            logger.info(f"[Import] 已转换旧版本格式，生成 {len(risk_packages)} 个风险包")

    try:
        # 1. 清空现有数据 (级联删除)
        # 注意表名需要与你的数据库实际表名一致
        db.execute(text("TRUNCATE TABLE contract_review_rules CASCADE"))
        db.execute(text("TRUNCATE TABLE contract_knowledge_types CASCADE"))
        db.execute(text("TRUNCATE TABLE risk_rule_packages CASCADE"))
        db.execute(text("TRUNCATE TABLE litigation_case_packages CASCADE"))
        db.execute(text("TRUNCATE TABLE categories CASCADE"))

        logger.info("[Import] 已清空旧数据")

        # 2. 导入分类 (必须按 ID 排序导入，否则子节点找不到父节点)
        categories_data = sorted(data.get("categories", []), key=lambda x: x["id"])
        for cat_data in categories_data:
            cat = Category(
                id=cat_data["id"],
                name=cat_data["name"],
                code=cat_data.get("code"),
                parent_id=cat_data.get("parent_id"),
                sort_order=cat_data.get("sort_order", 0),
                is_active=cat_data.get("is_active", True),
                meta_info=cat_data.get("meta_info")
            )
            db.add(cat)
        db.flush() # 确保分类ID已占用
        # 更新序列，防止后续手动插入冲突 (假设最大ID是200000以内)
        try:
            db.execute(text("SELECT setval('categories_id_seq', (SELECT MAX(id) FROM categories) + 1000)"))
        except Exception:
            pass # 如果序列名不对忽略

        # 3. 导入知识图谱
        for k_data in data.get("knowledge_types", []):
            kt = ContractKnowledgeType(
                name=k_data["name"],
                linked_category_id=k_data.get("linked_category_id"),
                category=k_data.get("category"),
                subcategory=k_data.get("subcategory"),
                transaction_nature=k_data["legal_features"].get("transaction_nature"),
                contract_object=k_data["legal_features"].get("contract_object"),
                stance=k_data["legal_features"].get("stance"),
                transaction_characteristics=k_data["legal_features"].get("transaction_characteristics"),
                usage_scenario=k_data["legal_features"].get("usage_scenario"),
                legal_basis=k_data["legal_features"].get("legal_basis"),
                is_active=k_data.get("is_active", True),
                is_system=k_data.get("is_system", True),
                created_at=datetime.utcnow()
            )
            db.add(kt)

        # 4. 导入审查规则
        for r_data in data.get("review_rules", []):
            rule = ReviewRule(
                name=r_data["name"],
                description=r_data.get("description"),
                content=r_data["content"],
                rule_category=r_data["rule_category"],
                priority=r_data.get("priority", 0),
                is_active=r_data.get("is_active", True),
                is_system=r_data.get("is_system", False),
                # 关键的 Hub-and-Spoke 字段
                apply_to_category_ids=r_data.get("apply_to_category_ids"),
                target_stance=r_data.get("target_stance"),
                created_at=datetime.utcnow()
            )
            db.add(rule)

        # 5. 导入风险包
        for p_data in data.get("risk_packages", []):
            pkg = RiskRulePackage(
                package_id=p_data["package_id"],
                package_name=p_data["package_name"],
                package_category=p_data["package_category"],
                description=p_data.get("description"),
                applicable_scenarios=p_data.get("applicable_scenarios"),
                target_entities=p_data.get("target_entities"),
                rules=p_data["rules"],
                is_active=p_data.get("is_active", True),
                is_system=p_data.get("is_system", True),
                version=p_data.get("version"),
                created_at=datetime.utcnow()
            )
            db.add(pkg)

        # 6. 导入案件分析规则包
        for lp_data in data.get("litigation_packages", []):
            lp = LitigationCasePackage(
                package_id=lp_data["package_id"],
                package_name=lp_data["package_name"],
                package_category=lp_data["package_category"],
                case_type=lp_data["case_type"],
                description=lp_data.get("description"),
                applicable_positions=lp_data.get("applicable_positions"),
                target_documents=lp_data.get("target_documents"),
                rules=lp_data["rules"],
                is_active=lp_data.get("is_active", True),
                is_system=lp_data.get("is_system", True),
                version=lp_data.get("version"),
                created_at=datetime.utcnow()
            )
            db.add(lp)

        db.commit()
        return {"success": True, "message": "数据导入成功！所有分类和规则已同步。"}

    except Exception as e:
        db.rollback()
        logger.error(f"Data Import Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")