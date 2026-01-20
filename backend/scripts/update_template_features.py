# backend/scripts/update_template_features.py
"""
更新现有模板的分类和法律特征

功能：
1. 扫描 templates_source 目录获取正确的分类信息
2. 根据模板名称匹配数据库中的模板
3. 更新模板的分类、子分类和法律特征
"""
import os
import sys
import re
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 源目录
SOURCE_DIR = project_root / "templates_source"

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# 尝试使用配置的数据库 URL，如果失败则使用 SQLite
try:
    from app.database import SessionLocal, engine
    logger.info("使用 PostgreSQL 数据库")
except Exception as e:
    logger.warning(f"PostgreSQL 连接失败: {e}，使用 SQLite 作为后备")
    SQLITE_DB = project_root.parent / "data" / "app.db"
    SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_DB}")
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=sqlite_engine)
    logger.info(f"使用 SQLite 数据库: {SQLITE_DB}")

from app.models.contract_template import ContractTemplate


# 默认法律特征映射（基于分类）
DEFAULT_FEATURES_MAP = {
    # 民法典典型合同
    "买卖合同": {
        "transaction_nature": "转移所有权",
        "contract_object": "货物",
        "stance": "中立"
    },
    "借款合同": {
        "transaction_nature": "融资借贷",
        "contract_object": "资金",
        "stance": "中立"
    },
    "租赁合同": {
        "transaction_nature": "许可使用",
        "contract_object": "不动产",
        "stance": "中立"
    },
    "建设工程合同": {
        "transaction_nature": "提供服务",
        "contract_object": "工程",
        "stance": "甲方"
    },
    "承揽合同": {
        "transaction_nature": "提供服务",
        "contract_object": "智力成果",
        "stance": "中立"
    },
    "技术合同": {
        "transaction_nature": "提供服务",
        "contract_object": "智力成果",
        "stance": "中立"
    },
    "委托合同": {
        "transaction_nature": "提供服务",
        "contract_object": "服务",
        "stance": "中立"
    },
    "合伙合同": {
        "transaction_nature": "合作经营",
        "contract_object": "股权",
        "stance": "平衡"
    },
    "劳动合同": {
        "transaction_nature": "劳动用工",
        "contract_object": "劳动力",
        "stance": "中立"
    },
    # 行业特定合同
    "股权转让协议": {
        "transaction_nature": "转移所有权",
        "contract_object": "股权",
        "stance": "中立"
    },
    "股权类协议": {
        "transaction_nature": "合作经营",
        "contract_object": "股权",
        "stance": "中立"
    },
    # 非典型合同
    "合伙协议": {
        "transaction_nature": "合作经营",
        "contract_object": "股权",
        "stance": "平衡"
    },
}


def parse_template_file(file_path: str) -> Optional[Dict]:
    """
    解析模板文件获取元数据

    Returns:
        {
            'name': '合同名称',
            'category': '分类',
            'subcategory': '子分类',
            'scenario': '场景',
            'tags': [],
            'content_hash': '内容哈希'
        }
    """
    try:
        filename = os.path.basename(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            full_content = f.read()

        # 解析 frontmatter
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)', full_content, re.DOTALL)
        if frontmatter_match:
            frontmatter_text = frontmatter_match.group(1)
            content = frontmatter_match.group(2)

            # 解析简单的 key: value 格式
            frontmatter = {}
            for line in frontmatter_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    # 处理列表格式 [a, b, c]
                    if value.startswith('[') and value.endswith(']'):
                        value = value[1:-1].split(',')
                        value = [v.strip().strip('"\'') for v in value if v.strip()]

                    frontmatter[key] = value
        else:
            content = full_content
            frontmatter = {}

        # 提取信息
        category = frontmatter.get('category', '')
        subcategory = frontmatter.get('type', '')
        scenario = frontmatter.get('scenario', '')
        tags = frontmatter.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]

        # 从文件名提取合同名称（最后一部分）
        name_parts = filename.replace('.md', '').split('_')
        contract_name = name_parts[-1] if len(name_parts) > 0 else filename.replace('.md', '')

        # 如果 frontmatter 没有分类，从文件名解析
        if not category and len(name_parts) >= 2:
            category = name_parts[0]
            if len(name_parts) >= 2:
                subcategory = name_parts[1]

        # 计算内容哈希（用于匹配）
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        return {
            'name': contract_name,
            'category': category,
            'subcategory': subcategory,
            'scenario': scenario,
            'tags': tags,
            'content_hash': content_hash,
            'file_path': file_path
        }

    except Exception as e:
        logger.error(f"解析文件失败 {file_path}: {e}")
        return None


def scan_source_templates() -> Dict[str, Dict]:
    """
    扫描源目录获取模板元数据

    Returns:
        {模板名称: 元数据字典}
    """
    source_templates = {}

    if not SOURCE_DIR.exists():
        logger.error(f"源目录不存在: {SOURCE_DIR}")
        return source_templates

    for file_path in SOURCE_DIR.rglob('*.md'):
        metadata = parse_template_file(str(file_path))
        if metadata:
            source_templates[metadata['name']] = metadata

    logger.info(f"从源目录扫描到 {len(source_templates)} 个模板")
    return source_templates


def get_default_features(category: str, subcategory: str) -> Dict:
    """根据分类获取默认法律特征"""
    # 先尝试精确匹配分类
    if category in DEFAULT_FEATURES_MAP:
        return DEFAULT_FEATURES_MAP[category].copy()

    # 尝试模糊匹配
    for key, features in DEFAULT_FEATURES_MAP.items():
        if key in category or category in key:
            return features.copy()

    # 默认特征
    return {
        "transaction_nature": "提供服务",
        "contract_object": "服务",
        "stance": "中立"
    }


