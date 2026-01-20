# backend/alembic/versions/20250115_add_risk_analysis_preorganization.py
"""
添加风险评估预整理结果表

Revision ID: 20250115_add_risk_analysis_preorganization
Revises: 20250114_add_celery_task_fields
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250115_add_risk_analysis_preorganization'
down_revision = '20250114_add_celery_task_fields'


def upgrade():
    # 创建 risk_analysis_preorganization 表
    op.create_table(
        'risk_analysis_preorganization',
        sa.Column('id', sa.Integer(), nullable=False),

        # 关联的风险分析会话
        sa.Column('session_id', sa.String(length=64), nullable=False, comment='关联的风险分析会话ID'),

        # 用户需求总结
        sa.Column('user_requirement_summary', sa.Text(), nullable=True, comment='用户需求总结（基于用户输入文本归纳）'),

        # 资料预整理
        sa.Column('documents_info', postgresql.JSON(), nullable=True, comment='资料预整理信息列表'),

        # 事实情况总结
        sa.Column('fact_summary', postgresql.JSON(), nullable=True, comment='基于用户输入和资料分析的事实情况总结'),

        # 合同法律特征
        sa.Column('contract_legal_features', postgresql.JSON(), nullable=True, comment='合同法律特征（从知识图谱查询）'),

        # 合同关系
        sa.Column('contract_relationships', postgresql.JSON(), nullable=True, comment='合同间关系（主合同-补充协议、协议-解除通知等）'),

        # 架构图数据
        sa.Column('architecture_diagram', postgresql.JSON(), nullable=True, comment='股权/投资架构图数据'),

        # 用户确认状态
        sa.Column('is_confirmed', sa.Boolean(), nullable=True, comment='用户是否已确认预整理结果'),

        # 用户修改记录
        sa.Column('user_modifications', postgresql.JSON(), nullable=True, comment='用户修改记录'),

        # 分析模式选择
        sa.Column('analysis_mode', sa.String(length=16), nullable=True, comment='分析模式：single（单模型）或 multi（多模型）'),
        sa.Column('selected_model', sa.String(length=64), nullable=True, comment='单模型模式下选择的模型名称'),

        # 时间戳
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True, comment='用户确认时间'),

        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('ix_risk_analysis_preorganization_id', 'risk_analysis_preorganization', ['id'], unique=False)
    op.create_index('ix_risk_analysis_preorganization_session_id', 'risk_analysis_preorganization', ['session_id'], unique=True)
    op.create_index('ix_risk_analysis_preorganization_is_confirmed', 'risk_analysis_preorganization', ['is_confirmed'], unique=False)

    # 创建外键约束
    op.create_foreign_key(
        'fk_risk_analysis_preorganization_session_id',
        'risk_analysis_preorganization', 'risk_analysis_sessions',
        ['session_id'], ['session_id']
    )


def downgrade():
    # 删除外键约束
    op.drop_constraint('fk_risk_analysis_preorganization_session_id', 'risk_analysis_preorganization', type_='foreignkey')

    # 删除索引
    op.drop_index('ix_risk_analysis_preorganization_is_confirmed', table_name='risk_analysis_preorganization')
    op.drop_index('ix_risk_analysis_preorganization_session_id', table_name='risk_analysis_preorganization')
    op.drop_index('ix_risk_analysis_preorganization_id', table_name='risk_analysis_preorganization')

    # 删除表
    op.drop_table('risk_analysis_preorganization')
