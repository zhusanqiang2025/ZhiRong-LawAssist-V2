"""
法律咨询模块 - LangGraph 工作流实现（重构版）

实现两阶段咨询流程：
1. 律师助理节点：使用 LLM 进行问题分类和意图识别
2. 专业律师节点：根据分类结果提供专业法律建议（内部自主判断是否需要检索）

架构设计：
    用户问题 → 律师助理（分类）→ 专业律师（咨询，按需检索）→ 结构化输出
"""

from typing import Dict, Any, List, Optional, Tuple, TypedDict, Annotated
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from operator import add

# LangGraph 和 LangChain 相关导入
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


# ==================== 辅助函数 ====================

async def get_legal_search_results(question: str, domain: str = None) -> dict:
    """获取法律检索结果（异步）"""
    try:
        from app.services.legal_search_skill import get_legal_search_skill, format_search_results_for_llm

        skill = get_legal_search_skill()

        # 并行检索法规和案例
        import asyncio
        laws_task = skill.search_laws(question, max_results=3)
        cases_task = skill.search_cases(question, max_results=3)

        laws, cases = await asyncio.gather(laws_task, cases_task)

        return {
            "laws": laws,
            "cases": cases,
            "formatted": format_search_results_for_llm({"laws": laws, "cases": cases})
        }
    except Exception as e:
        logger.warning(f"[法律检索] 检索失败: {e}")
        return {"laws": [], "cases": [], "formatted": ""}


# ==================== 法律检索配置 ====================

# 需要强制检索的法律领域（确保引用现行法律）
LEGAL_DOMAINS_REQUIRING_SEARCH = [
    # 民法典相关
    "合同法", "合同纠纷", "民法典·合同编",
    "物权法", "物权纠纷", "民法典·物权编",
    "侵权责任法", "侵权纠纷", "民法典·侵权责任编",
    "婚姻法", "婚姻家庭", "民法典·婚姻家庭编",
    "继承法", "继承纠纷", "民法典·继承编",

    # 其他民商事法律
    "公司法", "公司纠纷",
    "合伙企业法", "合伙纠纷",
    "破产法", "破产清算",
    "劳动法", "劳动争议",
]

# 已废止法律映射（用于后处理检查）
ABOLISHED_LAWS_MAPPING = {
    "《合同法》": "《民法典》合同编",
    "《中华人民共和国合同法》": "《中华人民共和国民法典》",
    "《物权法》": "《民法典》物权编",
    "《中华人民共和国物权法》": "《中华人民共和国民法典》",
    "《侵权责任法》": "《民法典》侵权责任编",
    "《中华人民共和国侵权责任法》": "《中华人民共和国民法典》",
    "《婚姻法》": "《民法典》婚姻家庭编",
    "《中华人民共和国婚姻法》": "《中华人民共和国民法典》",
    "《继承法》": "《民法典》继承编",
    "《中华人民共和国继承法》": "《中华人民共和国民法典》",
}

# 法律领域规范化映射（将不规范或不准确的分类映射到标准分类）
LEGAL_DOMAIN_NORMALIZATION = {
    # 不规范或过时的分类
    "建工法": "建设工程",
    "建筑法": "建设工程",
    "交通法": "侵权责任法",
    "交通事故": "侵权责任法",
    "交通肇事": "侵权责任法",

    # 更具体的分类（映射到更通用的分类）
    "房产纠纷": "物权法",
    "房屋买卖": "合同法",
    "房屋租赁": "合同法",
    "物业管理": "合同法",
    "借贷纠纷": "合同法",
    "借款纠纷": "合同法",
    "民间借贷": "合同法",
    "债务纠纷": "合同法",
    "股权纠纷": "公司法",
    "股东纠纷": "公司法",
    "投资纠纷": "公司法",
    "知识产权纠纷": "知识产权",
    "专利纠纷": "知识产权",
    "商标纠纷": "知识产权",
    "著作权纠纷": "知识产权",
    "工伤赔偿": "劳动法",
    "工伤认定": "劳动法",
    "社会保险": "劳动法",
    "违法解除": "劳动法",
    "违法辞退": "劳动法",
    "离婚诉讼": "婚姻家庭法",
    "抚养权": "婚姻家庭法",
    "赡养费": "婚姻家庭法",
    "抚养费": "婚姻家庭法",
    "财产分割": "婚姻家庭法",
    "遗嘱继承": "婚姻家庭法",
    "法定继承": "婚姻家庭法",

    # 英文或中英文混合
    "Contract Law": "合同法",
    "Labor Law": "劳动法",
    "Company Law": "公司法",
    "Criminal Law": "刑法",

    # 其他常见不规范表述
    "法律咨询": "民法",
    "法律问题": "民法",
    "其他": "民法",
    "未知": "民法",
}


def _normalize_legal_domain(domain: str) -> tuple[str, bool]:
    """
    规范化法律领域分类

    Args:
        domain: LLM 输出的法律领域

    Returns:
        (规范化后的领域, 是否进行了修正)
    """
    if not domain:
        return "民法", True

    # 去除空格和引号
    domain_clean = domain.strip().strip('"').strip("'")

    # 查找映射
    normalized_domain = LEGAL_DOMAIN_NORMALIZATION.get(domain_clean)

    if normalized_domain:
        logger.info(f"[领域规范化] '{domain_clean}' → '{normalized_domain}'")
        return normalized_domain, True

    # 如果没有映射，检查是否已经包含标准关键词
    standard_keywords = ["民法", "劳动法", "合同法", "公司法", "侵权责任法",
                       "婚姻家庭法", "建设工程", "刑法", "行政法", "知识产权",
                       "物权法", "破产法", "票据法", "证券法", "保险法", "海商法"]

    for keyword in standard_keywords:
        if keyword in domain_clean:
            # 如果已经是标准分类，直接返回
            if domain_clean == keyword or domain_clean.startswith(keyword) and domain_clean not in standard_keywords:
                logger.info(f"[领域规范化] '{domain_clean}' 已是标准分类")
                return domain_clean, False

    # 未找到映射，返回原值并记录
    logger.warning(f"[领域规范化] 未找到 '{domain_clean}' 的标准映射，保持原值")
    return domain_clean, False


def _check_and_fix_legal_references(text: str) -> tuple[str, bool]:
    """
    检查并修正过时的法律引用

    Args:
        text: LLM 输出的文本

    Returns:
        (修正后的文本, 是否有修正)
    """
    modified = False
    modifications = []

    for old_law, new_law in ABOLISHED_LAWS_MAPPING.items():
        if old_law in text:
            text = text.replace(old_law, new_law)
            modified = True
            modifications.append(f"{old_law} → {new_law}")

    if modified:
        logger.warning(f"[法律引用修正] 检测到过时引用，已自动修正: {', '.join(modifications)}")

    return text, modified


def _detect_user_intent(question: str) -> str:
    """
    检测用户在多轮对话中的意图

    返回：concise（简洁）, detailed（详细）, specific（具体问题）, normal（正常）
    """
    question_lower = question.lower()

    # 要求简洁的关键词
    concise_keywords = ["简要", "简短", "简单", "概括", "总结", "一句话", "太长"]
    if any(kw in question for kw in concise_keywords):
        return "concise"

    # 要求详细的关键词
    detailed_keywords = ["详细", "展开", "具体说明", "深入", "更多"]
    if any(kw in question for kw in detailed_keywords):
        return "detailed"

    # 特定问题
    specific_keywords = ["怎么", "如何", "什么", "为什么", "是否", "可以"]
    if any(kw in question for kw in specific_keywords):
        return "specific"

    return "normal"


# ==================== 数据模型定义 ====================

class ConsultationType(str, Enum):
    """法律咨询类型枚举"""
    CONTRACT_LAW = "合同法"
    LABOR_LAW = "劳动法"
    CORPORATE_LAW = "公司法"
    CIVIL_LAW = "民法"
    CRIMINAL_LAW = "刑法"
    CONSTRUCTION_LAW = "建工法"
    BANKRUPTCY_LAW = "破产法"
    TRAFFIC_LAW = "交通肇事"
    FAMILY_LAW = "婚姻家庭法"
    INTELLECTUAL_PROPERTY = "知识产权"
    OTHER = "其他"


