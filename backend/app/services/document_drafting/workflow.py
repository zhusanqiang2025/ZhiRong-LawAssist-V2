# backend/app/services/document_drafting/workflow.py
"""
文书起草工作流

使用 LangGraph 构建状态图，实现完整的文书起草流程

【三层文书起草架构】（复用合同生成的成功架构）
🧠 第一层：需求分析与文书类型识别（Analysis Layer）
    → 分析用户输入
    → 识别文书类型（函件/司法文书）
    → 提取关键信息

🧱 第二层：模板匹配（Template Matching Layer）
    → 根据文书类型匹配模板
    → 输出：template_match_result

🧾 第三层：生成策略选择与起草（Generation Layer）
    → 选择生成策略（模板改写/从零起草）
    → 加载模板文件
    → 基于模板改写生成文书

流程：
用户输入 → 需求分析 (预处理提取附件) → 模板匹配 → 策略选择 → 【加载模板文件】 → 文书起草 → 输出
"""
import logging
import os
from typing import TypedDict, List, Optional, Dict, Any

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.services.document_drafting.config import get_document_config, get_template_path
from app.services.document_drafting.agents.document_drafter import DocumentDrafterAgent

logger = logging.getLogger(__name__)


def _get_llm():
    """获取 LLM 实例"""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("LANGCHAIN_API_KEY", "")
    api_base = os.getenv("OPENAI_API_BASE") or os.getenv("DEEPSEEK_API_URL") or os.getenv("LANGCHAIN_API_BASE_URL", "https://api.deepseek.com/v1")
    model_name = os.getenv("MODEL_NAME", "deepseek-chat")

    if not api_key:
        logger.warning("[_get_llm] 未找到 API_KEY，LLM 功能将不可用")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_base,
        temperature=0.3,
        max_tokens=16000
    )


# ==================== 状态定义 ====================

class DocumentDraftingState(TypedDict):
    """文书起草状态"""
    # 输入层
    user_input: str                      # 用户文本描述
    uploaded_files: List[str]            # 上传文件路径列表
    reference_content: Optional[str]     # 参考资料文本（从附件提取）
    knowledge_graph_features: Optional[Dict]  # 知识图谱法律特征

    # 处理层
    document_type: Optional[str]         # 文书类型（如 lawyer_letter, civil_complaint）
    analysis_result: Optional[Dict]      # 需求分析结果
    template_match_result: Optional[Dict]  # 模板匹配结果
    generation_strategy: Optional[Dict]  # 生成策略

    # 物理层
    template_content: Optional[str]      # 从硬盘加载的模板内容

    # 输出层
    drafted_content: Optional[str]       # AI 起草的文书内容
    generated_documents: List[Dict]      # 已生成的文书列表

    # 错误处理
    error: Optional[str]
    requires_user_input: bool            # 是否需要用户补充信息
    clarification_questions: List[str]   # 需要澄清的问题


# ==================== 节点函数 ====================

async def process_user_input(state: DocumentDraftingState) -> DocumentDraftingState:
    """
    处理用户输入 & 预理文件
    提取上传文件的文本内容作为参考资料
    """
    logger.info("[DocumentDraftingWorkflow] 处理用户输入 & 预处理文件")

    uploaded_files = state.get("uploaded_files", [])
    reference_content = ""

    # 提取附件内容
    if uploaded_files:
        try:
            from app.services.unified_document_service import get_unified_document_service
            doc_service = get_unified_document_service()
            extracted_texts = []

            for file_path in uploaded_files:
                try:
                    success, text, error = doc_service.extract_text(file_path)
                    if success and text:
                        filename = os.path.basename(file_path)
                        extracted_texts.append(f"--- 附件文件: {filename} ---\n{text}")
                except Exception as file_err:
                    logger.warning(f"文件提取失败 {file_path}: {file_err}")

            if extracted_texts:
                reference_content = "\n\n".join(extracted_texts)
                logger.info(f"[DocumentDraftingWorkflow] 成功提取参考资料，长度: {len(reference_content)}")

        except Exception as e:
            logger.error(f"[DocumentDraftingWorkflow] 文档处理器初始化失败: {e}")

    state["reference_content"] = reference_content
    return state


