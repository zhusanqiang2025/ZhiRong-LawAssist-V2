# backend/alembic/versions/20250112_add_contract_knowledge_types.py
"""
添加合同法律特征知识图谱表

Revision ID: 20250112_add_contract_knowledge_types
Revises: 20250110_add_transaction_features
Create Date: 2025-01-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250112_add_contract_knowledge_types'
down_revision = '20250110_add_transaction_features'


def upgrade():
    # 创建 contract_knowledge_types 表
    op.create_table(
        'contract_knowledge_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, comment='合同类型名称'),
        sa.Column('aliases', postgresql.JSON(), nullable=True, comment='别名列表'),
        sa.Column('category', sa.String(length=100), nullable=True, comment='一级分类'),
        sa.Column('subcategory', sa.String(length=100), nullable=True, comment='二级分类'),

        # 法律特征字段
        sa.Column('transaction_nature', sa.String(length=100), nullable=True, comment='交易性质'),
        sa.Column('contract_object', sa.String(length=100), nullable=True, comment='合同标的'),
        sa.Column('stance', sa.String(length=50), nullable=True, comment='立场'),
        sa.Column('consideration_type', sa.String(length=50), nullable=True, comment='交易对价类型'),
        sa.Column('consideration_detail', sa.Text(), nullable=True, comment='交易对价详情'),
        sa.Column('transaction_characteristics', sa.Text(), nullable=True, comment='交易特征'),
        sa.Column('usage_scenario', sa.Text(), nullable=True, comment='使用场景'),
        sa.Column('legal_basis', postgresql.JSON(), nullable=True, comment='法律依据列表'),

        # 扩展字段
        sa.Column('recommended_template_ids', postgresql.JSON(), nullable=True, comment='推荐模板ID列表'),
        sa.Column('meta_info', postgresql.JSON(), nullable=True, comment='扩展元数据'),

        # 状态控制
        sa.Column('is_active', sa.Boolean(), nullable=True, comment='是否启用'),
        sa.Column('is_system', sa.Boolean(), nullable=True, comment='是否为系统预定义'),

        # 审计字段
        sa.Column('creator_id', sa.Integer(), nullable=True, comment='创建者ID'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),

        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index(op.f('ix_contract_knowledge_types_id'), 'contract_knowledge_types', ['id'], unique=False)
    op.create_index(op.f('ix_contract_knowledge_types_name'), 'contract_knowledge_types', ['name'], unique=True)
    op.create_index(op.f('ix_contract_knowledge_types_category'), 'contract_knowledge_types', ['category'], unique=False)
    op.create_index(op.f('ix_contract_knowledge_types_subcategory'), 'contract_knowledge_types', ['subcategory'], unique=False)
    op.create_index(op.f('ix_contract_knowledge_types_transaction_nature'), 'contract_knowledge_types', ['transaction_nature'], unique=False)
    op.create_index(op.f('ix_contract_knowledge_types_contract_object'), 'contract_knowledge_types', ['contract_object'], unique=False)
    op.create_index(op.f('ix_contract_knowledge_types_stance'), 'contract_knowledge_types', ['stance'], unique=False)
    op.create_index(op.f('ix_contract_knowledge_types_is_active'), 'contract_knowledge_types', ['is_active'], unique=False)


def downgrade():
    # 删除索引
    op.drop_index(op.f('ix_contract_knowledge_types_is_active'), table_name='contract_knowledge_types')
    op.drop_index(op.f('ix_contract_knowledge_types_stance'), table_name='contract_knowledge_types')
    op.drop_index(op.f('ix_contract_knowledge_types_contract_object'), table_name='contract_knowledge_types')
    op.drop_index(op.f('ix_contract_knowledge_types_transaction_nature'), table_name='contract_knowledge_types')
    op.drop_index(op.f('ix_contract_knowledge_types_subcategory'), table_name='contract_knowledge_types')
    op.drop_index(op.f('ix_contract_knowledge_types_category'), table_name='contract_knowledge_types')
    op.drop_index(op.f('ix_contract_knowledge_types_name'), table_name='contract_knowledge_types')
    op.drop_index(op.f('ix_contract_knowledge_types_id'), table_name='contract_knowledge_types')

    # 删除表
    op.drop_table('contract_knowledge_types')
