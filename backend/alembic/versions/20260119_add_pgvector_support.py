"""add pgvector support for intelligent template search

Revision ID: 20260119_add_pgvector_support
Revises: 20260118_add_case_overview
Create Date: 2026-01-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260119_add_pgvector_support'
down_revision = '20260118_add_case_overview'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 安装 pgvector 扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 2. 添加 embedding_updated_at 字段 (DateTime)
    op.add_column(
        'contract_templates',
        sa.Column(
            'embedding_updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='向量最后更新时间'
        )
    )

    # 3. 添加 embedding_text_hash 字段 (String)
    op.add_column(
        'contract_templates',
        sa.Column(
            'embedding_text_hash',
            sa.String(64),
            nullable=True,
            comment='向量源文本的SHA256哈希'
        )
    )

    # 4. 为 embedding_text_hash 创建索引
    op.create_index(
        'idx_contract_templates_embedding_text_hash',
        'contract_templates',
        ['embedding_text_hash']
    )

    # 5. 为 embedding_updated_at 创建索引
    op.create_index(
        'idx_contract_templates_embedding_updated_at',
        'contract_templates',
        ['embedding_updated_at']
    )

    # 6. 添加 embedding 向量字段 (使用 ARRAY 类型作为临时方案)
    # 注意: 由于 Alembic 可能不直接支持 pgvector.Vector 类型,
    # 我们使用原生 SQL 添加向量列
    op.execute("""
        ALTER TABLE contract_templates
        ADD COLUMN embedding vector(1024)
    """)

    # 7. 为 embedding 创建 HNSW 索引 (余弦相似度)
    # 这将显著提升向量搜索性能
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_contract_templates_embedding_cosine
        ON contract_templates
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # 8. 添加注释
    op.execute("""
        COMMENT ON COLUMN contract_templates.embedding IS '模板内容的向量嵌入 (BGE-M3, 1024维)'
    """)


def downgrade():
    # 回滚: 删除索引和字段

    # 删除 HNSW 索引
    op.execute('DROP INDEX IF EXISTS idx_contract_templates_embedding_cosine')

    # 删除索引
    op.drop_index('idx_contract_templates_embedding_updated_at', table_name='contract_templates')
    op.drop_index('idx_contract_templates_embedding_text_hash', table_name='contract_templates')

    # 删除字段
    op.drop_column('contract_templates', 'embedding')
    op.drop_column('contract_templates', 'embedding_text_hash')
    op.drop_column('contract_templates', 'embedding_updated_at')

    # 注意: 不删除 pgvector 扩展,因为可能被其他表使用
    # 如需删除,取消注释下面这行:
    # op.execute('DROP EXTENSION IF EXISTS vector')
