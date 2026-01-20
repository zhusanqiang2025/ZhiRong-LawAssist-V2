# backend/scripts/batch_upload_templates.py
"""
批量上传模板脚本 (简化版)

功能：
1. 扫描 templates_source 目录下的所有 Markdown 模板文件
2. 从文件名和 frontmatter 解析分类和特征信息
3. 跳过同名或内容相同的模板
4. 批量上传到数据库
"""
import os
import sys
import re
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional
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

# 源目录和目标目录
SOURCE_DIR = project_root / "templates_source"
STORAGE_DIR = project_root.parent / "storage" / "templates"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# 尝试使用配置的数据库 URL，如果失败则使用 SQLite
try:
    from app.database import SessionLocal, engine
    # 确保表存在
    from app.models.contract_template import ContractTemplate
    ContractTemplate.metadata.create_all(bind=engine)
    logger.info("使用 PostgreSQL 数据库")
except Exception as e:
    logger.warning(f"PostgreSQL 连接失败: {e}，使用 SQLite 作为后备")
    # 使用 SQLite 作为后备
    SQLITE_DB = project_root.parent / "data" / "app.db"
    SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_DB}")
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=sqlite_engine)

    # 导入模型并创建表
    from app.models.contract_template import ContractTemplate
    ContractTemplate.metadata.create_all(bind=sqlite_engine)

    logger.info(f"使用 SQLite 数据库: {SQLITE_DB}")


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


class TemplateMetadata:
    """模板元数据"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.content = ""
        self.frontmatter = {}
        self.contract_name = ""
        self.category = ""
        self.subcategory = ""
        self.scenario = ""
        self.tags = []

    def parse(self) -> bool:
        """解析模板文件"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                full_content = f.read()

            # 解析 frontmatter
            frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)', full_content, re.DOTALL)
            if frontmatter_match:
                frontmatter_text = frontmatter_match.group(1)
                self.content = frontmatter_match.group(2)

                # 解析简单的 key: value 格式
                for line in frontmatter_text.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()

                        # 处理列表格式 [a, b, c]
                        if value.startswith('[') and value.endswith(']'):
                            value = value[1:-1].split(',')
                            value = [v.strip().strip('"\'') for v in value if v.strip()]

                        self.frontmatter[key] = value
            else:
                self.content = full_content

            # 从 frontmatter 提取信息
            self.category = self.frontmatter.get('category', '')
            self.subcategory = self.frontmatter.get('type', '')
            self.scenario = self.frontmatter.get('scenario', '')
            self.tags = self.frontmatter.get('tags', [])
            if isinstance(self.tags, str):
                self.tags = [self.tags]

            # 从文件名提取合同名称（最后一部分）
            name_parts = self.filename.replace('.md', '').split('_')
            if len(name_parts) > 0:
                self.contract_name = name_parts[-1]
            else:
                self.contract_name = self.filename.replace('.md', '')

            # 如果 frontmatter 没有分类，从文件名解析
            if not self.category and len(name_parts) >= 2:
                self.category = name_parts[0]
                if len(name_parts) >= 2:
                    self.subcategory = name_parts[1]

            return True

        except Exception as e:
            logger.error(f"解析文件失败 {self.file_path}: {e}")
            return False

    def get_content_hash(self) -> str:
        """获取内容哈希，用于去重"""
        return hashlib.md5(self.content.encode('utf-8')).hexdigest()


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


def find_all_template_files() -> List[str]:
    """查找所有模板文件"""
    template_files = []

    if not SOURCE_DIR.exists():
        logger.error(f"源目录不存在: {SOURCE_DIR}")
        return template_files

    for file_path in SOURCE_DIR.rglob('*.md'):
        template_files.append(str(file_path))

    logger.info(f"找到 {len(template_files)} 个模板文件")
    return template_files


def get_existing_templates(db: Session) -> Dict[str, ContractTemplate]:
    """获取现有模板列表"""
    existing = db.query(ContractTemplate).all()
    return {template.name: template for template in existing}