class ConsultationState(TypedDict):
    """
    咨询工作流的状态

    这个状态会在各个节点之间传递和更新
    """
    # 输入
    question: str                          # 用户的问题
    context: Dict[str, Any]                # 额外的上下文信息
    conversation_history: List[BaseMessage]  # 对话历史（可选）

    # 两阶段执行控制
    user_confirmed: bool                   # 用户是否已确认（第二阶段标志）
    selected_suggested_questions: Optional[List[str]]  # 用户选择的建议问题（第二阶段）

    # 多轮对话支持（新增）
    is_follow_up: bool                      # 是否为后续问题（多轮对话）
    session_id: Optional[str]               # 会话ID（用于持久化）
    previous_specialist_output: Optional[Dict[str, Any]]  # 上一轮专业律师输出

    # 律师助理节点输出
    classification_result: Optional[Dict[str, Any]]  # 分类结果
    specialist_role: Optional[str]         # 专业律师角色
    confidence: Optional[float]            # 分类置信度

    # 资料分析节点输出 (新增)
    document_analysis: Optional[Dict[str, Any]]  # 文档分析结果

    # 专业律师节点输出
    legal_analysis: Optional[str]          # 法律分析
    legal_advice: Optional[str]            # 法律建议
    risk_warning: Optional[str]            # 风险提醒
    action_steps: Optional[List[str]]      # 行动步骤
    relevant_laws: Optional[List[str]]     # 相关法律

    # 最终输出
    final_report: Optional[str]            # 最终报告
    need_follow_up: bool                   # 是否需要后续咨询
    follow_up_questions: List[str]         # 后续问题

    # 错误处理
    error: Optional[str]                   # 错误信息
    current_step: str                      # 当前步骤（用于调试）


@dataclass
class ConsultationOutput:
    """咨询输出（用于 API 响应）"""
    question: str
    legal_basis: str
    analysis: str
    advice: str
    risk_warning: str
    action_steps: List[str]
    classification_result: Optional[Dict[str, Any]] = None
    need_follow_up: bool = False
    follow_up_questions: List[str] = field(default_factory=list)


# ==================== LLM 初始化 ====================

def get_consultation_llm() -> ChatOpenAI:
    """
    获取用于法律咨询的 LLM 实例

    模型选择：Qwen3-235B-A22B-Thinking-2507

    模型特点：
    - 235B 参数，深度思考能力强
    - 超时时间 120s，max_tokens 16000
    - 适合法律分类、分析和推理任务
    - 支持结构化输出（JSON）和长文本生成

    备用方案：
    1. DeepSeek-R1-0528（性价比高）
    2. 默认 OpenAI 配置
    """
    try:
        from app.core.llm_config import get_qwen3_thinking_llm
        llm = get_qwen3_thinking_llm()
        logger.info("[法律咨询] 使用 Qwen3-235B-Thinking 模型")
        return llm
    except Exception as e:
        logger.warning(f"Qwen3-Thinking 不可用: {e}，尝试使用 DeepSeek")
        try:
            from app.core.llm_config import get_deepseek_llm
            llm = get_deepseek_llm()
            logger.info("[法律咨询] 使用 DeepSeek-R1 模型")
            return llm
        except Exception as e2:
            logger.warning(f"DeepSeek 不可用: {e2}，使用默认 LLM")
            from app.core.llm_config import get_default_llm
            return get_default_llm()


# 兼容旧接口
def get_assistant_llm() -> ChatOpenAI:
    """获取律师助理节点的 LLM（与咨询使用同一模型）"""
    return get_consultation_llm()


def get_specialist_llm() -> ChatOpenAI:
    """获取专业律师节点的 LLM（与咨询使用同一模型）"""
    return get_consultation_llm()


# ==================== 节点1：律师助理（问题分类）====================

ASSISTANT_SYSTEM_PROMPT = """你是律师事务所前台助理，负责识别客户咨询的法律领域。

**任务**：分析客户问题，识别法律领域并提供引导性问题

**法律领域快速参考表**（用于准确分类）：
| 用户问题关键词 | 法律领域 |
|--------------|----------|
| 交通事故、人身损害、财产损害、医疗纠纷、产品责任、环境污染、打架斗殴 | 侵权责任法 |
| 工资拖欠、违法解除、工伤赔偿、社会保险、劳动合同、劳务派遣 | 劳动法 |
| 违约、欠款、借款、租赁、买卖、服务合同、建设工程款 | 合同法 |
| 股权、股东、公司治理、股权转让、公司清算、法人代表 | 公司法 |
| 离婚、抚养权、赡养费、财产分割、遗嘱继承、收养、登记结婚 | 婚姻家庭法 |
| 工程款、施工、质量纠纷、工期延误、违法分包、实际施工人 | 建设工程 |
| 刑事案件、辩护、取保候审、减刑假释、缓刑、不予起诉 | 刑法 |
| 罚款、拘留、吊销执照、行政复议、行政诉讼 | 行政法 |

**输出格式**：必须严格按照以下 JSON 格式输出，不要添加任何其他文字：

**示例1（劳动法）**：
```json
{
    "primary_type": "劳动法",
    "specialist_role": "劳动法专业律师",
    "confidence": 0.85,
    "urgency": "high",
    "complexity": "medium",
    "key_entities": ["公司名称", "员工"],
    "key_facts": ["公司拖欠工资3个月", "员工被迫辞职"],
    "relevant_laws": ["《劳动合同法》", "《工资支付暂行规定》"],
    "preliminary_assessment": "用人单位拖欠工资，劳动者可依法维权",
    "need_confirmation": true,
    "basic_summary": "员工咨询公司拖欠工资问题，涉及劳动法领域",
    "direct_questions": ["公司拖欠工资该如何维权？", "应该通过什么途径追讨工资？"],
    "suggested_questions": ["如何收集拖欠工资的证据？", "劳动仲裁的申请流程是什么？", "可以主张哪些经济补偿金？", "用人单位拖欠工资的法律责任有哪些？"],
    "recommended_approach": "转交劳动法专业律师深度分析"
}
```

**示例2（侵权责任法/交通事故）**：
```json
{
    "primary_type": "侵权责任法",
    "specialist_role": "侵权责任法专业律师",
    "confidence": 0.90,
    "urgency": "high",
    "complexity": "medium",
    "key_entities": ["受害人", "肇事方", "保险公司"],
    "key_facts": ["发生交通事故造成损害", "需要确定赔偿责任和金额"],
    "relevant_laws": ["《道路交通安全法》", "《民法典》侵权责任编"],
    "preliminary_assessment": "交通事故属于侵权责任纠纷，应根据事故责任认定和相关法律确定赔偿责任",
    "need_confirmation": true,
    "basic_summary": "用户咨询交通事故处理问题，涉及责任认定、赔偿标准和法律程序",
    "direct_questions": ["交通事故责任如何认定？", "可以主张哪些赔偿项目？", "赔偿标准如何计算？"],
    "suggested_questions": ["交通事故责任认定不服怎么办？", "如何申请交通事故伤残鉴定？", "交通事故赔偿的诉讼时效是多久？", "对方全责但无保险该如何索赔？"],
    "recommended_approach": "转交侵权责任法专业律师深度分析"
}
```

**字段说明**：
- primary_type: 法律领域（必须从上述参考表中选择：侵权责任法、劳动法、合同法、公司法、婚姻家庭法、建设工程、刑法、行政法、民法）
- specialist_role: 专业律师角色
- confidence: 置信度（0-1）
- urgency: 紧急程度（high/medium/low）
- complexity: 复杂程度（simple/medium/complex）
- key_entities: 关键当事人或机构
- key_facts: 关键事实（3-5条）
- relevant_laws: 相关法律（1-3个）
- preliminary_assessment: 初步评估（1-2句话）
- need_confirmation: 是否需要确认（true）
- basic_summary: 案件总结（2-3句话）
- direct_questions: 从用户输入提炼的核心问题（1-3个）
- suggested_questions: 推测用户可能关心的问题（2-5个）

**suggested_questions 生成规则**（面向专业法律咨询）：
- 问法律程序问题（如何申请仲裁？诉讼时效多久？鉴定程序如何进行？）
- 问权利救济问题（不服认定怎么办？如何申请异议？有哪些救济途径？）
- 问法律后果问题（对方应承担什么责任？可以主张哪些赔偿？标准如何计算？）
- 问证据收集问题（如何收集和保全证据？哪些证据有效？）
- 禁止事项：不要问"是否..."、"有没有..."、"是否已..."等向用户核实情况的问题

**重要提醒**：
1. 遇到"交通事故"、"人身损害"、"医疗纠纷"等问题，必须分类为"侵权责任法"
2. 遇到"工资"、"离职"、"劳动合同"等问题，必须分类为"劳动法"
3. 遇到"欠款"、"违约"、"借款"、"租赁"等问题，必须分类为"合同法"
4. 只输出 JSON，不要其他解释文字！
"""