def match_templates_by_content(
    db_templates: List[ContractTemplate],
    source_metadata: Dict[str, Dict]
) -> Dict[str, ContractTemplate]:
    """
    通过内容匹配模板

    Returns:
        {源模板名称: 数据库模板对象}
    """
    matches = {}

    # 计算数据库模板的内容哈希
    db_template_hashes = {}
    for template in db_templates:
        try:
            if os.path.exists(template.file_url):
                with open(template.file_url, 'r', encoding='utf-8') as f:
                    content = f.read()
                content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                db_template_hashes[content_hash] = template
        except:
            pass

    # 通过内容哈希匹配
    for name, metadata in source_metadata.items():
        if metadata['content_hash'] in db_template_hashes:
            matches[name] = db_template_hashes[metadata['content_hash']]

    logger.info(f"通过内容匹配到 {len(matches)} 个模板")
    return matches


def match_templates_by_name(
    db_templates: List[ContractTemplate],
    source_metadata: Dict[str, Dict],
    content_matches: Dict[str, ContractTemplate]
) -> Dict[str, ContractTemplate]:
    """
    通过名称匹配剩余的模板

    Returns:
        {源模板名称: 数据库模板对象}
    """
    matches = {}
    matched_names = set(content_matches.keys())

    # 创建名称到模板的映射
    name_to_template = {t.name: t for t in db_templates if t.name not in matched_names}

    # 精确匹配
    for name, metadata in source_metadata.items():
        if name in name_to_template and name not in matched_names:
            matches[name] = name_to_template[name]
            matched_names.add(name)

    logger.info(f"通过名称匹配到 {len(matches)} 个额外模板")
    return matches


def update_template_features():
    """更新模板的分类和法律特征"""
    logger.info("=" * 60)
    logger.info("开始更新模板分类和法律特征")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # 1. 获取所有数据库模板
        db_templates = db.query(ContractTemplate).all()
        logger.info(f"数据库中有 {len(db_templates)} 个模板")

        # 2. 扫描源目录获取正确的元数据
        source_metadata = scan_source_templates()

        if not source_metadata:
            logger.warning("没有找到源模板文件")
            return

        # 3. 匹配模板
        content_matches = match_templates_by_content(db_templates, source_metadata)
        name_matches = match_templates_by_name(db_templates, source_metadata, content_matches)

        # 合并匹配结果
        all_matches = {**content_matches, **name_matches}

        logger.info(f"总共匹配到 {len(all_matches)} 个模板")

        # 4. 更新模板
        stats = {
            "total": len(all_matches),
            "updated": 0,
            "skipped": 0,
            "failed": 0
        }

        for source_name, db_template in all_matches.items():
            metadata = source_metadata[source_name]

            logger.info(f"\n处理: {db_template.name}")
            logger.info(f"  当前分类: {db_template.category} / {db_template.subcategory}")
            logger.info(f"  源分类: {metadata['category']} / {metadata['subcategory']}")

            # 检查是否需要更新
            needs_update = (
                db_template.category != metadata['category'] or
                db_template.subcategory != metadata['subcategory'] or
                not db_template.transaction_nature or
                not db_template.contract_object
            )

            if not needs_update:
                logger.info(f"  ⊘ 跳过（已是最新）")
                stats["skipped"] += 1
                continue

            # 获取正确的特征
            features = get_default_features(metadata['category'], metadata['subcategory'])

            # 更新模板
            try:
                db_template.category = metadata['category'] or db_template.category
                db_template.subcategory = metadata['subcategory']
                db_template.transaction_nature = features["transaction_nature"]
                db_template.contract_object = features["contract_object"]
                db_template.stance = features["stance"]

                # 更新描述
                if metadata['subcategory']:
                    db_template.description = f"{metadata['category']} - {metadata['subcategory']}"
                else:
                    db_template.description = metadata['category']

                # 更新标签
                if metadata['tags']:
                    db_template.tags = metadata['tags']
                    db_template.keywords = metadata['tags']

                # 更新元数据
                if not db_template.metadata_info:
                    db_template.metadata_info = {}
                db_template.metadata_info.update({
                    "scenario": metadata['scenario'],
                    "source_matched": True,
                    "features_updated_at": datetime.now().isoformat()
                })

                db.commit()
                db.refresh(db_template)

                logger.info(f"  ✓ 更新成功")
                logger.info(f"    分类: {db_template.category} / {db_template.subcategory}")
                logger.info(f"    特征: {db_template.transaction_nature} / {db_template.contract_object} / {db_template.stance}")
                stats["updated"] += 1

            except Exception as e:
                logger.error(f"  ✗ 更新失败: {e}")
                db.rollback()
                stats["failed"] += 1

        # 5. 输出统计
        logger.info("\n" + "=" * 60)
        logger.info("更新完成")
        logger.info("=" * 60)
        logger.info(f"匹配到: {stats['total']} 个模板")
        logger.info(f"成功更新: {stats['updated']} 个")
        logger.info(f"跳过: {stats['skipped']} 个")
        logger.info(f"失败: {stats['failed']} 个")

        # 显示未匹配的模板
        matched_db_ids = set(t.id for t in all_matches.values())
        unmatched = [t for t in db_templates if t.id not in matched_db_ids]
        if unmatched:
            logger.info(f"\n未匹配的模板 ({len(unmatched)}):")
            for t in unmatched[:20]:
                logger.info(f"  - {t.name}: {t.category}")

    finally:
        db.close()


if __name__ == "__main__":
    try:
        update_template_features()
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"更新失败: {e}", exc_info=True)
        sys.exit(1)
