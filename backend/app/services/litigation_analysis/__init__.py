# backend/app/services/litigation_analysis/__init__.py
"""
案件分析模块服务层

包含案件分析的核心服务：
- workflow.py: LangGraph 工作流编排（完整版）
- case_preorganization.py: 案件文档预整理
- enhanced_case_preorganization.py: 增强版预整理（三层架构）
- case_rule_assembler.py: 案件规则组装器
- evidence_analyzer.py: 证据分析器
- multi_model_analyzer.py: 多模型智能推演引擎
- report_generator.py: 报告生成器
- strategy_generator.py: 策略生成器
- timeline_generator.py: 时间线生成器

3阶段架构：
1. 阶段1：预整理 → 用户确认
2. 阶段2：全案分析（run_stage2_analysis）→ 用户查看报告 → 按需生成文书
3. 阶段3：文书生成（generate_litigation_documents）

注意：workflow_simplified.py 已废弃并删除，请使用 workflow.py
"""

from .workflow import (
    build_litigation_analysis_graph,
    LitigationAnalysisState,
    run_litigation_analysis_workflow,
    run_stage2_analysis
)

__all__ = [
    "build_litigation_analysis_graph",
    "LitigationAnalysisState",
    "run_litigation_analysis_workflow",
    "run_stage2_analysis"
]