async def assistant_node(state: ConsultationState) -> ConsultationState:
    """
    律师助理节点：对用户问题进行分类和初步分析（支持多轮对话）

    多轮对话逻辑：
    - 如果 is_follow_up=True，跳过分类，直接路由到专业律师
    - 如果 is_follow_up=False，进行完整的问题分类
    - 【新增】如果已有 classification_result（用户确认阶段），跳过分类，直接使用

    输入：state["question"]
    输出：更新 state["classification_result"], state["specialist_role"], state["confidence"]
    """
    logger.info("[律师助理节点] 开始分析用户问题...")

    question = state["question"]
    context = state.get("context", {})

    # 检查是否为后续问题（多轮对话）
    is_follow_up = state.get("is_follow_up", False)

    # 【新增】检查是否已有分类结果（用户确认阶段）
    existing_classification = state.get("classification_result")

    if existing_classification:
        # 用户确认阶段：直接使用恢复的分类结果
        logger.info("[律师助理节点] 用户确认阶段：使用恢复的分类结果，跳过 LLM 重新分类")
        logger.info(f"[律师助理节点]   direct_questions: {existing_classification.get('direct_questions')}")
        logger.info(f"[律师助理节点]   suggested_questions: {existing_classification.get('suggested_questions')}")

        # 设置状态
        state["specialist_role"] = existing_classification.get("specialist_role", "专业律师")
        state["confidence"] = existing_classification.get("confidence", 0.8)
        state["current_step"] = "assistant_node_completed"
        state["user_confirmed"] = True  # 确保继续到专业律师
        state["relevant_laws"] = existing_classification.get("relevant_laws", [])

        return state

    if is_follow_up:
        # 多轮对话模式：跳过分类，直接使用上一轮的分类结果
        logger.info("[律师助理节点] 多轮对话模式，跳过分类，直接进入专业律师")

        # 从 previous_specialist_output 中提取或使用默认分类
        previous_output = state.get("previous_specialist_output", {})

        # 设置默认分类结果（基于上一轮的上下文）
        state["classification_result"] = {
            "primary_type": "后续咨询",
            "specialist_role": "专业律师",
            "confidence": 0.9,
            "urgency": "medium",
            "complexity": "medium",
            "key_entities": [],
            "key_facts": [],
            "relevant_laws": [],
            "preliminary_assessment": "后续咨询问题",
            "need_confirmation": False,  # 不需要确认
            "basic_summary": "用户基于之前的咨询提出后续问题",
            "direct_questions": [question],  # 直接使用用户的问题
            "suggested_questions": [],
            "recommended_approach": "由专业律师继续解答"
        }
        state["specialist_role"] = "专业律师"
        state["confidence"] = 0.9
        state["current_step"] = "assistant_node_completed"
        state["user_confirmed"] = True  # 自动确认，继续到专业律师
        state["relevant_laws"] = []

        return state

    # 新问题模式：进行完整的问题分类
    logger.info("[律师助理节点] 新问题模式，进行完整分类")

    # 获取律师助理专用 LLM
    llm = get_assistant_llm()

    # 构建消息
    # 人类消息：客户咨询问题
    human_content = f"客户咨询问题：\n\n{question}"

    # 【新增】追加文件预读内容（如果有）
    file_preview = context.get("file_preview_text")
    if file_preview and file_preview.strip():
        human_content += f"""

---
**📎 客户上传的文件内容**：
{file_preview}
---
"""
        logger.info(f"[律师助理节点] 文件预读内容长度：{len(file_preview)} 字符")

    messages = [
        SystemMessage(content=ASSISTANT_SYSTEM_PROMPT),
        HumanMessage(content=f"{human_content}\n\n请严格按照 JSON 格式输出分析结果。")
    ]

    # 如果有上传的文件内容，添加到消息中
    if context.get("has_file_content"):
        messages.append(SystemMessage(content="注意：客户已上传相关文件，请仔细分析文件内容。"))

    try:
        # 调用 LLM
        response: AIMessage = await llm.ainvoke(messages)
        response_text = response.content

        logger.info(f"[律师助理节点] LLM 完整响应：{response_text}")
        logger.info(f"[律师助理节点] LLM 响应长度：{len(response_text)} 字符")

        # 解析 JSON 响应
        classification = parse_classification_response(response_text)

        logger.info(f"[律师助理节点] 解析后的分类结果：{classification}")
        logger.info(f"[律师助理节点] direct_questions 数量：{len(classification.get('direct_questions', []))}")
        logger.info(f"[律师助理节点] suggested_questions 数量：{len(classification.get('suggested_questions', []))}")

        # 更新状态
        state["classification_result"] = classification
        state["specialist_role"] = classification.get("specialist_role", "专业律师")
        state["confidence"] = classification.get("confidence", 0.8)
        state["current_step"] = "assistant_node_completed"
        state["relevant_laws"] = classification.get("relevant_laws", [])

        logger.info(f"[律师助理节点] 分类完成：{classification.get('primary_type')} - {classification.get('specialist_role')}")

    except Exception as e:
        logger.error(f"[律师助理节点] 处理失败：{str(e)}")
        logger.error(f"[律师助理节点] 异常堆栈: {e.__traceback__}")
        state["error"] = f"问题分类失败：{str(e)}"
        # 设置默认值，确保流程可以继续
        state["classification_result"] = {
            "primary_type": "法律咨询",
            "specialist_role": "专业律师",
            "confidence": 0.5,
            "urgency": "medium",
            "complexity": "medium",
            "key_entities": [],
            "key_facts": [],
            "relevant_laws": ["《中华人民共和国民法典》"],
            "preliminary_assessment": "需要进一步分析",
            "need_confirmation": True,
            "basic_summary": "系统处理异常，待进一步分析",
            "direct_questions": [],  # 默认为空数组
            "suggested_questions": [],  # 默认为空数组
            "recommended_approach": "转交专业律师分析"
        }
        state["specialist_role"] = "专业律师"
        state["confidence"] = 0.5

    return state


def parse_classification_response(response_text: str) -> Dict[str, Any]:
    """
    解析律师助理节点的 JSON 响应

    Args:
        response_text: LLM 返回的文本

    Returns:
        解析后的分类结果字典
    """
    # 尝试提取 JSON
    import re

    # 查找 JSON 代码块
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 尝试直接查找 JSON 对象
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            # 无法找到 JSON，返回默认值
            logger.warning("[parse_classification] 未找到 JSON，使用默认分类")
            logger.warning(f"[parse_classification] LLM 响应内容: {response_text[:500]}...")
            return {
                "primary_type": "法律咨询",
                "specialist_role": "专业律师",
                "confidence": 0.6,
                "urgency": "medium",
                "complexity": "medium",
                "key_entities": [],
                "key_facts": [],
                "relevant_laws": ["《中华人民共和国民法典》"],
                "preliminary_assessment": "需要进一步分析",
                "need_confirmation": True,
                "basic_summary": "待分析",
                "direct_questions": [],  # 默认为空数组
                "suggested_questions": [],  # 默认为空数组
                "recommended_approach": "转交专业律师分析"
            }

    try:
        result = json.loads(json_str)

        # 确保包含必需的字段
        if "direct_questions" not in result:
            result["direct_questions"] = []
        if "suggested_questions" not in result:
            result["suggested_questions"] = []

        # 【新增】规范化法律领域分类
        if "primary_type" in result:
            original_type = result["primary_type"]
            normalized_type, was_normalized = _normalize_legal_domain(original_type)
            result["primary_type"] = normalized_type

            # 如果 specialist_role 也包含了原分类，一并更新
            if was_normalized and "specialist_role" in result:
                result["specialist_role"] = result["specialist_role"].replace(original_type, normalized_type)

        return result
    except json.JSONDecodeError as e:
        logger.error(f"[parse_classification] JSON 解析失败：{e}")
        logger.error(f"[parse_classification] 尝试解析的 JSON 字符串: {json_str[:500]}...")
        return {
            "primary_type": "民法",
            "specialist_role": "专业律师",
            "confidence": 0.6,
            "urgency": "medium",
            "complexity": "medium",
            "key_entities": [],
            "key_facts": [],
            "relevant_laws": ["《中华人民共和国民法典》"],
            "preliminary_assessment": "需要进一步分析",
            "need_confirmation": True,
            "basic_summary": "待分析",
            "direct_questions": [],  # 默认为空数组
            "suggested_questions": [],  # 默认为空数组
            "recommended_approach": "转交专业律师分析"
        }


# ==================== 节点2：资料分析（文档深度分析）====================

