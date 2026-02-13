"""add category_id to knowledge_documents

Revision ID: 20260206_add_category_id_to_knowledge_documents
Revises: 20260119_add_phone_to_users
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
import json

# revision identifiers, used by Alembic.
revision = '20260206_add_category_id_to_knowledge_documents'
down_revision = '20260119_add_phone_to_users'
branch_labels = None
depends_on = None


def upgrade():
    """Add category_id and category_name_cache to knowledge_documents table"""

    # Check if columns already exist (avoid duplicate migration errors)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('knowledge_documents')]

    if 'category_id' not in columns:
        # Add new columns
        op.add_column('knowledge_documents', sa.Column('category_id', sa.Integer(), nullable=True))
        op.add_column('knowledge_documents', sa.Column('category_name_cache', sa.String(length=100), nullable=True))

        # Create foreign key constraint
        op.create_foreign_key(
            'fk_knowledge_documents_category_id',
            'knowledge_documents', 'categories',
            ['category_id'], ['id']
        )

        # Create index
        op.create_index('ix_knowledge_documents_category_id', 'knowledge_documents', ['category_id'])

        # Data migration: map old category values to new category_id
        # Query all categories to build name -> id mapping
        categories = conn.execute(sa.text("SELECT id, name FROM categories")).fetchall()
        category_map = {row[1]: row[0] for row in categories}

        # Update knowledge_documents with category_id and category_name_cache
        for doc in conn.execute(sa.text("SELECT id, category FROM knowledge_documents WHERE category IS NOT NULL")).fetchall():
            doc_id = doc[0]
            category_name = doc[1]

            if category_name in category_map:
                conn.execute(
                    sa.text(
                        "UPDATE knowledge_documents "
                        "SET category_id = :cat_id, category_name_cache = :cat_name "
                        "WHERE id = :doc_id"
                    ),
                    {"cat_id": category_map[category_name], "cat_name": category_name, "doc_id": doc_id}
                )

        print(f"[Migration] Updated {len([doc for doc in conn.execute(sa.text('SELECT id, category FROM knowledge_documents WHERE category IS NOT NULL')).fetchall()])} documents with category_id")


def downgrade():
    """Remove category_id and category_name_cache from knowledge_documents table"""

    # Drop index
    op.drop_index('ix_knowledge_documents_category_id', table_name='knowledge_documents')

    # Drop foreign key
    op.drop_constraint('fk_knowledge_documents_category_id', 'knowledge_documents', type_='foreignkey')

    # Drop columns
    op.drop_column('knowledge_documents', 'category_name_cache')
    op.drop_column('knowledge_documents', 'category_id')
