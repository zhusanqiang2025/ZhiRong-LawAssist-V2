# backend/app/database/indexes.py
"""
数据库索引优化脚本
"""
from sqlalchemy import text
import logging
from . import SessionLocal

logger = logging.getLogger(__name__)

class DatabaseIndexer:
    """数据库索引管理器"""

    # 建议创建的索引列表
    INDEXES = [
        # 用户表索引
        {
            "name": "idx_users_email",
            "table": "users",
            "columns": ["email"],
            "unique": True,
            "description": "用户邮箱唯一索引"
        },
        {
            "name": "idx_users_created_at",
            "table": "users",
            "columns": ["created_at"],
            "unique": False,
            "description": "用户创建时间索引"
        },
        {
            "name": "idx_users_is_active",
            "table": "users",
            "columns": ["is_active"],
            "unique": False,
            "description": "用户状态索引"
        },

        # 任务表索引
        {
            "name": "idx_tasks_owner_id",
            "table": "tasks",
            "columns": ["owner_id"],
            "unique": False,
            "description": "任务所有者索引"
        },
        {
            "name": "idx_tasks_status",
            "table": "tasks",
            "columns": ["status"],
            "unique": False,
            "description": "任务状态索引"
        },
        {
            "name": "idx_tasks_created_at",
            "table": "tasks",
            "columns": ["created_at"],
            "unique": False,
            "description": "任务创建时间索引"
        },
        {
            "name": "idx_tasks_updated_at",
            "table": "tasks",
            "columns": ["updated_at"],
            "unique": False,
            "description": "任务更新时间索引"
        },
        {
            "name": "idx_tasks_owner_status",
            "table": "tasks",
            "columns": ["owner_id", "status"],
            "unique": False,
            "description": "任务所有者和状态复合索引"
        },
        {
            "name": "idx_tasks_owner_created",
            "table": "tasks",
            "columns": ["owner_id", "created_at"],
            "unique": False,
            "description": "任务所有者和创建时间复合索引"
        },

        # 合同模板表索引
        {
            "name": "idx_contract_templates_category",
            "table": "contract_templates",
            "columns": ["category"],
            "unique": False,
            "description": "合同模板分类索引"
        },
        {
            "name": "idx_contract_templates_is_public",
            "table": "contract_templates",
            "columns": ["is_public"],
            "unique": False,
            "description": "合同模板公开状态索引"
        },
        {
            "name": "idx_contract_templates_created_at",
            "table": "contract_templates",
            "columns": ["created_at"],
            "unique": False,
            "description": "合同模板创建时间索引"
        },
        {
            "name": "idx_contract_templates_category_public",
            "table": "contract_templates",
            "columns": ["category", "is_public"],
            "unique": False,
            "description": "合同模板分类和公开状态复合索引"
        },

        # 分类表索引
        {
            "name": "idx_categories_name",
            "table": "categories",
            "columns": ["name"],
            "unique": True,
            "description": "分类名称唯一索引"
        },

        # 会话表索引（如果存在）
        {
            "name": "idx_chat_sessions_user_id",
            "table": "chat_sessions",
            "columns": ["user_id"],
            "unique": False,
            "description": "聊天会话用户索引"
        },
        {
            "name": "idx_chat_sessions_created_at",
            "table": "chat_sessions",
            "columns": ["created_at"],
            "unique": False,
            "description": "聊天会话创建时间索引"
        }
    ]

    @classmethod
    def create_all_indexes(cls) -> bool:
        """创建所有建议的索引"""
        db = SessionLocal()
        try:
            success_count = 0
            total_count = len(cls.INDEXES)

            logger.info(f"开始创建 {total_count} 个数据库索引...")

            for index_config in cls.INDEXES:
                if cls._create_index(db, index_config):
                    success_count += 1

            logger.info(f"索引创建完成：{success_count}/{total_count} 成功")
            return success_count == total_count

        except Exception as e:
            logger.error(f"创建索引时发生错误: {e}")
            return False
        finally:
            db.close()

    @classmethod
    def _create_index(cls, db, index_config: dict) -> bool:
        """创建单个索引"""
        try:
            # 检查索引是否已存在
            if cls._index_exists(db, index_config["name"]):
                logger.info(f"索引 '{index_config['name']}' 已存在，跳过创建")
                return True

            # 构建创建索引的 SQL
            columns_str = ", ".join(index_config["columns"])
            unique_str = "UNIQUE " if index_config["unique"] else ""

            sql = f"""
            CREATE {unique_str}INDEX {index_config["name"]}
            ON {index_config["table"]} ({columns_str})
            """

            # 执行创建索引
            db.execute(text(sql))
            db.commit()

            logger.info(f"成功创建索引: {index_config['name']} - {index_config['description']}")
            return True

        except Exception as e:
            logger.error(f"创建索引 '{index_config['name']}' 失败: {e}")
            db.rollback()
            return False

    @classmethod
    def _index_exists(cls, db, index_name: str) -> bool:
        """检查索引是否存在"""
        try:
            # PostgreSQL 查询索引是否存在
            sql = """
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE indexname = :index_name
            )
            """
            result = db.execute(text(sql), {"index_name": index_name})
            return result.scalar()
        except Exception as e:
            logger.error(f"检查索引 '{index_name}' 是否存在时发生错误: {e}")
            return False

    @classmethod
    def analyze_database(cls) -> dict:
        """分析数据库性能"""
        db = SessionLocal()
        try:
            analysis = {}

            # 获取表统计信息
            tables = ["users", "tasks", "contract_templates", "categories"]
            for table in tables:
                if cls._table_exists(db, table):
                    analysis[table] = cls._get_table_stats(db, table)

            # 获取索引使用情况
            analysis["indexes"] = cls._get_index_usage(db)

            return analysis

        except Exception as e:
            logger.error(f"分析数据库时发生错误: {e}")
            return {}
        finally:
            db.close()

    @classmethod
    def _table_exists(cls, db, table_name: str) -> bool:
        """检查表是否存在"""
        try:
            sql = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = :table_name
            )
            """
            result = db.execute(text(sql), {"table_name": table_name})
            return result.scalar()
        except Exception:
            return False

    @classmethod
    def _get_table_stats(cls, db, table_name: str) -> dict:
        """获取表统计信息"""
        try:
            sql = f"""
            SELECT
                COUNT(*) as row_count,
                pg_size_pretty(pg_total_relation_size('{table_name}')) as total_size,
                pg_size_pretty(pg_relation_size('{table_name}')) as table_size
            FROM {table_name}
            """
            result = db.execute(text(sql))
            row = result.first()

            return {
                "row_count": row.row_count,
                "total_size": row.total_size,
                "table_size": row.table_size
            }
        except Exception as e:
            logger.error(f"获取表 '{table_name}' 统计信息失败: {e}")
            return {}

    @classmethod
    def _get_index_usage(cls, db) -> list:
        """获取索引使用情况"""
        try:
            sql = """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes
            ORDER BY idx_scan DESC
            """
            result = db.execute(text(sql))
            return [dict(row) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"获取索引使用情况失败: {e}")
            return []

    @classmethod
    def optimize_database(cls) -> dict:
        """优化数据库"""
        db = SessionLocal()
        try:
            results = {}

            # 更新表统计信息
            tables = ["users", "tasks", "contract_templates", "categories"]
            for table in tables:
                if cls._table_exists(db, table):
                    try:
                        db.execute(text(f"ANALYZE {table}"))
                        logger.info(f"已更新表 '{table}' 的统计信息")
                    except Exception as e:
                        logger.error(f"更新表 '{table}' 统计信息失败: {e}")

            # 清理无效索引
            results["cleaned_indexes"] = cls._clean_invalid_indexes(db)

            db.commit()
            logger.info("数据库优化完成")
            return results

        except Exception as e:
            logger.error(f"优化数据库时发生错误: {e}")
            db.rollback()
            return {}
        finally:
            db.close()

    @classmethod
    def _clean_invalid_indexes(cls, db) -> int:
        """清理无效索引"""
        try:
            # 查找未使用的索引
            sql = """
            SELECT indexname
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0 AND indexname NOT LIKE '%_pkey'
            """
            result = db.execute(text(sql))
            unused_indexes = [row.indexname for row in result.fetchall()]

            cleaned_count = 0
            for index_name in unused_indexes:
                try:
                    # 注意：删除索引要谨慎，这里只是记录
                    logger.warning(f"发现未使用的索引: {index_name}")
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"处理索引 '{index_name}' 时发生错误: {e}")

            return cleaned_count

        except Exception as e:
            logger.error(f"清理无效索引失败: {e}")
            return 0


def create_database_indexes():
    """创建数据库索引的便捷函数"""
    return DatabaseIndexer.create_all_indexes()

def analyze_database():
    """分析数据库的便捷函数"""
    return DatabaseIndexer.analyze_database()

def optimize_database():
    """优化数据库的便捷函数"""
    return DatabaseIndexer.optimize_database()

if __name__ == "__main__":
    # 如果直接运行此脚本，则创建索引
    from app.core.logger import setup_logging
    setup_logging()
    logger = logging.getLogger("legal_assistant")
    logger.info("开始创建数据库索引...")

    success = create_database_indexes()
    if success:
        logger.info("所有索引创建成功！")
    else:
        logger.error("部分索引创建失败，请查看日志详情。")