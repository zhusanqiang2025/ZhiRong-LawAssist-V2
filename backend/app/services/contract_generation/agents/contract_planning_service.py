# backend/app/services/contract_generation/agents/contract_planning_service.py
"""
合同规划服务

核心功能：
当用户需求被判定为"合同规划"时，该服务负责：
1. 分析复杂交易的合同需求
2. 规划需要的合同清单
3. 确定合同签署顺序
4. 识别合同关联关系
5. 输出合约规划给用户确认

支持两种模式：
- 单模型模式：使用单个 LLM 进行规划（原有功能）
- 多模型综合融合模式：使用多个模型并行规划，综合融合生成最优方案（新功能）

用户确认后才会进入合同生成流程。
"""

import logging
import json
import os
import re
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from .models import ContractPlanning, PlannedContract

logger = logging.getLogger(__name__)


class ContractPlanningService:
    """
    合同规划服务

    处理需要多份合同的复杂交易，输出合约规划

    支持两种模式：
    1. 单模型模式：使用单个 LLM 进行规划（默认）
    2. 多模型综合融合模式：使用多个模型并行规划，综合融合生成最优方案
    """

    def __init__(self, llm: ChatOpenAI, enable_multi_model: Optional[bool] = None):
        """
        初始化合同规划服务

        Args:
            llm: 默认使用的 LLM 实例
            enable_multi_model: 是否启用多模型综合融合模式
                                None: 根据 ENABLE_MULTI_MODEL_PLANNING 环境变量自动判断
                                True: 强制启用多模型模式
                                False: 强制使用单模型模式
        """
        self.llm = llm
        self.system_prompt = self._build_system_prompt()

        # 确定是否使用多模型模式
        if enable_multi_model is None:
            self.enable_multi_model = os.getenv("ENABLE_MULTI_MODEL_PLANNING", "false").lower() == "true"
        else:
            self.enable_multi_model = enable_multi_model

        if self.enable_multi_model:
            logger.info("[ContractPlanningService] 多模型综合融合模式已启用")
        else:
            logger.info("[ContractPlanningService] 单模型模式")

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的交易结构设计专家。你的任务是将复杂的交易拆解为多份合同的组合。

## 规划原则

### 合同拆分原则
1. **一合同一事项** - 每份合同只解决一个核心法律关系
2. **先主后辅** - 先签署主要合同，再签署配套合同
3. **风险隔离** - 通过不同合同隔离不同风险
4. **灵活性** - 为后续变化留有余地

### 常见合同组合

#### 股权投资交易
1. **股权转让协议** - 股权交易主协议
2. **股东协议** - 股东间权利义务、公司治理
3. **公司章程修正案** - 公司治理结构调整

#### 资产收购交易
1. **资产收购协议** - 资产交易主协议
2. **债权债务处理协议** - 债权债务安排
3. **员工安置协议** - 员工处理方案

#### 合作开发项目
1. **合作协议** - 合作主协议
2. **知识产权协议** - IP归属、使用、保护
3. **保密协议** - 商业秘密保护

#### 复杂并购交易
1. **投资意向书** - 初步框架
2. **股权转让协议** - 主交易协议
3. **陈述与保证协议** - 各方声明保证
4. **竞业禁止协议** - 核心人员竞业限制
5. **过渡期管理协议** - 交割前期间管理

## 输出格式

严格按照以下 JSON 格式输出：

```json
{
  "contracts": [
    {
      "id": "contract_1",
      "title": "合同标题",
      "contract_type": "合同类型",
      "purpose": "该合同在整体交易中的目的和作用",
      "key_parties": ["甲方", "乙方"],
      "priority": 1,
      "dependencies": [],
      "estimated_sections": ["标的条款", "价款条款", "履行条款"]
    }
  ],
  "signing_order": ["contract_1", "contract_2", "contract_3"],
  "relationships": {
    "contract_1": ["contract_2 依赖 contract_1 的签署"],
    "contract_2": ["contract_3 依赖 contract_2 的签署"]
  },
  "risk_notes": [
    "风险提示1",
    "风险提示2"
  ],
  "overall_description": "整体交易结构的说明",
  "total_estimated_contracts": 3
}
```

## 输出要求
- 只返回 JSON，不要其他说明
- 确保合同之间的逻辑关系清晰
- 标注每份合同的核心作用
- 明确签署的先后顺序
- 指出关键风险点"""

    def plan(self, user_input: str, context: Dict[str, Any] = None) -> ContractPlanning:
        """
        规划合同清单

        Args:
            user_input: 用户的自然语言输入
            context: 额外上下文信息（可选）

        Returns:
            ContractPlanning: 合同规划结果
        """
        # ✨ 检查是否使用多模型综合融合模式
        if self.enable_multi_model:
            return self._plan_with_multi_model(user_input, context)
        else:
            return self._plan_with_single_model(user_input, context)

    def _plan_with_single_model(self, user_input: str, context: Dict[str, Any] = None) -> ContractPlanning:
        """
        使用单模型进行规划（原有功能）

        Args:
            user_input: 用户的自然语言输入
            context: 额外上下文信息（可选）

        Returns:
            ContractPlanning: 合同规划结果
        """
        try:
            logger.info(f"[ContractPlanningService] 开始规划合同（单模型模式）")

            prompt = f"""## 用户需求

{user_input}

"""

            # 添加上下文信息
            if context:
                prompt += "\n## 上下文信息\n"
                for key, value in context.items():
                    prompt += f"**{key}**：{value}\n"

            prompt += """
## 规划要求