async def analyze_requirement(state: DocumentDraftingState) -> DocumentDraftingState:
    """
    分析用户需求，识别文书类型和关键信息

    第一层：需求分析与文书类型识别
    """
    logger.info("[DocumentDraftingWorkflow] 分析用户需求")

    user_input = state.get("user_input", "")
    reference_content = state.get("reference_content", "")

    # TODO: 使用 LLM 分析用户输入，识别文书类型和提取关键信息
    # 目前简化处理：直接使用用户输入作为分析结果

    # 简单的文书类型识别（实际应该使用 LLM）
    document_type = None

    # 关键词映射
    type_keywords = {
        "lawyer_letter": ["律师函", "律师通知", "律师事务所函"],
        "demand_letter": ["催告函", "催款函", "催告"],
        "notification_letter": ["通知函", "通知书", "通知"],
        "legal_opinion": ["法律意见书", "法律意见"],
        "civil_complaint": ["起诉状", "民事起诉状", "起诉"],
        "defense_statement": ["答辩状", "答辩"],
        "evidence_list": ["证据清单", "证据", "举证"],
        "application": ["申请书", "申请"],
        "power_of_attorney": ["授权委托书", "委托书", "授权"]
    }

    # 基于关键词识别文书类型
    for doc_type, keywords in type_keywords.items():
        if any(keyword in user_input for keyword in keywords):
            document_type = doc_type
            break

    if not document_type:
        # 默认为律师函
        document_type = "lawyer_letter"
        logger.warning(f"[DocumentDraftingWorkflow] 未识别到具体文书类型，默认使用: {document_type}")

    # 获取文书配置
    doc_config = get_document_config(document_type)

    # 构建分析结果
    analysis_result = {
        "document_type": document_type,
        "document_name": doc_config["name"] if doc_config else document_type,
        "template_type": doc_config["template_type"] if doc_config else "unknown",
        "key_info": {
            "用户需求": user_input,
            "文书类型": doc_config["name"] if doc_config else document_type
        },
        "processing_type": "single_document"
    }

    state["document_type"] = document_type
    state["analysis_result"] = analysis_result

    logger.info(f"[DocumentDraftingWorkflow] 需求分析完成，文书类型: {document_type}")
    return state


async def match_template(state: DocumentDraftingState) -> DocumentDraftingState:
    """
    匹配文书模板

    第二层：模板匹配层
    """
    logger.info("[DocumentDraftingWorkflow] 匹配文书模板")

    document_type = state.get("document_type")
    if not document_type:
        logger.error("[DocumentDraftingWorkflow] 文书类型为空，无法匹配模板")
        state["error"] = "文书类型为空"
        return state

    # 获取模板路径
    template_path = get_template_path(document_type)
    doc_config = get_document_config(document_type)

    template_match_result = {
        "matched": bool(template_path),
        "template_path": template_path,
        "template_type": doc_config["template_type"] if doc_config else "unknown",
        "document_name": doc_config["name"] if doc_config else document_type,
        "description": doc_config["description"] if doc_config else ""
    }

    state["template_match_result"] = template_match_result

    logger.info(f"[DocumentDraftingWorkflow] 模板匹配完成: {template_match_result}")
    return state


async def select_generation_strategy(state: DocumentDraftingState) -> DocumentDraftingState:
    """
    选择生成策略

    第三层：生成策略选择层
    决定使用模板改写还是从零起草
    """
    logger.info("[DocumentDraftingWorkflow] 选择生成策略")

    template_match_result = state.get("template_match_result", {})
    document_type = state.get("document_type", "")

    # 如果匹配到模板，使用模板改写策略
    if template_match_result.get("matched") and template_match_result.get("template_path"):
        generation_strategy = {
            "strategy": "template_based",
            "template_name": template_match_result.get("document_name", document_type),
            "template_category": template_match_result.get("template_type", "unknown"),
            "description": "使用模板改写生成"
        }
    else:
        # 没有匹配到模板，从零起草
        generation_strategy = {
            "strategy": "from_scratch",
            "template_name": "无",
            "template_category": "无",
            "description": "从零起草"
        }

    state["generation_strategy"] = generation_strategy

    logger.info(f"[DocumentDraftingWorkflow] 生成策略: {generation_strategy['strategy']}")
    return state


