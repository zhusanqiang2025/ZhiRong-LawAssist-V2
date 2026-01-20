# migration: add knowledge base type fields
"""add knowledge base type fields

Revision ID: 20250115_add_kb_type_fields
Revises: 20250115_add_knowledge_base
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250115_add_kb_type_fields'
down_revision = '20250115_add_knowledge_base'
branch_labels = None
depends_on = None


def upgrade():
    """添加知识库类型和权限字段"""

    # 1. 为 knowledge_documents 表添加类型和可见性字段
    op.add_column('knowledge_documents', sa.Column('kb_type', sa.String(length=20), nullable=False, server_default='user'))
    op.add_column('knowledge_documents', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('knowledge_documents', sa.Column('status', sa.String(length=20), nullable=False, server_default='active'))

    # 创建索引
    op.create_index(op.f('ix_knowledge_documents_kb_type'), 'knowledge_documents', ['kb_type'])
    op.create_index(op.f('ix_knowledge_documents_is_public'), 'knowledge_documents', ['is_public'])
    op.create_index(op.f('ix_knowledge_documents_status'), 'knowledge_documents', ['status'])

    # 2. 创建系统模块知识库配置表
    op.create_table(
        'system_module_kb_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('module_name', sa.String(length=50), nullable=False),
        sa.Column('system_kb_enabled', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('enabled_system_stores', postgresql.JSON(), nullable=True),
        sa.Column('allow_user_kb', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_module_kb_configs_id'), 'system_module_kb_configs', ['id'], unique=False)
    op.create_index(op.f('ix_system_module_kb_configs_module_name'), 'system_module_kb_configs', ['module_name'], unique=True)


def downgrade():
    """移除知识库类型和权限字段"""

    # 删除索引
    op.drop_index(op.f('ix_system_module_kb_configs_module_name'), table_name='system_module_kb_configs')
    op.drop_index(op.f('ix_system_module_kb_configs_id'), table_name='system_module_kb_configs')

    # 删除表
    op.drop_table('system_module_kb_configs')

    # 删除字段和索引
    op.drop_index(op.f('ix_knowledge_documents_status'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_is_public'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_kb_type'), table_name='knowledge_documents')

    op.drop_column('knowledge_documents', 'status')
    op.drop_column('knowledge_documents', 'is_public')
    op.drop_column('knowledge_documents', 'kb_type')
