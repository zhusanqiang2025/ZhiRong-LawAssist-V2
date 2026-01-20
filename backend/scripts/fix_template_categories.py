# backend/scripts/fix_template_categories.py
"""
修复模板的分类信息，使其与知识图谱的分类系统对齐

功能：
1. 加载知识图谱数据，获取每个合同类型的正确分类
2. 根据模板名称匹配知识图谱中的合同类型
3. 更新模板的 category 和 subcategory 字段
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Optional, List

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
        {合同名称: {category, subcategory, legal_features}}
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
                kg_data[name] = {
                    'category': item.get('category'),
                    'subcategory': item.get('subcategory'),
                    'aliases': item.get('aliases', []),
                    'legal_features': item.get('legal_features')
                }

        logger.info(f"从知识图谱加载了 {len(kg_data)} 个合同类型定义")
        return kg_data

    except Exception as e:
        logger.error(f"加载知识图谱失败: {e}")
        return kg_data


# 数据库分类名称到知识图谱分类名称的映射表
CATEGORY_MAPPING = {
    # 旧分类名称 -> 新分类名称（知识图谱标准名称）
    "非典型合同": "非典型商事合同",
    "非典型合同类型": "非典型商事合同",
    "补充与特殊合同类型": "通用框架与兜底协议",
    "兜底模板": "通用框架与兜底协议",
    "个人创客及自由职业者合同": "民法典典型合同",  # 需要根据具体模板进一步细分
}


def normalize_category_name(category: str) -> str:
    """
    将数据库中的分类名称标准化为知识图谱的标准名称

    Args:
        category: 数据库中的分类名称

    Returns:
        标准化后的分类名称
    """
    return CATEGORY_MAPPING.get(category, category)


def match_template_to_kg_category(
    template: ContractTemplate,
    kg_data: Dict
) -> Optional[Dict]:
    """
    匹配模板到知识图谱的正确分类

    Args:
        template: 数据库模板对象
        kg_data: 知识图谱数据

    Returns:
        {category, subcategory, legal_features} 或 None
    """
    template_name = template.name

    # 1. 精确名称匹配
    if template_name in kg_data:
        return kg_data[template_name]

    # 2. 别名匹配
    for kg_name, kg_info in kg_data.items():
        aliases = kg_info.get('aliases', [])
        if isinstance(aliases, list):
            for alias in aliases:
                if alias in template_name or template_name in alias:
                    return kg_info

    # 3. 模糊名称匹配（包含关系）
    for kg_name, kg_info in kg_data.items():
        if kg_name in template_name or template_name in kg_name:
            return kg_info

    return None


def fix_template_categories():
    """修复模板的分类信息"""
    logger.info("=" * 60)
    logger.info("开始修复模板分类信息")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # 1. 加载知识图谱
        kg_data = load_knowledge_graph()

        if not kg_data:
            logger.warning("知识图谱为空，无法修复")
            return

        # 2. 获取所有模板
        templates = db.query(ContractTemplate).all()
        logger.info(f"数据库中有 {len(templates)} 个模板")

        # 3. 统计信息
        stats = {
            "total": len(templates),
            "category_normalized": 0,  # 分类名称标准化
            "matched": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0
        }

        # 4. 第一遍：标准化分类名称（修复错误的分类名称）
        logger.info("\n" + "=" * 60)
        logger.info("第一步：标准化分类名称")
        logger.info("=" * 60)

        for template in templates:
            original_category = template.category
            normalized_category = normalize_category_name(original_category)

            if normalized_category != original_category:
                logger.info(f"\n标准化分类: {template.name}")
                logger.info(f"  旧分类: {original_category}")
                logger.info(f"  新分类: {normalized_category}")

                try:
                    template.category = normalized_category
                    # 记录到元数据
                    if not template.metadata_info:
                        template.metadata_info = {}
                    if 'category_normalized' not in template.metadata_info:
                        template.metadata_info['category_normalized'] = {}
                    template.metadata_info['category_normalized']['old_category'] = original_category
                    template.metadata_info['category_normalized']['new_category'] = normalized_category

                    db.commit()
                    db.refresh(template)
                    stats["category_normalized"] += 1
                    logger.info(f"  ✓ 分类标准化成功")
                except Exception as e:
                    logger.error(f"  ✗ 标准化失败: {e}")
                    db.rollback()
                    stats["failed"] += 1

        logger.info(f"\n分类名称标准化完成：{stats['category_normalized']} 个模板已更新")

        # 5. 第二遍：匹配知识图谱并更新详细分类
        logger.info("\n" + "=" * 60)
        logger.info("第二步：匹配知识图谱并更新详细分类")
        logger.info("=" * 60)

        # 4. 遍历模板进行匹配和更新
        for template in templates:
            logger.info(f"\n处理模板: {template.name}")
            logger.info(f"  当前分类: {template.category} / {template.subcategory}")

            # 匹配知识图谱
            kg_info = match_template_to_kg_category(template, kg_data)

            if not kg_info:
                logger.info(f"  ⊘ 未匹配到知识图谱")
                stats["skipped"] += 1
                continue

            stats["matched"] += 1
            kg_category = kg_info['category']
            kg_subcategory = kg_info['subcategory']

            logger.info(f"  ✓ 匹配到知识图谱: {kg_category} / {kg_subcategory}")

            # 检查是否需要更新
            needs_update = (
                template.category != kg_category or
                template.subcategory != kg_subcategory
            )

            if not needs_update:
                logger.info(f"  ⊘ 分类已是最新，跳过")
                stats["skipped"] += 1
                continue

            # 更新模板
            try:
                old_category = template.category
                old_subcategory = template.subcategory

                template.category = kg_category
                template.subcategory = kg_subcategory

                # 同时更新 primary_contract_type
                template.primary_contract_type = kg_category

                # 更新元数据
                if not template.metadata_info:
                    template.metadata_info = {}
                template.metadata_info['category_fixed'] = True
                template.metadata_info['old_category'] = old_category
                template.metadata_info['old_subcategory'] = old_subcategory
                template.metadata_info['kg_category_match'] = {
                    'category': kg_category,
                    'subcategory': kg_subcategory
                }

                db.commit()
                db.refresh(template)

                logger.info(f"  ✓ 更新成功")
                logger.info(f"    旧分类: {old_category} / {old_subcategory}")
                logger.info(f"    新分类: {template.category} / {template.subcategory}")
                stats["updated"] += 1

            except Exception as e:
                logger.error(f"  ✗ 更新失败: {e}")
                db.rollback()
                stats["failed"] += 1

        # 5. 输出统计
        logger.info("\n" + "=" * 60)
        logger.info("修复完成")
        logger.info("=" * 60)
        logger.info(f"总模板数: {stats['total']}")
        logger.info(f"分类名称标准化: {stats['category_normalized']}")
        logger.info(f"匹配到知识图谱: {stats['matched']}")
        logger.info(f"成功更新: {stats['updated']}")
        logger.info(f"跳过: {stats['skipped']}")
        logger.info(f"失败: {stats['failed']}")

        # 6. 验证更新结果
        logger.info("\n" + "=" * 60)
        logger.info("验证更新结果")
        logger.info("=" * 60)

        # 统计更新后的分类分布
        from sqlalchemy import func
        category_counts = db.query(
            ContractTemplate.category,
            func.count(ContractTemplate.id)
        ).group_by(ContractTemplate.category).all()

        logger.info("\n更新后的分类分布:")
        for category, count in sorted(category_counts, key=lambda x: x[1], reverse=True):
            logger.info(f"  {category}: {count}个模板")

    finally:
        db.close()


if __name__ == "__main__":
    try:
        fix_template_categories()
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"修复失败: {e}", exc_info=True)
        sys.exit(1)
