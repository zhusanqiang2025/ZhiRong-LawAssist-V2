# backend/scripts/sync_knowledge_graph_to_templates.py
"""
将知识图谱的法律特征同步到对应的合同模板

功能：
1. 加载知识图谱中的合同类型定义和法律特征
2. 匹配数据库中的模板与知识图谱的合同类型
3. 更新模板的法律特征字段
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional

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
from sqlalchemy import create_engine

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
    """
    加载知识图谱数据

    Returns:
        {合同名称: 法律特征字典}
    """
    kg_data = {}

    # 知识图谱数据文件路径
    kg_file = project_root / "app" / "services" / "legal_features" / "knowledge_graph_data.json"

    if not kg_file.exists():
        logger.warning(f"知识图谱文件不存在: {kg_file}")
        return kg_data

    try:
        import json
        with open(kg_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data.get('contract_types', []):
            name = item.get('name')
            if name:
                kg_data[name] = item

        logger.info(f"从知识图谱加载了 {len(kg_data)} 个合同类型定义")
        return kg_data

    except Exception as e:
        logger.error(f"加载知识图谱失败: {e}")
        return kg_data


def match_template_with_kg(
    template: ContractTemplate,
    kg_data: Dict
) -> Optional[Dict]:
    """
    匹配模板与知识图谱的合同类型

    Args:
        template: 数据库模板对象
        kg_data: 知识图谱数据

    Returns:
        匹配到的法律特征，如果没有匹配则返回 None
    """
    template_name = template.name
    template_category = template.category
    template_subcategory = template.subcategory

    # 1. 精确名称匹配
    if template_name in kg_data:
        kg_item = kg_data[template_name]
        if kg_item.get('legal_features'):
            logger.info(f"  匹配方式: 精确名称 ({template_name})")
            return kg_item['legal_features']

    # 2. 模糊名称匹配
    for kg_name, kg_item in kg_data.items():
        # 检查模板名称是否是知识图谱名称的子串
        if kg_name in template_name or template_name in kg_name:
            if kg_item.get('legal_features'):
                logger.info(f"  匹配方式: 模糊名称 ({template_name} ~ {kg_name})")
                return kg_item['legal_features']

        # 检查别名
        aliases = kg_item.get('aliases', [])
        if isinstance(aliases, list):
            for alias in aliases:
                if alias in template_name or template_name in alias:
                    if kg_item.get('legal_features'):
                        logger.info(f"  匹配方式: 别名 ({template_name} ~ {alias})")
                        return kg_item['legal_features']

    # 3. 分类匹配
    for kg_name, kg_item in kg_data.items():
        kg_category = kg_item.get('category', '')
        kg_subcategory = kg_item.get('subcategory', '')

        # 精确分类匹配
        if (template_category == kg_category and
            template_subcategory == kg_subcategory and
            kg_subcategory):  # 确保子分类不为空
            if kg_item.get('legal_features'):
                logger.info(f"  匹配方式: 分类匹配 ({template_category}/{template_subcategory})")
                return kg_item['legal_features']

        # 分类名称匹配
        if template_category and kg_category and template_category in kg_category:
            if kg_item.get('legal_features'):
                logger.info(f"  匹配方式: 分类名称 ({template_category} ~ {kg_category})")
                return kg_item['legal_features']

    return None


def sync_features_to_templates():
    """将知识图谱的法律特征同步到模板"""
    logger.info("=" * 60)
    logger.info("开始同步知识图谱法律特征到模板")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # 1. 加载知识图谱
        kg_data = load_knowledge_graph()

        if not kg_data:
            logger.warning("知识图谱为空，无法同步")
            return

        # 2. 获取所有模板
        templates = db.query(ContractTemplate).all()
        logger.info(f"数据库中有 {len(templates)} 个模板")

        # 3. 统计信息
        stats = {
            "total": len(templates),
            "matched": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0
        }

        # 4. 遍历模板进行匹配和更新
        for template in templates:
            logger.info(f"\n处理模板: {template.name}")
            logger.info(f"  当前特征: nature={template.transaction_nature}, object={template.contract_object}, stance={template.stance}")

            # 匹配知识图谱
            kg_features = match_template_with_kg(template, kg_data)

            if not kg_features:
                logger.info(f"  ⊘ 未匹配到知识图谱")

                # 为未匹配的模板提供默认扩展特征
                needs_default_update = False

                if not template.transaction_consideration:
                    # 根据交易性质提供默认对价
                    default_consideration = {
                        "转移所有权": "有偿，双方协商",
                        "提供服务": "有偿，双方协商",
                        "许可使用": "有偿，双方协商",
                        "合作经营": "有偿，双方协商",
                        "融资借贷": "有偿，按约定利率",
                        "劳动用工": "有偿，工资报酬"
                    }.get(template.transaction_nature, "有偿，双方协商")

                    template.transaction_consideration = default_consideration
                    needs_default_update = True

                if not template.transaction_characteristics:
                    # 根据交易性质和标的提供默认交易特征
                    default_characteristics = f"{template.transaction_nature}，标的为{template.contract_object}"
                    template.transaction_characteristics = default_characteristics
                    needs_default_update = True

                if not template.usage_scenario:
                    # 根据分类提供默认使用场景
                    default_scenario = f"适用于{template.category}的{template.subcategory or template.name}场景"
                    template.usage_scenario = default_scenario
                    needs_default_update = True

                if needs_default_update:
                    logger.info(f"  ✓ 设置默认扩展特征")
                    logger.info(f"    对价: {template.transaction_consideration}")
                    logger.info(f"    特征: {template.transaction_characteristics}")
                    logger.info(f"    场景: {template.usage_scenario}")

                    try:
                        db.commit()
                        db.refresh(template)
                        stats["updated"] += 1
                    except Exception as e:
                        logger.error(f"  ✗ 更新失败: {e}")
                        db.rollback()
                        stats["failed"] += 1

                stats["skipped"] += 1
                continue

            stats["matched"] += 1

            # 构建期望的扩展字段值
            consideration_type = kg_features.get('consideration_type')
            consideration_detail = kg_features.get('consideration_detail')
            expected_consideration = None
            if consideration_type or consideration_detail:
                consideration_parts = []
                if consideration_type:
                    consideration_parts.append(consideration_type)
                if consideration_detail:
                    consideration_parts.append(consideration_detail)
                expected_consideration = '，'.join(consideration_parts)

            # 检查是否需要更新（包括扩展字段）
            needs_update = (
                template.transaction_nature != kg_features.get('transaction_nature') or
                template.contract_object != kg_features.get('contract_object') or
                template.stance != kg_features.get('stance') or
                template.transaction_consideration != expected_consideration or
                template.transaction_characteristics != kg_features.get('transaction_characteristics') or
                template.usage_scenario != kg_features.get('usage_scenario')
            )

            if not needs_update:
                logger.info(f"  ⊘ 特征已是最新，跳过")
                stats["skipped"] += 1
                continue

            # 更新模板
            try:
                template.transaction_nature = kg_features.get('transaction_nature')
                template.contract_object = kg_features.get('contract_object')
                template.stance = kg_features.get('stance')

                # 更新扩展特征：交易对价（组合类型和详情）
                consideration_type = kg_features.get('consideration_type')
                consideration_detail = kg_features.get('consideration_detail')
                if consideration_type or consideration_detail:
                    consideration_parts = []
                    if consideration_type:
                        consideration_parts.append(consideration_type)
                    if consideration_detail:
                        consideration_parts.append(consideration_detail)
                    template.transaction_consideration = '，'.join(consideration_parts)

                # 更新扩展特征：交易特征
                if kg_features.get('transaction_characteristics'):
                    template.transaction_characteristics = kg_features['transaction_characteristics']

                # 更新使用场景到 usage_scenario 字段
                if kg_features.get('usage_scenario'):
                    template.usage_scenario = kg_features['usage_scenario']

                # 更新元数据
                if not template.metadata_info:
                    template.metadata_info = {}
                template.metadata_info['knowledge_graph_synced'] = True
                template.metadata_info['kg_synced_at'] = kg_features.get('usage_scenario', '')
                template.metadata_info['kg_legal_basis'] = kg_features.get('legal_basis', [])

                db.commit()
                db.refresh(template)

                logger.info(f"  ✓ 更新成功")
                logger.info(f"    新特征: nature={template.transaction_nature}, object={template.contract_object}, stance={template.stance}")
                logger.info(f"    扩展特征: consideration={template.transaction_consideration}, characteristics={template.transaction_characteristics}")
                logger.info(f"    usage_scenario={template.usage_scenario}")
                stats["updated"] += 1

            except Exception as e:
                logger.error(f"  ✗ 更新失败: {e}")
                db.rollback()
                stats["failed"] += 1

        # 5. 输出统计
        logger.info("\n" + "=" * 60)
        logger.info("同步完成")
        logger.info("=" * 60)
        logger.info(f"总模板数: {stats['total']}")
        logger.info(f"匹配到知识图谱: {stats['matched']}")
        logger.info(f"成功更新: {stats['updated']}")
        logger.info(f"跳过: {stats['skipped']}")
        logger.info(f"失败: {stats['failed']}")

        # 显示未匹配的模板
        if stats['total'] - stats['matched'] > 0:
            logger.info(f"\n未匹配到知识图谱的模板 ({stats['total'] - stats['matched']}):")
            for template in templates:
                if template.transaction_nature is None:
                    logger.info(f"  - {template.name}: {template.category} / {template.subcategory}")

    finally:
        db.close()


def initialize_knowledge_graph():
    """
    初始化知识图谱（如果不存在）

    从模板数据生成基础的知识图谱
    """
    logger.info("检查知识图谱文件...")

    kg_file = project_root / "app" / "services" / "legal_features" / "knowledge_graph_data.json"

    if kg_file.exists():
        logger.info("知识图谱文件已存在")
        return

    logger.info("知识图谱文件不存在，从模板初始化...")

    # 这里可以添加初始化逻辑
    # 例如从现有的模板分类生成基础的知识图谱结构
    logger.info("跳过初始化（请手动配置知识图谱或运行其他初始化脚本）")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="同步知识图谱法律特征到模板")
    parser.add_argument(
        "--init",
        action="store_true",
        help="初始化知识图谱"
    )

    args = parser.parse_args()

    try:
        if args.init:
            initialize_knowledge_graph()
        else:
            sync_features_to_templates()
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"同步失败: {e}", exc_info=True)
        sys.exit(1)
