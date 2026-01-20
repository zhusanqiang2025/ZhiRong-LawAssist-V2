# backend/alembic/versions/20250112_add_risk_rule_packages.py
"""
添加风险评估规则包表

Revision ID: 20250112_add_risk_rule_packages
Revises: 20250112_add_contract_knowledge_types
Create Date: 2025-01-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250112_add_risk_rule_packages'
down_revision = '20250112_add_contract_knowledge_types'


def upgrade():
    # 创建 risk_rule_packages 表
    op.create_table(
        'risk_rule_packages',
        sa.Column('id', sa.Integer(), nullable=False),

        # 基本信息
        sa.Column('package_id', sa.String(length=64), nullable=False, comment='规则包唯一标识'),
        sa.Column('package_name', sa.String(length=128), nullable=False, comment='规则包名称'),
        sa.Column('package_category', sa.String(length=64), nullable=True, comment='规则包分类'),
        sa.Column('description', sa.Text(), nullable=True, comment='规则包描述'),

        # 适用场景
        sa.Column('applicable_scenarios', postgresql.JSON(), nullable=True, comment='适用场景列表'),
        sa.Column('target_entities', postgresql.JSON(), nullable=True, comment='目标实体类型'),

        # 规则列表
        sa.Column('rules', postgresql.JSON(), nullable=False, comment='规则列表'),

        # 状态管理
        sa.Column('is_active', sa.Boolean(), nullable=True, comment='是否启用'),
        sa.Column('is_system', sa.Boolean(), nullable=True, comment='是否系统预定义'),
        sa.Column('version', sa.String(length=32), nullable=True, comment='版本号'),

        # 元数据
        sa.Column('creator_id', sa.Integer(), nullable=True, comment='创建者ID'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),

        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('ix_risk_rule_packages_id', 'risk_rule_packages', ['id'], unique=False)
    op.create_index('ix_risk_rule_packages_package_id', 'risk_rule_packages', ['package_id'], unique=True)
    op.create_index('ix_risk_rule_packages_package_category', 'risk_rule_packages', ['package_category'], unique=False)
    op.create_index('ix_risk_rule_packages_is_active', 'risk_rule_packages', ['is_active'], unique=False)


def downgrade():
    # 删除索引
    op.drop_index('ix_risk_rule_packages_is_active', table_name='risk_rule_packages')
    op.drop_index('ix_risk_rule_packages_package_category', table_name='risk_rule_packages')
    op.drop_index('ix_risk_rule_packages_package_id', table_name='risk_rule_packages')
    op.drop_index('ix_risk_rule_packages_id', table_name='risk_rule_packages')

    # 删除表
    op.drop_table('risk_rule_packages')
