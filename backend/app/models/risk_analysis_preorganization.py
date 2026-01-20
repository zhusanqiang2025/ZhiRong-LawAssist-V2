# backend/app/models/risk_analysis_preorganization.py
"""
风险评估预整理结果数据库模型

用于存储文档预整理的中间结果，供用户确认和修改后再进行风险分析。
这个模型与 RiskAnalysisSession 是一对一关系，独立存储预整理阶段的详细信息。
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class RiskAnalysisPreorganization(Base):
    """
    风险评估预整理结果表

    存储文档预整理的完整结果，包括：
    - 用户需求总结
    - 资料详细信息
    - 事实情况总结
    - 合同法律特征
    - 合同关系
    - 架构图数据
    - 用户确认状态
    - 用户修改记录
    """
    __tablename__ = "risk_analysis_preorganization"

    id = Column(Integer, primary_key=True, index=True)

    # 关联的风险分析会话
    session_id = Column(String(64), ForeignKey("risk_analysis_sessions.session_id"), nullable=False, unique=True, index=True, comment="关联的风险分析会话ID")

    # 用户需求总结
    user_requirement_summary = Column(Text, nullable=True, comment="用户需求总结（基于用户输入文本归纳）")

    # 资料预整理（JSON格式存储每份资料的详细信息）
    # 格式示例：
    # [
    #   {
    #     "file_name": "合同.pdf",
    #     "signing_date": "2024-01-01",
    #     "file_type": "买卖合同",
    #     "entities": ["甲方公司", "乙方公司"],
    #     "amount": "100万元",
    #     "subject": "房屋买卖",
    #     "core_content": "甲方同意向乙方出售..."
    #   }
    # ]
    documents_info = Column(JSON, nullable=True, comment="资料预整理信息列表")

    # 事实情况总结（JSON格式）
    # 格式示例：
    # {
    #   "timeline": ["2024-01-01: 签署合同", "2024-02-01: 付款"],
    #   "location": "北京市",
    #   "entities": ["甲方公司", "乙方公司", "丙方"],
    #   "core_events": ["签署合同", "付款", "交付"],
    #   "contract_name": "房屋买卖合同",
    #   "legal_relationships": ["买卖关系", "担保关系"]
    # }
    fact_summary = Column(JSON, nullable=True, comment="基于用户输入和资料分析的事实情况总结")

    # 合同法律特征（JSON格式，从知识图谱查询）
    # 格式示例：
    # {
    #   "transaction_nature": "所有权转让",
    #   "contract_object": "不动产",
    #   "stance": "中立",
    #   "consideration_type": "有偿",
    #   "consideration_detail": "双方约定",
    #   "transaction_characteristics": "...",
    #   "usage_scenario": "...",
    #   "legal_basis": ["民法典第595条"]
    # }
    contract_legal_features = Column(JSON, nullable=True, comment="合同法律特征（从知识图谱查询）")

    # 合同关系（JSON格式）
    # 格式示例：
    # [
    #   {
    #     "relationship_type": "master_supplement",
    #     "main_contract": "主合同.pdf",
    #     "related_contract": "补充协议.pdf",
    #     "confidence": 0.95
    #   },
    #   {
    #     "relationship_type": "termination",
    #     "main_contract": "主合同.pdf",
    #     "related_contract": "解除通知.pdf",
    #     "confidence": 0.98
    #   }
    # ]
    contract_relationships = Column(JSON, nullable=True, comment="合同间关系（主合同-补充协议、协议-解除通知等）")

    # 架构图数据（JSON格式，仅当检测到股权/投资结构时生成）
    # 格式示例：
    # {
    #   "diagram_type": "equity_structure",
    #   "format": "mermaid",
    #   "code": "graph TD\n  A[公司A] -->|50%| B[公司B]",
    #   "svg_data": "...",  # 可选，SVG格式数据
    #   "metadata": {
    #     "companies": ["公司A", "公司B"],
    #     "total_nodes": 2
    #   }
    # }
    architecture_diagram = Column(JSON, nullable=True, comment="股权/投资架构图数据")

    # 完整的增强分析数据（JSON格式）
    # 格式示例：
    # {
    #   "transaction_summary": "交易故事叙述",
    #   "contract_status": "磋商/履约/违约/终止",
    #   "dispute_focus": "争议焦点描述",
    #   "parties": [
    #     {
    #       "name": "主体名称",
    #       "role": "甲方/乙方",
    #       "obligations": ["义务1", "义务2"],
    #       "rights": ["权利1", "权利2"],
    #       "risk_exposure": "风险敞口描述"
    #     }
    #   ],
    #   "timeline": [
    #     {
    #       "date": "2024-01-01",
    #       "event": "事件描述",
    #       "source_doc": "来源文件",
    #       "type": "签署/履行/违约"
    #     }
    #   ],
    #   "doc_relationships": [...]
    # }
    enhanced_analysis_json = Column(Text, nullable=True, comment="完整的增强分析数据JSON")

    # 用户确认状态
    is_confirmed = Column(Boolean, default=False, index=True, comment="用户是否已确认预整理结果")

    # 用户修改记录（JSON格式，记录用户对预整理结果的修改）
    # 格式示例：
    # [
    #   {
    #     "field": "documents_info",
    #     "original_value": {...},
    #     "modified_value": {...},
    #     "modified_at": "2024-01-01T10:00:00"
    #   }
    # ]
    user_modifications = Column(JSON, default=list, comment="用户修改记录")

    # 分析模式选择（用户确认后选择的分析模式）
    analysis_mode = Column(String(16), nullable=True, comment="分析模式：single（单模型）或 multi（多模型）")
    selected_model = Column(String(64), nullable=True, comment="单模型模式下选择的模型名称")

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    confirmed_at = Column(DateTime, nullable=True, comment="用户确认时间")

    # 关系
    session = relationship("RiskAnalysisSession", backref="preorganization_result")

    def __repr__(self):
        return f"<RiskAnalysisPreorganization {self.session_id} - confirmed:{self.is_confirmed}>"

    def mark_as_confirmed(self, analysis_mode: str = "multi", selected_model: str = None):
        """标记预整理结果为已确认"""
        self.is_confirmed = True
        self.analysis_mode = analysis_mode
        self.selected_model = selected_model
        self.confirmed_at = datetime.utcnow()

    def add_modification(self, field: str, original_value, modified_value):
        """添加用户修改记录"""
        modification = {
            "field": field,
            "original_value": original_value,
            "modified_value": modified_value,
            "modified_at": datetime.utcnow().isoformat()
        }
        if self.user_modifications is None:
            self.user_modifications = []
        self.user_modifications.append(modification)
