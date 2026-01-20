"""add contract review task and extend models

Revision ID: 20260118_add_contract_review_task
Revises: 20260117_contract_indexes
Create Date: 2026-01-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260118_add_contract_review_task'
down_revision = '20260117_contract_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """升级数据库：添加合同审查任务表和扩展现有表"""

    # ========== 1. 创建 contract_review_tasks 表 ==========
    op.create_table(
        'contract_review_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.String(length=32), nullable=True, server_default='review'),
        sa.Column('stance', sa.String(length=16), nullable=True),
        sa.Column('use_custom_rules', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('use_langgraph', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('transaction_structures', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True, server_default='pending'),
        sa.Column('metadata_info', sa.JSON(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['contract_id'], ['contract_docs.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('ix_contract_review_tasks_id', 'contract_review_tasks', ['id'])
    op.create_index('ix_contract_review_tasks_contract_id', 'contract_review_tasks', ['contract_id'])
    op.create_index('ix_contract_review_tasks_user_id', 'contract_review_tasks', ['user_id'])
    op.create_index('ix_contract_review_tasks_status', 'contract_review_tasks', ['status'])
    op.create_index('ix_contract_review_tasks_celery_task_id', 'contract_review_tasks', ['celery_task_id'])

    # ========== 2. 扩展 contract_docs 表 ==========
    # 添加新字段
    op.add_column('contract_docs', sa.Column('transaction_structures', sa.JSON(), nullable=True, comment='用户选择的交易结构列表'))
    op.add_column('contract_docs', sa.Column('entity_risk_cache', sa.JSON(), nullable=True, comment='主体风险缓存信息'))
    op.add_column('contract_docs', sa.Column('current_review_task_id', sa.Integer(), nullable=True, comment='当前审查任务ID'))

    # 添加外键约束
    op.create_foreign_key('contract_docs_current_review_task_id_fkey', 'contract_docs', 'contract_review_tasks', ['current_review_task_id'], ['id'])

    # ========== 3. 扩展 contract_review_items 表 ==========
    # 添加新字段
    op.add_column('contract_review_items', sa.Column('entity_risk', sa.JSON(), nullable=True, comment='主体风险信息 (单个关联主体)'))
    op.add_column('contract_review_items', sa.Column('related_entities', sa.JSON(), nullable=True, comment="关联的主体名称列表; 示例: ['XX公司', 'YY科技有限公司']"))


def downgrade():
    """回滚数据库更改"""

    # ========== 1. 删除 contract_review_items 表的新字段 ==========
    op.drop_column('contract_review_items', 'related_entities')
    op.drop_column('contract_review_items', 'entity_risk')

    # ========== 2. 删除 contract_docs 表的新字段和外键 ==========
    op.drop_constraint('contract_docs_current_review_task_id_fkey', 'contract_docs')
    op.drop_column('contract_docs', 'current_review_task_id')
    op.drop_column('contract_docs', 'entity_risk_cache')
    op.drop_column('contract_docs', 'transaction_structures')

    # ========== 3. 删除 contract_review_tasks 表 ==========
    op.drop_index('ix_contract_review_tasks_celery_task_id', table_name='contract_review_tasks')
    op.drop_index('ix_contract_review_tasks_status', table_name='contract_review_tasks')
    op.drop_index('ix_contract_review_tasks_user_id', table_name='contract_review_tasks')
    op.drop_index('ix_contract_review_tasks_contract_id', table_name='contract_review_tasks')
    op.drop_index('ix_contract_review_tasks_id', table_name='contract_review_tasks')
    op.drop_table('contract_review_tasks')
