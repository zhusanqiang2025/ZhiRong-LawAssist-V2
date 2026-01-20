# backend/app/services/contract_generation/skills/__init__.py
"""
合同生成技能模块

该模块包含各种专业技能，用于合同生成流程中的特定任务。
"""

from .legal_features_extraction_skill import (
    LegalFeaturesExtractionSkill,
    LegalFeaturesExtractionResult,
    ComplexityAnalysis,
    get_legal_features_extraction_skill,
)

__all__ = [
    "LegalFeaturesExtractionSkill",
    "LegalFeaturesExtractionResult",
    "ComplexityAnalysis",
    "get_legal_features_extraction_skill",
]