async def document_analysis_node(state: ConsultationState) -> ConsultationState:
    """
    资料分析节点：深度分析上传的文件内容

    使用通用文档预整理服务 + 咨询特定功能
    """
    from app.services.consultation.document_analysis import get_consultation_document_analysis_service
    from app.services.unified_document_service import StructuredDocumentResult

    logger.info("[资料分析节点] 开始分析文档...")

    # 检查是否有文件内容
    context = state.get("context", {})
    uploaded_file_ids = context.get("uploaded_files", [])
    logger.info(f"[资料分析节点] uploaded_file_ids类型: {type(uploaded_file_ids)}, 内容: {uploaded_file_ids}")

    # 如果是列表(文件ID列表),需要从全局存储中获取文件信息
    # 如果是字典(文件信息字典),直接使用
    if isinstance(uploaded_file_ids, list):
        # 从全局 uploaded_files 存储中获取文件信息
        from app.api.consultation_router import uploaded_files as global_uploaded_files
        uploaded_files_dict = {}
        for file_id in uploaded_file_ids:
            logger.info(f"[资料分析节点] 处理文件ID: {file_id}, 类型: {type(file_id)}")
            # 确保file_id是字符串
            if isinstance(file_id, dict):
                # 如果是字典,直接使用
                uploaded_files_dict[file_id.get("file_id", str(hash(str(file_id))))] = file_id
            elif isinstance(file_id, str) and file_id in global_uploaded_files:
                uploaded_files_dict[file_id] = global_uploaded_files[file_id]
        uploaded_files = uploaded_files_dict
        logger.info(f"[资料分析节点] 从全局存储加载了 {len(uploaded_files)} 个文件")
    else:
        # 已经是字典格式
        uploaded_files = uploaded_file_ids

    if not uploaded_files:
        # 无文件,跳过分析
        logger.info("[资料分析节点] 无文件，跳过分析")
        state["document_analysis"] = None
        state["current_step"] = "document_analysis_skipped"
        return state

    try:
        # 构建 StructuredDocumentResult 列表
        documents = []
        for file_id, file_info in uploaded_files.items():
            if file_info.get("content"):
                doc = StructuredDocumentResult(
                    status="success",
                    content=file_info["content"],
                    metadata=file_info.get("metadata", {}),
                    processing_method=file_info.get("processing_method"),
                    warnings=file_info.get("warnings", [])
                )
                documents.append(doc)

        logger.info(f"[资料分析节点] 开始分析 {len(documents)} 个文档")

        # 调用咨询文档分析服务
        llm = get_consultation_llm()
        analysis_service = get_consultation_document_analysis_service(llm)

        # 执行分析
        classification_result = state.get("classification_result", {})
        analysis_result = await analysis_service.analyze_for_consultation(
            documents=documents,
            user_question=state["question"],
            classification=classification_result
        )

        # 更新状态
        state["document_analysis"] = analysis_result
        state["current_step"] = "document_analysis_completed"

        logger.info(f"[资料分析节点] 分析完成: {len(analysis_result.get('document_summaries', {}))} 个摘要, "
                   f"{len(analysis_result.get('legal_issues', []))} 个法律问题, "
                   f"{len(analysis_result.get('dispute_points', []))} 个争议焦点")

    except Exception as e:
        logger.error(f"[资料分析节点] 分析失败: {e}", exc_info=True)
        state["document_analysis"] = None
        state["error"] = f"文档分析失败：{str(e)}"
        state["current_step"] = "document_analysis_failed"

    return state


def should_analyze_documents(state: ConsultationState) -> str:
    """
    决定是否需要资料分析

    条件路由：如果有文件则分析，否则跳过
    """
    context = state.get("context", {})
    uploaded_files = context.get("uploaded_files", [])

    if uploaded_files:
        return "analyze"
    return "skip"


# ==================== 节点3：专业律师（法律咨询）====================

SPECIALIST_SYSTEM_PROMPT_TEMPLATE = """你是一位{specialist_role}，拥有15年执业经验的资深律师。

【专业背景】
- 15年执业经验，处理过500+法律案件
- 专注领域：{legal_domain}
- 具备律师资格证和法学硕士学位

【核心工作原则】
1. **简洁明确**：直接回答问题，不要绕圈子
2. **基于事实和法律**：每个结论都要有法律依据或事实支撑
3. **可操作建议**：提供具体、可执行的建议
4. **风险提示**：明确告知潜在法律风险
5. **逐一回答原则**：必须针对用户提出的每个问题逐一给出明确、具体的回答

【输出要求】
- 使用清晰简洁的语言，避免法言法语堆砌
- 严禁简单复述文档内容或用户问题
- 必须使用 Markdown 格式，所有标题使用 ## ### 标记

**请严格按照以下结构提供专业法律意见**：

---

## 一、文件情况

<<<FILE_DESCRIPTION_PLACEHOLDER>>>

---

## 二、问题解答

**【必须逐一回答用户提出的所有问题】**

<<<USER_QUESTIONS_PLACEHOLDER>>>

---

## 三、简要分析

**基于事实情况的法律分析（2-3段）**：

1. **核心法律关系**：识别案件的核心法律关系和争议焦点
2. **法律依据**：引用相关法律条文（注明法条编号和内容）
3. **事实与法律结合**：将具体事实与法律规定结合分析

---

## 四、专业建议

**具体、可操作的建议（3-5条）**：

每条建议包括：
- 具体行动内容
- 法律依据
- 预期效果
- 注意事项

---

## 五、风险提示

**主要法律风险（按严重程度排序）**：

1. **风险1**：风险描述 + 应对措施
2. **风险2**：风险描述 + 应对措施
3. **风险3**：风险描述 + 应对措施

---

【重要禁忌】
- ❌ 不要简单复述文档内容或用户问题
- ❌ 不要使用"建议查阅"、"收集证据"等空泛表述
- ❌ 不要给出模棱两可的建议
- ❌ **严禁遗漏用户提出的任何一个问题**

【专业标准】
- ✅ 每个结论都要有明确的法律依据
- ✅ 建议要具体到"做什么"、"怎么做"
- ✅ 体现15年执业经验的专业判断
- ✅ **针对每个问题都给出明确、具体的回答**

**关于法律检索**：
- 你拥有丰富的法律知识和实践经验
- 对于常规法律问题，可以直接凭专业知识提供准确建议
- 对于复杂或罕见的法律问题，如果需要查找具体法条或类似案例，请先进行分析再说明需要进一步检索
- 不要为了检索而检索，以你的专业判断为准
"""


