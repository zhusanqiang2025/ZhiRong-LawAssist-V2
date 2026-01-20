"""
文书起草服务模块初始化文件
"""

from app.services.document_drafting.config import (
    DOCUMENT_DRAFTING_CONFIG,
    get_document_config,
    get_template_path,
    list_document_types
)

__all__ = [
    "DOCUMENT_DRAFTING_CONFIG",
    "get_document_config",
    "get_template_path",
    "list_document_types"
]
