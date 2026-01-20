# backend/scripts/fix_subcategory_mapping.py
"""
修正模板的subcategory名称映射

功能：
1. 加载知识图谱数据，获取正确的subcategory名称
2. 识别数据库中错误的subcategory名称
3. 批量更新为正确的subcategory名称
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Set

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


# Subcategory 映射表（错误的 -> 正确的）
SUBCATEGORY_MAPPING = {
    # 非典型商事合同下的映射
    "股权协议": "股权与投资",
    "回购协议": "股权与投资",
    "股权合同": "股权与投资",

    # 民法典典型合同下的映射
    "承揽协议": "承揽合同",
    "委托协议": "委托合同",

    # 劳动与人力资源下的映射
    "劳务协议": "灵活用工",
    "劳动合同": "标准劳动关系",

    # 通用框架与兜底协议下的映射
    "合作框架": "意向与框架",
    "承诺书": "单方声明与承诺",

    # 可以继续添加其他映射...
}


def get_valid_subcategories_from_kg() -> Dict[str, Set[str]]:
    """
    从知识图谱获取有效的subcategory列表

    Returns:
        {category: set([subcategory1, subcategory2, ...])}
    """
    kg_file = project_root / "app" / "services" / "legal_features" / "knowledge_graph_data.json"

    if not kg_file.exists():
        logger.warning(f"知识图谱文件不存在: {kg_file}")
        return {}

    valid_subcategories = {}

    try:
        import json
        with open(kg_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data.get('contract_types', []):
            category = item.get('category')
            subcategory = item.get('subcategory')

            if category and subcategory:
                if category not in valid_subcategories:
                    valid_subcategories[category] = set()
                valid_subcategories[category].add(subcategory)

        logger.info(f"从知识图谱加载了 {len(valid_subcategories)} 个一级分类的有效subcategory")
        return valid_subcategories

    except Exception as e:
        logger.error(f"加载知识图谱失败: {e}")
        return {}


def fix_subcategory_mapping():
    """修正subcategory映射"""
    logger.info("=" * 60)
    logger.info("开始修正subcategory映射")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # 1. 获取所有模板
        templates = db.query(ContractTemplate).all()
        logger.info(f"数据库中有 {len(templates)} 个模板")

        # 2. 获取知识图谱中的有效subcategory
        valid_subcategories = get_valid_subcategories_from_kg()

        # 3. 统计信息
        stats = {
            "total": len(templates),
            "checked": 0,
            "needs_fix": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0
        }

        # 4. 构建完整的映射表（手动映射 + 知识图谱验证）
        logger.info("\n" + "=" * 60)
        logger.info("检查subcategory映射")
        logger.info("=" * 60)

        for template in templates:
            stats["checked"] += 1

            current_category = template.category
            current_subcategory = template.subcategory

            if not current_subcategory:
                stats["skipped"] += 1
                continue

            # 检查是否需要修正
            new_subcategory = None

            # 优先使用手动映射表
            if current_subcategory in SUBCATEGORY_MAPPING:
                new_subcategory = SUBCATEGORY_MAPPING[current_subcategory]
                logger.info(f"\n{template.name}")
                logger.info(f"  当前: {current_category} / {current_subcategory}")
                logger.info(f"  映射规则: {current_subcategory} -> {new_subcategory}")

            # 检查subcategory是否在知识图谱中
            elif current_category in valid_subcategories:
                if current_subcategory not in valid_subcategories[current_category]:
                    # subcategory不在知识图谱中，可能需要修正
                    logger.info(f"\n{template.name}")
                    logger.info(f"  当前: {current_category} / {current_subcategory}")
                    logger.info(f"  警告: subcategory不在知识图谱中")

                    # 尝试模糊匹配
                    valid_subs = valid_subcategories[current_category]
                    for valid_sub in valid_subs:
                        if current_subcategory in valid_sub or valid_sub in current_subcategory:
                            new_subcategory = valid_sub
                            logger.info(f"  模糊匹配: {current_subcategory} -> {new_subcategory}")
                            break

                    if not new_subcategory:
                        logger.info(f"  未找到匹配，保持原样")
                        stats["skipped"] += 1
                        continue
                else:
                    stats["skipped"] += 1
                    continue
            else:
                stats["skipped"] += 1
                continue

            if new_subcategory and new_subcategory != current_subcategory:
                stats["needs_fix"] += 1

                # 更新模板
                try:
                    old_subcategory = current_subcategory
                    template.subcategory = new_subcategory

                    # 更新元数据
                    if not template.metadata_info:
                        template.metadata_info = {}
                    if 'subcategory_fixed' not in template.metadata_info:
                        template.metadata_info['subcategory_fixed'] = {}
                    template.metadata_info['subcategory_fixed']['old_subcategory'] = old_subcategory
                    template.metadata_info['subcategory_fixed']['new_subcategory'] = new_subcategory

                    db.commit()
                    db.refresh(template)

                    logger.info(f"  ✓ 更新成功: {old_subcategory} -> {new_subcategory}")
                    stats["updated"] += 1

                except Exception as e:
                    logger.error(f"  ✗ 更新失败: {e}")
                    db.rollback()
                    stats["failed"] += 1

        # 5. 输出统计
        logger.info("\n" + "=" * 60)
        logger.info("修正完成")
        logger.info("=" * 60)
        logger.info(f"总模板数: {stats['total']}")
        logger.info(f"已检查: {stats['checked']}")
        logger.info(f"需要修正: {stats['needs_fix']}")
        logger.info(f"成功更新: {stats['updated']}")
        logger.info(f"跳过: {stats['skipped']}")
        logger.info(f"失败: {stats['failed']}")

        # 6. 验证更新结果
        logger.info("\n" + "=" * 60)
        logger.info("验证更新结果")
        logger.info("=" * 60)

        # 统计更新后的subcategory分布
        from sqlalchemy import func

        # 显示每个category下的subcategory分布
        categories = db.query(ContractTemplate.category).distinct().all()
        for (category,) in categories:
            logger.info(f"\n{category}:")

            subcat_counts = db.query(
                ContractTemplate.subcategory,
                func.count(ContractTemplate.id)
            ).filter(
                ContractTemplate.category == category
            ).group_by(ContractTemplate.subcategory).all()

            for subcat, count in sorted(subcat_counts, key=lambda x: x[1], reverse=True):
                logger.info(f"  {subcat}: {count}个模板")

    finally:
        db.close()


if __name__ == "__main__":
    try:
        fix_subcategory_mapping()
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"修正失败: {e}", exc_info=True)
        sys.exit(1)
