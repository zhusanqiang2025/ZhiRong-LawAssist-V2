"""add case_overview to litigation_analysis_session

Revision ID: 20260118_add_case_overview
Revises: d918653949f7
Create Date: 2026-01-18 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260118_add_case_overview'
down_revision = 'd918653949f7'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 case_overview 字段到 litigation_analysis_sessions 表
    op.add_column(
        'litigation_analysis_sessions',
        sa.Column('case_overview', sa.Text(), nullable=True, comment='案件全景综述（AI生成的整体概述）')
    )


def downgrade():
    # 回滚：删除 case_overview 字段
    op.drop_column('litigation_analysis_sessions', 'case_overview')