async def specialist_node(state: ConsultationState) -> ConsultationState:
    """
    专业律师节点：根据分类结果提供专业法律咨询（支持多轮对话）

    特点：
    - 使用 LLM 自主判断是否需要检索法律信息
    - 如果问题复杂或需要精确法条，自动调用检索工具
    - 如果是常规问题，直接基于知识提供建议
    - 支持多轮对话：根据 is_follow_up 标志判断是否为后续问题

    输入：state["question"], state["classification_result"], state["specialist_role"]
    输出：更新 state["legal_analysis"], state["legal_advice"], state["action_steps"], 等
    """
    logger.info("[专业律师节点] 开始提供专业咨询...")

    question = state["question"]
    classification = state.get("classification_result") or {}
    specialist_role = state.get("specialist_role") or "专业律师"

    # 检查是否为后续问题（多轮对话）
    is_follow_up = state.get("is_follow_up", False)
    previous_output = state.get("previous_specialist_output")

    # 获取专业律师专用 LLM（优先使用 Qwen3-235B-Thinking）
    llm = get_specialist_llm()

    # 构建专业律师的系统提示词
    # 如果 classification 为空（多轮对话时直接进入 specialist），使用默认值
    legal_domain = classification.get("primary_type", "法律") if classification else "法律"
    specialist_role = classification.get("specialist_role", "专业律师") if classification else "专业律师"
    system_prompt = SPECIALIST_SYSTEM_PROMPT_TEMPLATE.format(
        specialist_role=specialist_role,
        legal_domain=legal_domain
    )

    # 多轮对话模式：添加上下文连续性提示，并包含上一轮对话内容
    if is_follow_up and previous_output:
        logger.info("[专业律师节点] 多轮对话模式，包含上一轮完整上下文")

        # 检测用户意图
        user_intent = _detect_user_intent(question)

        # 添加多轮对话指令（根据用户意图调整）
        system_prompt += "\n\n【多轮对话模式】\n"
        system_prompt += "用户正在基于你之前的建议提出后续问题。\n"

        if user_intent == "concise":
            system_prompt += "**用户要求简洁回答**：请用1-2句话概括核心要点，不要展开论述。\n"
        elif user_intent == "detailed":
            system_prompt += "**用户要求详细说明**：请提供更深入的分析和更多细节。\n"
        elif user_intent == "specific":
            system_prompt += "**用户提出具体问题**：请直接回答该问题，不要重复之前的内容。\n"
        else:
            system_prompt += "请根据用户的问题调整回答风格，保持案件分析的连贯性。\n"

        system_prompt += "\n【多轮对话核心原则】\n"
        system_prompt += "1. **禁止重复**：不要复述或重新说明之前已经提供的内容\n"
        system_prompt += "2. **引用为主**：如需提及前文内容，使用'如前所述'、'正如之前分析'等引用方式\n"
        system_prompt += "3. **聚焦新问题**：直接回答用户新提出的问题，不需要重新铺垫背景\n"
        system_prompt += "4. **简洁优先**：除非用户明确要求详细说明，否则保持回答简洁\n"
        system_prompt += "5. **上下文连续**：确保新回答与之前的建议保持一致性和连贯性\n"

    # 添加额外的上下文信息（精简版，避免LLM过度复述）
    additional_context_parts = []

    # 【多轮对话】只传递引用，不传递完整内容
    if is_follow_up and previous_output:
        previous_steps = previous_output.get("action_steps", [])

        # 不传递完整内容，只传递简短引用
        additional_context_parts.append("\n\n【上下文提示】")
        additional_context_parts.append("用户正在基于你之前的法律建议提出后续问题。")
        additional_context_parts.append("你之前已经提供了：")
        additional_context_parts.append(f"- 问题分析（已提供）")
        additional_context_parts.append(f"- 专业建议（已提供）")
        additional_context_parts.append(f"- 风险提醒（已提供）")
        additional_context_parts.append(f"- 行动步骤（{len(previous_steps)}项，已提供）")
        additional_context_parts.append("\n请参考之前的分析，直接回答用户的新问题。")
        additional_context_parts.append("**重要**：不要重复之前已经说明的内容，除非用户明确要求重述。")

        logger.info(f"[专业律师节点] 已添加上一轮对话引用（使用引用模式）")

    # 1. 案件基本情况 (来自律师助理的摘要，非完整文档)
    if classification.get("basic_summary"):
        additional_context_parts.append(f"\n\n**案件基本情况**：\n{classification['basic_summary']}")

    # 2. 待咨询问题清单（增强可见性）
    question_list_parts = []
    if classification.get("direct_questions"):
        question_list_parts.extend(classification["direct_questions"])
    selected_questions = state.get("selected_suggested_questions")
    if selected_questions:
        question_list_parts.extend(selected_questions)

    if question_list_parts:
        # 使用更突出的格式
        questions_summary = "\n\n".join(f"### 问题 {i+1}：{q}\n【请针对此问题给出明确回答】" for i, q in enumerate(question_list_parts))
        additional_context_parts.append(f"\n\n**客户要求逐一回答的问题清单**（共 {len(question_list_parts)} 个问题）")
        additional_context_parts.append("**重要：您必须针对以下每个问题逐一给出明确、具体的回答，不可遗漏**\n")
        additional_context_parts.append(questions_summary)
        logger.info(f"[专业律师节点] 将回答 {len(question_list_parts)} 个问题")

    # 3. 关键事实（限制数量，避免过多）
    if classification.get("key_facts"):
        additional_context_parts.append("\n\n**关键事实**：\n" + "\n".join(f"- {fact}" for fact in classification["key_facts"][:5]))

    # 4. 文档分析结果（精简版 - 只提取关键信息，不包含完整摘要）
    document_analysis = state.get("document_analysis")
    if document_analysis:
        # 只添加识别的法律问题和争议焦点（不添加完整文件摘要和时间线）
        if document_analysis.get("legal_issues"):
            additional_context_parts.append("\n\n**识别的法律问题**：")
            for issue in document_analysis["legal_issues"][:5]:  # 最多5个
                additional_context_parts.append(f"- {issue}")

        if document_analysis.get("dispute_points"):
            additional_context_parts.append("\n\n**争议焦点**：")
            for dispute in document_analysis["dispute_points"][:3]:  # 最多3个
                additional_context_parts.append(f"- {dispute}")

    additional_context = "\n".join(additional_context_parts)

    # 构建精简的检索查询（不包含完整上下文，避免搜索查询过长）
    search_query = question
    if classification.get("direct_questions"):
        search_query = classification["direct_questions"][0]  # 使用第一个核心问题

    # 判断是否需要检索（对于民法典相关领域，强制检索）
    force_search = any(domain in legal_domain for domain in LEGAL_DOMAINS_REQUIRING_SEARCH)

    search_formatted = ""
    if force_search:
        logger.info(f"[专业律师节点] 法律领域'{legal_domain}'需要强制检索，以确保引用现行法律")

        # 策略1：先使用本地知识库
        try:
            from app.services.legal_knowledge_base import get_legal_knowledge_base
            kb = get_legal_knowledge_base()
            kb_articles = kb.search(search_query, legal_domain)
            if kb_articles:
                logger.info(f"[专业律师节点] 从知识库找到 {len(kb_articles)} 条相关条文")
                search_formatted = kb.format_for_llm(kb_articles)
        except Exception as e:
            logger.warning(f"[专业律师节点] 知识库加载失败: {e}")

        # 策略2：如果知识库没有结果，尝试在线搜索
        if not search_formatted:
            logger.info(f"[专业律师节点] 知识库未找到，尝试在线搜索")
            try:
                search_data = await get_legal_search_results(search_query, legal_domain)
                search_formatted = search_data["formatted"]
                logger.info(f"[专业律师节点] 在线检索完成")
            except Exception as e:
                logger.warning(f"[专业律师节点] 在线搜索失败: {e}")
                # 使用知识库的默认条文
                try:
                    from app.services.legal_knowledge_base import get_legal_knowledge_base
                    kb = get_legal_knowledge_base()
                    kb_articles = kb.get_default_articles(legal_domain)
                    if kb_articles:
                        logger.info(f"[专业律师节点] 使用知识库默认条文（{len(kb_articles)}条）")
                        search_formatted = kb.format_for_llm(kb_articles)
                except Exception as e2:
                    logger.warning(f"[专业律师节点] 获取默认条文失败: {e2}")
    else:
        # 其他领域由 LLM 判断是否需要检索
        need_search = await _decide_if_search_needed(llm, system_prompt, search_query, "", legal_domain)
        if need_search:
            logger.info(f"[专业律师节点] 判断需要检索，使用精简查询: {search_query[:50]}...")
            try:
                search_data = await get_legal_search_results(search_query, legal_domain)
                search_formatted = search_data["formatted"]
                logger.info(f"[专业律师节点] 检索完成")
            except Exception as e:
                logger.warning(f"[专业律师节点] 检索失败: {str(e)}")
        else:
            logger.info("[专业律师节点] 判断无需检索，直接基于专业知识提供咨询")

    # 添加检索结果（如果有）
    if search_formatted:
        additional_context += f"\n\n**法律检索结果（现行有效法律）**：\n{search_formatted}"

        # 强调使用检索结果
        system_prompt += "\n\n【⚠️ 重要提示】\n"
        system_prompt += "你刚刚通过法律检索获得了现行有效的法律法规。\n"
        system_prompt += "**必须优先引用检索结果中的法律条文**，这些是现行有效的法律依据。\n"
        system_prompt += "切勿引用已废止的法律（如《合同法》、《物权法》等）。\n"

    # 构建系统提示词（先填充用户问题）
    # 准备用户问题列表
    questions_to_answer = []

    # 【调试】打印分类结果和状态
    logger.info(f"[专业律师节点] classification.direct_questions = {classification.get('direct_questions')}")
    logger.info(f"[专业律师节点] state.selected_suggested_questions = {state.get('selected_suggested_questions')}")
    logger.info(f"[专业律师节点] state keys = {list(state.keys())}")

    # 【修复问题1】始终包含原始问题 + (用户选择 OR 推荐问题)
    # 构建问题列表：原始问题 + (用户选择 OR 推荐问题)
    questions_to_answer = []

    # 1. 始终包含用户的原始输入（除非是"继续"等无关输入）
    original_question = state.get("question")
    if original_question and "继续" not in original_question and original_question.strip():
        questions_to_answer.append(original_question)
        logger.info(f"[专业律师节点] 添加原始问题: {original_question[:50]}...")

    # 2. 追加补充问题（优先用户选择，其次 AI 推荐）
    selected_questions = state.get("selected_suggested_questions")
    if selected_questions and len(selected_questions) > 0:
        # A方案：用户有明确选择
        for q in selected_questions:
            if q not in questions_to_answer:  # 避免重复
                questions_to_answer.append(q)
        logger.info(f"[专业律师节点] 追加用户选择的 {len(selected_questions)} 个补充问题")
    elif classification.get("direct_questions"):
        # B方案：用户无选择，追加 AI 推荐的核心问题
        for q in classification["direct_questions"]:
            if q not in questions_to_answer:  # 避免重复
                questions_to_answer.append(q)
        logger.info(f"[专业律师节点] 追加 AI 推荐的 {len(classification['direct_questions'])} 个问题")

    logger.info(f"[专业律师节点] 最终问题列表: {len(questions_to_answer)} 个问题")

    # 如果有用户选择的问题，填充到系统提示词中
    if questions_to_answer:
        # 【修复问题2】增强问题格式，使其更显眼，确保 LLM 逐一回答
        questions_formatted = "\n\n" + "="*60 + "\n"
        questions_formatted += f"【必须逐一回答的问题清单】（共 {len(questions_to_answer)} 个问题）\n"
        questions_formatted += "="*60 + "\n\n"
        for i, q in enumerate(questions_to_answer):
            questions_formatted += f"### 🔷 问题 {i+1}：{q}\n"
            questions_formatted += "**【必须针对此问题给出明确、具体的回答，不可遗漏】**\n\n"
        questions_formatted += "="*60 + "\n"

        # 填充问题占位符（使用自定义占位符避免与 format() 冲突）
        system_prompt = system_prompt.replace("<<<USER_QUESTIONS_PLACEHOLDER>>>", questions_formatted)
        logger.info(f"[专业律师节点] 已填充 {len(questions_to_answer)} 个用户问题到系统提示词（增强格式）")
    else:
        # 理论上不会进入这里（因为至少有原始问题）
        logger.warning("[专业律师节点] 无问题列表，使用兜底逻辑")

    # ==================== 构建文件描述 ====================
    file_description = ""
    document_analysis = state.get("document_analysis")
    if document_analysis and document_analysis.get("document_summaries"):
        # 有文件：构建文件描述
        file_description = "客户已提供以下文件：\n\n"

        # 从 context 获取文件信息（用于获取文件名和类型）
        context = state.get("context", {})
        uploaded_file_ids = context.get("uploaded_files", [])

        # 从全局存储获取文件信息
        from app.api.consultation_router import uploaded_files as global_uploaded_files
        file_info_map = {}
        if isinstance(uploaded_file_ids, list):
            for file_id in uploaded_file_ids:
                if isinstance(file_id, str) and file_id in global_uploaded_files:
                    file_info_map[file_id] = global_uploaded_files[file_id]

        summaries = document_analysis.get("document_summaries", {})

        # 遍历所有摘要，生成文件描述
        for file_path, summary in summaries.items():
            # 获取文件名和类型
            filename = "未知文件"
            file_type = "未知类型"

            # 从 file_info_map 中查找匹配的文件信息
            for file_id, info in file_info_map.items():
                if info.get("file_path") == file_path or file_path.endswith(info.get("filename", "")):
                    filename = info.get("filename", "未知文件")
                    file_type = info.get("file_type", "未知类型")
                    break

            # 限制摘要长度（300字）
            summary_text = summary.summary
            if len(summary_text) > 300:
                summary_text = summary_text[:300] + "..."

            file_description += f"**文件名称**: {filename}\n"
            file_description += f"**文件类型**: {file_type}\n"
            file_description += f"**文件摘要**: {summary_text}\n\n"

        logger.info(f"[专业律师节点] 已添加 {len(summaries)} 个文件的描述")
    else:
        # 无文件：不添加文件描述部分
        file_description = ""
        logger.info("[专业律师节点] 无文件，跳过文件描述")

    # 填充文件描述占位符
    if file_description:
        system_prompt = system_prompt.replace("<<<FILE_DESCRIPTION_PLACEHOLDER>>>", file_description)
    else:
        # 移除整个"一、文件情况"部分
        system_prompt = system_prompt.replace("## 一、文件情况\n\n<<<FILE_DESCRIPTION_PLACEHOLDER>>>\n\n---\n\n", "")
        logger.info("[专业律师节点] 无文件描述，已移除文件情况章节")

    # 构建人类消息 - 简洁版本，因为问题已在 system prompt 中
    if questions_to_answer:
        # 有明确的问题列表 - 使用简洁格式（问题详情已在 system prompt 中）
        human_content = f"""【客户咨询】{original_question}

{additional_context}

---
**🚨 输出要求（严格执行）**：
1. **必须逐一回答上述系统提示词中的所有 {len(questions_to_answer)} 个问题，不可遗漏任何一个**
2. 每个问题的回答应包含：直接回答 + 法律依据 + 具体建议
3. **建议使用清晰的标题格式，如："🔷 问题1：[问题标题]"**
"""
    else:
        # 没有具体问题列表（兜底逻辑）
        human_content = f"客户咨询问题：{original_question}{additional_context}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content)
    ]

    try:
        # 调用 LLM
        response: AIMessage = await llm.ainvoke(messages)
        response_text = response.content

        # 【新增】检查并修正过时的法律引用
        response_text, was_fixed = _check_and_fix_legal_references(response_text)
        if was_fixed:
            logger.info(f"[专业律师节点] 已自动修正过时的法律引用，确保输出现行有效法律")

        logger.info(f"[专业律师节点] LLM 响应长度：{len(response_text)} 字符")

        # 解析专业律师的回复
        parsed_result = parse_specialist_response(response_text)

        # 使用渲染器清理 Markdown 符号（转为纯文本，用于前端显示）
        from app.services.markdown_renderer import get_markdown_renderer
        renderer = get_markdown_renderer()

        # 清理各个部分的 Markdown 符号
        clean_analysis = renderer.render_to_clean_text(parsed_result.get("analysis", response_text))
        clean_advice = renderer.render_to_clean_text(parsed_result.get("advice", ""))
        clean_risk_warning = renderer.render_to_clean_text(parsed_result.get("risk_warning", ""))

        # 更新状态（存储纯文本）
        state["legal_analysis"] = clean_analysis
        state["legal_advice"] = clean_advice
        state["risk_warning"] = clean_risk_warning
        state["action_steps"] = parsed_result.get("action_steps", [])
        state["relevant_laws"] = parsed_result.get("relevant_laws", state.get("relevant_laws", []))
        state["current_step"] = "specialist_node_completed"

        # 生成最终报告（纯文本格式，移除 Markdown 符号）
        state["final_report"] = generate_final_report(state, renderer)

        logger.info("[专业律师节点] 咨询完成")

    except Exception as e:
        logger.error(f"[专业律师节点] 处理失败：{str(e)}")
        import traceback
        traceback.print_exc()
        state["error"] = f"专业咨询失败：{str(e)}"
        state["legal_analysis"] = "抱歉，处理您的咨询时遇到问题。"
        state["legal_advice"] = "请稍后重试或联系专业律师。"
        state["action_steps"] = ["请重新提交咨询", "或联系线下专业律师"]

    return state


