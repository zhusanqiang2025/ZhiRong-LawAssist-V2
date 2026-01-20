"""
Schemas module

本文件重新导出 ../schemas.py 文件中的所有 Schema 定义，以保持向后兼容性
由于 Python 优先导入目录而非同名 .py 文件，因此需要在此重新导出
"""
import sys
import importlib.util
from pathlib import Path

# 动态加载 schemas.py 文件，避免循环导入
# 获取父目录中的 schemas.py 文件路径
schemas_file_path = Path(__file__).parent.parent / "schemas.py"

if schemas_file_path.exists():
    # 动态加载 schemas.py 模块
    spec = importlib.util.spec_from_file_location("_schemas_module", schemas_file_path)
    if spec and spec.loader:
        _schemas_module = importlib.util.module_from_spec(spec)
        sys.modules["_schemas_module"] = _schemas_module
        spec.loader.exec_module(_schemas_module)

        # 导出所有 Schema 类
        Token = _schemas_module.Token
        TokenPayload = _schemas_module.TokenPayload

        UserBase = _schemas_module.UserBase
        UserCreate = _schemas_module.UserCreate
        UserUpdate = _schemas_module.UserUpdate
        User = _schemas_module.User

        TaskBase = _schemas_module.TaskBase
        TaskCreate = _schemas_module.TaskCreate
        TaskUpdate = _schemas_module.TaskUpdate
        Task = _schemas_module.Task

        ContractTemplateBase = _schemas_module.ContractTemplateBase
        ContractTemplateCreate = _schemas_module.ContractTemplateCreate
        ContractTemplateUpdate = _schemas_module.ContractTemplateUpdate
        ContractTemplateResponse = _schemas_module.ContractTemplateResponse
        ContractTemplateSearchRequest = _schemas_module.ContractTemplateSearchRequest
        ContractTemplateSearchResponse = _schemas_module.ContractTemplateSearchResponse

        CategoryCreate = _schemas_module.CategoryCreate
        CategoryUpdate = _schemas_module.CategoryUpdate
        CategoryResponse = _schemas_module.CategoryResponse

        ReviewRuleBase = _schemas_module.ReviewRuleBase
        ReviewRuleCreate = _schemas_module.ReviewRuleCreate
        ReviewRuleUpdate = _schemas_module.ReviewRuleUpdate
        ReviewRuleOut = _schemas_module.ReviewRuleOut
        ReviewItemBase = _schemas_module.ReviewItemBase
        ReviewItemUpdate = _schemas_module.ReviewItemUpdate
        ReviewItemOut = _schemas_module.ReviewItemOut
        ContractMetadataSchema = _schemas_module.ContractMetadataSchema
        ContractDocBase = _schemas_module.ContractDocBase
        ContractDocCreate = _schemas_module.ContractDocCreate
        ContractDocUpdate = _schemas_module.ContractDocUpdate
        ContractDocOut = _schemas_module.ContractDocOut
        ReviewIssue = _schemas_module.ReviewIssue
        ReviewOutput = _schemas_module.ReviewOutput

        RuleInstruction = _schemas_module.RuleInstruction
        FeatureRuleCategory = _schemas_module.FeatureRuleCategory
        StanceRuleRole = _schemas_module.StanceRuleRole
        ReviewRulesConfig = _schemas_module.ReviewRulesConfig
        UniversalRule = _schemas_module.UniversalRule
        UniversalRulesOut = _schemas_module.UniversalRulesOut
        FeatureRuleOut = _schemas_module.FeatureRuleOut
        StanceRuleOut = _schemas_module.StanceRuleOut
        RuleCreate = _schemas_module.RuleCreate
        RuleUpdate = _schemas_module.RuleUpdate

        RiskSectionRef = _schemas_module.RiskSectionRef
        RiskItemCreate = _schemas_module.RiskItemCreate
        RiskItemResponse = _schemas_module.RiskItemResponse
        RiskAnalysisSubmitRequest = _schemas_module.RiskAnalysisSubmitRequest
        RiskAnalysisSessionResponse = _schemas_module.RiskAnalysisSessionResponse
        RiskAnalysisDetailResponse = _schemas_module.RiskAnalysisDetailResponse
        RiskAnalysisStatusResponse = _schemas_module.RiskAnalysisStatusResponse
        RiskAnalysisUploadResponse = _schemas_module.RiskAnalysisUploadResponse
        RiskAnalysisStartResponse = _schemas_module.RiskAnalysisStartResponse
        RiskAnalysisRuleCreate = _schemas_module.RiskAnalysisRuleCreate
        RiskAnalysisRuleResponse = _schemas_module.RiskAnalysisRuleResponse
else:
    raise ImportError(f"Cannot find schemas.py file at {schemas_file_path}")

__all__ = [
    # Token
    'Token',
    'TokenPayload',
    # User
    'UserBase',
    'UserCreate',
    'UserUpdate',
    'User',
    # Task
    'TaskBase',
    'TaskCreate',
    'TaskUpdate',
    'Task',
    # Contract Template
    'ContractTemplateBase',
    'ContractTemplateCreate',
    'ContractTemplateUpdate',
    'ContractTemplateResponse',
    'ContractTemplateSearchRequest',
    'ContractTemplateSearchResponse',
    # Category
    'CategoryCreate',
    'CategoryUpdate',
    'CategoryResponse',
    # Contract Review
    'ReviewRuleBase',
    'ReviewRuleCreate',
    'ReviewRuleUpdate',
    'ReviewRuleOut',
    'ReviewItemBase',
    'ReviewItemUpdate',
    'ReviewItemOut',
    'ContractMetadataSchema',
    'ContractDocBase',
    'ContractDocCreate',
    'ContractDocUpdate',
    'ContractDocOut',
    'ReviewIssue',
    'ReviewOutput',
    # JSON 规则系统
    'RuleInstruction',
    'FeatureRuleCategory',
    'StanceRuleRole',
    'ReviewRulesConfig',
    'UniversalRule',
    'UniversalRulesOut',
    'FeatureRuleOut',
    'StanceRuleOut',
    'RuleCreate',
    'RuleUpdate',
    # Risk Analysis
    'RiskSectionRef',
    'RiskItemCreate',
    'RiskItemResponse',
    'RiskAnalysisSubmitRequest',
    'RiskAnalysisSessionResponse',
    'RiskAnalysisDetailResponse',
    'RiskAnalysisStatusResponse',
    'RiskAnalysisUploadResponse',
    'RiskAnalysisStartResponse',
    'RiskAnalysisRuleCreate',
    'RiskAnalysisRuleResponse',
]
