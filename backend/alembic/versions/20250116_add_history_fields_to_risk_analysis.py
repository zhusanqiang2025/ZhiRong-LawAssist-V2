# pylint: disable=invalid-name
"""add history fields to risk_analysis

Revision ID: add_history_fields
Revises:
Create Date: 2025-01-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_history_fields'
down_revision = '20250115_add_kb_type_fields'
branch_labels = None
depends_on = None


def upgrade():
    """添加历史任务管理字段"""
    # 添加新字段
    op.add_column('risk_analysis_sessions', sa.Column('title', sa.String(255), nullable=True, comment='会话标题（用于历史记录显示）'))
    op.add_column('risk_analysis_sessions', sa.Column('is_unread', sa.Boolean(), nullable=True, server_default='1', comment='是否未读'))
    op.add_column('risk_analysis_sessions', sa.Column('is_background', sa.Boolean(), nullable=True, server_default='0', comment='是否为后台任务'))


def downgrade():
    """移除历史任务管理字段"""
    op.drop_column('risk_analysis_sessions', 'is_background')
    op.drop_column('risk_analysis_sessions', 'is_unread')
    op.drop_column('risk_analysis_sessions', 'title')