def upload_template_to_db(
    db: Session,
    metadata: TemplateMetadata
) -> Optional[ContractTemplate]:
    """上传模板到数据库"""
    try:
        # 获取默认特征
        features = get_default_features(metadata.category, metadata.subcategory)

        # 复制文件到存储目录
        target_filename = f"{metadata.contract_name}.md"
        target_path = STORAGE_DIR / target_filename

        with open(metadata.file_path, 'r', encoding='utf-8') as src:
            content = src.read()

        with open(target_path, 'w', encoding='utf-8') as dst:
            dst.write(content)

        # 创建数据库记录
        template = ContractTemplate(
            name=metadata.contract_name,
            category=metadata.category or "通用",
            subcategory=metadata.subcategory,
            description=f"{metadata.category} - {metadata.subcategory}" if metadata.subcategory else metadata.category,
            file_url=str(target_path),
            file_name=metadata.filename,
            file_size=os.path.getsize(metadata.file_path),
            file_type="md",
            is_public=True,
            owner_id=None,
            keywords=metadata.tags,
            tags=metadata.tags,
            status="active",
            # 结构锚点字段
            primary_contract_type=metadata.category or "通用",
            delivery_model="单一交付",
            payment_model="一次性付款",
            risk_level="mid",
            is_recommended=False,
            # V2 法律特征
            transaction_nature=features["transaction_nature"],
            contract_object=features["contract_object"],
            stance=features["stance"],
            # 元数据
            metadata_info={
                "source_file": metadata.file_path,
                "batch_uploaded": True,
                "upload_date": datetime.now().isoformat(),
                "scenario": metadata.scenario,
                "frontmatter": metadata.frontmatter
            }
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        logger.info(f"  ✓ 成功: {metadata.contract_name}")
        return template

    except Exception as e:
        logger.error(f"  ✗ 失败 {metadata.contract_name}: {e}")
        db.rollback()
        return None


def batch_upload_templates(skip_existing: bool = True):
    """批量上传模板"""
    logger.info("=" * 60)
    logger.info("开始批量上传模板")
    logger.info("=" * 60)

    # 1. 查找所有模板文件
    template_files = find_all_template_files()
    if not template_files:
        logger.warning("没有找到模板文件")
        return

    # 2. 获取现有模板
    db = SessionLocal()
    try:
        existing_templates = get_existing_templates(db)
        existing_names = set(existing_templates.keys())
        existing_hashes = {}

        # 计算现有模板的内容哈希
        for name, template in existing_templates.items():
            try:
                if os.path.exists(template.file_url):
                    with open(template.file_url, 'r', encoding='utf-8') as f:
                        content = f.read()
                    existing_hashes[hashlib.md5(content.encode('utf-8')).hexdigest()] = name
            except:
                pass

        logger.info(f"数据库中已有 {len(existing_names)} 个模板")

        # 3. 统计信息
        stats = {
            "total": len(template_files),
            "skipped": 0,
            "uploaded": 0,
            "failed": 0,
            "duplicate_name": 0,
            "duplicate_content": 0
        }

        # 4. 处理每个模板文件
        for i, file_path in enumerate(template_files, 1):
            basename = os.path.basename(file_path)
            logger.info(f"\n[{i}/{stats['total']}] {basename}")

            # 解析元数据
            metadata = TemplateMetadata(file_path)
            if not metadata.parse():
                stats["failed"] += 1
                continue

            logger.info(f"  名称: {metadata.contract_name}")
            logger.info(f"  分类: {metadata.category} / {metadata.subcategory}")

            # 检查名称是否已存在
            if skip_existing and metadata.contract_name in existing_names:
                logger.info(f"  ⊘ 跳过（名称重复）")
                stats["skipped"] += 1
                stats["duplicate_name"] += 1
                continue

            # 内容去重检查
            content_hash = metadata.get_content_hash()
            if content_hash in existing_hashes:
                logger.info(f"  ⊘ 跳过（内容重复，与 '{existing_hashes[content_hash]}' 相同）")
                stats["skipped"] += 1
                stats["duplicate_content"] += 1
                continue

            # 上传到数据库
            template = upload_template_to_db(db, metadata)
            if template:
                stats["uploaded"] += 1
                existing_names.add(metadata.contract_name)
                # 更新内容哈希字典
                existing_hashes[content_hash] = metadata.contract_name
            else:
                stats["failed"] += 1

        # 5. 输出统计
        logger.info("\n" + "=" * 60)
        logger.info("批量上传完成")
        logger.info("=" * 60)
        logger.info(f"总计文件: {stats['total']}")
        logger.info(f"成功上传: {stats['uploaded']}")
        logger.info(f"跳过: {stats['skipped']}")
        logger.info(f"  - 名称重复: {stats['duplicate_name']}")
        logger.info(f"  - 内容重复: {stats['duplicate_content']}")
        logger.info(f"失败: {stats['failed']}")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="批量上传合同模板")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制上传所有模板，不跳过已存在的"
    )

    args = parser.parse_args()

    try:
        batch_upload_templates(skip_existing=not args.force)
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"批量上传失败: {e}", exc_info=True)
        sys.exit(1)
