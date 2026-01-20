"""add evaluation_stance to risk_analysis_sessions

Revision ID: 20260116_add_evaluation_stance
Revises: 20260116_add_enhanced_analysis_json
Create Date: 2026-01-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260116_add_evaluation_stance'
down_revision = '20260116_add_enhanced_analysis_json'
branch_labels = None
depends_on = None


def upgrade():
    """添加 evaluation_stance 字段到 risk_analysis_sessions 表"""
    op.add_column(
        'risk_analysis_sessions',
        sa.Column('evaluation_stance', sa.Text(), nullable=True, comment='风险评估立场')
    )


def downgrade():
    """移除 evaluation_stance 字段"""
    op.drop_column('risk_analysis_sessions', 'evaluation_stance')
