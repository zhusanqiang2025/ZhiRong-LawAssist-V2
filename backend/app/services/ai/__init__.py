# backend/app/services/ai/__init__.py
"""
AI 服务模块
"""
from .legal_features_generator import LegalFeaturesGenerator, get_legal_features_generator, LegalFeaturesPrompt

__all__ = [
    "LegalFeaturesGenerator",
    "get_legal_features_generator",
    "LegalFeaturesPrompt"
]
