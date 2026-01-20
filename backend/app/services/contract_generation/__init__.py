# backend/app/services/contract_generation/__init__.py
"""
合同生成服务

使用 LangChain + LangGraph 实现智能合同生成流程

核心特性：
1. 需求分析 - 判断处理类型（变更/解除/单一/规划）
2. 文档智能处理 - 复用现有服务
3. 合同起草 - AI 生成合同内容
4. 格式转换 - 生成 Word/PDF 文件
"""

from .workflow import get_contract_workflow
from .tools.document_processor import DocumentProcessorTool

__all__ = [
    "get_contract_workflow",
    "DocumentProcessorTool",
]
