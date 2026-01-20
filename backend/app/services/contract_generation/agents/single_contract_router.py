# backend/app/services/contract_generation/agents/single_contract_router.py
"""
单一合同路由器（第二层判断）

核心功能：
当用户需求被判定为"单一合同"时，进一步判断：
1. 生成全新合同
2. 变更已有合同
3. 解除已有合同

判断逻辑：
- 全新合同：用户没有提供现有合同，需要从头生成
- 变更合同：用户提供了现有合同，并要求修改/变更/补充
- 解除合同：用户提供了现有合同，并要求解除/终止/撤销
"""

import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from .models import (
    SingleContractRoutingResult,
    SingleContractType,
    ModificationType
)

logger = logging.getLogger(__name__)


class SingleContractRouter:
    """
    单一合同路由器

    第二层判断：区分全新合同、变更合同、解除合同
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的法律顾问，擅长判断用户的合同需求类型。

## 你的任务

根据用户的描述和上下文，判断用户的需求属于哪种类型：
1. **全新合同 (new_contract)**：用户没有提供现有合同，需要从头生成一份新合同
2. **变更合同 (contract_modification)**：用户提供了现有合同，并要求修改、变更、补充或调整
3. **解除合同 (contract_termination)**：用户提供了现有合同，并要求解除、终止或撤销

## 判断标准

### 全新合同 (new_contract)
**特征：**
- 用户描述的是一个新的交易或合作需求
- 没有提及已有的合同
- 没有提供现有合同文本
- 关键词：签订、签署、起草、拟定、制定

**示例：**
- "我要和XX公司签订一份软件开发合同"
- "帮我起草一份房屋租赁合同"
- "拟定一份股权转让协议"

### 变更合同 (contract_modification)
**特征：**
- 用户明确提到了已有的合同
- 要求对合同进行修改、补充或调整
- 可能提供了现有合同文本
- 关键词：变更、修改、补充、修订、调整、续签

**示例：**
- "我们要变更原合同的价格条款"
- "对原合同进行补充，增加售后服务内容"
- "修改合同的交付时间"

### 解除合同 (contract_termination)
**特征：**
- 用户明确提到了已有的合同
- 要求终止合同关系
- 可能提供了现有合同文本
- 关键词：解除、终止、撤销、废止、不再履行

**示例：**
- "我们要解除原合同"
- "终止租赁合同"
- "不再履行原合作协议"

## 判断原则

1. **优先检查是否提及已有合同**：如果明确提及"原合同"、"现有合同"等，说明不是全新合同
2. **区分变更和解除**：
   - 变更：继续履行合同，但修改部分条款
   - 解除：彻底终止合同关系
3. **关注用户意图**：
   - 变更：希望继续合作，但需要调整
   - 解除：希望结束合同关系

## 输出要求

严格按照 JSON 格式输出，包含以下字段：
- contract_type: 合同类型（new_contract, contract_modification, contract_termination）
- modification_type: 变更或解除类型（仅当适用时）
- intent_description: 用户意图描述
- has_original_contract: 是否提供了原有合同
- modification_reason: 变更或解除的原因/说明
- confidence: 置信度
- reasoning: 推理过程"""

    def route(
        self,
        user_input: str,
        has_original_contract: bool = False,
        original_contract_content: Optional[str] = None,
        context: Dict[str, Any] = None
    ) -> SingleContractRoutingResult:
        """
        路由单一合同需求

        Args:
            user_input: 用户的自然语言输入
            has_original_contract: 是否提供了原有合同
            original_contract_content: 原有合同内容（可选）
            context: 额外上下文信息（可选）

        Returns:
            SingleContractRoutingResult: 路由结果
        """
        try:
            logger.info(f"[SingleContractRouter] 开始路由单一合同需求")

            prompt = f"""## 用户需求

{user_input}

"""

            # 添加原合同信息
            if has_original_contract:
                prompt += f"""
## 原有合同信息

用户提供了原有合同：{'是' if has_original_contract else '否'}
"""
                if original_contract_content:
                    # 截取前500个字符作为参考
                    preview = original_contract_content[:500]
                    prompt += f"原有合同内容预览：\n{preview}...\n"

            # 添加上下文信息
            if context:
                prompt += "\n## 上下文信息\n"
                for key, value in context.items():
                    prompt += f"**{key}**：{value}\n"

            prompt += """
## 任务

请分析用户的需求，判断：
1. 是全新合同、变更合同还是解除合同？
2. 如果是变更或解除，具体的变更/解除原因是什么？
3. 描述用户的真实意图
4. 说明你的推理过程

严格按照 JSON 格式输出。"""

            # 使用结构化输出
            structured_llm = self.llm.with_structured_output(SingleContractRoutingResult)
            result: SingleContractRoutingResult = structured_llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ])

            # 检查 result 是否为 None
            if result is None:
                logger.warning("[SingleContractRouter] LLM 返回 None，使用默认结果")
                return SingleContractRoutingResult(
                    contract_type=SingleContractType.NEW_CONTRACT,
                    modification_type=None,
                    intent_description="用户需求合同服务",
                    has_original_contract=has_original_contract,
                    modification_reason="",
                    confidence=0.3,
                    reasoning="LLM 返回 None，使用默认类型"
                )

            # 确保设置 has_original_contract
            if not result.has_original_contract:
                result.has_original_contract = has_original_contract

            logger.info(f"[SingleContractRouter] 路由完成:")
            logger.info(f"  - 合同类型: {result.contract_type}")
            logger.info(f"  - 意图描述: {result.intent_description}")
            logger.info(f"  - 有原合同: {result.has_original_contract}")
            logger.info(f"  - 置信度: {result.confidence}")

            return result

        except Exception as e:
            logger.error(f"[SingleContractRouter] 路由失败: {str(e)}", exc_info=True)

            # 返回默认结果（全新合同）
            return SingleContractRoutingResult(
                contract_type=SingleContractType.NEW_CONTRACT,
                modification_type=None,
                intent_description="用户需求合同服务",
                has_original_contract=has_original_contract,
                modification_reason="",
                confidence=0.5,
                reasoning="路由失败，使用默认类型"
            )


def get_single_contract_router(llm: ChatOpenAI) -> SingleContractRouter:
    """获取单一合同路由器实例"""
    return SingleContractRouter(llm)
