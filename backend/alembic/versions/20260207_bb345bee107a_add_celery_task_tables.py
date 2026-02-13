"""add_celery_task_tables

Revision ID: bb345bee107a
Revises: add_session_state_field
Create Date: 2026-02-07 11:00:48.940446

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bb345bee107a'
down_revision = 'add_session_state_field'
branch_labels = None
depends_on = None


def upgrade():
    # 创建 Celery 任务元数据表
    op.create_table(
        'celery_taskmeta',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.String(length=155), unique=True, nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('date_done', sa.DateTime(), nullable=True),
        sa.Column('traceback', sa.Text(), nullable=True),
        sa.Column('name', sa.String(length=155), nullable=True),
        sa.Column('args', sa.Text(), nullable=True),
        sa.Column('kwargs', sa.Text(), nullable=True),
        sa.Column('worker', sa.String(length=155), nullable=True),
        sa.Column('retries', sa.Integer(), nullable=True),
        sa.Column('queue', sa.String(length=155), nullable=True)
    )
    
    # 创建 Celery 任务集元数据表
    op.create_table(
        'celery_tasksetmeta',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('taskset_id', sa.String(length=155), unique=True, nullable=False),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('date_done', sa.DateTime(), nullable=True)
    )
    
    # 创建索引优化查询性能
    op.create_index('celery_taskmeta_task_id_idx', 'celery_taskmeta', ['task_id'])
    op.create_index('celery_taskmeta_status_idx', 'celery_taskmeta', ['status'])
    op.create_index('celery_tasksetmeta_taskset_id_idx', 'celery_tasksetmeta', ['taskset_id'])


def downgrade():
    # 删除索引
    op.drop_index('celery_tasksetmeta_taskset_id_idx', table_name='celery_tasksetmeta')
    op.drop_index('celery_taskmeta_status_idx', table_name='celery_taskmeta')
    op.drop_index('celery_taskmeta_task_id_idx', table_name='celery_taskmeta')
    
    # 删除表（注意顺序：先删依赖表）
    op.drop_table('celery_tasksetmeta')
    op.drop_table('celery_taskmeta')