# backend/alembic/versions/20250110_add_transaction_features.py
"""
添加交易对价和交易特征字段

Revision ID: 20250110_add_transaction_features
Revises:
Create Date: 2025-01-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250110_add_transaction_features'
down_revision = None  # 替换为你的上一个版本号


def upgrade():
    # 添加新字段
    op.add_column('contract_templates', sa.Column('transaction_consideration', sa.String(200), nullable=True, comment='交易对价'))
    op.add_column('contract_templates', sa.Column('transaction_characteristics', sa.Text(), nullable=True, comment='交易特征'))


def downgrade():
    # 移除字段
    op.drop_column('contract_templates', 'transaction_characteristics')
    op.drop_column('contract_templates', 'transaction_consideration')
