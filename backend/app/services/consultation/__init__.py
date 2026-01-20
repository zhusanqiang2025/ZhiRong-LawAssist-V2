# backend/app/services/consultation/__init__.py
"""
智能咨询模块服务层

包含智能咨询的核心服务:
- document_analysis: 文档分析服务
"""

from .document_analysis import (
    ConsultationDocumentAnalysisService,
    get_consultation_document_analysis_service
)

__all__ = [
    "ConsultationDocumentAnalysisService",
    "get_consultation_document_analysis_service"
]