async def _decide_if_search_needed(
    llm: ChatOpenAI,
    system_prompt: str,
    question: str,
    additional_context: str,
    legal_domain: str
) -> bool:
    """
    判断是否需要检索法律信息

    使用 LLM 评估问题的复杂度和是否需要精确法条

    Returns:
        True 表示需要检索，False 表示不需要
    """
    decision_prompt = f"""{system_prompt}

**当前任务**：
判断以下法律咨询问题是否需要检索最新的法律法规或类似案例。

**判断标准**：
1. 需要检索的情况：
   - 问题涉及具体法条条文编号
   - 问题涉及最新的法律修改或司法解释
   - 问题属于罕见或复杂的法律情形
   - 用户明确要求查找相关案例
   - 问题时效性较强（如新颁布的法规）

2. 不需要检索的情况：
   - 常规法律问题（如劳动纠纷、合同违约的一般处理）
   - 基础法律概念解释
   - 常见法律流程咨询
   - 可以凭专业知识直接回答的问题

**咨询问题**：
{question}{additional_context}

**法律领域**：{legal_domain}

请只回答 "需要检索" 或 "不需要检索"，不要其他解释。
"""

    try:
        messages = [
            SystemMessage(content=decision_prompt),
            HumanMessage(content="请判断：")
        ]

        response: AIMessage = await llm.ainvoke(messages)
        response_text = response.content.strip()

        logger.info(f"[检索判断] LLM 判断结果: {response_text}")

        # 判断响应
        if "需要检索" in response_text or "需要" in response_text:
            return True
        else:
            return False

    except Exception as e:
        logger.warning(f"[检索判断] 判断失败: {e}，默认不检索")
        return False


