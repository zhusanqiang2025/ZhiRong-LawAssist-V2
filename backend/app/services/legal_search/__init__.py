"""Legal Search Service Module

This module provides legal document retrieval and analysis capabilities
using RAG (Retrieval-Augmented Generation) systems.
"""

from .rag_system import (
    LegalRAGSystem,
    LegalDocument,
    LegalSearchResult,
    create_legal_rag_system
)

__all__ = [
    "LegalRAGSystem",
    "LegalDocument",
    "LegalSearchResult",
    "create_legal_rag_system"
]
