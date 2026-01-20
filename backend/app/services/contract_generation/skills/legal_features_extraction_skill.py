# backend/app/services/contract_generation/skills/legal_features_extraction_skill.py
"""
法律特征提取技能

核心功能：
从用户输入中提取完整的法律特征，用于判断是单一合同还是需要合同规划。

使用场景：
- ContractRequirementRouter 在判断用户需求类型时调用
- 当用户输入不包含明确关键词时，需要通过法律特征来判断复杂度
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

# 导入法律知识图谱
try:
    from app.services.legal_features.contract_knowledge_graph import (
        ContractKnowledgeGraph,
        ContractLegalFeatures,
        TransactionNature,
        ContractObject,
        ConsiderationType,
        Stance,
    )
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False
    # 定义备用枚举
    class TransactionNature(str):
        pass
    class ContractObject(str):
        pass
    class ConsiderationType(str):
        pass
    class Stance(str):
        pass

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class ComplexityAnalysis(BaseModel):
    """特征复杂度分析结果"""
    # 是否为单一特征（单一合同）
    is_single_feature: bool = Field(
        description="是否为单一特征，True表示单一合同，False表示需要合同规划"
    )

    # 检测到的特征数量
    detected_feature_count: int = Field(
        description="检测到的不同特征数量"
    )

    # 检测到的交易性质列表
    detected_natures: List[str] = Field(
        description="检测到的交易性质列表（使用枚举值）",
        default_factory=list
    )

    # 检测到的合同标的列表
    detected_objects: List[str] = Field(
        description="检测到的合同标的列表（使用枚举值）",
        default_factory=list
    )

    # 复杂度评分 (0-1, 越高越复杂)
    complexity_score: float = Field(
        description="复杂度评分，0-1之间，越高表示越复杂",
        ge=0.0,
        le=1.0
    )

    # 需要合同规划的原因
    planning_reasons: List[str] = Field(
        description="需要合同规划的原因列表",
        default_factory=list
    )


class LegalFeaturesExtractionResult(BaseModel):
    """法律特征提取结果"""
    # 提取的法律特征（主要特征）
    legal_features: Optional[Dict[str, Any]] = Field(
        description="提取的主要法律特征",
        default=None
    )

    # 交易性质
    transaction_nature: Optional[str] = Field(
        description="交易性质",
        default=None
    )

    # 合同标的
    contract_object: Optional[str] = Field(
        description="合同标的",
        default=None
    )

    # 起草立场
    stance: Optional[str] = Field(
        description="起草立场",
        default=None
    )

    # 对价类型
    consideration_type: Optional[str] = Field(
        description="对价类型",
        default=None
    )

    # 交易特征描述
    transaction_characteristics: str = Field(
        description="交易特征描述",
        default=""
    )

    # 匹配的合同类型（可能是多个）
    matched_contract_types: List[str] = Field(
        description="匹配的合同类型列表",
        default_factory=list
    )

    # 特征复杂度分析
    complexity_analysis: ComplexityAnalysis = Field(
        description="特征复杂度分析结果"
    )

    # 置信度
    confidence: float = Field(
        description="提取的置信度",
        ge=0.0,
        le=1.0
    )


# ==================== 交易性质枚举值（用于提示词）====================

TRANSACTION_NATURES = [
    "ASSET_TRANSFER",  # 转移所有权
    "SERVICE_DELIVERY",  # 提供服务
    "AUTHORIZATION",  # 许可使用
    "ENTITY_CREATION",  # 合作经营
    "CAPITAL_FINANCE",  # 融资借贷
    "LABOR_EMPLOYMENT",  # 劳动用工
    "DISPUTE_RESOLUTION",  # 争议解决
]

TRANSACTION_NATURE_LABELS = {
    "ASSET_TRANSFER": "转移所有权",
    "SERVICE_DELIVERY": "提供服务",
    "AUTHORIZATION": "许可使用",
    "ENTITY_CREATION": "合作经营",
    "CAPITAL_FINANCE": "融资借贷",
    "LABOR_EMPLOYMENT": "劳动用工",
    "DISPUTE_RESOLUTION": "争议解决",
}

# 合同标的枚举值
CONTRACT_OBJECTS = [
    "TANGIBLE_GOODS",  # 货物
    "PROJECT",  # 工程
    "IP",  # 智力成果
    "SERVICE",  # 服务
    "EQUITY",  # 股权
    "MONETARY_DEBT",  # 资金
    "HUMAN_LABOR",  # 劳动力
    "REAL_ESTATE",  # 不动产
    "MOVABLE_PROPERTY",  # 动产
]

CONTRACT_OBJECT_LABELS = {
    "TANGIBLE_GOODS": "货物",
    "PROJECT": "工程",
    "IP": "智力成果",
    "SERVICE": "服务",
    "EQUITY": "股权",
    "MONETARY_DEBT": "资金",
    "HUMAN_LABOR": "劳动力",
    "REAL_ESTATE": "不动产",
    "MOVABLE_PROPERTY": "动产",
}


# ==================== 法律特征提取技能 ====================

class LegalFeaturesExtractionSkill:
    """
    法律特征提取技能

    从用户输入中提取法律特征，用于判断合同复杂度
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.knowledge_graph = None
        self.system_prompt = self._build_system_prompt()

        # 尝试初始化知识图谱
        if KNOWLEDGE_GRAPH_AVAILABLE:
            try:
                from app.services.legal_features.contract_knowledge_graph import get_contract_knowledge_graph
                self.knowledge_graph = get_contract_knowledge_graph()
                logger.info("[LegalFeaturesExtractionSkill] 知识图谱已加载")
            except Exception as e:
                logger.warning(f"[LegalFeaturesExtractionSkill] 知识图谱加载失败: {e}")

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        natures_str = "\n".join([
            f"- {nature}: {label}" for nature, label in TRANSACTION_NATURE_LABELS.items()
        ])
        objects_str = "\n".join([
            f"- {obj}: {label}" for obj, label in CONTRACT_OBJECT_LABELS.items()
        ])

        return f"""你是一个专业的法律顾问，擅长从用户的描述中提取法律特征。

## 你的任务

从用户的自然语言输入中提取法律特征，并分析其复杂程度。

## 法律特征字段

### 交易性质 (TransactionNature)
{natures_str}

### 合同标的 (ContractObject)
{objects_str}

### 起草立场 (Stance)
- BUYER_FRIENDLY: 甲方
- SELLER_FRIENDLY: 乙方
- NEUTRAL: 中立
- BALANCED: 平衡

### 对价类型 (ConsiderationType)
- PAID: 有偿
- FREE: 无偿
- HYBRID: 混合

## 特征复杂度判断规则

你需要分析用户描述中的法律特征，判断：

1. **检测到的交易性质**：用户描述涉及哪些交易性质？
2. **检测到的合同标的**：用户描述涉及哪些合同标的？
3. **是否为单一特征**：
   - 如果只涉及一种交易性质和一种合同标的 → 单一特征（单一合同）
   - 如果涉及多种交易性质或多种合同标的 → 复杂特征（需要合同规划）

## 判断示例

### 单一特征示例
- "开发一个软件" → SERVICE_DELIVERY + IP → 单一特征
- "购买一批设备" → ASSET_TRANSFER + TANGIBLE_GOODS → 单一特征
- "租赁一个办公室" → AUTHORIZATION + REAL_ESTATE → 单一特征

### 复杂特征示例
- "投资公司取得股权，同时参与经营管理" → CAPITAL_FINANCE + ENTITY_CREATION → 复杂特征
- "转让技术并许可使用，同时提供服务" → ASSET_TRANSFER + AUTHORIZATION + SERVICE_DELIVERY → 复杂特征

## 输出格式

严格按照 JSON 格式输出，包含以下字段：
- transaction_nature: 主要的交易性质（使用枚举值，如 "SERVICE_DELIVERY"）
- contract_object: 主要的合同标的（使用枚举值，如 "IP"）
- stance: 起草立场（使用枚举值）
- consideration_type: 对价类型（使用枚举值）
- transaction_characteristics: 交易特征的详细描述
- matched_contract_types: 可能匹配的合同类型列表（如 ["软件开发合同"]）
- complexity_analysis: 复杂度分析
  - is_single_feature: 是否为单一特征
  - detected_natures: 检测到的所有交易性质列表
  - detected_objects: 检测到的所有合同标的列表
  - complexity_score: 复杂度评分（0-1）
  - planning_reasons: 如果需要规划，说明原因
- confidence: 置信度（0-1）"""

    def extract_features(self, user_input: str, context: Dict[str, Any] = None) -> LegalFeaturesExtractionResult:
        """
        提取法律特征

        Args:
            user_input: 用户的自然语言输入
            context: 额外上下文信息（可选）

        Returns:
            LegalFeaturesExtractionResult: 特征提取结果
        """
        try:
            logger.info(f"[LegalFeaturesExtractionSkill] 开始提取法律特征")

            prompt = f"""## 用户需求

{user_input}

"""

            # 添加上下文信息
            if context:
                prompt += "\n## 上下文信息\n"
                for key, value in context.items():
                    prompt += f"**{key}**：{value}\n"

            prompt += """
## 任务

请分析用户的描述，提取：
1. 主要的法律特征（交易性质、合同标的等）
2. 匹配可能的合同类型
3. 分析特征复杂度（是否为单一特征）

严格按照 JSON 格式输出。"""

            # 使用结构化输出
            structured_llm = self.llm.with_structured_output(LegalFeaturesExtractionResult)
            result: LegalFeaturesExtractionResult = structured_llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ])

            # 如果有知识图谱，尝试匹配合同类型
            if self.knowledge_graph and result.matched_contract_types:
                result.matched_contract_types = self._match_with_knowledge_graph(result)

            logger.info(f"[LegalFeaturesExtractionSkill] 特征提取完成:")
            logger.info(f"  - 交易性质: {result.transaction_nature}")
            logger.info(f"  - 合同标的: {result.contract_object}")
            logger.info(f"  - 单一特征: {result.complexity_analysis.is_single_feature}")
            logger.info(f"  - 置信度: {result.confidence}")

            return result

        except Exception as e:
            logger.error(f"[LegalFeaturesExtractionSkill] 特征提取失败: {str(e)}", exc_info=True)
            # 返回默认结果
            return LegalFeaturesExtractionResult(
                transaction_nature=None,
                contract_object=None,
                stance=None,
                consideration_type=None,
                transaction_characteristics="",
                matched_contract_types=[],
                complexity_analysis=ComplexityAnalysis(
                    is_single_feature=True,
                    detected_feature_count=0,
                    detected_natures=[],
                    detected_objects=[],
                    complexity_score=0.0,
                    planning_reasons=[]
                ),
                confidence=0.0
            )

    def _match_with_knowledge_graph(self, result: LegalFeaturesExtractionResult) -> List[str]:
        """使用知识图谱匹配合同类型"""
        try:
            # 基于交易性质和标的搜索
            search_results = self.knowledge_graph.search_by_features(
                transaction_nature=result.transaction_nature,
                contract_object=result.contract_object
            )

            if search_results:
                return [result.name for result, score in search_results[:3]]

            return result.matched_contract_types

        except Exception as e:
            logger.warning(f"[LegalFeaturesExtractionSkill] 知识图谱匹配失败: {e}")
            return result.matched_contract_types


def get_legal_features_extraction_skill(llm: ChatOpenAI) -> LegalFeaturesExtractionSkill:
    """获取法律特征提取技能实例"""
    return LegalFeaturesExtractionSkill(llm)
