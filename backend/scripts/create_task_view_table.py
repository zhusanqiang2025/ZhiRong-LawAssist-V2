# backend/scripts/create_task_view_table.py
"""
创建 task_view_records 表的脚本

这是一个安全的数据库迁移脚本，只创建新表，不修改任何现有数据。
"""
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine
from app.models.task_view import TaskViewRecord
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_task_view_table():
    """
    创建 task_view_records 表

    这个操作是安全的，因为：
    1. 只创建新表，不修改任何现有表
    2. 不影响任何现有数据（知识图谱、规则、任务等）
    3. 如果表已存在，checkfirst=True 会跳过创建
    """
    try:
        logger.info("开始创建 task_view_records 表...")

        # 创建表（如果不存在）
        TaskViewRecord.__table__.create(engine, checkfirst=True)

        logger.info("✅ task_view_records 表创建成功！")
        logger.info("表结构:")
        logger.info(f"  - 表名: {TaskViewRecord.__tablename__}")
        logger.info(f"  - 字段: id, task_id, user_id, has_viewed_result, first_viewed_at, last_viewed_at, view_count, created_at")
        logger.info(f"  - 外键: task_id -> tasks.id, user_id -> users.id")

        return True

    except Exception as e:
        logger.error(f"❌ 创建表失败: {e}")
        return False

def verify_table():
    """验证表是否创建成功"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)

        # 获取所有表名
        tables = inspector.get_table_names()

        if 'task_view_records' in tables:
            logger.info("✅ 验证通过: task_view_records 表已存在于数据库中")
            return True
        else:
            logger.warning("⚠️  task_view_records 表未找到")
            logger.info(f"数据库中的表: {tables}")
            return False

    except Exception as e:
        logger.error(f"❌ 验证失败: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("数据库迁移: 创建 task_view_records 表")
    logger.info("=" * 60)

    # 创建表
    success = create_task_view_table()

    if success:
        # 验证表
        verify_table()
        logger.info("=" * 60)
        logger.info("迁移完成！")
        logger.info("=" * 60)
    else:
        logger.error("=" * 60)
        logger.error("迁移失败，请检查错误信息")
        logger.error("=" * 60)
        sys.exit(1)
