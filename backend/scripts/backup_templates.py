# backend/scripts/backup_templates.py
"""
备份合同模板数据

功能：
1. 导出所有模板数据到JSON文件
2. 支持选择性备份（按分类、按ID范围）
3. 生成备份清单
"""
import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional, List
from datetime import datetime
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


def template_to_dict(template: ContractTemplate) -> dict:
    """
    将模板对象转换为字典

    Args:
        template: 模板对象

    Returns:
        模板数据字典
    """
    return {
        'id': template.id,
        'name': template.name,
        'file_url': template.file_url,
        'description': template.description,
        'category': template.category,
        'subcategory': template.subcategory,
        'primary_contract_type': template.primary_contract_type,
        'tags': template.tags,
        'is_public': template.is_public,
        'status': template.status,
        'version': template.version,
        'language': template.language,
        'complexity': template.complexity,
        'transaction_nature': template.transaction_nature,
        'contract_object': template.contract_object,
        'stance': template.stance,
        'transaction_consideration': template.transaction_consideration,
        'transaction_characteristics': template.transaction_characteristics,
        'usage_scenario': template.usage_scenario,
        'metadata_info': template.metadata_info,
        'created_at': template.created_at.isoformat() if template.created_at else None,
        'updated_at': template.updated_at.isoformat() if template.updated_at else None,
    }


def backup_templates(
    category: Optional[str] = None,
    limit: Optional[int] = None,
    output_dir: Optional[Path] = None
) -> str:
    """
    备份模板数据

    Args:
        category: 按分类过滤（可选）
        limit: 限制备份的模板数量（可选）
        output_dir: 输出目录（可选）

    Returns:
        备份文件路径
    """
    logger.info("=" * 60)
    logger.info("开始备份模板数据")
    logger.info("=" * 60)

    # 确定输出目录
    if output_dir is None:
        output_dir = project_root.parent / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成备份文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = output_dir / f"templates_backup_{timestamp}.json"

    logger.info(f"备份文件: {backup_file}")

    db = SessionLocal()
    try:
        # 构建查询
        query = db.query(ContractTemplate)

        if category:
            query = query.filter(ContractTemplate.category == category)
            logger.info(f"按分类过滤: {category}")

        if limit:
            query = query.limit(limit)
            logger.info(f"限制数量: {limit}")

        templates = query.all()

        logger.info(f"找到 {len(templates)} 个模板")

        # 转换为字典
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'total_count': len(templates),
            'filters': {
                'category': category,
                'limit': limit
            },
            'templates': [template_to_dict(t) for t in templates]
        }

        # 保存到文件
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✓ 备份完成: {backup_file}")
        logger.info(f"  备份了 {len(templates)} 个模板")

        # 生成备份清单
        manifest_file = output_dir / f"templates_manifest_{timestamp}.txt"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            f.write(f"备份时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"备份文件: {backup_file.name}\n")
            f.write(f"模板数量: {len(templates)}\n")
            f.write(f"\n模板清单:\n")
            f.write("-" * 60 + "\n")

            # 按分类统计
            category_stats = {}
            for template in templates:
                cat = template.category or "未分类"
                if cat not in category_stats:
                    category_stats[cat] = []
                category_stats[cat].append(template.name)

            for cat, names in sorted(category_stats.items()):
                f.write(f"\n[{cat}] {len(names)}个\n")
                for name in names:
                    f.write(f"  - {name}\n")

        logger.info(f"✓ 备份清单: {manifest_file}")

        return str(backup_file)

    finally:
        db.close()


def restore_templates(backup_file: Path, dry_run: bool = True):
    """
    从备份文件恢复模板数据

    Args:
        backup_file: 备份文件路径
        dry_run: 干运行模式，不实际恢复
    """
    logger.info("=" * 60)
    logger.info("开始恢复模板数据")
    if dry_run:
        logger.info("【干运行模式】不会实际恢复数据")
    logger.info("=" * 60)

    if not backup_file.exists():
        logger.error(f"备份文件不存在: {backup_file}")
        return

    # 读取备份文件
    with open(backup_file, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)

    logger.info(f"备份时间: {backup_data['timestamp']}")
    logger.info(f"模板数量: {backup_data['total_count']}")

    db = SessionLocal()
    try:
        restored_count = 0
        failed_count = 0

        for template_dict in backup_data['templates']:
            template_id = template_dict['id']
            template_name = template_dict['name']

            try:
                if not dry_run:
                    # 检查模板是否已存在
                    existing = db.query(ContractTemplate).filter(
                        ContractTemplate.id == template_id
                    ).first()

                    if existing:
                        # 更新现有模板
                        for key, value in template_dict.items():
                            if key != 'id':
                                setattr(existing, key, value)
                    else:
                        # 创建新模板
                        new_template = ContractTemplate(**template_dict)
                        db.add(new_template)

                    db.commit()

                restored_count += 1

                if restored_count % 10 == 0:
                    logger.info(f"处理进度: {restored_count}/{backup_data['total_count']}")

            except Exception as e:
                failed_count += 1
                db.rollback()
                logger.error(f"恢复失败 [{template_id}] {template_name}: {e}")

        logger.info("\n" + "=" * 60)
        logger.info("恢复完成")
        logger.info("=" * 60)
        logger.info(f"成功恢复: {restored_count}")
        logger.info(f"失败: {failed_count}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='备份或恢复合同模板数据')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # 备份命令
    backup_parser = subparsers.add_parser('backup', help='备份模板数据')
    backup_parser.add_argument('--category', type=str, help='按分类过滤')
    backup_parser.add_argument('--limit', type=int, help='限制备份的模板数量')
    backup_parser.add_argument('--output-dir', type=str, help='输出目录')

    # 恢复命令
    restore_parser = subparsers.add_parser('restore', help='从备份恢复模板数据')
    restore_parser.add_argument('backup_file', type=str, help='备份文件路径')
    restore_parser.add_argument('--dry-run', action='store_true', help='干运行模式')
    restore_parser.add_argument('--no-dry-run', action='store_true', help='实际执行恢复')

    args = parser.parse_args()

    try:
        if args.command == 'backup':
            output_dir = Path(args.output_dir) if args.output_dir else None
            backup_file = backup_templates(
                category=args.category,
                limit=args.limit,
                output_dir=output_dir
            )
            logger.info(f"\n备份文件已保存至: {backup_file}")

        elif args.command == 'restore':
            backup_file = Path(args.backup_file)
            # 默认使用干运行模式，除非明确指定 --no-dry-run
            dry_run = not args.no_dry_run
            restore_templates(backup_file, dry_run=dry_run)

        else:
            parser.print_help()

    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"操作失败: {e}", exc_info=True)
        sys.exit(1)