async def load_template_file(state: DocumentDraftingState) -> DocumentDraftingState:
    """
    物理加载模板文件内容

    如果生成策略是 template_based，则加载模板文件
    """
    logger.info("[DocumentDraftingWorkflow] 加载模板文件")

    generation_strategy = state.get("generation_strategy", {})

    # 只有模板改写策略才需要加载模板
    if generation_strategy.get("strategy") != "template_based":
        logger.info("[DocumentDraftingWorkflow] 非模板改写策略，跳过模板加载")
        return state

    document_type = state.get("document_type")
    template_path = get_template_path(document_type)

    if not template_path:
        logger.warning(f"[DocumentDraftingWorkflow] 模板路径为空: {document_type}")
        state["template_content"] = None
        return state

    try:
        # 加载模板内容
        from pathlib import Path
        template_full_path = Path(__file__).parent.parent.parent.parent / "templates" / "documents" / template_path.split("/")[-1]

        if template_full_path.exists():
            with open(template_full_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            state["template_content"] = template_content
            logger.info(f"[DocumentDraftingWorkflow] 成功加载模板: {template_full_path.name}, 长度: {len(template_content)}")
        else:
            logger.warning(f"[DocumentDraftingWorkflow] 模板文件不存在: {template_full_path}")
            state["template_content"] = None

    except Exception as e:
        logger.error(f"[DocumentDraftingWorkflow] 加载模板失败: {str(e)}", exc_info=True)
        state["template_content"] = None

    return state


async def draft_document(state: DocumentDraftingState) -> DocumentDraftingState:
    """
    起草文书（核心节点）

    第三层：生成层
    根据策略进行模板改写或从零起草
    """
    logger.info("[DocumentDraftingWorkflow] 开始起草文书")

    # 初始化 Agent
    llm = _get_llm()
    drafter = DocumentDrafterAgent(llm)

    analysis_result = state.get("analysis_result", {})
    generation_strategy = state.get("generation_strategy", {})
    template_content = state.get("template_content")
    reference_content = state.get("reference_content", "")
    knowledge_graph_features = state.get("knowledge_graph_features")

    try:
        if generation_strategy.get("strategy") == "template_based" and template_content:
            # 模板改写模式
            logger.info("[DocumentDraftingWorkflow] 使用模板改写模式")
            drafted_content, template_info = drafter.draft_with_template(
                analysis_result=analysis_result,
                template_content=template_content,
                strategy=generation_strategy,
                reference_content=reference_content,
                knowledge_graph_features=knowledge_graph_features
            )
        else:
            # 从零起草模式
            logger.info("[DocumentDraftingWorkflow] 使用从零起草模式")
            drafted_content = drafter.draft_from_scratch(
                analysis_result=analysis_result,
                reference_content=reference_content,
                knowledge_graph_features=knowledge_graph_features
            )

        if not drafted_content:
            logger.error("[DocumentDraftingWorkflow] 文书起草失败，内容为空")
            state["error"] = "文书起草失败，内容为空"
            return state

        # 构建生成结果
        document_type = state.get("document_type", "unknown")
        doc_config = get_document_config(document_type)

        generated_doc = {
            "document_type": document_type,
            "document_name": doc_config["name"] if doc_config else document_type,
            "content": drafted_content,
            "format": "markdown",
            "strategy": generation_strategy.get("strategy", "unknown"),
            "template_info": template_info if generation_strategy.get("strategy") == "template_based" else None
        }

        state["drafted_content"] = drafted_content
        state["generated_documents"] = [generated_doc]

        logger.info(f"[DocumentDraftingWorkflow] 文书起草完成，类型: {document_type}, 长度: {len(drafted_content)}")

    except Exception as e:
        logger.error(f"[DocumentDraftingWorkflow] 文书起草异常: {str(e)}", exc_info=True)
        state["error"] = f"文书起草异常: {str(e)}"

    return state


# ==================== 构建工作流 ====================

def create_document_drafting_workflow():
    """
    创建文书起草工作流

    Returns:
        编译后的工作流
    """
    # 定义工作流图
    workflow = StateGraph(DocumentDraftingState)

    # 添加节点
    workflow.add_node("process_input", process_user_input)
    workflow.add_node("analyze_requirement", analyze_requirement)
    workflow.add_node("match_template", match_template)
    workflow.add_node("select_strategy", select_generation_strategy)
    workflow.add_node("load_template", load_template_file)
    workflow.add_node("draft_document", draft_document)

    # 设置入口点
    workflow.set_entry_point("process_input")

    # 添加边（定义节点之间的流转）
    workflow.add_edge("process_input", "analyze_requirement")
    workflow.add_edge("analyze_requirement", "match_template")
    workflow.add_edge("match_template", "select_strategy")
    workflow.add_edge("select_strategy", "load_template")
    workflow.add_edge("load_template", "draft_document")
    workflow.add_edge("draft_document", END)

    # 编译工作流
    app = workflow.compile()

    logger.info("[DocumentDraftingWorkflow] 工作流创建成功")
    return app


# 全局工作流实例
_document_drafting_workflow = None


def get_document_drafting_workflow():
    """
    获取文书起草工作流实例（单例模式）

    Returns:
        编译后的工作流
    """
    global _document_drafting_workflow
    if _document_drafting_workflow is None:
        _document_drafting_workflow = create_document_drafting_workflow()
    return _document_drafting_workflow
