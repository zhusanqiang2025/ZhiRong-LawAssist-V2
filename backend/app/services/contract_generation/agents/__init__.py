# backend/app/services/contract_generation/agents/__init__.py
"""
合同生成代理模块

该模块负责合同生成流程中的各种意图理解和处理任务。

## 业务流程架构

```
用户需求
    ↓
ContractRequirementRouter (第一层判断)
    ├─→ 合同规划 (ContractPlanningService)
    │       └─→ 输出合约规划给用户确认
    │            └─→ 确认后进入合同生成流程
    │
    └─→ 单一合同 (SingleContractRouter - 第二层判断)
            ├─→ 变更/解除已有合同 (ContractModificationService)
            │       ├─→ 变更协议
            │       └─→ 解除协议
            │
            └─→ 生成全新合同 (ContractIntentAnalyzer)
                    └─→ 识别合同类型和关键要素
```

## 模块说明

### 第一层：需求路由
- ContractRequirementRouter: 判断是单一合同还是合同规划
- RequirementType: 需求类型枚举

### 合同规划分支
- ContractPlanningService: 处理合同规划场景
- ContractPlanning: 合同规划结果模型

### 第二层：单一合同路由
- SingleContractRouter: 判断是全新合同、变更还是解除
- SingleContractType: 单一合同类型枚举

### 合同变更/解除分支
- ContractModificationService: 处理合同变更/解除场景
- ModificationType: 变更/解除类型枚举
- ContractModificationResult: 变更/解除结果模型

### 全新合同分支
- ContractIntentAnalyzer: 处理全新合同场景，识别合同类型
- IntentResult: 意图识别结果模型

## 保留的旧模块（向后兼容）
- RequirementAnalyzer: 旧版需求分析器（已废弃，建议使用新架构）
- ContractDrafterAgent: 合同起草代理
- 注意：ContractPlannerAgent 已删除，请使用 ContractPlanningService 替代
"""

# ==================== 新架构模块 ====================

from .models import (
    RequirementType,
    SingleContractType,
    ModificationType,
    RequirementRoutingResult,
    SingleContractRoutingResult,
    PlannedContract,
    ContractPlanning,
    ContractModificationResult,
)

from .contract_requirement_router import (
    ContractRequirementRouter,
    get_contract_requirement_router,
)

from .contract_planning_service import (
    ContractPlanningService,
    get_contract_planning_service,
)

from .single_contract_router import (
    SingleContractRouter,
    get_single_contract_router,
)

from .contract_modification_service import (
    ContractModificationService,
    get_contract_modification_service,
)

from .contract_intent_analyzer import (
    ContractIntentAnalyzer,
    IntentResult,
    get_contract_intent_analyzer,
)

from .complexity_analyzer import (
    ComplexityAnalyzer,
    get_complexity_analyzer,
)

from .single_contract_generation_service import (
    SingleContractGenerationService,
    get_single_contract_generation_service,
    TemplateMatchAndFormResult,
    ContractGenerationResult,
)

# ==================== 旧版模块（向后兼容） ====================
from .requirement_analyzer import RequirementAnalyzer
from .contract_drafter import ContractDrafterAgent
# 注意：ContractPlannerAgent 已被 ContractPlanningService 替代并删除

__all__ = [
    # ==================== 新架构导出 ====================

    # 数据模型
    "RequirementType",
    "SingleContractType",
    "ModificationType",
    "RequirementRoutingResult",
    "SingleContractRoutingResult",
    "PlannedContract",
    "ContractPlanning",
    "ContractModificationResult",
    "IntentResult",

    # 第一层：需求路由
    "ContractRequirementRouter",
    "get_contract_requirement_router",

    # 合同规划
    "ContractPlanningService",
    "get_contract_planning_service",

    # 第二层：单一合同路由
    "SingleContractRouter",
    "get_single_contract_router",

    # 合同变更/解除
    "ContractModificationService",
    "get_contract_modification_service",

    # 全新合同意图分析
    "ContractIntentAnalyzer",
    "get_contract_intent_analyzer",

    # 复杂度分析
    "ComplexityAnalyzer",
    "get_complexity_analyzer",

    # 单一合同生成服务
    "SingleContractGenerationService",
    "get_single_contract_generation_service",
    "TemplateMatchAndFormResult",
    "ContractGenerationResult",

    # ==================== 旧版导出（向后兼容） ====================
    "RequirementAnalyzer",
    "ContractDrafterAgent",
    # 注意：ContractPlannerAgent 已被 ContractPlanningService 替代并删除
]
