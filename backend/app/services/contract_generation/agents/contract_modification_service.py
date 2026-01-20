# backend/app/services/contract_generation/agents/contract_modification_service.py
"""
合同变更/解除服务

核心功能：
当用户需求被判定为"变更已有合同"或"解除已有合同"时，该服务负责：
1. 分析用户提供的原合同
2. 理解用户的变更/解除意图
3. 提取关键变更点或解除要点
4. 为后续生成变更协议或解除协议提供必要信息

注意：
- 该服务只负责分析和提取信息
- 实际的变更协议/解除协议生成由后续的合同起草服务完成
"""

import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from .models import ContractModificationResult, ModificationType

logger = logging.getLogger(__name__)


# 知识图谱中的合同类型（简化版，用于识别原合同类型）
KNOWLEDGE_GRAPH_CONTRACT_TYPES = [
    "不动产买卖合同", "房屋买卖合同", "设备采购合同", "货物买卖合同", "汽车买卖合同",
    "建材采购合同", "办公用品采购合同", "原材料采购合同",
    "技术开发合同", "技术转让合同", "技术咨询合同", "技术服务合同", "软件开发合同",
    "委托合同", "委托开发合同", "委托销售合同", "委托代理合同", "委托加工合同",
    "建设工程施工合同", "建设工程设计合同", "建设工程监理合同", "装修工程合同",
    "安装工程合同", "EPC工程总承包合同",
    "租赁合同", "房屋租赁合同", "设备租赁合同", "车辆租赁合同", "场地租赁合同",
    "劳动合同", "劳务合同", "雇佣合同", "实习协议", "退休返聘协议",
    "股权转让合同", "股权收购合同", "增资扩股协议", "股东协议", "投资协议",
    "合伙协议", "有限合伙协议",
    "软件许可合同", "专利实施许可合同", "商标使用许可合同", "版权转让合同",
    "知识产权授权合同",
    "借款合同", "借款协议", "抵押借款合同", "保证合同", "融资租赁合同",
    "承揽合同", "运输合同", "保管合同", "仓储合同", "赠与合同", "物业服务合同",
    "中介合同", "行纪合同", "旅游合同", "教育培训合同",
]


class ContractModificationService:
    """
    合同变更/解除服务

    处理合同的变更和解除场景
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        contract_types_str = "\n".join(f"- {ct}" for ct in KNOWLEDGE_GRAPH_CONTRACT_TYPES)

        return f"""你是一个专业的法律顾问，擅长处理合同的变更和解除事务。

## 你的任务

分析用户提供的原合同和变更/解除需求，提取关键信息供后续生成变更协议或解除协议使用。

## 知识图谱中的合同类型

{contract_types_str}

## 合同变更分析要点

当用户要求变更合同时，需要分析：

1. **原合同类型识别**：从原合同文本中识别合同类型
2. **变更范围确定**：哪些条款需要变更
3. **变更内容提取**：具体的变更内容是什么
4. **变更原因理解**：为什么需要变更

常见变更类型：
- 价格/费用调整
- 履行期限/时间调整
- 履行方式/地点调整
- 权利义务调整
- 增加或删除条款
- 其他条款修改

## 合同解除分析要点

当用户要求解除合同时，需要分析：

1. **原合同类型识别**：从原合同文本中识别合同类型
2. **解除原因确定**：为什么需要解除
3. **解除方式判断**：
   - 协商解除（双方一致同意）
   - 单方解除（基于合同约定或法定理由）
4. **解除后果处理**：已履行部分如何处理、违约责任等

常见解除原因：
- 双方协商一致
- 不可抗力
- 对方违约
- 合同目的无法实现
- 期限届满
- 其他约定或法定事由

## 输出格式

严格按照 JSON 格式输出，包含以下字段：
- modification_type: "modification"（变更）或 "termination"（解除）
- original_contract_type: 原合同类型（从知识图谱中选择）
- agreement_type: 需要生成的协议类型（如"变更协议"、"解除协议"等）
- key_points: 关键变更点或解除要点列表
- intent_description: 用户意图描述
- confidence: 置信度（0-1）

## 分析原则

1. **准确识别原合同类型**：从合同标题、首部、核心条款中判断
2. **完整提取变更/解除要点**：不要遗漏用户提到的重要信息
3. **理解业务实质**：不仅看字面意思，更要理解背后的商业目的
4. **考虑法律效力**：关注变更/解除的法律依据和效力"""

    def analyze(
        self,
        user_input: str,
        original_contract: Optional[str] = None,
        modification_type: ModificationType = ModificationType.MODIFICATION,
        context: Dict[str, Any] = None
    ) -> ContractModificationResult:
        """
        分析变更/解除需求

        Args:
            user_input: 用户的自然语言输入（变更/解除需求说明）
            original_contract: 原合同内容（可选）
            modification_type: 变更或解除类型
            context: 额外上下文信息（可选）

        Returns:
            ContractModificationResult: 分析结果
        """
        try:
            logger.info(f"[ContractModificationService] 开始分析变更/解除需求")
            logger.info(f"[ContractModificationService] 类型: {modification_type}")

            prompt = f"""## 用户需求

{user_input}

"""

            # 添加原合同信息
            if original_contract:
                prompt += f"""
## 原合同内容

{original_contract}

"""
            else:
                prompt += """
## 原合同信息

用户未提供原合同内容。

"""

            # 添加修改类型提示
            type_hint = "变更" if modification_type == ModificationType.MODIFICATION else "解除"
            prompt += f"""
## 任务类型

这是一个合同{type_hint}需求。

"""

            # 添加上下文信息
            if context:
                prompt += "\n## 上下文信息\n"
                for key, value in context.items():
                    prompt += f"**{key}**：{value}\n"

            analysis_task = """
## 分析要求

请分析上述信息，提取：
1. 原合同类型（从知识图谱的合同类型中选择）
2. 需要生成的协议类型
3. 关键变更点或解除要点
4. 用户意图描述

严格按照 JSON 格式输出。"""

            prompt += analysis_task

            # 使用结构化输出
            structured_llm = self.llm.with_structured_output(ContractModificationResult)
            result: ContractModificationResult = structured_llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ])

            # 确保设置 modification_type
            if result.modification_type != modification_type:
                result.modification_type = modification_type

            logger.info(f"[ContractModificationService] 分析完成:")
            logger.info(f"  - 类型: {result.modification_type}")
            logger.info(f"  - 原合同类型: {result.original_contract_type}")
            logger.info(f"  - 协议类型: {result.agreement_type}")
            logger.info(f"  - 关键点数量: {len(result.key_points)}")
            logger.info(f"  - 置信度: {result.confidence}")

            return result

        except Exception as e:
            logger.error(f"[ContractModificationService] 分析失败: {str(e)}", exc_info=True)

            # 返回默认结果
            return ContractModificationResult(
                modification_type=modification_type,
                original_contract_type="委托合同",
                agreement_type="变更协议" if modification_type == ModificationType.MODIFICATION else "解除协议",
                key_points=[],
                intent_description="用户需求合同变更/解除服务",
                confidence=0.5
            )


def get_contract_modification_service(llm: ChatOpenAI) -> ContractModificationService:
    """获取合同变更/解除服务实例"""
    return ContractModificationService(llm)
