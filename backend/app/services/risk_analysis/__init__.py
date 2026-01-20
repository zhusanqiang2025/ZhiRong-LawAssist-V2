# backend/app/services/risk_analysis/__init__.py
"""
风险评估服务模块

包含：
- DocumentPreorganizationService: 文档预整理服务
- DiagramGeneratorService: 图表生成服务
- RiskRuleAssembler: 规则组装器服务
- MultiModelAnalyzer: 多模型分析器服务
- RiskAnalysisWorkflowService: LangGraph 工作流服务
"""

from .document_preorganization import DocumentPreorganizationService, get_document_preorganization_service
from .diagram_generator import DiagramGeneratorService, get_diagram_generator_service
from .rule_assembler import RiskRuleAssembler, get_risk_rule_assembler
from .multi_model_analyzer import MultiModelAnalyzer, get_multi_model_analyzer
from .workflow import RiskAnalysisWorkflowService, build_risk_analysis_graph, run_risk_analysis_workflow

__all__ = [
    "DocumentPreorganizationService",
    "get_document_preorganization_service",
    "DiagramGeneratorService",
    "get_diagram_generator_service",
    "RiskRuleAssembler",
    "get_risk_rule_assembler",
    "MultiModelAnalyzer",
    "get_multi_model_analyzer",
    "RiskAnalysisWorkflowService",
    "build_risk_analysis_graph",
    "run_risk_analysis_workflow",
]
