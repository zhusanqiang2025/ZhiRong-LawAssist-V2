"""add contract generation indexes

Revision ID: 20260117_add_contract_generation_indexes
Revises: 20260116_add_evaluation_stance
Create Date: 2026-01-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260117_contract_indexes'
down_revision = '20250115_add_kb_type_fields'
branch_labels = None
depends_on = None


def upgrade():
    """添加合同生成任务查询优化索引"""

    # 1. 复合索引：按用户和任务类型查询（最常用）
    op.create_index(
        'ix_tasks_owner_type_created',
        'tasks',
        ['owner_id', 'task_type', 'created_at'],
        unique=False
    )

    # 2. 表达式索引：查询 JSON 字段中的 planning_mode（PostgreSQL）
    # 注意：表达式索引需要 PostgreSQL 数据库支持
    # 使用 execute 执行原始 SQL，因为 Alembic 的 op.create_index 不支持表达式索引
    try:
        op.execute("""
            CREATE INDEX ix_tasks_params_planning_mode
            ON tasks ((task_params->>'planning_mode'))
            WHERE task_params->>'planning_mode' IS NOT NULL;
        """)
    except Exception:
        # 如果数据库不支持表达式索引（如 SQLite），静默失败
        pass

    # 3. 部分索引：仅对合同生成任务的状态查询优化
    # postgresql_where 参数会自动生成带 WHERE 子句的索引
    try:
        op.create_index(
            'ix_tasks_contract_gen_status',
            'tasks',
            ['status', 'updated_at'],
            unique=False,
            postgresql_where=sa.text("task_type = 'contract_generation'")
        )
    except Exception:
        # 如果数据库不支持部分索引，创建普通索引作为降级方案
        op.create_index(
            'ix_tasks_contract_gen_status_fallback',
            'tasks',
            ['status', 'updated_at', 'task_type'],
            unique=False
        )


def downgrade():
    """回滚索引创建"""
    # 删除部分索引（或降级索引）
    try:
        op.drop_index('ix_tasks_contract_gen_status', table_name='tasks')
    except Exception:
        try:
            op.drop_index('ix_tasks_contract_gen_status_fallback', table_name='tasks')
        except Exception:
            pass

    # 删除表达式索引
    try:
        op.execute("DROP INDEX IF EXISTS ix_tasks_params_planning_mode;")
    except Exception:
        pass

    # 删除复合索引
    op.drop_index('ix_tasks_owner_type_created', table_name='tasks')
