# backend/scripts/sync_template_categories_from_kg.py
"""
从知识图谱同步模板分类

功能：
1. 加载知识图谱数据
2. 使用模糊匹配和关键词匹配将模板映射到知识图谱
3. 更新模板的 category 和 subcategory
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re

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
        {合同名称: {category, subcategory, legal_features, aliases}}
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


def extract_keywords(text: str) -> List[str]:
    """
    从文本中提取关键词

    Args:
        text: 输入文本

    Returns:
        关键词列表
    """
    # 移除常见的后缀
    text = re.sub(r'\(.*?\)', '', text)  # 括号内容
    text = re.sub(r'[（(].*?[)）]', '', text)
    text = text.replace('合同', '').replace('协议', '').replace('书', '').strip()

    # 分词（简单按空格和标点分割）
    keywords = re.split(r'[,，、\s]+', text)

    # 返回非空关键词
    return [kw for kw in keywords if kw]


def calculate_similarity(template_name: str, kg_name: str, kg_info: Dict) -> float:
    """
    计算模板名称与知识图谱合同名称的相似度

    Args:
        template_name: 模板名称
        kg_name: 知识图谱合同名称
        kg_info: 知识图谱信息

    Returns:
        相似度分数 (0-1)
    """
    score = 0.0

    # 1. 精确匹配
    if template_name == kg_name:
        return 1.0

    # 2. 别名匹配
    aliases = kg_info.get('aliases', [])
    for alias in aliases:
        if template_name == alias:
            return 0.95

    # 3. 包含关系（模板名包含KG名或反之）
    if kg_name in template_name or template_name in kg_name:
        score += 0.7

    # 4. 别名包含关系
    for alias in aliases:
        if alias in template_name or template_name in alias:
            score += 0.65
            break

    # 5. 关键词匹配
    template_keywords = set(extract_keywords(template_name))
    kg_keywords = set(extract_keywords(kg_name))

    if template_keywords and kg_keywords:
        # 计算关键词重叠度
        intersection = template_keywords & kg_keywords
        union = template_keywords | kg_keywords

        if intersection:
            jaccard = len(intersection) / len(union)
            score += jaccard * 0.5

    return min(score, 1.0)


def match_template_to_kg(
    template: ContractTemplate,
    kg_data: Dict,
    threshold: float = 0.6
) -> Optional[Tuple[str, Dict, float]]:
    """
    匹配模板到知识图谱

    Args:
        template: 数据库模板对象
        kg_data: 知识图谱数据
        threshold: 相似度阈值

    Returns:
        (知识图谱名称, 知识图谱信息, 相似度分数) 或 None
    """
    template_name = template.name

    best_match = None
    best_score = 0.0

    for kg_name, kg_info in kg_data.items():
        score = calculate_similarity(template_name, kg_name, kg_info)

        if score > best_score:
            best_score = score
            best_match = (kg_name, kg_info, score)

    # 只有当相似度超过阈值时才返回匹配
    if best_score >= threshold:
        return best_match

    return None


def sync_template_categories():
    """同步模板分类到知识图谱标准"""
    logger.info("=" * 60)
    logger.info("开始同步模板分类到知识图谱标准")
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
            "high_confidence": 0,    # 高置信度匹配 (>0.8)
            "medium_confidence": 0,  # 中置信度匹配 (0.6-0.8)
            "low_confidence": 0,     # 低置信度匹配 (<0.6)
            "updated": 0,
            "skipped": 0,
            "failed": 0
        }

        # 4. 遍历模板进行匹配和更新
        for template in templates:
            logger.info(f"\n处理模板: {template.name}")
            logger.info(f"  当前分类: {template.category} / {template.subcategory}")

            # 匹配知识图谱
            match_result = match_template_to_kg(template, kg_data)

            if not match_result:
                logger.info(f"  ⊘ 未匹配到知识图谱（相似度低于阈值）")
                stats["low_confidence"] += 1
                stats["skipped"] += 1
                continue

            kg_name, kg_info, score = match_result

            # 根据相似度分类
            if score >= 0.8:
                confidence = "高"
                stats["high_confidence"] += 1
            elif score >= 0.6:
                confidence = "中"
                stats["medium_confidence"] += 1
            else:
                confidence = "低"
                stats["low_confidence"] += 1

            kg_category = kg_info['category']
            kg_subcategory = kg_info['subcategory']

            logger.info(f"  ✓ 匹配到知识图谱: {kg_name} (相似度: {score:.2f}, 置信度: {confidence})")
            logger.info(f"    KG分类: {kg_category} / {kg_subcategory}")

            # 检查是否需要更新
            needs_update = (
                template.category != kg_category or
                template.subcategory != kg_subcategory
            )

            if not needs_update:
                logger.info(f"  ⊘ 分类已是最新，跳过")
                stats["skipped"] += 1
                continue

            # 只有高置信度的匹配才自动更新
            if score < 0.8:
                logger.info(f"  ⊘ 相似度较低，不自动更新")
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
                template.metadata_info['kg_synced'] = True
                template.metadata_info['old_category'] = old_category
                template.metadata_info['old_subcategory'] = old_subcategory
                template.metadata_info['kg_match'] = {
                    'name': kg_name,
                    'category': kg_category,
                    'subcategory': kg_subcategory,
                    'similarity': score,
                    'confidence': confidence
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
        logger.info("同步完成")
        logger.info("=" * 60)
        logger.info(f"总模板数: {stats['total']}")
        logger.info(f"高置信度匹配 (>0.8): {stats['high_confidence']}")
        logger.info(f"中置信度匹配 (0.6-0.8): {stats['medium_confidence']}")
        logger.info(f"低置信度匹配 (<0.6): {stats['low_confidence']}")
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

        # 7. 显示低置信度匹配的模板（可能需要手动处理）
        logger.info("\n" + "=" * 60)
        logger.info("需要手动检查的模板（低置信度匹配）")
        logger.info("=" * 60)

        for template in templates:
            match_result = match_template_to_kg(template, kg_data)
            if match_result:
                kg_name, kg_info, score = match_result
                if score < 0.8:
                    logger.info(f"\n{template.name} (相似度: {score:.2f})")
                    logger.info(f"  当前分类: {template.category} / {template.subcategory}")
                    logger.info(f"  建议分类: {kg_info['category']} / {kg_info['subcategory']}")
                    logger.info(f"  匹配到: {kg_name}")

    finally:
        db.close()


if __name__ == "__main__":
    try:
        sync_template_categories()
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"同步失败: {e}", exc_info=True)
        sys.exit(1)
