"""
智能咨询模块 - LangGraph 工作流实现（重构版）

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

from app.core.llm_config import get_assistant_model, get_specialist_model
from app.services.consultation.dynamic_persona_generator import dynamic_persona_generator
from app.database import SessionLocal

logger = logging.getLogger(__name__)


# ==================== 输入清洗函数 ====================

def _sanitize_user_question(question: str) -> str:
    """
    清洗用户问题中的指令性文本，防止 Prompt 污染

    仅移除明确的指令性文本，保留业务语义：
    - 移除：AI指令标记（如【必须逐一回答】）
    - 保留：合法的业务文本（如"【问题1】...【问题2】"格式的问题列表）

    批准条件：正则优化为仅移除指令性文本，避免误删业务语义
    """
    import re

    # 定义精确的指令性文本模式（仅匹配AI指令，不匹配业务内容）
    instruction_patterns = [
        # 匹配明确的AI指令（包含"必须"、"请"、"逐一"等指令性词汇）
        r'【(?:必须|请|务必|需要)(?:逐一|全部)?(?:回答|输出|提供|列举|说明)(?:所有)?(?:问题|内容|建议|信息)】',
        r'【不可(?:遗漏|跳过|省略)(?:任何)?问题】',
        r'【(?:针对|按照)(?:上述|以下)(?:所有)?问题(?:逐一)?给出回答】',

        # 匹配系统生成的指令标记（不匹配用户输入的问题编号）
        r'【\s*必须\s*】',
        r'【\s*逐一\s*回答\s*】',
    ]

    cleaned = question
    for pattern in instruction_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # 移除多余空白但保留段落结构
    lines = cleaned.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:  # 保留非空行
            cleaned_lines.append(stripped)

    return '\n'.join(cleaned_lines)


# ==================== 辅助函数 ====================

async def get_legal_search_results(question: str, domain: str = None, user_id: int = None, session_id: str = None) -> dict:
    """获取法律检索结果（异步）

    Args:
        question: 用户问题
        domain: 法律领域（可选）
        user_id: 用户ID（可选）
        session_id: 会话ID（可选，用于多轮对话缓存隔离）
    """
    try:
        from app.services.knowledge_base.unified_service import get_unified_kb_service

        service = get_unified_kb_service()

        # 使用统一知识服务进行搜索
        # enabled_stores=None 表示搜索所有可用存储 (Generic Search + Knowledge Base)
        # 除非我们要区分 Search Node 和 RAG Node。
        # 这里集成在一起。

        search_result = await service.search(
            query=question,
            domain=domain,
            limit=5,
            user_id=user_id,
            session_id=session_id  # 新增：传递 session_id 用于缓存隔离
        )
        
        # 格式化结果
        # 需要将 KnowledgeSearchResult 适配为 specialized_node 期望的 dict 结构
        # 原始结构: {"laws": [], "cases": [], "formatted": "..."}
        # Unified Service 返回 items 列表
        
        # 为了兼容性，我们尝试提取
        # 注意：Unified Service 已封装了 "laws" "cases" 等来源
        
        # 这里我们统一返回 formatted 文本，并保留 raw items
        formatted = ""
        if search_result.items:
            formatted = "【检索结果】\n"
            for i, item in enumerate(search_result.items, 1):
                formatted += f"{i}. {item.title} (来源: {item.source})\n"
                formatted += f"   {item.content[:200]}...\n\n"
                
        return {
            "laws": [], # Legacy, maybe not needed if prompt uses formatted
            "cases": [], 
            "formatted": formatted,
            "raw_items": [item.to_dict() for item in search_result.items]
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


async def _should_perform_rag_search(
    question: str,
    legal_domain: Optional[str] = None,
    user_id: Optional[int] = None
) -> tuple[bool, str]:
    """
    判断是否应该执行 RAG 检索，并返回检索策略

    Args:
        question: 用户问题
        legal_domain: 法律领域
        user_id: 用户ID（可选）

    Returns:
        (should_rag: bool, strategy: str)
        strategy 可以是 "chroma_first", "hybrid", "sql_fallback", 或 "disabled"
    """
    default_strategy = "chroma_first"  # 默认策略

    try:
        # 1. 检查法律领域是否强制检索
        domain = legal_domain or ""
        for mandatory_domain in LEGAL_DOMAINS_REQUIRING_SEARCH:
            if mandatory_domain in domain:
                logger.info(f"[RAG判断] 领域 '{legal_domain}' 需要强制检索，使用默认策略")
                return True, default_strategy

        # 2. 检查数据库配置
        if legal_domain:
            db = SessionLocal()
            try:
                from app.models.category import Category

                # 查询对应分类的配置
                category = db.query(Category).filter(
                    Category.name == legal_domain,
                    Category.is_active == True
                ).first()

                if category and category.meta_info:
                    meta_info = category.meta_info
                    if isinstance(meta_info, dict):
                        # P1-1: 提取 RAG 策略配置
                        force_rag = meta_info.get("force_rag", False)
                        rag_strategy = meta_info.get("rag_strategy", "chroma_first")

                        if force_rag:
                            logger.info(f"[RAG判断] 分类配置强制检索，策略: {rag_strategy}")
                            return True, rag_strategy

                        # 即使不强制，如果配置了策略，也返回
                        if rag_strategy in ["chroma_first", "hybrid", "sql_fallback"]:
                            logger.info(f"[RAG判断] 分类配置 RAG 策略: {rag_strategy}")
                            return True, rag_strategy

            except Exception as e:
                logger.warning(f"[RAG判断] 查询分类配置失败: {e}")
            finally:
                db.close()

        # 3. 检查问题复杂度（简单启发式）
        complex_keywords = ["具体法条", "最新规定", "司法解释", "案例", "时效", "赔偿标准"]
        if any(kw in question for kw in complex_keywords):
            logger.info(f"[RAG判断] 问题包含复杂关键词，使用默认策略")
            return True, default_strategy

        return False, "disabled"

    except Exception as e:
        logger.warning(f"[RAG判断] 判断失败: {e}，默认不检索")
        return False, "disabled"

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
    user_id: Optional[int]                 # 用户ID（用于知识库权限控制）

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

    # P1-2/P1-3: RAG 检索状态和结果
    rag_triggered: bool                    # 是否触发了RAG检索
    rag_results: Optional[List[Dict[str, Any]]]  # RAG检索结果原始数据
    rag_sources: Optional[List[str]]       # RAG来源列表（用于前端显示）

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
    # P1-2/P1-3: RAG 检索状态和结果
    rag_triggered: bool = False
    rag_sources: List[str] = field(default_factory=list)


# ==================== LLM 初始化 ====================

# ==================== LLM 初始化 ====================
# 使用 app.core.llm_config 中的分层模型配置
# get_assistant_model(): Tier 1 快速模型
# get_specialist_model(): Tier 2 专家模型


# ==================== 节点1：律师助理（问题分类）====================

ASSISTANT_SYSTEM_PROMPT = """你是律师事务所前台助理，负责识别客户咨询的法律领域。


