"""
添加手机号字段到用户表

Revision ID: 20260119_add_phone_to_users
Revises: 20260119_add_pgvector_support
Create Date: 2026-01-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260119_add_phone_to_users'
down_revision = '20260119_add_pgvector_support'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 phone 字段
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True, comment='手机号'))

    # 创建唯一索引
    op.create_index('idx_users_phone', 'users', ['phone'], unique=True)


def downgrade():
    # 删除索引
    op.drop_index('idx_users_phone', table_name='users')

    # 删除字段
    op.drop_column('users', 'phone')
