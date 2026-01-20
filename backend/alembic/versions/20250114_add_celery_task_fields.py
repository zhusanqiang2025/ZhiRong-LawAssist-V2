# Add Celery task fields to tasks table
# This migration adds fields required for Celery task queue integration

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '20250114_add_celery_task_fields'
down_revision = 'add_litigation_analysis_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add Celery integration fields to the tasks table"""

    # Check if columns exist before adding them
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('tasks')]

    # Add celery_task_id if it doesn't exist
    if 'celery_task_id' not in columns:
        op.add_column(
            'tasks',
            sa.Column('celery_task_id', sa.String(255), nullable=True, unique=True)
        )
        # Create index for celery_task_id
        op.create_index('ix_tasks_celery_task_id', 'tasks', ['celery_task_id'])

    # Add worker_name if it doesn't exist
    if 'worker_name' not in columns:
        op.add_column(
            'tasks',
            sa.Column('worker_name', sa.String(255), nullable=True)
        )

    # Add queue_name if it doesn't exist
    if 'queue_name' not in columns:
        op.add_column(
            'tasks',
            sa.Column('queue_name', sa.String(100), nullable=True)
        )

    # Add task_type if it doesn't exist
    if 'task_type' not in columns:
        op.add_column(
            'tasks',
            sa.Column('task_type', sa.String(100), nullable=True)
        )
        # Create index for task_type
        op.create_index('ix_tasks_task_type', 'tasks', ['task_type'])

    # Add last_retry_at if it doesn't exist
    if 'last_retry_at' not in columns:
        op.add_column(
            'tasks',
            sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True)
        )

    # Add task_params if it doesn't exist
    if 'task_params' not in columns:
        op.add_column(
            'tasks',
            sa.Column('task_params', postgresql.JSON(), nullable=True)
        )

    # Add result_data if it doesn't exist
    if 'result_data' not in columns:
        op.add_column(
            'tasks',
            sa.Column('result_data', postgresql.JSON(), nullable=True)
        )


def downgrade():
    """Remove Celery integration fields from the tasks table"""

    # Drop indexes first
    op.drop_index('ix_tasks_task_type', table_name='tasks')
    op.drop_index('ix_tasks_celery_task_id', table_name='tasks')

    # Remove columns
    op.drop_column('tasks', 'result_data')
    op.drop_column('tasks', 'task_params')
    op.drop_column('tasks', 'last_retry_at')
    op.drop_column('tasks', 'task_type')
    op.drop_column('tasks', 'queue_name')
    op.drop_column('tasks', 'worker_name')
    op.drop_column('tasks', 'celery_task_id')
