# backend/app/services/contract_generation/agents/contract_intent_analyzer.py
"""
合同意图分析服务（全新合同场景）

核心功能：
这是合同生成流程中"全新合同"场景的第一步，负责：
1. 理解用户的自然语言输入
2. 识别用户意图对应的合同类型（基于知识图谱）
3. 从知识图谱获取该合同类型的完整法律特征
4. 提取关键要素（当事人、标的、价格、期限等）

使用场景：
- 仅在用户需求被判定为"单一合同" → "全新合同"时使用
- 不处理合同变更/解除场景（由 ContractModificationService 处理）
- 不处理合同规划场景（由 ContractPlanningService 处理）
"""

import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ==================== 知识图谱合同类型定义 ====================
# 这些是从知识图谱中提取的所有合同类型

KNOWLEDGE_GRAPH_CONTRACT_TYPES = [
    # 买卖合同类
    "不动产买卖合同", "房屋买卖合同", "设备采购合同", "货物买卖合同", "汽车买卖合同",
    "建材采购合同", "办公用品采购合同", "原材料采购合同",

    # 技术合同类
    "技术开发合同", "技术转让合同", "技术咨询合同", "技术服务合同", "软件开发合同",

    # 委托合同类
    "委托合同", "委托开发合同", "委托销售合同", "委托代理合同", "委托加工合同",

    # 建设工程类
    "建设工程施工合同", "建设工程设计合同", "建设工程监理合同", "装修工程合同",
    "安装工程合同", "EPC工程总承包合同",

    # 租赁合同类
    "租赁合同", "房屋租赁合同", "设备租赁合同", "车辆租赁合同", "场地租赁合同",

    # 劳动合同类
    "劳动合同", "劳务合同", "雇佣合同", "实习协议", "退休返聘协议",

    # 股权投资类
    "股权转让合同", "股权收购合同", "增资扩股协议", "股东协议", "投资协议",
    "合伙协议", "有限合伙协议",

    # 知识产权类
    "软件许可合同", "专利实施许可合同", "商标使用许可合同", "版权转让合同",
    "知识产权授权合同",

    # 借款融资类
    "借款合同", "借款协议", "抵押借款合同", "保证合同", "融资租赁合同",

    # 其他合同类
    "承揽合同", "运输合同", "保管合同", "仓储合同", "赠与合同", "物业服务合同",
    "中介合同", "行纪合同", "旅游合同", "教育培训合同",
]


class IntentResult(BaseModel):
    """意图识别结果"""
    # 识别的合同类型（来自知识图谱）
    contract_type: str = Field(
        description="识别的合同类型名称，必须从知识图谱的合同类型中选择"
    )

    # 用户意图描述
    intent_description: str = Field(
        description="用简洁的语言描述用户的真实意图"
    )

    # 关键要素提取
    key_elements: Dict[str, str] = Field(
        description="提取的关键要素，如当事人、标的、价格等",
        default_factory=dict
    )

    # 置信度
    confidence: float = Field(
        description="识别的置信度，0-1之间",
        ge=0.0,
        le=1.0
    )

    # 是否需要澄清
    needs_clarification: bool = Field(
        description="是否需要用户澄清更多信息",
        default=False
    )

    # 澄清问题列表
    clarification_questions: List[str] = Field(
        description="需要向用户澄清的问题列表",
        default_factory=list
    )


class ContractIntentAnalyzer:
    """
    合同意图分析服务（全新合同场景）

    使用 LLM 理解用户的自然语言输入，识别其意图对应的合同类型
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        contract_types_str = "\n".join(f"- {ct}" for ct in KNOWLEDGE_GRAPH_CONTRACT_TYPES)

        return f"""你是一个专业的法律合同顾问，擅长理解用户的合同需求并识别合同类型。

## 你的任务

根据用户的自然语言描述，识别用户意图对应的合同类型，并提取关键信息。

## 重要提示