**任务**：分析客户问题，识别法律领域并提供引导性问题

**法律领域快速参考表**（用于准确分类）：
{reference_table}

**输出格式**：必须严格按照以下 JSON 格式输出，不要添加任何其他文字：

**示例1（劳动法）**：
```json
{{
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
}}
```

**示例2（侵权责任法/交通事故）**：
```json
{{
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
}}
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
- 问法律程序问题问题（如何申请仲裁？诉讼时效多久？鉴定程序如何进行？）
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

    # 【修改】检查是否已有分类结果（用户确认阶段）
    existing_classification = state.get("classification_result")

    if existing_classification and state.get("user_confirmed", False):
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

    # 新问题模式：进行完整的问题分类
    logger.info("[律师助理节点] 新问题模式，进行完整分类")

    # 使用动态人设与策略生成器
    db = SessionLocal()
    try:
        # 生成动态人设和策略
        persona_strategy = await dynamic_persona_generator.generate_persona_and_strategy(
            question=question,
            db=db,
            context=context
        )
    finally:
        db.close()
    
    # 提取相关信息
    classification = {
        "primary_type": persona_strategy.get("primary_type", "法律咨询"),
        "specialist_role": persona_strategy.get("specialist_role", "专业律师"),
        "confidence": persona_strategy.get("confidence", 0.8),
        "urgency": persona_strategy.get("urgency", "medium"),
        "complexity": persona_strategy.get("complexity", "medium"),
        "key_entities": [],
        "key_facts": [],
        "relevant_laws": persona_strategy.get("relevant_laws", []),
        "preliminary_assessment": "已生成动态人设，准备专业分析",
        "need_confirmation": True,
        "basic_summary": persona_strategy.get("basic_summary", "系统处理中"),
        "direct_questions": [],
        "suggested_questions": [],
        "recommended_approach": "转交动态生成的专业律师进行深度分析",
        "persona_definition": persona_strategy.get("persona_definition", {}),
        "strategic_focus": persona_strategy.get("strategic_focus", {})
    }

    logger.info(f"[律师助理节点] 解析后的分类结果：{classification}")
    logger.info(f"[律师助理节点] direct_questions 数量：{len(classification.get('direct_questions', []))}")
    logger.info(f"[律师助理节点] suggested_questions 数量：{len(classification.get('suggested_questions', []))}")

    # 更新状态
    state["classification_result"] = classification
    state["specialist_role"] = classification.get("specialist_role", "专业律师")
    state["confidence"] = classification.get("confidence", 0.8)
    state["current_step"] = "assistant_node_completed"
    state["relevant_laws"] = classification.get("relevant_laws", [])
    state["force_rag"] = classification.get("strategic_focus", {}).get("force_rag", False)

    logger.info(f"[律师助理节点] 分类完成：{classification.get('primary_type')} - {classification.get('specialist_role')}")

    return state


def parse_classification_response(response_text: str) -> Dict[str, Any]:
    """
    解析律师助理节点的 JSON 响应

    Args:
        response_text: LLM 返回的文本

    Returns:
        解析后的分类结果字典
    """
    import re
    import json

    # 默认返回值
    default_result = {
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
        "direct_questions": [],
        "suggested_questions": [],
        "recommended_approach": "转交专业律师分析"
    }

    # 预处理：清理文本，移除可能的格式问题
    cleaned_text = response_text.strip()

    # 尝试提取 JSON
    json_str = None

    # 方法1: 查找 ```json 代码块
    json_match = re.search(r'```json\s*(.*?)\s*```', cleaned_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
        logger.info("[parse_classification] 使用方法1提取JSON (```json代码块)")

    # 方法2: 查找 ``` 代码块（不带json标记）
    if not json_str:
        json_match = re.search(r'```\s*(\{.*?\})\s*```', cleaned_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
            logger.info("[parse_classification] 使用方法2提取JSON (```代码块)")

    # 方法3: 使用更精确的括号匹配
    if not json_str:
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(cleaned_text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx >= 0:
                    json_str = cleaned_text[start_idx:i+1]
                    logger.info("[parse_classification] 使用方法3提取JSON (括号匹配)")
                    break

    # 方法4: 尝试直接查找 JSON 对象（最宽松）
    if not json_str:
        json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            logger.info("[parse_classification] 使用方法4提取JSON (正则匹配)")

    # 如果所有方法都失败，返回默认值
    if not json_str:
        logger.warning("[parse_classification] 未找到 JSON，使用默认分类")
        logger.warning(f"[parse_classification] LLM 响应内容前500字符: {response_text[:500]}")
        return default_result

    # 清理 JSON 字符串
    # 移除可能的控制字符
    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

    try:
        # 解析 JSON
        result = json.loads(json_str)
        logger.info(f"[parse_classification] JSON 解析成功，解析出的keys: {list(result.keys())}")

        # 验证 result 是字典类型
        if not isinstance(result, dict):
            logger.error(f"[parse_classification] 解析结果不是字典类型: {type(result)}")
            return default_result

        # 【新增】处理可能的键名问题（去除键名的空格和换行）
        cleaned_result = {}
        for key, value in result.items():
            # 清理键名：去除首尾空格、换行、引号
            clean_key = str(key).strip().strip('"').strip("'").strip()
            cleaned_result[clean_key] = value

        if cleaned_result != result:
            logger.info(f"[parse_classification] 清理了键名，原始keys: {list(result.keys())}, 清理后: {list(cleaned_result.keys())}")
            result = cleaned_result

        # 确保包含必需的字段
        if "direct_questions" not in result:
            result["direct_questions"] = []
        if "suggested_questions" not in result:
            result["suggested_questions"] = []

        # 【新增】规范化法律领域分类
        if "primary_type" in result:
            original_type = result["primary_type"]
            # 确保 primary_type 是字符串
            if not isinstance(original_type, str):
                logger.warning(f"[parse_classification] primary_type 不是字符串: {type(original_type)}, 值: {original_type}")
                original_type = str(original_type)

            normalized_type, was_normalized = _normalize_legal_domain(original_type)
            result["primary_type"] = normalized_type

            # 如果 specialist_role 也包含了原分类，一并更新
            if was_normalized and "specialist_role" in result and isinstance(result["specialist_role"], str):
                result["specialist_role"] = result["specialist_role"].replace(original_type, normalized_type)

        return result

    except json.JSONDecodeError as e:
        logger.error(f"[parse_classification] JSON 解析失败：{e}")
        logger.error(f"[parse_classification] 尝试解析的 JSON 字符串: {json_str[:500]}...")
        return default_result
    except Exception as e:
        logger.error(f"[parse_classification] 未知错误：{e}")
        logger.error(f"[parse_classification] JSON 字符串: {json_str[:500]}...")
        return default_result


# ==================== 节点2：资料分析（文档深度分析）====================

async def document_analysis_node(state: ConsultationState) -> ConsultationState:
    """
    资料分析节点：深度分析上传的文件内容

    使用通用文档预整理服务 + 咨询特定功能
    """
    from app.services.consultation.document_analysis import get_consultation_document_analysis_service
    from app.services.common.unified_document_service import StructuredDocumentResult

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
        llm = get_assistant_model() # 使用快速模型进行文档分析
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
    - 支持多轮对话：根据 user_confirmed 标志判断是否为后续问题

    输入：state["question"], state["classification_result"], state["specialist_role"]
    输出：更新 state["legal_analysis"], state["legal_advice"], state["action_steps"], 等
    """
    logger.info("[专业律师节点] 开始提供专业咨询...")

    question = state["question"]

    # 【新增】清洗用户问题中的指令性文本（仅移除AI指令，保留业务语义）
    original_question = question  # 保存原始问题用于日志
    question = _sanitize_user_question(question)
    if question != original_question:
        logger.info(f"[输入清洗] 已移除指令性文本，原长度={len(original_question)}, 清洗后={len(question)}")

    classification = state.get("classification_result") or {}
    specialist_role = state.get("specialist_role") or "专业律师"

    # 【新增】验证 classification 字典结构，防止被污染的键名
    if classification:
        logger.info(f"[专业律师节点] classification keys: {list(classification.keys())}")
        # 清理可能的异常键名
        cleaned_classification = {}
        for key, value in classification.items():
            clean_key = str(key).strip().strip('"').strip("'").strip()
            cleaned_classification[clean_key] = value
        if cleaned_classification != classification:
            logger.info(f"[专业律师节点] 清理了classification键名")
            classification = cleaned_classification

    # 检查是否为后续问题（多轮对话）
    user_confirmed = state.get("user_confirmed", False)
    is_follow_up = state.get("is_follow_up", False)  # 【新增】获取追问标识
    previous_output = state.get("previous_specialist_output")
    user_id = state.get("user_id")

    # 获取专业律师专用 LLM (Tier 2)
    llm = get_specialist_model() # 使用专家模型

    # 【修复】区分"首份报告生成"与"后续追问"
    # 使用灵活提示词生成器，不强制使用五章节结构
    persona_def = classification.get("persona_definition", {})
    strategic_focus = classification.get("strategic_focus", {})
    legal_domain = classification.get("primary_type", "法律") if classification else "法律"
    specialist_role_display = classification.get("specialist_role", "专业律师") if classification else "专业律师"

    system_prompt = build_flexible_specialist_prompt(
        specialist_role=specialist_role_display,
        legal_domain=legal_domain,
        persona_def=persona_def,
        strategic_focus=strategic_focus,
        is_follow_up=is_follow_up
    )

    if is_follow_up:
        logger.info("[专业律师节点] 追问模式：使用灵活的简洁提示词")
    else:
        logger.info("[专业律师节点] 首份报告生成：使用灵活的自然提示词（包含人设和战略重点）")
"""
            logger.info("[专业律师节点] 首份报告生成：使用完整的 strategic_focus 提示词")
        else:
            # 使用原有模板
            legal_domain = classification.get("primary_type", "法律") if classification else "法律"
            specialist_role = classification.get("specialist_role", "专业律师") if classification else "专业律师"
            system_prompt = SPECIALIST_SYSTEM_PROMPT_TEMPLATE.format(
                specialist_role=specialist_role,
                legal_domain=legal_domain
            )
            logger.info("[专业律师节点] 首份报告生成：使用默认模板")

    # 【已移除】旧的多轮对话模式逻辑（已被上面的追问模式替代）
    # 原来的逻辑：if user_confirmed and previous_output: ...

        # 添加多轮对话指令
        system_prompt += "\n\n【多轮对话模式】\n"
        system_prompt += "用户正在基于你之前的建议提出后续问题。\n"
        system_prompt += "\n【多轮对话核心原则】\n"
        system_prompt += "1. **禁止重复**：不要复述或重新说明之前已经提供的内容\n"
        system_prompt += "2. **引用为主**：如需提及前文内容，使用'如前所述'、'正如之前分析'等引用方式\n"
        system_prompt += "3. **聚焦新问题**：直接回答用户提出的新问题，不需要重新铺垫背景\n"
        system_prompt += "4. **上下文连续**：确保新回答与之前的建议保持一致性和连贯性\n"
        system_prompt += "5. **格式严格**：必须完整输出以下所有章节（即使某个章节内容较少，也要保留章节标题）：\n"
        system_prompt += "   - ## 二、问题解答（或 ## 问题解答）\n"
        system_prompt += "   - ## 三、简要分析（或 ## 简要分析）\n"
        system_prompt += "   - ## 四、专业建议（或 ## 专业建议）\n"
        system_prompt += "   - ## 五、风险提示（或 ## 风险提示）\n"
        system_prompt += "   **重要**：缺少任何章节会导致解析失败，请务必保持完整结构！\n"

    # 添加额外的上下文信息（精简版，避免LLM过度复述）
    additional_context_parts = []

    # 【P1 优化】提前定义 original_question，确保后续代码可以正确引用
    original_question = state.get("question", "")

    # 【多轮对话】只传递引用，不传递完整内容
    if user_confirmed and previous_output:
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
    basic_summary = classification.get("basic_summary")
    if basic_summary:
        additional_context_parts.append(f"\n\n**案件基本情况**：\n{basic_summary}")

    # 【已删除】移除待咨询问题清单逻辑 - 专家律师不需要处理问题列表

    # 【新增】决定分析模式：根据复杂度和领域类型选择合适的分析深度
    analysis_complexity = classification.get("complexity", "medium")
    primary_type = classification.get("primary_type", "")
    
    # 定义复杂领域列表
    complex_domains = ["公司治理", "股权纠纷", "证券合规", "投融资", "破产清算", "知识产权"]
    
    # 如果复杂度高或属于复杂领域，使用深度分析模式
    if analysis_complexity == 'high' or primary_type in complex_domains:
        analysis_mode = "deep"
        logger.info(f"[专业律师节点] 使用深度分析模式 (complexity: {analysis_complexity}, domain: {primary_type})")
    else:
        analysis_mode = "standard"
        logger.info(f"[专业律师节点] 使用标准分析模式 (complexity: {analysis_complexity}, domain: {primary_type})")

    # 2. 检索结果（如果需要）
    force_rag = state.get("force_rag", False) or classification.get("strategic_focus", {}).get("force_rag", False)
    should_rag, rag_strategy = await _should_perform_rag_search(
        question=question,
        legal_domain=classification.get("primary_type"),
        user_id=user_id
    )
    if should_rag:
        logger.info(f"[专业律师节点] 执行RAG检索... (策略: {rag_strategy})")
        search_results = await get_legal_search_results(
            question=question,
            domain=classification.get("primary_type"),
            user_id=user_id,
            session_id=state.get("session_id")  # 新增：从 state 获取 session_id 传递给缓存机制
        )
        if search_results.get("formatted"):
            additional_context_parts.append(f"\n\n**相关法律信息**：\n{search_results['formatted']}")
            # P1-2: 保存 RAG 结果用于后续注入
            state["rag_results"] = search_results.get("raw_items", [])
            state["rag_sources"] = [item.get("title", "未知来源") for item in search_results.get("raw_items", [])]
            state["rag_triggered"] = True  # P1-2/P1-3: 标记 RAG 已触发
        else:
            state["rag_triggered"] = True  # P1-2/P1-3: 检索已执行但无结果
            state["rag_results"] = []
            state["rag_sources"] = []
    else:
        logger.info("[专业律师节点] 跳过RAG检索")
        state["rag_triggered"] = False  # P1-2/P1-3: RAG 未触发
        state["rag_results"] = []
        state["rag_sources"] = []

    # 组合完整的消息
    additional_context = "".join(additional_context_parts)
    
    # 根据分析模式调整human_content
    if analysis_mode == "deep":
        # 深度分析模式：提供更多细节和要求
        human_content = f"""客户咨询问题：\n\n{question}

【深度分析要求】
由于这是一个复杂法律问题，请进行非常详尽的分析，包括但不限于：
1. 法律关系梳理（多个层面）
2. 法规政策解读（包括最新的法规变动）
3. 类似案例参考（如有）
4. 风险评估（多维度）
5. 解决方案（多种可选方案及优劣对比）

{additional_context}"""
    else:
        # 标准分析模式：保持简洁
        human_content = f"客户咨询问题：\n\n{question}{additional_context}"

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
        try:
            parsed_result = parse_specialist_response(response_text)
        except KeyError as e:
            logger.error(f"[专业律师节点] 解析回复时出现 KeyError: {e}")
            # 使用安全的默认值
            parsed_result = {
                "analysis": response_text[:1000],  # 使用前1000字符作为分析
                "advice": "",
                "risk_warning": "",
                "action_steps": [],
                "relevant_laws": state.get("relevant_laws", [])
            }

        # 使用渲染器清理 Markdown 符号（转为纯文本，用于前端显示）
        from app.services.common.markdown_renderer import get_markdown_renderer
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

        # 【修复】确保 classification_result 被正确传递（避免在多轮对话中丢失）
        if "classification_result" not in state and classification:
            state["classification_result"] = classification
        elif classification:
            # 确保 classification_result 保持最新
            state["classification_result"] = classification

        # 生成最终报告（纯文本格式，移除 Markdown 符号）
        state["final_report"] = generate_final_report(state, renderer)

        logger.info("[专业律师节点] 咨询完成")

    except KeyError as e:
        logger.error(f"[专业律师节点] KeyError: {e}")
        logger.error(f"[专业律师节点] 可能存在字典键访问问题，使用默认值")
        import traceback
        traceback.print_exc()
        state["error"] = f"专业咨询失败（KeyError）：{str(e)}"
        state["legal_analysis"] = "抱歉，处理您的咨询时遇到问题。"
        state["legal_advice"] = "请稍后重试或联系专业律师。"
        state["action_steps"] = ["请重新提交咨询", "或联系线下专业律师"]
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
    解析专业律师节点的结构化回复（架构师增强版）
    """
    result = {
        "analysis": "",
        "advice": "",
        "risk_warning": "",
        "action_steps": [],
        "relevant_laws": []
    }

    import re

    # ==================== 1. 预处理：强力截断思维链 ====================
    # 针对思维模型，优先寻找最后一个闭合标签
    closing_tags = [r'</think>', r'\[/THOUGHT\]', r'</thinking>', r'-->', r'<\|endthought\|>']
    best_cutoff = 0
    
    for tag in closing_tags:
        matches = list(re.finditer(tag, response_text, re.IGNORECASE))
        if matches:
            # 截取闭合标签之后的内容
            best_cutoff = max(best_cutoff, matches[-1].end())
    
    if best_cutoff > 0:
        response_text = response_text[best_cutoff:].strip()
    else:
        # 兜底：如果没有闭合标签，尝试找开始标签并跳过它（虽然这可能导致保留部分思考过程，但比全丢强）
        start_tags = [r'<think>', r'\[THOUGHT\]', r'Thought:', r'<thinking>', r'<\|startthought\|>']
        for tag in start_tags:
            matches = list(re.finditer(tag, response_text, re.IGNORECASE))
            if matches:
                # 尽量往后截
                best_cutoff = max(best_cutoff, matches[-1].end())
        response_text = response_text[best_cutoff:].strip()

    # ==================== 2. 剔除残留的标签块 ====================
    # 防止模型输出多个思考块或未闭合块
    tag_patterns = [
        r'<think>.*?</think>', r'\[THOUGHT\].*?\[/THOUGHT\]',
        r'<thinking>.*?</thinking>', r'<!--.*?-->',
        r'<\|startthought\|>.*?<\|endthought\|>',
        r'<think>.*', r'\[THOUGHT\].*', r'<thinking>.*' # 兜底：删除未闭合的标签及其后内容
    ]
    cleaned_text = response_text
    for pattern in tag_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL | re.IGNORECASE)

    # ==================== 3. 清洗系统指令与提示词回显 ====================
    # 重点：防止模型复读“必须逐一回答”
    instruction_garbage = [
        r'(?i)必须逐一回答.*?\n', 
        r'(?i)🚨 输出要求.*?\n',
        r'(?i)系统提示词.*?\n',
        r'(?i)每个问题的回答应包含.*?\n',
        r'(?i)建议使用清晰的标题格式.*?\n',
        r'(?i)逐一回答上述系统提示词中的所有.*?问题.*?\n'
    ]
    for pattern in instruction_garbage:
        cleaned_text = re.sub(pattern, '', cleaned_text)

    # ==================== 4. 结构化解析 ====================
    # 使用通用的章节提取逻辑
    def extract_section(content, section_names, next_section_names):
        # 构造匹配当前章节的正则：# 一、问题解答 或 二、问题解答 等
        pattern = r'[#\s]*[一二三四五六七]\s*[、.]?\s*(' + '|'.join(section_names) + r')'
        # 构造停止符：下一个章节名 或 文件结尾
        stop_pattern = r'(?=[#\s]*[一二三四五六七]\s*[、.]?\s*(' + '|'.join(next_section_names) + r'))'
        
        full_regex = pattern + r'[:：]?\n*(.*?)(?:' + stop_pattern + r'|\Z)'
        match = re.search(full_regex, content, re.DOTALL | re.IGNORECASE)
        return match.group(2).strip() if match else ""

    result["analysis"] = extract_section(cleaned_text, ['问题解答', '问题分析', '法律分析', '分析'], ['简要分析', '专业建议', '建议'])
    # 如果解答为空，尝试提取简要分析
    if not result["analysis"]:
        result["analysis"] = extract_section(cleaned_text, ['简要分析'], ['专业建议', '建议', '风险提示'])
    
    result["advice"] = extract_section(cleaned_text, ['专业建议', '具体建议', '操作建议', '建议'], ['风险提示', '注意事项', '行动步骤'])
    result["risk_warning"] = extract_section(cleaned_text, ['风险提示', '风险警告', '注意事项'], ['行动步骤', '相关法规', '法律依据'])
    
    # 行动步骤的提取：强化列表识别
    steps_raw = extract_section(cleaned_text, ['行动步骤', '行动建议'], ['相关法规', '法律依据', '结语'])
    if steps_raw:
        # 识别多种列表前缀
        lines = [l.strip() for l in steps_raw.split('\n') if l.strip()]
        for line in lines:
            # 过滤掉明显的提示词残留
            if any(k in line for k in ["描述：", "应对：", "填充内容", "使用Markdown"]):
                continue
            # 提取带符号的行，或者紧跟在符号行后的行（简单处理）
            clean_line = re.sub(r'^[-•*]|^\[\d+\]|^\d+[.、)]', '', line).strip()
            if clean_line:
                result["action_steps"].append(clean_line)

    # 提取法规
    laws_raw = extract_section(cleaned_text, ['相关法规', '法律依据'], ['END'])
    if laws_raw:
        result["relevant_laws"] = [l.strip() for l in laws_raw.split('\n') if len(l.strip()) > 4]

    # ==================== 5. 兜底策略 ====================
    if not result["analysis"] and len(cleaned_text) > 50:
        result["analysis"] = cleaned_text
        logger.warning("[parse_specialist] 章节匹配失败，启用全文分析兜底")

    return result


# ==================== 追问问题提取函数 ====================

def extract_follow_up_questions(response: str) -> List[str]:
    """
    从 LLM 响应中提取后续追问问题

    优先提取 JSON 格式，如失败则使用正则备选方案

    Args:
        response: LLM 返回的完整响应文本

    Returns:
        后续追问问题列表
    """
    import re
    import json

    # 方法1：查找 JSON 格式的 follow_up_questions
    json_match = re.search(r'"follow_up_questions"[\s\n]*:[\s\n]*\[', response, re.DOTALL)

    if json_match:
        # 找到匹配，向后查找完整的 JSON 结构
        start_pos = json_match.start()
        brace_count = 0
        end_pos = start_pos

        for i in range(start_pos, min(start_pos + 1000, len(response))):
            char = response[i]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i + 1
                    break

        try:
            json_str = response[start_pos:end_pos]
            data = json.loads(json_str)
            questions = data.get("follow_up_questions", [])
            logger.info(f"[专业律师节点] 提取到 {len(questions)} 个追问问题（JSON方式）")
            return questions[:5]  # 最多 5 个
        except json.JSONDecodeError:
            logger.warning(f"[专业律师节点] JSON 解析失败: {json_str[:100]}")

    # 方法2：备选方案，使用正则提取问题
    lines = response.split('\n')
    potential_questions = []

    # 查找最后的几行中可能的问题
    for line in lines[-10:]:
        line = line.strip()
        # 跳过 JSON 相关行
        if 'follow_up_questions' in line or line.startswith('{') or line.startswith('}'):
            continue
        # 查找可能的问句
        if any(keyword in line for keyword in ['？', '?', '如何', '可以', '需要', '是否应该']):
            if len(line) > 5 and len(line) < 100:
                potential_questions.append(line)

    if potential_questions:
        logger.info(f"[专业律师节点] 备选提取到 {len(potential_questions)} 个追问问题（正则方式）")
        return potential_questions[:5]

    logger.info("[专业律师节点] 未提取到追问问题")
    return []


# ==================== 灵活提示词生成函数 ====================

def build_flexible_specialist_prompt(
    specialist_role: str,
    legal_domain: str,
    persona_def: dict = None,
    strategic_focus: dict = None,
    is_follow_up: bool = False
) -> str:
    """
    生成灵活的专业律师提示词，不强制使用五章节结构

    Args:
        specialist_role: 专业律师角色
        legal_domain: 法律领域
        persona_def: 人设定义（可选）
        strategic_focus: 战略重点（可选）
        is_follow_up: 是否为追问模式

    Returns:
        系统提示词字符串
    """
    if is_follow_up:
        # 追问模式：简洁直接
        return f"""你是{specialist_role}，专注于{legal_domain}领域的法律咨询。

【追问模式】
用户正在基于之前的法律建议提出后续问题或追问。

【核心原则】
1. **直接回答**：直接回答用户提出的新问题，不要重新铺垫背景
2. **保持一致**：确保新回答与之前的建议保持一致性和连贯性
3. **简洁明确**：使用清晰简洁的语言，直接给出答案
4. **格式规范**：使用 Markdown 格式，保持良好的可读性

【输出要求】
请按照以下结构回答用户的问题：

## 问题解答

直接回答用户提出的问题。

## 补充分析

如果需要，提供补充的法律分析。

## 后续建议

如有必要，提供后续的建议或行动指引。

---

**注意**：这是一个追问场景，请聚焦于用户的具体问题，不要重复之前已经说明的内容。"""

    # 首次回答模式：使用灵活的自然输出格式
    if persona_def and strategic_focus:
        # 使用动态生成的人设
        base_prompt = f"""你是{persona_def.get('role_title', '一位资深律师')}，{persona_def.get('professional_background', '具有深厚的法学功底')}，
拥有{persona_def.get('years_of_experience', '丰富')}的{', '.join(persona_def.get('expertise_area', ['法律咨询']))}经验，
采用{persona_def.get('approach_style', '专业严谨')}的分析风格。

【战略分析重点】
- 分析角度: {strategic_focus.get('analysis_angle', '法律关系分析')}
- 关键关注点: {', '.join(strategic_focus.get('key_points', ['事实认定', '法律适用']))}
- 风险预警: {', '.join(strategic_focus.get('risk_alerts', ['法律风险', '程序风险']))}
- 注意事项: {', '.join(strategic_focus.get('attention_matters', ['时效性', '证据效力']))}

【核心工作原则】
1. **准确专业**：基于现行有效法律提供专业分析
2. **清晰简洁**：直接回答问题，避免法言法语堆砌
3. **可操作建议**：提供具体、可执行的建议
4. **风险提示**：明确告知潜在法律风险
5. **逐一回答**：必须针对用户提出的每个问题逐一给出明确、具体的回答

【输出格式要求】
- 使用清晰简洁的语言，像通用大模型一样自然流畅地回答
- 使用 Markdown 格式组织内容，但不强制要求固定章节结构
- 根据问题特点灵活组织回答结构
- 严禁简单复述文档内容或用户问题

在回答结束时，请提供 2-4 个用户可能关心的后续问题，格式如下：
```json
{{"follow_up_questions": ["问题1", "问题2", "问题3"]}}
```

【专业标准】
- 每个结论都要有明确的法律依据
- 建议要具体到"做什么"、"怎么做"
- 体现资深律师的专业判断
- 针对每个问题都给出明确、具体的回答"""
        logger.info("[灵活提示词] 使用动态人设生成灵活提示词")
        return base_prompt
    else:
        # 使用默认的灵活模板
        base_prompt = f"""你是一位{specialist_role}，拥有15年执业经验的资深律师。

【专业背景】
- 15年执业经验，处理过500+法律案件
- 专注领域：{legal_domain}
- 具备律师资格证和法学硕士学位

【核心工作原则】
1. **准确专业**：基于现行有效法律提供专业分析
2. **清晰简洁**：直接回答问题，避免法言法语堆砌
3. **可操作建议**：提供具体、可执行的建议
4. **风险提示**：明确告知潜在法律风险
5. **逐一回答**：必须针对用户提出的每个问题逐一给出明确、具体的回答

【输出格式要求】
- 使用清晰简洁的语言，像通用大模型一样自然流畅地回答
- 使用 Markdown 格式组织内容，但不强制要求固定章节结构
- 根据问题特点灵活组织回答结构
- 严禁简单复述文档内容或用户问题

在回答结束时，请提供 2-4 个用户可能关心的后续问题，格式如下：
```json
{{"follow_up_questions": ["问题1", "问题2", "问题3"]}}
```

【专业标准】
- 每个结论都要有明确的法律依据
- 建议要具体到"做什么"、"怎么做"
- 体现15年执业经验的专业判断
- 针对每个问题都给出明确、具体的回答"""
        logger.info("[灵活提示词] 使用默认模板生成灵活提示词")
        return base_prompt


# ==================== 标题去重函数 ====================

def _deduplicate_report_titles(text: str) -> str:
    """
    移除报告中重复的中文标题

    处理两种类型的重复：
    1. 完全相同的标题连续重复：【一、问题解答】【一、问题解答】
    2. 相同内容不同序号：【一、问题解答】【二、问题解答】
    """
    import re

    # 匹配重复的【X、标题】模式（完全重复）
    # 例如：【一、问题解答】【一、问题解答】→【一、问题解答】
    pattern = r'([【][一二三四五六七八九十]、[^】]+[】])\1+'
    text = re.sub(pattern, r'\1', text)

    # 匹配连续的相同标题（不同序号）
    # 例如：【一、问题解答】【二、问题解答】→【一、问题解答】
    lines = text.split('\n')
    deduplicated_lines = []
    prev_title = None

    for line in lines:
        # 检测是否为【X、...】格式的标题
        title_match = re.match(r'^([【][一二三四五六七八九十]、[^]]+[】])', line.strip())
        if title_match:
            current_title_content = title_match.group(1)
            # 检查标题内容是否相同（忽略序号）
            current_content = re.sub(r'^[【][一二三四五六七八九十]、', '', current_title_content)
            prev_content = re.sub(r'^[【][一二三四五六七八九十]、', '', prev_title) if prev_title else None

            if prev_content and current_content == prev_content:
                # 跳过重复标题
                continue
            prev_title = current_title_content
        else:
            prev_title = None

        deduplicated_lines.append(line)

    return '\n'.join(deduplicated_lines)


def generate_final_report(state: ConsultationState, renderer=None) -> str:
    """
    生成最终报告

    Args:
        state: 咨询状态
        renderer: Markdown 渲染器（可选）

    Returns:
        最终报告（纯文本格式，已移除 Markdown 符号）
    """
    question = state.get("question", "")
    classification = state.get("classification_result") or {}
    relevant_laws = state.get("relevant_laws") or []
    analysis = state.get("legal_analysis") or ""
    advice = state.get("legal_advice") or ""
    risk_warning = state.get("risk_warning") or ""
    action_steps = state.get("action_steps") or []

    # 使用渲染器清理 Markdown 符号，转为纯文本
    if renderer:
        clean_analysis = renderer.render_to_clean_text(analysis)
        clean_advice = renderer.render_to_clean_text(advice)
        clean_risk_warning = renderer.render_to_clean_text(risk_warning)
    else:
        clean_analysis = analysis
        clean_advice = advice
        clean_risk_warning = risk_warning

    # 构建报告，按照要求的格式
    report = "【一、问题解答】\n"  # 按要求使用指定格式作为报告开头
    
    # 【二、问题分析】部分，将法律依据包含在此部分
    report += f"\n【二、问题分析】\n"
    if relevant_laws:
        report += f"法律依据：\n"
        for law in relevant_laws:
            report += f"• {law}\n\n"
    if clean_analysis:
        report += f"{clean_analysis}\n"

    # 【三、专业建议】部分
    if clean_advice:
        report += f"\n【三、专业建议】\n{clean_advice}\n"

    # 【四、风险提醒】部分
    if clean_risk_warning:
        report += f"\n【四、风险提醒】\n{clean_risk_warning}\n"

    # 【五、行动建议】部分
    if action_steps:
        report += f"\n【五、行动建议】\n"
        for i, step in enumerate(action_steps, 1):
            report += f"{i}. {step}\n"

    # 【新增】去重处理：移除重复的标题
    report = _deduplicate_report_titles(report)

    return report


# ==================== 条件路由函数 ====================

def should_start_with_assistant(state: ConsultationState) -> str:
    """
    智能入口路由：决定从哪个节点开始（支持多轮对话）

    路由逻辑：
    - 情况1：用户确认阶段（第一次对话，点击"转交专家"）→ 从律师助理节点恢复
    - 情况2：真正的后续追问 → 直接进入专业律师节点
    - 情况3：新问题 → 从律师助理节点开始
    """
    user_confirmed = state.get("user_confirmed", False)
    is_follow_up = state.get("is_follow_up", False)
    saved_classification = state.get("saved_classification")

    # 情况1：用户确认阶段（第一次对话，点击"转交专家"）
    if user_confirmed and saved_classification and not is_follow_up:
        logger.info("[路由] 用户确认阶段：从assistant节点恢复")
        return "assistant"

    # 情况2：真正的后续追问
    if is_follow_up:
        logger.info("[路由] 后续追问：直接进入specialist")
        return "specialist"

    # 情况3：新问题
    logger.info("[路由] 新问题：从assistant开始")
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

    # 【关键修改】使用 START 条件入口点，基于 user_confirmed 路由
    # 实现架构级路由：多轮对话直接进入专业律师节点，无需经过助理节点
    from langgraph.graph import START
    
    workflow.add_conditional_edges(
        START,
        should_start_with_assistant,  # 基于 user_confirmed 的路由决策
        {
            "assistant": "assistant",
            "specialist": "specialist"
        }
    )

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

    logger.info("[工作流] LangGraph 构建完成（支持多轮对话 - 通过START条件入口点）")

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
        # 【关键修复】使用更新后的版本，支持真正的条件入口点
        _legal_consultation_graph = create_legal_consultation_graph()
        logger.info("[工作流] 使用新版（支持START条件入口点）")
    return _legal_consultation_graph


async def run_legal_consultation(
    question: str,
    context: Dict[str, Any],
    conversation_history: Optional[List[BaseMessage]] = None,
    user_confirmed: bool = False,
    selected_suggested_questions: Optional[List[str]] = None,
    is_follow_up: bool = False,
    session_id: Optional[str] = None,
    previous_specialist_output: Optional[Dict[str, Any]] = None,
    saved_classification: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
) -> tuple[ConsultationOutput, Any]:
    """
    运行法律咨询工作流
    """
    logger.info(f"[咨询流程] ===== 开始处理 =====")
    logger.info(f"[咨询流程] 问题：{question[:50]}... (is_follow_up={is_follow_up}, user_confirmed={user_confirmed})")

    # 【已删除】移除 selected_suggested_questions 相关日志（该功能已废弃）

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
        "user_id": user_id, # 新增：用户ID
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
        "rag_triggered": False,  # P1-2/P1-3: RAG 检索状态
        "rag_results": [],  # P1-2/P1-3: RAG 检索结果
        "rag_sources": [],  # P1-2/P1-3: RAG 来源列表
        "error": None,
        "current_step": "start"
    }

    try:
        # 获取工作流
        graph = get_consultation_graph()

        # 执行工作流
        result_state = await graph.ainvoke(initial_state)

        # 检查是否有错误
        error = result_state.get("error")
        if error:
            logger.error(f"[咨询流程] 执行失败：{error}")
            return None, error

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
            follow_up_questions=result_state.get("follow_up_questions", []),
            rag_triggered=result_state.get("rag_triggered", False),
            rag_sources=result_state.get("rag_sources", [])
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
