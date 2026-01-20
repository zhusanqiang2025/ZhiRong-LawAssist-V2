# migration: add knowledge base tables
"""add knowledge base tables

Revision ID: 20250115_add_knowledge_base
Revises: 20250115_add_risk_analysis_preorganization
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250115_add_knowledge_base'
down_revision = '20250115_add_risk_analysis_preorganization'
branch_labels = None
depends_on = None


def upgrade():
    """创建知识库相关表"""

    # 1. 创建知识库配置表
    op.create_table(
        'knowledge_base_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('config_key', sa.String(length=100), nullable=False),
        sa.Column('config_value', postgresql.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_base_configs_config_key'), 'knowledge_base_configs', ['config_key'], unique=True)
    op.create_index(op.f('ix_knowledge_base_configs_id'), 'knowledge_base_configs', ['id'], unique=False)

    # 2. 创建用户模块偏好设置表
    op.create_table(
        'user_module_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('module_name', sa.String(length=50), nullable=False),
        sa.Column('knowledge_base_enabled', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('enabled_stores', postgresql.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_module_preferences_id'), 'user_module_preferences', ['id'], unique=False)
    # 创建唯一约束
    op.create_unique_constraint('unique_user_module', 'user_module_preferences', ['user_id', 'module_name'])

    # 3. 创建知识库文档表
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doc_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.String(length=200), nullable=True),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('extra_data', postgresql.JSON(), nullable=True),  # 改名避免 SQLAlchemy 保留字冲突
        sa.Column('vectorized', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('vector_ids', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_documents_doc_id'), 'knowledge_documents', ['doc_id'], unique=True)
    op.create_index(op.f('ix_knowledge_documents_id'), 'knowledge_documents', ['id'], unique=False)


def downgrade():
    """删除知识库相关表"""

    # 删除表（按依赖关系逆序）
    op.drop_index(op.f('ix_knowledge_documents_id'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_doc_id'), table_name='knowledge_documents')
    op.drop_table('knowledge_documents')

    op.drop_constraint('unique_user_module', 'user_module_preferences')
    op.drop_index(op.f('ix_user_module_preferences_id'), table_name='user_module_preferences')
    op.drop_table('user_module_preferences')

    op.drop_index(op.f('ix_knowledge_base_configs_config_key'), table_name='knowledge_base_configs')
    op.drop_index(op.f('ix_knowledge_base_configs_id'), table_name='knowledge_base_configs')
    op.drop_table('knowledge_base_configs')