**你处理的都是"全新合同"场景**
- 用户没有提供现有合同
- 用户需要从头生成一份新合同
- 不要处理合同变更或解除的需求

## 知识图谱中的合同类型

{contract_types_str}

## 分析原则

1. **理解核心意图**：关注用户真正想达成的交易，而非表面表述
2. **优先精确匹配**：优先选择最具体的合同类型（如"股权转让合同"而不是"协议"）
3. **考虑关键要素**：提取当事人、标的、价格、期限等关键信息
4. **识别缺失信息**：如果关键信息缺失，需要提出澄清问题

## 特殊情况处理

- **股权转让/股权收购/增资扩股** → 股权转让合同 或 增资扩股协议
- **软件开发/委托开发/网站开发** → 软件开发合同 或 委托开发合同
- **设备采购/货物采购** → 设备采购合同 或 货物买卖合同
- **技术合作/技术服务** → 技术服务合同 或 技术开发合同
- **房屋出租/场地出租** → 房屋租赁合同 或 场地租赁合同
- **借款/融资/贷款** → 借款合同

## 提取的关键要素

根据合同类型提取相应的关键要素：
- **当事人**：甲方（转让方/委托方/买方等）、乙方（受让方/受托方/卖方等）
- **标的**：股权、设备、房屋、服务内容等
- **价格/对价**：金额、支付方式等
- **期限**：履行期限、交付时间等
- **其他特殊要求**

