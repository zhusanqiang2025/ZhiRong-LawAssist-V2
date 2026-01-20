# backend/scripts/verify_template_categories.py
"""
验证合同模板的分类信息和法律特征完整性

功能：
1. 检查分类完整性（category、subcategory、primary_contract_type）
2. 检查法律特征完整性（7个核心字段）
3. 检查知识图谱一致性
4. 生成统计报告
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List
import json

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from sqlalchemy import create_engine, func

# 尝试使用配置的数据库 URL，如果失败则使用 SQLite
SessionLocal = None
try:
    from app.database import SessionLocal as DBSessionLocal, engine
    SessionLocal = DBSessionLocal
    logger.info("使用 PostgreSQL 数据库")
    # 测试连接
    db = SessionLocal()
    from app.models.contract_template import ContractTemplate
    _ = db.query(ContractTemplate).count()
    db.close()
except Exception as e:
    logger.warning(f"PostgreSQL 连接失败: {e}，使用 SQLite 作为后备")
    SQLITE_DB = project_root.parent / "data" / "app.db"
    SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_DB}")
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=sqlite_engine)
    logger.info(f"使用 SQLite 数据库: {SQLITE_DB}")

from app.models.contract_template import ContractTemplate


def load_knowledge_graph() -> Dict:
    """加载知识图谱数据"""
    kg_data = {}

    kg_file = project_root / "app" / "services" / "legal_features" / "knowledge_graph_data.json"

    if not kg_file.exists():
        logger.warning(f"知识图谱文件不存在: {kg_file}")
        return kg_data

    try:
        with open(kg_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data.get('contract_types', []):
            name = item.get('name')
            if name:
                kg_data[name] = {
                    'category': item.get('category'),
                    'subcategory': item.get('subcategory'),
                    'legal_features': item.get('legal_features')
                }

        logger.info(f"从知识图谱加载了 {len(kg_data)} 个合同类型定义")
        return kg_data

    except Exception as e:
        logger.error(f"加载知识图谱失败: {e}")
        return kg_data


def check_category_integrity(db: Session, templates: List[ContractTemplate]) -> List[str]:
    """
    检查分类完整性

    Returns:
        问题列表
    """
    issues = []

    for template in templates:
        template_id = template.id
        template_name = template.name

        # 检查必要字段
        if not template.category:
            issues.append(f"[{template_id}] {template_name}: 缺少category")

        if not template.subcategory:
            issues.append(f"[{template_id}] {template_name}: 缺少subcategory")

        if not template.primary_contract_type:
            issues.append(f"[{template_id}] {template_name}: 缺少primary_contract_type")

    return issues


def check_legal_features(db: Session, templates: List[ContractTemplate]) -> List[str]:
    """
    检查法律特征完整性

    Returns:
        问题列表
    """
    issues = []

    for template in templates:
        template_id = template.id
        template_name = template.name

        # 检查V2核心特征
        if not template.transaction_nature:
            issues.append(f"[{template_id}] {template_name}: 缺少transaction_nature")

        if not template.contract_object:
            issues.append(f"[{template_id}] {template_name}: 缺少contract_object")

        # 检查扩展特征（这些对自动填充很重要）
        if not template.transaction_consideration:
            issues.append(f"[{template_id}] {template_name}: 缺少transaction_consideration")

        if not template.transaction_characteristics:
            issues.append(f"[{template_id}] {template_name}: 缺少transaction_characteristics")

    return issues


def check_kg_consistency(db: Session, templates: List[ContractTemplate], kg_data: Dict) -> List[str]:
    """
    检查知识图谱一致性

    Returns:
        问题列表
    """
    issues = []

    for template in templates:
        template_id = template.id
        template_name = template.name

        # 如果有subcategory，检查是否在知识图谱中
        if template.subcategory and template.subcategory in kg_data:
            kg_info = kg_data[template.subcategory]

            # 检查category是否一致
            if template.category and kg_info['category'] and template.category != kg_info['category']:
                issues.append(
                    f"[{template_id}] {template_name}: category不一致 "
                    f"数据库={template.category} KG={kg_info['category']}"
                )

    return issues


def generate_statistics(db: Session) -> Dict:
    """生成统计报告"""
    stats = {}

    # 总模板数
    stats['total_templates'] = db.query(func.count(ContractTemplate.id)).scalar()

    # 按一级分类统计
    category_counts = db.query(
        ContractTemplate.category,
        func.count(ContractTemplate.id)
    ).group_by(ContractTemplate.category).all()
    stats['by_category'] = dict(category_counts)

    # 按二级分类统计（只显示数量最多的前20个）
    subcategory_counts = db.query(
        ContractTemplate.category,
        ContractTemplate.subcategory,
        func.count(ContractTemplate.id)
    ).group_by(
        ContractTemplate.category,
        ContractTemplate.subcategory
    ).order_by(
        func.count(ContractTemplate.id).desc()
    ).limit(20).all()
    stats['by_subcategory_top20'] = [
        {'category': cat, 'subcategory': sub, 'count': count}
        for cat, sub, count in subcategory_counts
    ]

    # 法律特征完整度统计
    stats['features_completeness'] = {}

    with_transaction_nature = db.query(func.count(ContractTemplate.id)).filter(
        ContractTemplate.transaction_nature.isnot(None)
    ).scalar()
    stats['features_completeness']['with_transaction_nature'] = with_transaction_nature

    with_contract_object = db.query(func.count(ContractTemplate.id)).filter(
        ContractTemplate.contract_object.isnot(None)
    ).scalar()
    stats['features_completeness']['with_contract_object'] = with_contract_object

    with_transaction_characteristics = db.query(func.count(ContractTemplate.id)).filter(
        ContractTemplate.transaction_characteristics.isnot(None)
    ).scalar()
    stats['features_completeness']['with_transaction_characteristics'] = with_transaction_characteristics

    # 完整特征（同时有 transaction_nature 和 contract_object）
    with_complete_features = db.query(func.count(ContractTemplate.id)).filter(
        ContractTemplate.transaction_nature.isnot(None),
        ContractTemplate.contract_object.isnot(None)
    ).scalar()
    stats['features_completeness']['with_complete_features'] = with_complete_features

    if stats['total_templates'] > 0:
        stats['features_completeness']['transaction_nature_rate'] = \
            f"{with_transaction_nature * 100 / stats['total_templates']:.1f}%"
        stats['features_completeness']['contract_object_rate'] = \
            f"{with_contract_object * 100 / stats['total_templates']:.1f}%"
        stats['features_completeness']['transaction_characteristics_rate'] = \
            f"{with_transaction_characteristics * 100 / stats['total_templates']:.1f}%"
        stats['features_completeness']['complete_features_rate'] = \
            f"{with_complete_features * 100 / stats['total_templates']:.1f}%"

    return stats


def verify_template_categories():
    """验证模板分类的完整性和一致性"""
    logger.info("=" * 60)
    logger.info("开始验证模板分类")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # 加载数据
        templates = db.query(ContractTemplate).all()
        kg_data = load_knowledge_graph()

        logger.info(f"加载了 {len(templates)} 个模板")
        logger.info(f"加载了 {len(kg_data)} 个知识图谱定义")

        # 1. 分类完整性检查
        logger.info("\n" + "=" * 60)
        logger.info("1. 分类完整性检查")
        logger.info("=" * 60)

        category_issues = check_category_integrity(db, templates)
        if category_issues:
            logger.warning(f"发现 {len(category_issues)} 个问题:")
            for issue in category_issues[:20]:  # 只显示前20个
                logger.warning(f"  - {issue}")
            if len(category_issues) > 20:
                logger.warning(f"  ... 还有 {len(category_issues) - 20} 个问题")
        else:
            logger.info("✓ 所有模板分类字段完整")

        # 2. 法律特征完整性检查
        logger.info("\n" + "=" * 60)
        logger.info("2. 法律特征完整性检查")
        logger.info("=" * 60)

        features_issues = check_legal_features(db, templates)
        if features_issues:
            logger.warning(f"发现 {len(features_issues)} 个问题:")
            for issue in features_issues[:20]:
                logger.warning(f"  - {issue}")
            if len(features_issues) > 20:
                logger.warning(f"  ... 还有 {len(features_issues) - 20} 个问题")
        else:
            logger.info("✓ 所有模板法律特征完整")

        # 3. 知识图谱一致性检查
        logger.info("\n" + "=" * 60)
        logger.info("3. 知识图谱一致性检查")
        logger.info("=" * 60)

        kg_issues = check_kg_consistency(db, templates, kg_data)
        if kg_issues:
            logger.warning(f"发现 {len(kg_issues)} 个问题:")
            for issue in kg_issues[:20]:
                logger.warning(f"  - {issue}")
            if len(kg_issues) > 20:
                logger.warning(f"  ... 还有 {len(kg_issues) - 20} 个问题")
        else:
            logger.info("✓ 所有模板与知识图谱一致")

        # 4. 统计报告
        logger.info("\n" + "=" * 60)
        logger.info("4. 统计报告")
        logger.info("=" * 60)

        stats = generate_statistics(db)

        logger.info(f"\n总模板数: {stats['total_templates']}")
        logger.info(f"\n按一级分类统计:")
        for cat, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {cat}: {count}个")

        logger.info(f"\n法律特征完整度:")
        logger.info(f"  总模板数: {stats['total_templates']}")
        logger.info(f"  有交易性质: {stats['features_completeness']['with_transaction_nature']} "
                   f"({stats['features_completeness']['transaction_nature_rate']})")
        logger.info(f"  有合同标的: {stats['features_completeness']['with_contract_object']} "
                   f"({stats['features_completeness']['contract_object_rate']})")
        logger.info(f"  有交易特征: {stats['features_completeness']['with_transaction_characteristics']} "
                   f"({stats['features_completeness']['transaction_characteristics_rate']})")
        logger.info(f"  完整特征: {stats['features_completeness']['with_complete_features']} "
                   f"({stats['features_completeness']['complete_features_rate']})")

        # 5. 总结
        logger.info("\n" + "=" * 60)
        logger.info("验证总结")
        logger.info("=" * 60)

        total_issues = len(category_issues) + len(features_issues) + len(kg_issues)

        if total_issues == 0:
            logger.info("✓ 验证通过！所有模板的分类和法律特征都是完整的")
        else:
            logger.warning(f"发现 {total_issues} 个问题:")
            logger.warning(f"  - 分类完整性: {len(category_issues)} 个")
            logger.warning(f"  - 法律特征完整性: {len(features_issues)} 个")
            logger.warning(f"  - 知识图谱一致性: {len(kg_issues)} 个")

    finally:
        db.close()


if __name__ == "__main__":
    try:
        verify_template_categories()
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"验证失败: {e}", exc_info=True)
        sys.exit(1)