def parse_specialist_response(response_text: str) -> Dict[str, Any]:
    """
    解析专业律师节点的结构化回复

    Args:
        response_text: LLM 返回的文本

    Returns:
        解析后的结构化字典
    """
    result = {
        "analysis": "",
        "advice": "",
        "risk_warning": "",
        "action_steps": [],
        "relevant_laws": []
    }

    # 提取各个部分（使用正则表达式，支持多级标题）
    import re

    # 提取法律依据（支持 # 或 ## 或 ###）
    legal_basis_match = re.search(r'#+\s*法律依据\s*\n(.*?)(?=#+\s*(?:问题分析|专业建议|风险提醒|行动步骤)|\Z)', response_text, re.DOTALL)
    if legal_basis_match:
        result["relevant_laws"] = [line.strip() for line in legal_basis_match.group(1).strip().split('\n') if line.strip() and not line.strip().startswith('#')]

    # 提取问题分析
    analysis_match = re.search(r'#+\s*问题分析\s*\n(.*?)(?=#+\s*(?:专业建议|风险提醒|行动步骤)|\Z)', response_text, re.DOTALL)
    if analysis_match:
        result["analysis"] = analysis_match.group(1).strip()

    # 提取专业建议
    advice_match = re.search(r'#+\s*专业建议\s*\n(.*?)(?=#+\s*(?:风险提醒|行动步骤)|\Z)', response_text, re.DOTALL)
    if advice_match:
        result["advice"] = advice_match.group(1).strip()

    # 提取风险提醒
    risk_match = re.search(r'#+\s*风险提醒\s*\n(.*?)(?=#+\s*行动步骤|\Z)', response_text, re.DOTALL)
    if risk_match:
        result["risk_warning"] = risk_match.group(1).strip()

    # 提取行动步骤
    steps_match = re.search(r'#+\s*行动步骤\s*\n(.*?)(?=\Z)', response_text, re.DOTALL)
    if steps_match:
        steps_text = steps_match.group(1).strip()
        # 解析步骤列表（支持多种格式）
        steps = []
        for line in steps_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # 移除序号前缀（如 "1." 或 "[紧急]"）
            step = re.sub(r'^[\d\[\]]+\.\s*', '', line)  # 移除 "1. "
            step = re.sub(r'^\[.*?\]\s*', '', step)  # 移除 "[紧急] "
            step = re.sub(r'^\*\*.*?\*\*\s*', '', step)  # 移除 "**紧急**"
            step = step.strip('-*• ')  # 移除列表符号
            if step:
                steps.append(step)
        result["action_steps"] = steps

    # 如果分析为空，使用整个文本
    if not result["analysis"]:
        result["analysis"] = response_text

    return result


def generate_final_report(state: ConsultationState, renderer=None) -> str:
    """
    生成最终报告

    Args:
        state: 咨询状态
        renderer: Markdown 渲染器（可选）

    Returns:
        最终报告（纯文本格式，已移除 Markdown 符号）
    """
    question = state["question"]
    classification = state.get("classification_result") or {}
    relevant_laws = state.get("relevant_laws") or []
    analysis = state.get("legal_analysis") or ""
    advice = state.get("legal_advice") or ""
    risk_warning = state.get("risk_warning") or ""
    action_steps = state.get("action_steps") or []

    # 使用渲染器清理 Markdown 符号，转为纯文本
    if renderer:
        clean_question = renderer.render_to_clean_text(question)
        clean_analysis = renderer.render_to_clean_text(analysis)
        clean_advice = renderer.render_to_clean_text(advice)
        clean_risk_warning = renderer.render_to_clean_text(risk_warning)
    else:
        clean_question = question
        clean_analysis = analysis
        clean_advice = advice
        clean_risk_warning = risk_warning

    # 构建纯文本报告
    report = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    法律咨询报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【问题描述】
{clean_question}

【分类结果】
  专业领域：{classification.get('primary_type') or '未知'}
  专业律师：{state.get('specialist_role') or '专业律师'}
  置信度：{(classification.get('confidence') or 0.8) * 100:.1f}%
  复杂程度：{classification.get('complexity') or 'medium'}
  紧急程度：{classification.get('urgency') or 'medium'}
"""

    if relevant_laws:
        report += f"""
【法律依据】
"""
        for law in relevant_laws:
            report += f"  • {law}\n"

    report += f"""
【问题分析】
{clean_analysis}
"""

    # 只在有内容时添加专业建议
    if clean_advice and clean_advice.strip():
        report += f"""

【专业建议】
{clean_advice}"""

    # 只在有内容时添加风险提醒
    if clean_risk_warning and clean_risk_warning.strip():
        report += f"""

【风险提醒】
{clean_risk_warning}"""

    # 只在有步骤时添加行动步骤
    if action_steps:
        report += """

