"""Mako template for Alembic migration scripts"""

"""merge heads before adding case_overview

Revision ID: d918653949f7
Revises: 20260116_add_evaluation_stance, 20260118_add_contract_review_task
Create Date: 2026-01-18 15:11:36.387223

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd918653949f7'
down_revision = ('20260116_add_evaluation_stance', '20260118_add_contract_review_task')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
