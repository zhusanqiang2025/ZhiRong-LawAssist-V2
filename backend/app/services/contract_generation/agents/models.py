# backend/app/services/contract_generation/agents/models.py
"""
合同生成流程的数据模型
"""

from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


# ==================== 第一层：需求类型 ====================

class RequirementType(str, Enum):
    """用户需求类型"""
    SINGLE_CONTRACT = "single_contract"                # 单一全新合同
    CONTRACT_MODIFICATION = "contract_modification"    # 合同变更
    CONTRACT_TERMINATION = "contract_termination"      # 合同解除
    CONTRACT_PLANNING = "contract_planning"            # 合同规划


# ==================== 第二层：单一合同类型 ====================

class SingleContractType(str, Enum):
    """单一合同的具体类型"""
    NEW_CONTRACT = "new_contract"  # 生成全新合同
    CONTRACT_MODIFICATION = "contract_modification"  # 变更已有合同
    CONTRACT_TERMINATION = "contract_termination"  # 解除已有合同


class ModificationType(str, Enum):
    """合同变更/解除的具体类型"""
    MODIFICATION = "modification"  # 变更
    TERMINATION = "termination"  # 解除


# ==================== 需求路由结果 ====================

class RequirementRoutingResult(BaseModel):
    """第一层需求路由结果"""
    # 需求类型
    requirement_type: RequirementType = Field(
        description="需求类型：单一合同、合同变更、合同解除或合同规划"
    )

    # 用户意图描述
    intent_description: str = Field(
        description="用简洁的语言描述用户的真实意图"
    )

    # 置信度
    confidence: float = Field(
        description="识别的置信度，0-1之间",
        ge=0.0,
        le=1.0
    )

    # 推理过程
    reasoning: str = Field(
        description="判断的推理过程",
        default=""
    )


# ==================== 单一合同路由结果 ====================

class SingleContractRoutingResult(BaseModel):
    """第二层单一合同路由结果"""
    # 单一合同类型
    contract_type: SingleContractType = Field(
        description="单一合同类型：全新合同、变更或解除"
    )

    # 变更/解除类型（仅当contract_type为MODIFICATION或TERMINATION时有效）
    modification_type: Optional[ModificationType] = Field(
        description="变更或解除类型",
        default=None
    )

    # 用户意图描述
    intent_description: str = Field(
        description="用简洁的语言描述用户的真实意图"
    )

    # 是否提供了原有合同
    has_original_contract: bool = Field(
        description="用户是否提供了原有合同",
        default=False
    )

    # 变更/解除的原因或说明
    modification_reason: str = Field(
        description="变更或解除的原因/说明",
        default=""
    )

    # 置信度
    confidence: float = Field(
        description="识别的置信度，0-1之间",
        ge=0.0,
        le=1.0
    )

    # 推理过程
    reasoning: str = Field(
        description="判断的推理过程",
        default=""
    )


# ==================== 合同规划结果 ====================

class PlannedContract(BaseModel):
    """规划的单一合同"""
    # 合同ID
    id: str = Field(description="合同唯一标识")

    # 合同标题
    title: str = Field(description="合同标题")

    # 合同类型
    contract_type: str = Field(description="合同类型")

    # 该合同的目的
    purpose: str = Field(description="该合同在整体交易中的目的")

    # 关键当事人
    key_parties: List[str] = Field(
        description="关键当事人",
        default_factory=list
    )

    # 优先级（数字越小越优先）
    priority: int = Field(
        description="签署优先级",
        default=1
    )

    # 依赖关系（依赖的其他合同ID）
    dependencies: List[str] = Field(
        description="依赖的其他合同ID列表",
        default_factory=list
    )

    # 预计的主要条款
    estimated_sections: List[str] = Field(
        description="预计的主要条款",
        default_factory=list
    )


class ContractPlanning(BaseModel):
    """合同规划结果"""
    # 规划的合同列表
    contracts: List[PlannedContract] = Field(
        description="规划的合同列表",
        default_factory=list
    )

    # 签署顺序
    signing_order: List[str] = Field(
        description="合同签署顺序（合同ID列表）",
        default_factory=list
    )

    # 合同关系说明
    relationships: dict = Field(
        description="合同之间的关系说明",
        default_factory=dict
    )

    # 风险提示
    risk_notes: List[str] = Field(
        description="风险提示",
        default_factory=list
    )

    # 总体说明
    overall_description: str = Field(
        description="整体交易结构的说明",
        default=""
    )

    # 预计合同数量
    total_estimated_contracts: int = Field(
        description="预计的合同总数",
        default=0
    )


# ==================== 合同变更/解除结果 ====================

class ContractModificationResult(BaseModel):
    """合同变更/解除处理结果"""
    # 变更/解除类型
    modification_type: ModificationType = Field(
        description="变更或解除"
    )

    # 原合同类型
    original_contract_type: str = Field(
        description="原合同的类型"
    )

    # 变更/解除协议类型
    agreement_type: str = Field(
        description="需要生成的协议类型（如：变更协议、解除协议）"
    )

    # 关键变更点/解除要点
    key_points: List[str] = Field(
        description="关键变更点或解除要点",
        default_factory=list
    )

    # 意图描述
    intent_description: str = Field(
        description="用户意图描述"
    )

    # 置信度
    confidence: float = Field(
        description="识别的置信度",
        ge=0.0,
        le=1.0
    )
