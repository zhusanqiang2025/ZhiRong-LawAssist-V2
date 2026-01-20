# backend/scripts/sync_template_status.py
"""
同步模板文件状态

检查数据库中的模板记录与实际文件是否匹配，
将不匹配的模板状态设为 archived
"""
import sys
import os
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.contract_template import ContractTemplate
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_template_status():
    """同步模板状态"""
    logger.info("[Sync] 开始同步模板状态")

    db = SessionLocal()

    try:
        # 获取所有模板
        templates = db.query(ContractTemplate).all()
        logger.info(f"[Sync] 找到 {len(templates)} 个模板记录")

        archived_count = 0
        active_count = 0

        for template in templates:
            file_url = template.file_url

            # 检查文件是否存在
            file_exists = os.path.exists(file_url)

            if not file_exists and template.status == "active":
                # 文件不存在但状态为 active，设为 archived
                template.status = "archived"
                archived_count += 1
                logger.warning(
                    f"[Sync] 文件不存在，归档模板: {template.name} "
                    f"(file_url={file_url})"
                )
            elif file_exists and template.status == "archived":
                # 文件存在但状态为 archived，重新激活
                template.status = "active"
                active_count += 1
                logger.info(
                    f"[Sync] 文件存在，重新激活模板: {template.name} "
                    f"(file_url={file_url})"
                )

        db.commit()

        logger.info(f"[Sync] 同步完成！")
        logger.info(f"[Sync]  归档: {archived_count} 个")
        logger.info(f"[Sync]  激活: {active_count} 个")

    except Exception as e:
        logger.error(f"[Sync] 同步失败: {str(e)}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    sync_template_status()