请将上述交易拆解为多份合同的组合，考虑：
1. 交易涉及的法律关系复杂度
2. 风险隔离需求
3. 签署的先后顺序
4. 合同之间的关联关系

返回 JSON 格式的合同规划。"""

            response = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ])

            result = self._parse_response(response.content)

            logger.info(f"[ContractPlanningService] 规划完成，合同数量: {result.total_estimated_contracts}")

            return result

        except Exception as e:
            logger.error(f"[ContractPlanningService] 规划失败: {str(e)}", exc_info=True)
            return self._get_default_planning()

    def _plan_with_multi_model(self, user_input: str, context: Dict[str, Any] = None) -> ContractPlanning:
        """
        使用多模型综合融合进行规划（新功能）

        Args:
            user_input: 用户的自然语言输入
            context: 额外上下文信息（可选）

        Returns:
            ContractPlanning: 合同规划结果
        """
        try:
            logger.info(f"[ContractPlanningService] 开始规划合同（多模型综合融合模式）")

            # 导入多模型规划服务
            from .multi_model_planning_service import get_multi_model_planning_service

            # 获取多模型规划服务
            multi_model_service = get_multi_model_planning_service()

            if multi_model_service is None:
                logger.warning("[ContractPlanningService] 多模型规划服务不可用，降级到单模型模式")
                return self._plan_with_single_model(user_input, context)

            # 执行多模型综合融合规划
            result = multi_model_service.plan(
                user_input=user_input,
                context=context or {}
            )

            # 提取最终规划
            final_planning = result.final_planning

            # 记录融合报告
            logger.info(f"[ContractPlanningService] 多模型综合融合完成:")
            logger.info(f"  - 最终合同数量: {len(final_planning.contracts)}")
            logger.info(f"  - 融合策略: {result.synthesis_report.fusion_strategy[:100]}...")
            logger.info(f"  - 执行统计: 总耗时={result.execution_stats['total_time']:.2f}s, "
                       f"成功模型数={result.execution_stats['successful_count']}")

            return final_planning

        except Exception as e:
            logger.error(f"[ContractPlanningService] 多模型规划失败: {str(e)}", exc_info=True)
            logger.warning("[ContractPlanningService] 降级到单模型模式")
            return self._plan_with_single_model(user_input, context)

    def _parse_response(self, response: str) -> ContractPlanning:
        """解析 LLM 响应"""
        try:
            # 尝试直接解析 JSON
            data = json.loads(response)

            # 转换为 Pydantic 模型
            contracts = [
                PlannedContract(**contract_data)
                for contract_data in data.get("contracts", [])
            ]

            return ContractPlanning(
                contracts=contracts,
                signing_order=data.get("signing_order", []),
                relationships=data.get("relationships", {}),
                risk_notes=data.get("risk_notes", []),
                overall_description=data.get("overall_description", ""),
                total_estimated_contracts=data.get("total_estimated_contracts", len(contracts))
            )

        except json.JSONDecodeError:
            # 尝试提取 JSON 代码块
            json_match = re.search(r'```json\s*(.+?)\s*```', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    contracts = [PlannedContract(**c) for c in data.get("contracts", [])]
                    return ContractPlanning(
                        contracts=contracts,
                        signing_order=data.get("signing_order", []),
                        relationships=data.get("relationships", {}),
                        risk_notes=data.get("risk_notes", []),
                        overall_description=data.get("overall_description", ""),
                        total_estimated_contracts=data.get("total_estimated_contracts", len(contracts))
                    )
                except (json.JSONDecodeError, TypeError):
                    pass

            # 尝试提取花括号内容
            brace_match = re.search(r'\{.+?\}', response, re.DOTALL)
            if brace_match:
                try:
                    data = json.loads(brace_match.group(0))
                    contracts = [PlannedContract(**c) for c in data.get("contracts", [])]
                    return ContractPlanning(
                        contracts=contracts,
                        signing_order=data.get("signing_order", []),
                        relationships=data.get("relationships", {}),
                        risk_notes=data.get("risk_notes", []),
                        overall_description=data.get("overall_description", ""),
                        total_estimated_contracts=data.get("total_estimated_contracts", len(contracts))
                    )
                except (json.JSONDecodeError, TypeError):
                    pass

            logger.warning(f"[ContractPlanningService] 解析失败，使用默认规划")
            return self._get_default_planning()

    def _get_default_planning(self) -> ContractPlanning:
        """返回默认规划"""
        return ContractPlanning(
            contracts=[
                PlannedContract(
                    id="contract_1",
                    title="主协议",
                    contract_type="contract",
                    purpose="规范双方主要的权利义务",
                    key_parties=["甲方", "乙方"],
                    priority=1,
                    dependencies=[],
                    estimated_sections=[]
                )
            ],
            signing_order=["contract_1"],
            relationships={},
            risk_notes=[],
            overall_description="未能生成详细规划，建议提供更多信息",
            total_estimated_contracts=1
        )


def get_contract_planning_service(
    llm: ChatOpenAI,
    enable_multi_model: Optional[bool] = None
) -> ContractPlanningService:
    """
    获取合同规划服务实例

    Args:
        llm: 默认使用的 LLM 实例
        enable_multi_model: 是否启用多模型综合融合模式
                            None: 根据 ENABLE_MULTI_MODEL_PLANNING 环境变量自动判断
                            True: 强制启用多模型模式
                            False: 强制使用单模型模式

    Returns:
        ContractPlanningService: 合同规划服务实例
    """
    return ContractPlanningService(llm, enable_multi_model=enable_multi_model)