严格按照 JSON 格式输出。"""

    def analyze(self, user_input: str, context: Dict[str, Any] = None) -> IntentResult:
        """
        分析用户意图，识别合同类型

        Args:
            user_input: 用户的自然语言输入
            context: 额外上下文信息（可选）

        Returns:
            IntentResult: 意图识别结果
        """
        try:
            logger.info(f"[ContractIntentAnalyzer] 开始分析用户意图: {user_input[:100]}...")

            # 构建提示词
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

请分析用户的真实意图：
1. 识别最合适的合同类型（从知识图谱的合同类型中选择）
2. 描述用户的真实意图
3. 提取关键要素（当事人、标的、价格、期限等）
4. 判断是否需要澄清更多信息
5. 如果需要澄清，列出具体问题

严格按照 JSON 格式输出。"""

            # 使用结构化输出
            try:
                structured_llm = self.llm.with_structured_output(IntentResult)
                result: IntentResult = structured_llm.invoke([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=prompt)
                ])
                logger.debug(f"[ContractIntentAnalyzer] structured_output 返回: {result}")
            except Exception as e:
                # 某些模型（如 Qwen3）可能不支持 with_structured_output
                # 使用基于 JSON 解析的降级方案
                logger.warning(f"[ContractIntentAnalyzer] with_structured_output 失败: {e}，使用 JSON 解析降级方案")
                result = self._parse_json_response(user_input, prompt)

            # 验证结果是否有效（with_structured_output 可能返回 None）
            if result is None:
                logger.error("[ContractIntentAnalyzer] structured_output 返回None，使用 JSON 解析降级方案")
                result = self._parse_json_response(user_input, prompt)

            # 调试日志：记录LLM原始返回
            logger.info(f"[ContractIntentAnalyzer] 意图分析完成:")
            logger.info(f"  - 合同类型: {result.contract_type}")
            logger.info(f"  - 意图描述: {result.intent_description}")
            logger.info(f"  - 置信度: {result.confidence}")

            # 验证合同类型是否在知识图谱中
            if result.contract_type not in KNOWLEDGE_GRAPH_CONTRACT_TYPES:
                logger.warning(f"[ContractIntentAnalyzer] 识别的合同类型不在知识图谱中: {result.contract_type}")
                # 尝试模糊匹配
                original_type = result.contract_type
                result.contract_type = self._fuzzy_match_contract_type(result.contract_type)
                logger.info(f"[ContractIntentAnalyzer] 模糊匹配: '{original_type}' -> '{result.contract_type}'")

            logger.info(f"[ContractIntentAnalyzer] 最终合同类型: {result.contract_type}")
            logger.info(f"[ContractIntentAnalyzer] 需要澄清: {result.needs_clarification}")

            return result

        except Exception as e:
            logger.error(f"[ContractIntentAnalyzer] 意图分析失败: {str(e)}", exc_info=True)
            # 使用基于关键词的降级识别
            logger.info("[ContractIntentAnalyzer] 使用关键词降级识别")
            return self._fallback_keyword_detection(user_input)

    def _fuzzy_match_contract_type(self, input_type: str) -> str:
        """
        模糊匹配合同类型

        当 LLM 返回的合同类型不在知识图谱中时，尝试找到最相似的类型
        """
        input_lower = input_type.lower()

        # 关键词映射
        keyword_mapping = {
            "股权": "股权转让合同",
            "转让": "技术转让合同",
            "软件": "软件开发合同",
            "开发": "软件开发合同",
            "委托": "委托合同",
            "采购": "设备采购合同",
            "买卖": "货物买卖合同",
            "租赁": "租赁合同",
            "房屋": "房屋租赁合同",
            "借款": "借款合同",
            "技术": "技术服务合同",
            "服务": "技术服务合同",
            "施工": "建设工程施工合同",
            "工程": "建设工程施工合同",
        }

        # 精确匹配
        if input_type in KNOWLEDGE_GRAPH_CONTRACT_TYPES:
            return input_type

        # 关键词匹配
        for keyword, contract_type in keyword_mapping.items():
            if keyword in input_type:
                return contract_type

        # 默认返回
        return "委托合同"

    def _fallback_keyword_detection(self, user_input: str) -> IntentResult:
        """
        基于关键词的降级合同类型识别

        当LLM调用失败时，使用关键词匹配来识别合同类型
        """
        user_input_lower = user_input.lower()

        # 关键词映射（优先级从高到低）
        keyword_mapping = [
            # 借款类
            ("借款", "借款合同"),
            ("借款协议", "借款协议"),
            ("贷款", "借款合同"),
            ("融资", "借款合同"),
            # 买卖类（【修复】添加购房相关关键词）
            ("购房", "房屋买卖合同"),
            ("买房", "房屋买卖合同"),
            ("房产", "房屋买卖合同"),
            ("房子", "房屋买卖合同"),
            ("不动产", "不动产买卖合同"),
            ("买卖", "货物买卖合同"),
            ("采购", "设备采购合同"),
            ("购买", "货物买卖合同"),
            # 股权类
            ("股权", "股权转让合同"),
            ("转让", "技术转让合同"),
            ("增资", "增资扩股协议"),
            # 技术类
            ("软件", "软件开发合同"),
            ("技术开发", "技术开发合同"),
            ("技术服务", "技术服务合同"),
            # 委托类
            ("委托", "委托合同"),
            # 租赁类
            ("租赁", "租赁合同"),
            ("出租", "房屋租赁合同"),
            # 建设类
            ("施工", "建设工程施工合同"),
            ("工程", "建设工程施工合同"),
            # 劳动类
            ("雇佣", "劳动合同"),
            ("聘用", "聘用协议"),
        ]

        # 按优先级匹配
        for keyword, contract_type in keyword_mapping:
            if keyword in user_input_lower:
                logger.info(f"[ContractIntentAnalyzer] 关键词匹配: '{keyword}' -> '{contract_type}'")
                return IntentResult(
                    contract_type=contract_type,
                    intent_description=f"基于关键词识别为{contract_type}",
                    key_elements={"识别关键词": keyword},
                    confidence=0.7,
                    needs_clarification=True,
                    clarification_questions=[
                        f"系统识别您的需求为{contract_type}，请确认是否正确",
                        "请补充合同的详细信息（当事人、标的、价格、期限等）"
                    ]
                )

        # 【修复】当所有分析都失败时，使用用户输入的前15个字作为合同类型，而不是默认返回"委托合同"
        # 这样至少能保留用户的原始意图，避免完全误判
        user_input_prefix = user_input[:15].strip() if user_input else "合同"
        logger.warning(f"[ContractIntentAnalyzer] 关键词匹配失败，使用用户输入前缀作为合同类型: '{user_input_prefix}'")
        return IntentResult(
            contract_type=user_input_prefix,
            intent_description=f"未能识别具体合同类型，使用用户描述: {user_input_prefix}",
            key_elements={"用户原始输入": user_input},
            confidence=0.3,
            needs_clarification=True,
            clarification_questions=[
                f"系统识别您的需求可能与'{user_input_prefix}'相关，请确认合同类型",
                "请补充合同的详细信息（当事人、标的、价格、期限等）"
            ]
        )

    def _parse_json_response(self, user_input: str, prompt: str) -> IntentResult:
        """
        使用 JSON 解析的降级方案

        当 with_structured_output 不可用时，调用普通 LLM 并解析返回的 JSON
        """
        try:
            logger.info("[ContractIntentAnalyzer] 使用 JSON 解析降级方案")

            response = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ])

            # 提取响应内容
            response_text = response.content if hasattr(response, 'content') else str(response)
            logger.debug(f"[ContractIntentAnalyzer] LLM 原始响应: {response_text[:500]}...")

            # 尝试提取 JSON（处理可能的前后缀文本）
            import json
            import re

            # 策略1: 查找 ```json 代码块
            if "```json" in response_text:
                match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
                    logger.debug(f"[ContractIntentAnalyzer] 从 ```json 代码块提取 JSON")
                else:
                    json_str = None
            elif "```" in response_text:
                # 策略2: 查找普通 ``` 代码块
                match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
                    logger.debug(f"[ContractIntentAnalyzer] 从 ``` 代码块提取 JSON")
                else:
                    json_str = None
            else:
                # 策略3: 查找最外层的 {}（支持嵌套）
                start = response_text.find('{')
                if start != -1:
                    # 使用栈来匹配嵌套的 {}
                    stack = []
                    for i in range(start, len(response_text)):
                        if response_text[i] == '{':
                            stack.append(i)
                        elif response_text[i] == '}':
                            if stack:
                                stack.pop()
                            if not stack:
                                json_str = response_text[start:i+1]
                                logger.debug(f"[ContractIntentAnalyzer] 从裸 JSON 提取")
                                break
                    else:
                        # 没有找到闭合的 }
                        json_str = None
                else:
                    json_str = None

            if not json_str:
                raise ValueError("无法从响应中提取 JSON")

            logger.debug(f"[ContractIntentAnalyzer] 提取的 JSON 字符串: {json_str[:200]}...")

            # 解析 JSON
            data = json.loads(json_str)

            # 验证必需字段
            contract_type = data.get("contract_type", "")
            if not contract_type:
                raise ValueError("JSON 中缺少 contract_type 字段")

            # 创建 IntentResult 对象
            result = IntentResult(
                contract_type=contract_type,
                intent_description=data.get("intent_description", "基于LLM分析"),
                key_elements=data.get("key_elements", {}),
                confidence=float(data.get("confidence", 0.7)),
                needs_clarification=bool(data.get("needs_clarification", False)),
                clarification_questions=data.get("clarification_questions", [])
            )

            logger.info(f"[ContractIntentAnalyzer] JSON 解析成功: {result.contract_type}")
            return result

        except Exception as e:
            logger.error(f"[ContractIntentAnalyzer] JSON 解析失败: {e}，使用关键词降级识别")
            return self._fallback_keyword_detection(user_input)


def get_contract_intent_analyzer(llm: ChatOpenAI) -> ContractIntentAnalyzer:
    """获取合同意图分析器实例"""
    return ContractIntentAnalyzer(llm)