【行动步骤】
"""
        for i, step in enumerate(action_steps, 1):
            report += f"  {i}. {step}\n"

    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
以上建议仅供参考，重要法律事务建议线下咨询专业执业律师。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    return report


# ==================== 条件路由函数 ====================

def should_start_with_assistant(state: ConsultationState) -> str:
    """
    智能入口路由：决定从哪个节点开始（支持多轮对话）

    路由逻辑：
    - 如果是后续问题 (is_follow_up=True) → 直接进入专业律师节点
    - 如果是新问题 → 从律师助理节点开始
    """
    if state.get("is_follow_up"):
        # 后续问题，直接进入专业律师节点
        logger.info("[路由] 检测到后续问题，直接进入专业律师节点")
        return "specialist"
    else:
        # 新问题，从律师助理开始
        logger.info("[路由] 新问题，从律师助理节点开始")
        return "assistant"


def should_continue_after_assistant(state: ConsultationState) -> str:
    """
    律师助理节点后的路由决策

    两阶段执行模式：
    - 如果用户已确认 (user_confirmed=True) → 继续执行文档分析和专业律师
    - 如果用户未确认 (user_confirmed=False) → 返回 END，等待前端确认

    路由逻辑：
    - 如果有错误，结束
    - 如果用户已确认且有文件，执行文档分析
    - 如果用户已确认且无文件，直接到专业律师
    - 如果用户未确认，结束（返回确认消息）
    """
    if state.get("error"):
        logger.error("[路由] 检测到错误，结束流程")
        return "end"

    if state.get("user_confirmed"):
        # 用户已确认，继续执行
        context = state.get("context", {})
        uploaded_files = context.get("uploaded_files", [])
        if uploaded_files:
            logger.info("[路由] 用户已确认且有文件，执行文档分析")
            return "analyze"
        else:
            logger.info("[路由] 用户已确认且无文件，直接到专业律师")
            return "specialist"
    else:
        # 用户未确认，返回确认消息
        logger.info("[路由] 用户未确认，返回确认消息")
        return "end"


def should_analyze_documents(state: ConsultationState) -> str:
    """
    决定是否需要文档分析

    用于文档分析节点后的路由
    """
    return "specialist"  # 总是继续到专业律师


def should_continue_to_specialist(state: ConsultationState) -> str:
    """
    决定是否继续到专业律师节点（已弃用，保留兼容性）
    """
    if state.get("error"):
        logger.error("[路由] 检测到错误，结束流程")
        return "end"

    if state.get("classification_result"):
        logger.info("[路由] 分类完成，继续到专业律师节点")
        return "specialist"

    logger.warning("[路由] 未完成分类，结束流程")
    return "end"


# ==================== 构建 LangGraph 工作流 ====================

def create_legal_consultation_graph():
    """
    创建法律咨询的 LangGraph 工作流（支持多轮对话）

    多轮对话模式：
    - 新问题：通过路由函数决定从 assistant 开始
    - 后续问题：通过路由函数决定直接进入 specialist

    1. assistant_node: 问题分类和意图识别,生成 basic_summary 和 question_list
    2. document_analysis_node: 文档深度分析（仅在有文件时执行）
    3. specialist_node: 生成专业法律建议（内部自主决定是否检索）
    """
    logger.info("[工作流] 构建法律咨询 LangGraph（支持多轮对话）...")

    # 创建状态图
    workflow = StateGraph(ConsultationState)

    # 添加节点
    workflow.add_node("assistant", assistant_node)
    workflow.add_node("doc_analysis", document_analysis_node)
    workflow.add_node("specialist", specialist_node)

    # 【关键修改】使用条件入口点，支持多轮对话直接进入专业律师节点
    workflow.set_entry_point("assistant")  # 设置默认入口点

    # 添加边：assistant → [条件路由: END(等待确认) 或 doc_analysis 或 specialist]
    workflow.add_conditional_edges(
        "assistant",
        should_continue_after_assistant,
        {
            "analyze": "doc_analysis",
            "specialist": "specialist",
            "end": END
        }
    )

    # 添加边：doc_analysis → specialist
    workflow.add_edge("doc_analysis", "specialist")

    # 添加边：specialist → END
    workflow.add_edge("specialist", END)

    # 编译工作流
    app = workflow.compile()

    logger.info("[工作流] LangGraph 构建完成（支持多轮对话 - 通过assistant节点内部判断）")

    return app


def create_legal_consultation_graph_v2():
    """
    创建法律咨询的 LangGraph 工作流（V2版本 - 真正的条件入口点）

    【架构改进】使用条件入口点，多轮对话完全绕过assistant节点

    注意：此版本需要 LangGraph 0.2.0+ 支持，如果报错请使用 create_legal_consultation_graph
    """
    logger.info("[工作流 V2] 构建法律咨询 LangGraph（真正的条件入口点）...")

    # 创建状态图
    workflow = StateGraph(ConsultationState)

    # 添加节点
    workflow.add_node("assistant", assistant_node)
    workflow.add_node("doc_analysis", document_analysis_node)
    workflow.add_node("specialist", specialist_node)

    # 【关键修改】真正的条件入口点
    # 多轮对话时，后续问题完全跳过 assistant_node
    try:
        # 尝试使用 START 节点作为条件入口
        from langgraph.graph import START

        workflow.add_conditional_edges(
            START,
            should_start_with_assistant,
            {
                "assistant": "assistant",
                "specialist": "specialist"
            }
        )

        # assistant 节点后的路由
        workflow.add_conditional_edges(
            "assistant",
            should_continue_after_assistant,
            {
                "analyze": "doc_analysis",
                "specialist": "specialist",
                "end": END
            }
        )

        # 添加边：doc_analysis → specialist
        workflow.add_edge("doc_analysis", "specialist")

        # 添加边：specialist → END
        workflow.add_edge("specialist", END)

        logger.info("[工作流 V2] 使用 START 条件入口点成功")

    except Exception as e:
        logger.warning(f"[工作流 V2] START 条件入口点不支持: {e}")
        logger.info("[工作流 V2] 回退到传统固定入口点模式")
        # 回退到传统模式
        workflow.set_entry_point("assistant")

        workflow.add_conditional_edges(
            "assistant",
            should_continue_after_assistant,
            {
                "analyze": "doc_analysis",
                "specialist": "specialist",
                "end": END
            }
        )

        workflow.add_edge("doc_analysis", "specialist")
        workflow.add_edge("specialist", END)

    # 编译工作流
    app = workflow.compile()

    logger.info("[工作流 V2] LangGraph 构建完成")

    return app


# ==================== 主要接口函数 ====================

# 创建全局工作流实例
_legal_consultation_graph = None


def get_consultation_graph():
    """获取咨询工作流单例"""
    global _legal_consultation_graph
    if _legal_consultation_graph is None:
        # 【关键修复】使用 V2 版本，支持真正的条件入口点
        _legal_consultation_graph = create_legal_consultation_graph_v2()
        logger.info("[工作流] 使用 V2 版本（支持条件入口点）")
    return _legal_consultation_graph


async def run_legal_consultation(
    question: str,
    context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[BaseMessage]] = None,
    user_confirmed: bool = False,
    selected_suggested_questions: Optional[List[str]] = None,
    is_follow_up: bool = False,  # 新增：多轮对话标志
    session_id: Optional[str] = None,  # 新增：会话ID
    previous_specialist_output: Optional[Dict[str, Any]] = None,  # 新增：上一轮输出
    saved_classification: Optional[Dict[str, Any]] = None  # 【新增】恢复的分类结果
) -> Tuple[Optional[ConsultationOutput], Optional[str]]:
    """
    运行法律咨询工作流（支持多轮对话）

    Args:
        question: 用户问题
        context: 额外上下文信息
        conversation_history: 对话历史（可选）
        user_confirmed: 用户是否已确认（用于两阶段执行）
        selected_suggested_questions: 用户选择的建议问题（第二阶段）
        is_follow_up: 是否为后续问题（多轮对话标志）
        session_id: 会话ID（用于持久化）
        previous_specialist_output: 上一轮专业律师输出（用于多轮对话上下文）
        saved_classification: 恢复的分类结果（用户确认阶段使用）

    Returns:
        (ConsultationOutput, final_report)
    """
    logger.info(f"[咨询流程] ===== 开始处理 =====")
    logger.info(f"[咨询流程] 问题：{question[:50]}... (is_follow_up={is_follow_up}, user_confirmed={user_confirmed})")
    logger.info(f"[咨询流程] selected_suggested_questions 类型: {type(selected_suggested_questions)}")
    logger.info(f"[咨询流程] selected_suggested_questions 值: {selected_suggested_questions}")
    if selected_suggested_questions:
        logger.info(f"[咨询流程] selected_suggested_questions 长度: {len(selected_suggested_questions)}")
        for i, q in enumerate(selected_suggested_questions):
            logger.info(f"[咨询流程]   问题 {i+1}: {q}")
    else:
        logger.warning(f"[咨询流程] selected_suggested_questions 为 None 或空！")

    # 【新增】如果有恢复的分类结果，打印日志
    if saved_classification:
        logger.info(f"[咨询流程] 使用恢复的分类结果: primary_type={saved_classification.get('primary_type')}")
        logger.info(f"[咨询流程]   direct_questions: {saved_classification.get('direct_questions')}")
        logger.info(f"[咨询流程]   suggested_questions: {saved_classification.get('suggested_questions')}")

    # 初始化状态
    initial_state: ConsultationState = {
        "question": question,
        "context": context or {},
        "conversation_history": conversation_history or [],
        "user_confirmed": user_confirmed,
        "selected_suggested_questions": selected_suggested_questions,
        "is_follow_up": is_follow_up,  # 新增：多轮对话标志
        "session_id": session_id,  # 新增：会话ID
        "previous_specialist_output": previous_specialist_output,  # 新增：上一轮输出
        "classification_result": saved_classification,  # 【修改】使用恢复的分类结果
        "specialist_role": None,
        "confidence": None,
        "document_analysis": None,
        "legal_analysis": None,
        "legal_advice": None,
        "risk_warning": None,
        "action_steps": None,
        "relevant_laws": None,
        "final_report": None,
        "need_follow_up": False,
        "follow_up_questions": [],
        "error": None,
        "current_step": "start"
    }

    try:
        # 获取工作流
        graph = get_consultation_graph()

        # 执行工作流
        result_state = await graph.ainvoke(initial_state)

        # 检查是否有错误
        if result_state.get("error"):
            logger.error(f"[咨询流程] 执行失败：{result_state['error']}")
            return None, result_state["error"]

        # 构建输出
        output = ConsultationOutput(
            question=question,
            legal_basis="、".join(result_state.get("relevant_laws", [])),
            analysis=result_state.get("legal_analysis", ""),
            advice=result_state.get("legal_advice", ""),
            risk_warning=result_state.get("risk_warning", ""),
            action_steps=result_state.get("action_steps", []),
            classification_result=result_state.get("classification_result"),
            need_follow_up=result_state.get("need_follow_up", False),
            follow_up_questions=result_state.get("follow_up_questions", [])
        )

        final_report = result_state.get("final_report", "")

        logger.info("[咨询流程] 处理完成")
        return output, final_report

    except Exception as e:
        logger.error(f"[咨询流程] 执行异常：{str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"处理咨询时发生错误：{str(e)}"


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import asyncio

    async def test_consultation():
        """测试法律咨询功能"""
        # 测试问题1：简单问题
        test_question_1 = "公司设立法律要求"

        # 测试问题2：复杂建工纠纷
        test_question_2 = """成都兴业建筑工程有限公司以四川鑫绵兴建筑工程有限公司名义取得了一个施工总承包项目...
        （详细案情省略，请查看测试用例）
        """

        print("=" * 80)
        print("测试问题1：", test_question_1)
        print("=" * 80)

        result1, report1 = await run_legal_consultation(test_question_1)

        if result1:
            print("\n✅ 咨询成功！")
            print(f"分类：{result1.classification_result}")
            print(f"分析：{result1.analysis[:200]}...")
            print("\n完整报告：")
            print(report1)
        else:
            print(f"❌ 咨询失败：{report1}")

    # 运行测试
    asyncio.run(test_consultation())
