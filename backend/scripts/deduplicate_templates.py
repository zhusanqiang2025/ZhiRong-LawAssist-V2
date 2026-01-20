"""
清理重复的模板记录

对于同名模板，保留最新的记录（按创建时间），归档其他记录
"""
import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SessionLocal
from app.models.contract_template import ContractTemplate
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def deduplicate_templates():
    """清理重复的模板记录"""
    logger.info("[Deduplicate] 开始清理重复模板")

    db = SessionLocal()

    try:
        # 查找所有重复的模板名称
        duplicate_query = db.query(
            ContractTemplate.name,
            func.count().label('count')
        ).group_by(
            ContractTemplate.name
        ).having(
            func.count() > 1
        ).order_by(
            func.count().desc()
        )

        duplicates = duplicate_query.all()
        logger.info(f"[Deduplicate] 找到 {len(duplicates)} 个重复的模板名称")

        archived_count = 0
        kept_count = 0

        for name, count in duplicates:
            # 获取所有同名记录
            templates = db.query(ContractTemplate).filter(
                ContractTemplate.name == name
            ).order_by(
                ContractTemplate.created_at.desc()
            ).all()

            logger.info(f"[Deduplicate] 模板 '{name}' 有 {count} 条记录")

            # 保留第一条（最新的），归档其他
            for i, template in enumerate(templates):
                if i == 0:
                    # 保留最新的一条
                    logger.info(f"  ✓ 保留: {template.id} (created at {template.created_at})")
                    kept_count += 1
                else:
                    # 归档旧的记录
                    template.status = "archived"
                    archived_count += 1
                    logger.info(f"  × 归档: {template.id} (created at {template.created_at})")

        db.commit()

        logger.info(f"[Deduplicate] 清理完成！")
        logger.info(f"[Deduplicate]  保留: {kept_count} 条")
        logger.info(f"[Deduplicate]  归档: {archived_count} 条")

    except Exception as e:
        logger.error(f"[Deduplicate] 清理失败: {str(e)}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    deduplicate_templates()
