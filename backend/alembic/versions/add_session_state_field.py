"""add session_state to consultation_history

Revision ID: add_session_state_field
Revises: 20260206_add_category_id_to_knowledge_documents
Create Date: 2026-02-06 16:52:42.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

# revision identifiers
revision = 'add_session_state_field'
down_revision = '20260206_add_category_id_to_knowledge_documents'
branch_labels = None
depends_on = None


def upgrade():
    # 添加session_state列，使用JSONB类型
    op.add_column('consultation_history', sa.Column('session_state', JSONB(), nullable=True))


def downgrade():
    # 删除session_state列
    op.drop_column('consultation_history', 'session_state')