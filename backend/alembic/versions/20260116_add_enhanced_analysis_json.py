# pylint: disable=invalid-name
"""add enhanced_analysis_json field

Revision ID: add_enhanced_analysis_json
Revises: add_history_fields
Create Date: 2026-01-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260116_add_enhanced_analysis_json'
down_revision = 'add_history_fields'
branch_labels = None
depends_on = None


def upgrade():
    """添加 enhanced_analysis_json 字段"""
    op.add_column('risk_analysis_preorganizations',
        sa.Column('enhanced_analysis_json', sa.Text(), nullable=True, comment='完整的增强分析数据JSON')
    )


def downgrade():
    """移除 enhanced_analysis_json 字段"""
    op.drop_column('risk_analysis_preorganizations', 'enhanced_analysis_json')
