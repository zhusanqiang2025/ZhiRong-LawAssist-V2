# add_litigation_analysis_tables.py
"""add litigation analysis tables

Revision ID: add_litigation_analysis_tables
Revises:
Create Date: 2025-01-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_litigation_analysis_tables'
down_revision = '20250112_add_risk_rule_packages'
branch_labels = None
depends_on = None


def upgrade():
    # 创建 litigation_case_packages 表
    op.create_table(
        'litigation_case_packages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('package_id', sa.String(length=64), nullable=False),
        sa.Column('package_name', sa.String(length=128), nullable=False),
        sa.Column('package_category', sa.String(length=64), nullable=True),
        sa.Column('case_type', sa.String(length=64), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('applicable_positions', postgresql.JSON(), nullable=True),
        sa.Column('target_documents', postgresql.JSON(), nullable=True),
        sa.Column('rules', postgresql.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=True),
        sa.Column('version', sa.String(length=32), nullable=True),
        sa.Column('creator_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('litigation_case_packages', 'litigation_case_packages_package_id', ['package_id'], unique=True)
    op.create_index('litigation_case_packages', 'litigation_case_packages_package_category', ['package_category'])
    op.create_index('litigation_case_packages', 'litigation_case_packages_case_type', ['case_type'])
    op.create_index('litigation_case_packages', 'litigation_case_packages_is_active', ['is_active'])

    # 创建 litigation_analysis_sessions 表
    op.create_table(
        'litigation_analysis_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('case_type', sa.String(length=64), nullable=True),
        sa.Column('case_position', sa.String(length=32), nullable=True),
        sa.Column('user_input', sa.Text(), nullable=True),
        sa.Column('package_id', sa.String(length=64), nullable=True),
        sa.Column('document_ids', postgresql.JSON(), nullable=True),
        sa.Column('case_summary', sa.Text(), nullable=True),
        sa.Column('case_strength', postgresql.JSON(), nullable=True),
        sa.Column('evidence_assessment', postgresql.JSON(), nullable=True),
        sa.Column('legal_issues', postgresql.JSON(), nullable=True),
        sa.Column('strategies', postgresql.JSON(), nullable=True),
        sa.Column('risk_warnings', postgresql.JSON(), nullable=True),
        sa.Column('recommendations', postgresql.JSON(), nullable=True),
        sa.Column('timeline_events', postgresql.JSON(), nullable=True),
        sa.Column('evidence_chain', postgresql.JSON(), nullable=True),
        sa.Column('case_diagrams', postgresql.JSON(), nullable=True),
        sa.Column('model_results', postgresql.JSON(), nullable=True),
        sa.Column('selected_model', sa.String(length=32), nullable=True),
        sa.Column('websocket_id', sa.String(length=128), nullable=True),
        sa.Column('report_md', sa.Text(), nullable=True),
        sa.Column('report_json', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('litigation_analysis_sessions', 'litigation_analysis_sessions_session_id', ['session_id'], unique=True)
    op.create_index('litigation_analysis_sessions', 'litigation_analysis_sessions_user_id', ['user_id'])
    op.create_index('litigation_analysis_sessions', 'litigation_analysis_sessions_status', ['status'])
    op.create_index('litigation_analysis_sessions', 'litigation_analysis_sessions_case_type', ['case_type'])

    # 创建 litigation_case_items 表
    op.create_table(
        'litigation_case_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('item_type', sa.String(length=32), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('strength_level', sa.String(length=16), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('analysis', postgresql.JSON(), nullable=True),
        sa.Column('sources', postgresql.JSON(), nullable=True),
        sa.Column('legal_basis', postgresql.JSON(), nullable=True),
        sa.Column('related_evidence', postgresql.JSON(), nullable=True),
        sa.Column('related_strategies', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['litigation_analysis_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('litigation_case_items', 'litigation_case_items_session_id', ['session_id'])
    op.create_index('litigation_case_items', 'litigation_case_items_item_type', ['item_type'])

    # 创建 litigation_evidence 表
    op.create_table(
        'litigation_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.String(length=64), nullable=True),
        sa.Column('evidence_type', sa.String(length=32), nullable=True),
        sa.Column('evidence_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('admissibility', sa.Boolean(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('relevance', sa.Float(), nullable=True),
        sa.Column('facts_to_prove', postgresql.JSON(), nullable=True),
        sa.Column('legal_issues', postgresql.JSON(), nullable=True),
        sa.Column('source_document_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['litigation_analysis_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('litigation_evidence', 'litigation_evidence_session_id', ['session_id'])
    op.create_index('litigation_evidence', 'litigation_evidence_evidence_id', ['evidence_id'])
    op.create_index('litigation_evidence', 'litigation_evidence_evidence_type', ['evidence_type'])

    # 创建 litigation_timeline_events 表
    op.create_table(
        'litigation_timeline_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_date', sa.DateTime(), nullable=True),
        sa.Column('event_type', sa.String(length=32), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('related_documents', postgresql.JSON(), nullable=True),
        sa.Column('related_evidence', postgresql.JSON(), nullable=True),
        sa.Column('legal_significance', sa.Text(), nullable=True),
        sa.Column('statute_implications', postgresql.JSON(), nullable=True),
        sa.Column('importance', sa.String(length=16), nullable=True),
        sa.Column('order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['litigation_analysis_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('litigation_timeline_events', 'litigation_timeline_events_session_id', ['session_id'])
    op.create_index('litigation_timeline_events', 'litigation_timeline_events_event_date', ['event_date'])


def downgrade():
    op.drop_table('litigation_timeline_events')
    op.drop_table('litigation_evidence')
    op.drop_table('litigation_case_items')
    op.drop_table('litigation_analysis_sessions')
    op.drop_table('litigation_case_packages')
