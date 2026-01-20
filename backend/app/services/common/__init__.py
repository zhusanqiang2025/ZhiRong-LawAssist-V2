# backend/app/services/common/__init__.py
"""
通用服务层

提供跨模块复用的通用服务
"""

from .document_preorganization import (
    UniversalDocumentPreorganizationService,
    DocumentCategory,
    DocumentSummary,
    DocumentQuality,
    DocumentRelationship,
    PartyInfo,
    PreorganizedDocuments,
    get_universal_document_preorganization_service
)

__all__ = [
    "UniversalDocumentPreorganizationService",
    "DocumentCategory",
    "DocumentSummary",
    "DocumentQuality",
    "DocumentRelationship",
    "PartyInfo",
    "PreorganizedDocuments",
    "get_universal_document_preorganization_service"
]
