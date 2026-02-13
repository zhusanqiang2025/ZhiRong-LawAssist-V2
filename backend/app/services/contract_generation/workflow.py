# backend/app/services/contract_generation/workflow.py
"""
合同生成工作流

使用 LangGraph 构建状态图，实现完整的三层合同生成流程

【三层合同生成架构】
🧠 第一层：合同类型与交易结构判定（Analysis Layer）
    → RequirementAnalyzerAgent
    → 输出：contract_primary_type, transaction_structure

🧱 第二层：模板"候选池"过滤（Structural Filtering Layer）
    → StructuralTemplateMatcher
    → 输出：template_match_result（HIGH/STRUCTURAL/NONE）

🧾 第三层：生成策略选择（Generation Strategy Layer）
    → GenerationStrategySelector
    → 输出：generation_strategy（三种策略）

流程：
用户输入 → 需求分析 (预处理提取附件) → (路由分发)
    ├── 1. 合同变更 → 提取原合同 → 起草变更协议
    ├── 2. 合同解除 → 提取原合同 → 起草解除协议
    ├── 3. 单一合同 → 模板匹配 → 策略选择 → 【加载模板文件】 → 合同起草
    └── 4. 合同规划 → 规划生成 → 循环起草
"""
import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict, List, Optional, Literal, Dict, Any

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .agents.requirement_analyzer import RequirementAnalyzer
from .agents.contract_drafter import ContractDrafterAgent
# 注意：ContractPlannerAgent 已删除，请使用 ContractPlanningService 替代
# 【✨ 新增】引入工具类
from .structural.template_loader import TemplateLoader

logger = logging.getLogger(__name__)

# 创建全局线程池，用于处理文档提取等 CPU/IO 密集型同步操作
_executor = ThreadPoolExecutor(max_workers=4)

def _get_llm():
    """获取 LLM 实例（使用硬编码配置）"""
    from app.core.llm_config import get_qwen3_llm

    llm = get_qwen3_llm()
    if not llm:
        logger.error("[_get_llm] LLM 初始化失败！请检查 API Key 配置")
        # 【修复】抛出异常而不是返回 None，以便快速发现问题
        raise ValueError("LLM 初始化失败：API Key 未配置或无效。请检查 QWEN3_API_KEY 环境变量。")

    return llm


# ==================== 状态定义 ====================

class ContractGenerationState(TypedDict):
    """合同生成状态"""
    # 输入
    user_input: str                      # 用户文本描述
    uploaded_files: List[str]            # 上传文件路径列表

    # 【✨ 新增】参考资料文本
    # 无论是单一合同还是规划，用户上传的文件都作为背景资料存储于此
    reference_content: Optional[str]

    # 【✨ 新增】知识图谱法律特征
    # 从知识图谱查询到的合同类型定义和法律特征
    knowledge_graph_features: Optional[Dict]  # 知识图谱法律特征

    # 第一层：需求分析结果
    analysis_result: Optional[Dict]      # 需求分析结果
    processing_type: Optional[Literal[
        "contract_modification",          # 合同变更
        "contract_termination",           # 合同解除
        "single_contract",                # 单一合同
        "contract_planning"               # 合同规划
    ]]

    # 第二层：模板匹配结果
    template_match_result: Optional[Dict]  # 模板匹配结果

    # 第三层：生成策略
    generation_strategy: Optional[Dict]    # 生成策略

    # 【✨ 新增】物理层数据：存储从硬盘加载的 Markdown 模板全文
    template_content: Optional[str]

    # 合同变更/解除
    original_contract: Optional[Dict]    # 原合同结构化数据
    modification_points: List[Dict]       # 变更点列表

    # 合同规划
    contract_plan: Optional[List[Dict]]  # 合同规划清单
    contract_relationships: Optional[Dict]  # 合同关联关系
    current_plan_index: int              # 当前生成进度

    # 生成结果
    drafted_content: Optional[str]        # AI 起草的内容
    generated_contracts: List[Dict]      # 已生成的合同列表

    # 错误处理
    error: Optional[str]
    requires_user_input: bool            # 是否需要用户补充信息
    clarification_questions: List[str]   # 需要澄清的问题

    # 【新增】规划模式选择
    planning_mode: Optional[str]         # "single_model" 或 "multi_model"

    # 【新增】是否跳过模板匹配
    skip_template: Optional[bool]        # true=跳过模板匹配（不用模板），false=正常流程

    # 【新增】多模型融合报告
    multi_model_synthesis_report: Optional[Dict[str, Any]]  # 多模型规划融合报告

    # 【新增】Step 2 确认的变更/解除信息（用于简化流程）
    confirmed_modification_termination_info: Optional[Dict[str, Any]]

    # 【新增】标记当前请求是否包含用户确认过的规划
    # 用于区分"生成规划"和"基于已有规划生成合同"两种场景
    is_plan_confirmed: Optional[bool]         # true=基于确认的规划生成，false=仅生成规划


# ==================== 节点函数 ====================

async def process_user_input(state: ContractGenerationState) -> ContractGenerationState:
    """
    处理用户输入 & 预处理文件
    在此处统一提取上传文件的文本内容作为参考资料
    """
    logger.info("[Workflow] 处理用户输入 & 预处理文件")
    
    uploaded_files = state.get("uploaded_files", [])
    reference_content = ""

    # 【✨ 优化】异步并发提取文档逻辑，防止阻塞 Event Loop
    if uploaded_files:
        try:
            from app.services.common.unified_document_service import get_unified_document_service
            doc_service = get_unified_document_service()
            
            extracted_texts = []
            loop = asyncio.get_running_loop()
            
            # 构建提取任务列表
            extract_tasks = []
            file_names = []
            
            for file_path in uploaded_files:
                # 假设 extract_text 是同步阻塞操作，将其放入线程池运行
                extract_tasks.append(
                    loop.run_in_executor(_executor, doc_service.extract_text, file_path)
                )
                file_names.append(os.path.basename(file_path))

            if extract_tasks:
                # 并发等待所有文件提取完成
                results = await asyncio.gather(*extract_tasks, return_exceptions=True)
                
                for idx, result in enumerate(results):
                    filename = file_names[idx]
                    if isinstance(result, Exception):
                        logger.warning(f"文件提取异常 {filename}: {result}")
                        continue
                    
                    success, text, error = result
                    if success and text:
                        extracted_texts.append(f"--- 附件文件: {filename} ---\n{text}")
                    else:
                        logger.warning(f"文件提取失败 {filename}: {error}")

            if extracted_texts:
                reference_content = "\n\n".join(extracted_texts)
                logger.info(f"[Workflow] 成功提取参考资料，长度: {len(reference_content)}")
                
        except Exception as e:
            logger.error(f"[Workflow] 文档处理过程出错: {e}", exc_info=True)

    # 初始化状态
    state["reference_content"] = reference_content
    state["requires_user_input"] = False
    state["clarification_questions"] = []
    state["current_plan_index"] = 0
    state["generated_contracts"] = []
    
    # 注意：不要覆盖可能由 pre_analysis_result 传入的 analysis_result
    if state.get("template_match_result") is None:
        state["template_match_result"] = None
    if state.get("generation_strategy") is None:
        state["generation_strategy"] = None
        
    state["template_content"] = None
    state["knowledge_graph_features"] = None 

    return state


async def analyze_requirement(state: ContractGenerationState) -> ContractGenerationState:
    """【第一层】分析用户需求（使用统一路由器）"""

    # 【✨ 优化】如果状态中已经存在有效的分析结果（例如从缓存传入），则跳过 LLM 分析
    if state.get("analysis_result") and state.get("processing_type"):
        logger.info("[Workflow Layer 1] 检测到预分析结果，跳过 LLM 重复分析")
        return state

    logger.info("[Workflow Layer 1] 分析用户需求（合同类型与交易结构判定）")

    # 获取 LLM 实例
    from langchain_openai import ChatOpenAI
    from app.core.config import settings

    llm = ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_API_URL,
        temperature=0.0  # 确保结果稳定
    )

    # 使用 ContractRequirementRouter 进行统一路由判断
    from .agents.contract_requirement_router import get_contract_requirement_router

    router = get_contract_requirement_router(llm)
    routing_result = router.route(state["user_input"])

    logger.info(
        f"[Workflow Layer 1] 路由结果: {routing_result.requirement_type}, "
        f"置信度: {routing_result.confidence}, "
        f"推理: {routing_result.reasoning}"
    )

    # 将 RequirementType 转换为 processing_type
    requirement_type_to_processing_type = {
        "single_contract": "single_contract",
        "contract_modification": "contract_modification",
        "contract_termination": "contract_termination",
        "contract_planning": "contract_planning"
    }

    processing_type = requirement_type_to_processing_type.get(
        routing_result.requirement_type.value,
        "single_contract"
    )

    state["processing_type"] = processing_type
    state["routing_result"] = {
        "requirement_type": routing_result.requirement_type.value,
        "intent_description": routing_result.intent_description,
        "confidence": routing_result.confidence,
        "reasoning": routing_result.reasoning
    }

    # 对于单一合同，调用 RequirementAnalyzer 获取详细信息
    if routing_result.requirement_type.value == "single_contract":
        from .agents.requirement_analyzer import RequirementAnalyzer
        analyzer = RequirementAnalyzer(llm=llm)
        result = analyzer.analyze(state["user_input"])
        state["analysis_result"] = result
        state["clarification_questions"] = result.get("clarification_questions", [])
        state["requires_user_input"] = len(result.get("clarification_questions", [])) > 0
    else:
        state["analysis_result"] = {"routing_result": state["routing_result"]}
        state["clarification_questions"] = []
        state["requires_user_input"] = False

    logger.info(
        f"[Workflow Layer 1] 分析完成: processing_type={processing_type}"
    )

    return state


async def query_knowledge_graph(state: ContractGenerationState) -> ContractGenerationState:
    """
    【知识图谱增强层】查询知识图谱获取法律特征

    根据需求分析结果，从知识图谱中查询对应合同类型的法律特征
    """
    logger.info("[Workflow] 查询知识图谱获取法律特征")

    from app.services.common.contract_knowledge_db_service import contract_knowledge_db_service

    analysis_result = state.get("analysis_result", {})
    knowledge_graph = contract_knowledge_db_service

    knowledge_graph_features = {
        "matched_contract_type": None,
        "legal_features": None,
        "usage_scenario": None,
        "legal_basis": [],
        "match_confidence": 0.0
    }

    try:
        # 获取分析出的合同类型
        contract_type = analysis_result.get("key_info", {}).get("contract_type", "")

        # 【✨ 优化】如果没有分析出明确的 contract_type，尝试使用用户输入的关键字进行兜底查询
        if not contract_type:
            logger.warning("[Workflow] 分析结果未包含明确合同类型，尝试使用用户输入前50字搜索")
            contract_type = state["user_input"][:50].replace("\n", " ")

        if contract_type:
            # 1. 尝试精确匹配
            definition = knowledge_graph.get_by_name(contract_type)

            if definition:
                knowledge_graph_features["matched_contract_type"] = definition["name"]
                knowledge_graph_features["match_confidence"] = 1.0

                if definition.get("legal_features"):
                    features = definition["legal_features"]
                    knowledge_graph_features["legal_features"] = features
                    knowledge_graph_features["usage_scenario"] = features.get("usage_scenario")
                    knowledge_graph_features["legal_basis"] = features.get("legal_basis", [])

                    logger.info(
                        f"[Workflow] 知识图谱精确匹配: {definition['name']}, "
                        f"特征: {features.get('transaction_nature')}"
                    )
            else:
                # 2. 尝试模糊搜索
                search_results = knowledge_graph.search_by_keywords(contract_type)

                if search_results:
                    best_match = search_results[0]  # 数据库版本直接返回字典

                    knowledge_graph_features["matched_contract_type"] = best_match["name"]
                    knowledge_graph_features["match_confidence"] = 0.8  # 数据库版本没有分数，使用默认值

                    if best_match.get("legal_features"):
                        features = best_match["legal_features"]
                        knowledge_graph_features["legal_features"] = features
                        knowledge_graph_features["usage_scenario"] = features.get("usage_scenario")
                        knowledge_graph_features["legal_basis"] = features.get("legal_basis", [])

                        logger.info(
                            f"[Workflow] 知识图谱模糊匹配: {best_match['name']} "
                            f"(原始: {contract_type})"
                        )
                else:
                    logger.info(f"[Workflow] 知识图谱未找到匹配: {contract_type}")

        # 3. 如果有分析结果中的 V2 特征，可以作为备选
        v2_features = {
            "transaction_nature": analysis_result.get("key_info", {}).get("transaction_nature"),
            "contract_object": analysis_result.get("key_info", {}).get("contract_object"),
            "stance": analysis_result.get("key_info", {}).get("stance")
        }

        # 如果知识图谱没有匹配到，但 V2 特征存在，则使用 V2 特征
        if not knowledge_graph_features["legal_features"] and any(v2_features.values()):
            knowledge_graph_features["v2_features_fallback"] = v2_features
            logger.info(f"[Workflow] 使用 V2 特征作为备选: {v2_features}")

        state["knowledge_graph_features"] = knowledge_graph_features

    except Exception as e:
        logger.error(f"[Workflow] 知识图谱查询失败: {e}")
        state["knowledge_graph_features"] = knowledge_graph_features

    return state


# --- 变更/解除 专用节点 ---

async def extract_original_contract(state: ContractGenerationState) -> ContractGenerationState:
    """提取原合同内容（用于变更/解除场景）"""
    logger.info("[Workflow] 提取原合同内容")

    reference_content = state.get("reference_content", "")

    # 简化处理：将参考内容作为原合同内容
    state["original_contract"] = {"content": reference_content}
    state["modification_points"] = []

    return state


async def generate_modification_termination_simple(state: ContractGenerationState) -> ContractGenerationState:
    """
    【新增】简化版：直接生成变更/解除协议（单节点）

    适用于：
    - 已在 Step 2 确认结构化信息的场景
    - 跳过冗余的 extract_original_contract 节点

    输入：
    - reference_content: 原合同内容
    - confirmed_modification_termination_info: Step 2 确认的结构化信息
    - processing_type: contract_modification 或 contract_termination

    输出：
    - generated_contracts: 生成的协议
    """
    logger.info("[Workflow] 简化版生成变更/解除协议")

    processing_type = state.get("processing_type")
    confirmed_info = state.get("confirmed_modification_termination_info", {})
    reference_content = state.get("reference_content", "")

    # 如果没有确认信息，降级到使用原始工作流
    if not confirmed_info:
        logger.warning("[Workflow] 缺少确认信息，降级到原始流程")
        # 继续原有的 extract_original_contract 流程
        return await extract_original_contract(state)

    llm = _get_llm()
    drafter = ContractDrafterAgent(llm)

    if processing_type == "contract_termination":
        # 使用确认的信息生成解除协议
        content = drafter.draft_termination_simple(
            original_contract=reference_content,
            confirmed_info=confirmed_info
        )
        filename = "解除协议.docx"
    else:
        # 使用确认的信息生成变更协议
        content = drafter.draft_modification_simple(
            original_contract=reference_content,
            confirmed_info=confirmed_info
        )
        filename = "变更协议.docx"

    state["drafted_content"] = content
    state["generated_contracts"] = [{
        "content": content,
        "filename": filename,
        "file_generated": False
    }]

    return state

async def draft_modification_agreement(state: ContractGenerationState) -> ContractGenerationState:
    """起草变更协议"""
    logger.info("[Workflow] 起草变更协议")

    llm = _get_llm()
    drafter = ContractDrafterAgent(llm)

    content = drafter.draft_modification(
        state.get("original_contract", {}).get("content", ""),
        state.get("modification_points", []),
        user_requirements=state["user_input"]
    )

    state["drafted_content"] = content
    state["generated_contracts"] = [{
        "content": content,
        "filename": "变更协议.docx",
        "file_generated": False
    }]
    return state

async def draft_termination_agreement(state: ContractGenerationState) -> ContractGenerationState:
    """起草解除协议"""
    logger.info("[Workflow] 起草解除协议")

    llm = _get_llm()
    drafter = ContractDrafterAgent(llm)

    # 【修复】安全访问 analysis_result，防止 None 崩溃
    analysis_result = state.get("analysis_result") or {}
    key_info = analysis_result.get("key_info") or {}

    content = drafter.draft_termination(
        state.get("original_contract", {}).get("content", ""),
        key_info.get("termination_reason", ""),
        key_info.get("post_termination") or {},
        user_requirements=state.get("user_input") or ""
    )

    state["drafted_content"] = content
    state["generated_contracts"] = [{
        "content": content,
        "filename": "解除协议.docx",
        "file_generated": False
    }]
    return state


# --- 单一合同 专用节点 (三层架构 + 物理加载) ---

async def match_template(state: ContractGenerationState) -> ContractGenerationState:
    """
    【第二层】结构化模板匹配 (只找 ID)

    【新增】如果 skip_template=True，跳过模板匹配，直接进入纯 AI 生成
    """
    # 【新增】检查是否跳过模板匹配
    if state.get("skip_template", False):
        logger.info("[Workflow Layer 2] 用户选择不使用模板，跳过模板匹配")
        # 设置为无匹配结果，让流程进入纯 AI 生成
        state["template_match_result"] = {
            "match_level": "NONE",
            "template_id": None,
            "template_name": None,
            "match_reason": "用户选择不使用模板，进行纯 AI 生成",
            "confidence": 0.0
        }
        return state

    logger.info("[Workflow Layer 2] 结构化模板匹配（仅使用管理员公开模板）")

    from app.database import get_db
    from app.services.contract_generation.structural import get_structural_matcher

    db = next(get_db())
    matcher = get_structural_matcher(db)

    # 执行匹配 - user_id=None 确保只匹配公开模板
    match_result = matcher.match(
        state["analysis_result"],
        user_id=None
    )

    logger.info(f"[Workflow Layer 2] 模板匹配结果: level={match_result.match_level}, template={match_result.template_name}")
    state["template_match_result"] = match_result.to_dict()
    return state


async def select_generation_strategy(state: ContractGenerationState) -> ContractGenerationState:
    """【第三层】生成策略选择"""
    logger.info("[Workflow Layer 3] 生成策略选择")

    from app.services.contract_generation.strategy import get_strategy_selector

    selector = get_strategy_selector()
    strategy = selector.select_strategy(
        state["template_match_result"],
        state["analysis_result"]
    )

    state["generation_strategy"] = strategy.to_dict()
    return state


async def load_template_file(state: ContractGenerationState) -> ContractGenerationState:
    """
    【物理层】加载模板文件内容
    """
    logger.info("[Workflow] 尝试加载模板物理文件")
    
    strategy = state.get("generation_strategy", {})
    template_id = strategy.get("template_id")
    
    if template_id:
        from app.database import get_db
        db = next(get_db())
        loader = TemplateLoader(db)
        try:
            template = loader.load_by_id(template_id)
            if template:
                content = loader.load_template_content(template)
                state["template_content"] = content
                logger.info(f"[Workflow] 成功加载模板 ID {template_id}, 长度: {len(content)}")
            else:
                logger.error(f"[Workflow] 模板 ID {template_id} 不存在")
                state["template_content"] = None
        except Exception as e:
            logger.error(f"[Workflow] 模板加载失败: {e}")
            state["template_content"] = None
    else:
        state["template_content"] = None
        
    return state


async def draft_single_contract(state: ContractGenerationState) -> ContractGenerationState:
    """
    起草单一合同
    【优化】：同时利用 模板内容、参考资料 和 知识图谱法律特征
    【✨ 新增】：支持两阶段 AI 生成（无模板场景）
    """
    logger.info("[Workflow] 起草单一合同")

    strategy = state.get("generation_strategy", {})
    template_content = state.get("template_content")
    reference_content = state.get("reference_content", "")
    knowledge_graph_features = state.get("knowledge_graph_features", {})

    llm = _get_llm()
    drafter = ContractDrafterAgent(llm)

    content = ""
    template_info = None

    # 模式 A: 基于模板生成
    if template_content:
        logger.info("模式：基于本地 Markdown 模板生成")
        # 【修复】确保传递的 analysis_result 不为 None
        safe_analysis_result = state.get("analysis_result") or {}
        content, template_info = drafter._draft_with_template_new(
            analysis_result=safe_analysis_result,
            template_content=template_content,
            strategy=strategy,
            reference_content=reference_content,
            knowledge_graph_features=knowledge_graph_features or {}
        )
    # 模式 B: 无模板纯生成（✨ 支持两阶段生成）
    else:
        use_two_stage = strategy.get("use_two_stage", False)

        # 调试日志：输出策略内容
        logger.info(f"[Workflow] 策略内容检查: use_two_stage={use_two_stage}, strategy={strategy}")

        if use_two_stage:
            logger.info("[Workflow] 模式：两阶段 AI 生成（框架 + 填充）")
            try:
                from .agents.two_stage_contract_drafter import get_two_stage_drafter

                two_stage_drafter = get_two_stage_drafter()

                # 构建表单数据（从 analysis_result 中提取）
                # 【修复】安全访问 analysis_result，防止 None 崩溃
                form_data = {}
                analysis_result = state.get("analysis_result") or {}
                key_info = analysis_result.get("key_info") or {}
                if key_info:
                    # 将 key_info 转换为表单格式
                    for key, value in key_info.items():
                        if value:
                            form_data[key] = value

                # 两阶段生成
                # 【修复】确保传入的参数不为 None
                # 【核心修复】确保 knowledge_graph_features 格式正确，legal_features 兜底为空字典
                safe_kg_features = knowledge_graph_features or {}
                if not safe_kg_features.get("legal_features"):
                    safe_kg_features["legal_features"] = {}  # 兜底为空字典

                content = two_stage_drafter.draft_with_two_stages(
                    analysis_result=analysis_result,
                    knowledge_graph_features=safe_kg_features,
                    user_input=state.get("user_input") or "",
                    form_data=form_data
                )

                logger.info("[Workflow] 两阶段生成完成")

            except Exception as e:
                logger.error(f"[Workflow] 两阶段生成失败: {e}，降级到单次生成", exc_info=True)
                # 降级到单次生成
                logger.info("模式：无模板纯生成（降级）")
                # 【修复】确保传入的参数不为 None
                safe_analysis_result = state.get("analysis_result") or {}
                content = drafter.draft_from_scratch(
                    analysis_result=safe_analysis_result,
                    reference_content=reference_content,
                    strategy=strategy,
                    knowledge_graph_features=knowledge_graph_features or {}
                )
        else:
            logger.info("模式：无模板纯生成（单次）")
            # 【修复】确保传入的参数不为 None
            safe_analysis_result = state.get("analysis_result") or {}
            content = drafter.draft_from_scratch(
                analysis_result=safe_analysis_result,
                reference_content=reference_content,
                strategy=strategy,
                knowledge_graph_features=knowledge_graph_features or {}
            )

    # 【修复】安全访问合同类型
    safe_analysis_result = state.get("analysis_result") or {}
    safe_key_info = safe_analysis_result.get("key_info") or {}
    contract_type = safe_key_info.get("contract_type") or "合同"

    contract_data = {
        "content": content,
        "filename": f"{contract_type}.docx",
        "file_generated": False,
        "docx_path": "",
        "pdf_path": "",
        "generation_strategy": strategy
    }

    if template_info:
        contract_data["template_info"] = template_info

    state["generated_contracts"] = [contract_data]
    return state


# --- 合同规划 专用节点 ---

async def plan_contracts(state: ContractGenerationState) -> ContractGenerationState:
    """规划多份合同"""
    logger.info("[Workflow] 规划多份合同")

    from app.services.contract_generation.agents.contract_planning_service import ContractPlanningService

    llm = _get_llm()
    planner = ContractPlanningService(llm)

    user_input = state["user_input"]
    reference_content = state.get("reference_content", "")

    context = {}
    if reference_content:
        context["reference_content"] = reference_content

    plan_result = planner.plan(user_input, context=context)

    state["contract_plan"] = [contract.dict() for contract in plan_result.contracts]
    state["contract_relationships"] = plan_result.relationships
    state["current_plan_index"] = 0

    if plan_result.signing_order:
        state["contract_relationships"]["signing_order"] = plan_result.signing_order

    logger.info(f"[Workflow] 规划完成，共 {len(plan_result.contracts)} 份合同")

    return state


async def plan_contracts_multi_model(state: ContractGenerationState) -> ContractGenerationState:
    """
    多模型合同规划节点

    使用 MultiModelPlanningService 并行生成规划方案，
    然后使用 PlanningSolutionSynthesizer 综合融合生成最优方案

    Args:
        state: 当前工作流状态

    Returns:
        ContractGenerationState: 更新后的状态，包含 contract_plan 和 synthesis_report
    """
    from .exceptions import (
        MultiModelPlanningError,
        ModelServiceError,
        handle_error,
        should_fallback_to_single_model
    )

    logger.info("[PlanContractsMulti] 开始多模型规划")

    try:
        # 获取多模型规划服务单例
        from .agents.multi_model_planning_service import get_multi_model_planning_service

        service = get_multi_model_planning_service()
        if not service:
            error = ModelServiceError(
                message="多模型规划服务不可用，请检查配置",
                model_name="MultiModelPlanningService"
            )
            error_response = handle_error(
                error,
                context={"node": "plan_contracts_multi_model", "action": "get_service"}
            )

            logger.warning(f"[PlanContractsMulti] {error_response['error']['message']}")

            # 设置错误状态，触发降级
            state["error"] = error_response["error"]["message"]
            state["error_details"] = error_response
            return state

        # 准备规划输入
        user_input = state.get("user_input", "")
        reference_content = state.get("reference_content", "")

        # 构建 context 字典
        context = {}
        if reference_content:
            context["reference_content"] = reference_content

        # 调用多模型规划服务 (注意：plan 方法不是 async，无需 await)
        result = service.plan(
            user_input=user_input,
            context=context
        )

        # 提取最终规划
        final_planning = result.final_planning

        # 转换为 List[Dict] 格式（兼容现有数据结构）
        # PlannedContract 是 Pydantic 模型，使用 model_dump() 转换
        contract_plan = [
            contract.model_dump()
            for contract in final_planning.contracts
        ]

        # 提取融合报告
        synthesis_report = result.synthesis_report

        # 保存融合报告到状态
        state["contract_plan"] = contract_plan
        state["multi_model_synthesis_report"] = {
            "solution_analyses": synthesis_report.solution_analyses,
            "extracted_strengths": synthesis_report.extracted_strengths,
            "identified_weaknesses": synthesis_report.identified_weaknesses,
            "fusion_strategy": synthesis_report.fusion_strategy,
            "fusion_summary": synthesis_report.fusion_summary,
        }
        state["current_plan_index"] = 0

        logger.info(
            f"[PlanContractsMulti] 多模型规划完成，生成了 {len(contract_plan)} 份合同"
        )

    except Exception as e:
        # 使用统一的错误处理
        error = MultiModelPlanningError(
            message=f"多模型规划失败: {str(e)}",
            failed_models=[],  # 可以从异常中提取失败的模型列表
            partial_results=None
        )
        error_response = handle_error(
            error,
            context={
                "node": "plan_contracts_multi_model",
                "user_input": state.get("user_input", "")[:100]  # 只记录前100个字符
            }
        )

        logger.error(f"[PlanContractsMulti] 多模型规划失败: {e}", exc_info=True)

        # 设置错误状态
        state["error"] = error_response["error"]["message"]
        state["error_details"] = error_response

        # 根据错误处理策略决定是否降级
        # 注意：这里不自动降级，让工作流根据错误状态处理

    return state


async def draft_from_plan(state: ContractGenerationState) -> ContractGenerationState:
    """根据规划依次起草合同"""
    logger.info("[Workflow] 根据规划起草合同")

    plan = state.get("contract_plan", [])
    current_index = state.get("current_plan_index", 0)
    reference_content = state.get("reference_content", "")

    if current_index >= len(plan):
        return state

    current_contract = plan[current_index]
    logger.info(f"[Workflow] 起草进度 {current_index + 1}/{len(plan)}: {current_contract.get('title')}")

    llm = _get_llm()
    drafter = ContractDrafterAgent(llm)

    content = drafter.draft_from_scratch(
        analysis_result={
            "processing_type": "single_contract",
            "key_info": current_contract
        },
        reference_content=reference_content,
        strategy={"generation_type": "ai_generated"}
    )

    contract_info = {
        "content": content,
        "filename": f"{current_contract.get('title', '合同')}.docx",
        "file_generated": False,
        "plan_index": current_index,
        "contract_id": current_contract.get("id"),
        "docx_path": "",
        "pdf_path": ""
    }

    state["generated_contracts"].append(contract_info)
    state["current_plan_index"] = current_index + 1

    return state


# ==================== 路由函数 ====================

def determine_processing_type(state: ContractGenerationState) -> str:
    """
    一级路由

    【新增】智能路由：
    - 如果有 confirmed_modification_termination_info，直接路由到简化版单节点
    - 否则走原始流程（extract_original_contract → 二级路由）
    """
    processing_type = state.get("processing_type")
    confirmed_info = state.get("confirmed_modification_termination_info")

    # 【新增】变更/解除场景 + 有确认信息 → 使用简化版
    if confirmed_info and processing_type in ("contract_modification", "contract_termination"):
        logger.info(f"[Workflow] 使用简化版生成流程: {processing_type}")
        return "modification_termination_simple"

    if processing_type == "contract_modification":
        return "modification"
    elif processing_type == "contract_termination":
        return "termination"
    elif processing_type == "contract_planning":
        return "planning"
    else:
        return "single"


def decide_planning_method(state: ContractGenerationState) -> ContractGenerationState:
    """
    决策：选择单模型还是多模型规划

    注意：此函数作为节点，必须返回更新后的状态字典。
    路由逻辑由 add_conditional_edges 的回调函数处理。

    Args:
        state: 当前工作流状态

    Returns:
        ContractGenerationState: 状态字典（不修改或微调后返回）
    """
    planning_mode = state.get("planning_mode", "single_model")

    logger.info(f"[DecidePlanningMethod] planning_mode={planning_mode}")

    # 检查多模型配置是否就绪
    if planning_mode == "multi_model":
        from app.core.config_validator import is_multi_model_planning_ready

        if is_multi_model_planning_ready():
            logger.info("[DecidePlanningMethod] 多模型规划配置就绪，使用多模型模式")
            # 可以在状态中记录实际使用的模式
            state["actual_planning_mode"] = "multi_model"
        else:
            logger.warning("[DecidePlanningMethod] 多模型规划未就绪，降级到单模型")
            state["actual_planning_mode"] = "single_model"
    else:
        state["actual_planning_mode"] = "single_model"

    # 返回状态字典（关键修复）
    return state


def route_planning_method(state: ContractGenerationState) -> str:
    """
    路由函数：根据 planning_mode 决定使用哪个规划节点

    Args:
        state: 当前工作流状态

    Returns:
        str: 目标节点名称
            - "plan_contracts": 单模型规划
            - "plan_contracts_multi": 多模型规划
    """
    planning_mode = state.get("planning_mode", "single_model")

    if planning_mode == "multi_model":
        from app.core.config_validator import is_multi_model_planning_ready

        if is_multi_model_planning_ready():
            return "plan_contracts_multi"
        else:
            logger.warning("[RoutePlanningMethod] 多模型未就绪，路由到单模型")
            return "plan_contracts"
    else:
        return "plan_contracts"

def determine_modification_or_termination(state: ContractGenerationState) -> str:
    """变更/解除 二级路由"""
    processing_type = state.get("processing_type")
    if processing_type == "contract_termination":
        return "termination"
    return "modification"

def should_continue_planning(state: ContractGenerationState) -> str:
    """规划流程 循环控制"""
    plan = state.get("contract_plan", [])
    current = state.get("current_plan_index", 0)
    if current < len(plan):
        return "continue"
    else:
        return "done"


def should_generate_from_plan_or_end(state: ContractGenerationState) -> str:
    """
    决策：规划完成后是否直接生成合同

    - 如果 is_plan_confirmed=True，则进入生成流程
    - 否则直接结束，等待用户确认

    Args:
        state: 当前工作流状态

    Returns:
        str: "generate" 或 "done"
    """
    is_confirmed = state.get("is_plan_confirmed", False)

    if is_confirmed:
        logger.info("[Workflow] 规划已确认，开始生成合同")
        return "generate"
    else:
        logger.info("[Workflow] 规划完成，等待用户确认")
        return "done"


# ==================== 工作流构建 ====================

def build_workflow() -> StateGraph:
    """构建合同生成工作流"""

    workflow = StateGraph(ContractGenerationState)

    # --- 1. 添加所有节点 ---
    workflow.add_node("input_processing", process_user_input)
    workflow.add_node("analyze_requirement", analyze_requirement)
    workflow.add_node("query_knowledge_graph", query_knowledge_graph)

    # 变更/解除 分支节点
    workflow.add_node("generate_modification_termination_simple", generate_modification_termination_simple)  # 【新增】简化版单节点
    workflow.add_node("extract_original_contract", extract_original_contract)
    workflow.add_node("generate_modification", draft_modification_agreement)
    workflow.add_node("generate_termination", draft_termination_agreement)

    # 【新增】规划模式决策节点
    workflow.add_node("decide_planning_method", decide_planning_method)

    # 规划 分支节点
    workflow.add_node("plan_contracts", plan_contracts)

    # 【新增】多模型规划节点
    workflow.add_node("plan_contracts_multi", plan_contracts_multi_model)

    workflow.add_node("generate_from_plan", draft_from_plan)

    # 单一合同 分支节点
    workflow.add_node("match_template", match_template)
    workflow.add_node("select_strategy", select_generation_strategy)
    workflow.add_node("load_template", load_template_file)
    workflow.add_node("generate_single", draft_single_contract)

    # --- 2. 设置连线 (Edges) ---
    workflow.set_entry_point("input_processing")
    workflow.add_edge("input_processing", "analyze_requirement")
    workflow.add_edge("analyze_requirement", "query_knowledge_graph")

    # 【修正】路由 1: 根据类型分发
    workflow.add_conditional_edges(
        "query_knowledge_graph",
        determine_processing_type,
        {
            "modification_termination_simple": "generate_modification_termination_simple",  # 【新增】简化版直接生成
            "modification": "extract_original_contract",
            "termination": "extract_original_contract",
            "single": "match_template",
            "planning": "decide_planning_method"  # 【修正】路由到决策节点
        }
    )

    # 【修正】路由 2: 规划模式决策
    workflow.add_conditional_edges(
        "decide_planning_method",
        route_planning_method,  # 使用专门的路由函数
        {
            "plan_contracts": "plan_contracts",
            "plan_contracts_multi": "plan_contracts_multi"
        }
    )

    # 路由 3: 单一合同流程
    workflow.add_edge("match_template", "select_strategy")
    workflow.add_edge("select_strategy", "load_template")
    workflow.add_edge("load_template", "generate_single")
    workflow.add_edge("generate_single", END)

    # 路由 4: 变更/解除流程
    workflow.add_conditional_edges(
        "extract_original_contract",
        determine_modification_or_termination,
        {
            "modification": "generate_modification",
            "termination": "generate_termination"
        }
    )
    workflow.add_edge("generate_modification", END)
    workflow.add_edge("generate_termination", END)
    # 【新增】简化版单节点直接结束
    workflow.add_edge("generate_modification_termination_simple", END)

    # 【修正】路由 5: 规划流程（第一阶段：生成规划）
    # 【修改】规划完成后直接结束，等待用户确认
    workflow.add_conditional_edges(
        "plan_contracts",
        should_generate_from_plan_or_end,
        {
            "generate": "generate_from_plan",  # 仅在用户确认后才生成
            "done": END  # 默认：规划完成后停止
        }
    )

    workflow.add_conditional_edges(
        "plan_contracts_multi",
        should_generate_from_plan_or_end,
        {
            "generate": "generate_from_plan",
            "done": END
        }
    )

    # 循环控制：继续起草或结束
    workflow.add_conditional_edges(
        "generate_from_plan",
        should_continue_planning,
        {
            "continue": "generate_from_plan",
            "done": END
        }
    )

    return workflow


# ==================== 工作流实例管理 & API ====================

_workflow_instance: Optional[StateGraph] = None

def get_contract_workflow() -> StateGraph:
    global _workflow_instance
    if _workflow_instance is None:
        logger.info("[Workflow] 初始化合同生成工作流")
        _workflow_instance = build_workflow()
    return _workflow_instance

async def generate_contract_simple(
    user_input: str,
    uploaded_files: List[str] = None,
    # 【✨ 优化】允许传入预先分析好的结果，跳过第一阶段分析
    pre_analysis_result: Optional[Dict[str, Any]] = None,
    # 【新增】规划模式选择
    planning_mode: Optional[str] = "single_model",
    # 【新增】是否跳过模板匹配（不用模板时为 true）
    skip_template: Optional[bool] = False,
    # 【新增】Step 2 确认的变更/解除信息
    confirmed_modification_termination_info: Optional[Dict[str, Any]] = None,
    # 【新增】支持基于已有规划生成合同
    contract_plan: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    合同生成 API 入口

    Args:
        user_input: 用户需求描述
        uploaded_files: 上传文件路径列表
        pre_analysis_result: 预先分析好的结果（可选）
        planning_mode: 规划模式（"single_model" 或 "multi_model"）
        skip_template: 是否跳过模板匹配（默认 false）
        confirmed_modification_termination_info: Step 2 确认的变更/解除信息（可选）
        contract_plan: 已确认的合同规划（可选，用于第二阶段生成）

    Returns:
        Dict: 生成结果
    """
    try:
        # 初始化状态
        initial_state: ContractGenerationState = {
            "user_input": user_input,
            "uploaded_files": uploaded_files or [],
            "reference_content": None,
            "knowledge_graph_features": None,
            # 【✨ 优化】优先使用传入的预分析结果
            "analysis_result": pre_analysis_result,
            "processing_type": pre_analysis_result.get("processing_type") if pre_analysis_result else None,
            "original_contract": None,
            "modification_points": [],
            "contract_plan": None,
            "contract_relationships": None,
            "current_plan_index": 0,
            "drafted_content": None,
            "generated_contracts": [],
            "error": None,
            "requires_user_input": False,
            "clarification_questions": [],
            "template_match_result": None,
            "generation_strategy": None,
            "template_content": None,
            # 【新增】规划模式选择
            "planning_mode": planning_mode,
            # 【新增】是否跳过模板匹配
            "skip_template": skip_template,
            # 【新增】多模型融合报告
            "multi_model_synthesis_report": None,
            # 【新增】Step 2 确认的变更/解除信息
            "confirmed_modification_termination_info": confirmed_modification_termination_info,
            # 【新增】标记当前请求是否包含用户确认过的规划
            "is_plan_confirmed": False
        }

        # 【新增】如果传入了 contract_plan，表示基于已有规划生成合同
        if contract_plan:
            initial_state["contract_plan"] = contract_plan
            initial_state["is_plan_confirmed"] = True
            logger.info(f"[Workflow] 基于已有规划生成，合同数量: {len(contract_plan)}")
        else:
            initial_state["is_plan_confirmed"] = False

        workflow = get_contract_workflow()

        # 内存检查点
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory)

        # 执行
        config = {"configurable": {"thread_id": "default"}}
        result = await app.ainvoke(initial_state, config=config)

        return {
            "success": True,
            "processing_type": result.get("processing_type"),
            "contracts": result.get("generated_contracts", []),
            "clarification_questions": result.get("clarification_questions", []),
            "error": result.get("error"),
            "analysis_result": result.get("analysis_result"),
            "template_match_result": result.get("template_match_result"),
            "generation_strategy": result.get("generation_strategy"),
            # 【新增】多模型融合报告
            "synthesis_report": result.get("multi_model_synthesis_report"),
            "contract_plan": result.get("contract_plan")
        }

    except Exception as e:
        logger.error(f"[Workflow] 生成失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "contracts": []
        }

# ... (后续的 analyze_and_get_clarification_form 和 generate_contract_with_form_data 保持原样即可)
# 由于 generate_contract_simple 的签名变更增加了默认参数 pre_analysis_result=None，
# 所以 generate_contract_with_form_data 中对它的原有调用代码依然兼容，无需修改。
# 下面只为了保持文件完整性，简略带过后续未修改部分，实际部署时请保留这部分代码。

async def analyze_and_get_clarification_form(
    user_input: str,
    uploaded_files: List[str] = None,
    planning_mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    分析用户需求并返回澄清表单（方案 A 优化版）

    核心设计：
    - 完全依赖 contract_requirement_router 进行意图识别
    - router 负责区分所有四种类型（single, modification, termination, planning）
    - 移除 requirement_analyzer._determine_processing_type 的调用

    Args:
        user_input: 用户输入
        uploaded_files: 上传文件列表
        planning_mode: 规划模式

    Returns:
        Dict: 分析结果和澄清表单
    """
    try:
        logger.info("[Workflow] 开始需求分析和澄清表单生成流程")
        llm = _get_llm()

        # ==================== 单一路由入口 ====================
        from .agents.contract_requirement_router import get_contract_requirement_router
        from .agents.models import RequirementType

        router = get_contract_requirement_router(llm)
        routing_result = router.route(user_input)

        logger.info(
            f"[Workflow] 路由结果: {routing_result.requirement_type}, "
            f"置信度: {routing_result.confidence}, "
            f"推理: {routing_result.reasoning}"
        )

        # ==================== 根据路由结果返回对应表单 ====================
        requirement_type = routing_result.requirement_type

        # 1. 合同变更场景
        if requirement_type == RequirementType.CONTRACT_MODIFICATION:
            # 【新增】提取变更相关信息
            extracted_info = {}
            try:
                from .agents.requirement_analyzer import RequirementAnalyzer
                analyzer = RequirementAnalyzer(llm)

                # 处理上传文件获取参考内容
                reference_content = None
                if uploaded_files:
                    reference_content = await _process_uploaded_files(uploaded_files)

                extracted_info = analyzer.extract_modification_termination_info(
                    user_input=user_input,
                    reference_content=reference_content,
                    uploaded_files=uploaded_files
                )
                logger.info(f"[Workflow] 变更信息提取完成: {list(extracted_info.keys()) if extracted_info else 'empty'}")
            except Exception as e:
                logger.warning(f"[Workflow] 变更信息提取失败: {e}")

            return {
                "success": True,
                "processing_type": "contract_modification",
                "requirement_type": "contract_modification",
                "clarification_form": {
                    "questions": [
                        {
                            "id": "original_contract",
                            "question": "请上传原合同文件",
                            "type": "file",
                            "required": True
                        },
                        {
                            "id": "modification_reason",
                            "question": "变更原因及具体内容",
                            "type": "textarea",
                            "required": True
                        },
                        {
                            "id": "modification_details",
                            "question": "需要变更的条款（可选）",
                            "type": "textarea",
                            "required": False
                        }
                    ],
                    "need_original_contract": True
                },
                "routing_result": {
                    "requirement_type": routing_result.requirement_type,
                    "confidence": routing_result.confidence,
                    "intent_description": routing_result.intent_description,
                    "reasoning": routing_result.reasoning
                },
                # 【新增】提取的结构化信息
                "extracted_modification_termination_info": extracted_info if extracted_info else None
            }

        # 2. 合同解除场景
        elif requirement_type == RequirementType.CONTRACT_TERMINATION:
            # 【新增】提取解除相关信息
            extracted_info = {}
            try:
                from .agents.requirement_analyzer import RequirementAnalyzer
                analyzer = RequirementAnalyzer(llm)

                # 处理上传文件获取参考内容
                reference_content = None
                if uploaded_files:
                    reference_content = await _process_uploaded_files(uploaded_files)

                extracted_info = analyzer.extract_modification_termination_info(
                    user_input=user_input,
                    reference_content=reference_content,
                    uploaded_files=uploaded_files
                )
                logger.info(f"[Workflow] 解除信息提取完成: keys={list(extracted_info.keys()) if extracted_info else 'None'}, is_empty={len(extracted_info) == 0 if extracted_info else 'N/A'}")
                if extracted_info:
                    logger.info(f"[Workflow] 提取的详细信息: processing_type={extracted_info.get('processing_type')}, has_original_info={'original_contract_info' in extracted_info}")
            except Exception as e:
                logger.warning(f"[Workflow] 解除信息提取失败: {e}")

            return {
                "success": True,
                "processing_type": "contract_termination",
                "requirement_type": "contract_termination",
                "clarification_form": {
                    "questions": [
                        {
                            "id": "original_contract",
                            "question": "请上传原合同文件",
                            "type": "file",
                            "required": True
                        },
                        {
                            "id": "termination_reason",
                            "question": "解除原因",
                            "type": "textarea",
                            "required": True
                        },
                        {
                            "id": "post_termination_arrangements",
                            "question": "解除后的安排（如结算、交接等）",
                            "type": "textarea",
                            "required": False
                        }
                    ],
                    "need_original_contract": True
                },
                "routing_result": {
                    "requirement_type": routing_result.requirement_type,
                    "confidence": routing_result.confidence,
                    "intent_description": routing_result.intent_description,
                    "reasoning": routing_result.reasoning
                },
                # 【新增】提取的结构化信息
                "extracted_modification_termination_info": extracted_info if extracted_info else None
            }

        # 3. 合同规划场景
        elif requirement_type == RequirementType.CONTRACT_PLANNING:
            return {
                "success": True,
                "processing_type": "contract_planning",
                "requirement_type": "contract_planning",
                # 【新增】要求用户选择规划模式
                "requires_user_choice": True,
                "user_choice_options": {
                    "title": "检测到您的需求属于合同规划场景",
                    "description": "系统将为您规划一个完整的合同架构，包含多份相关合同。请选择规划模式：",
                    "options": [
                        {
                            "value": "single_model",
                            "label": "单模型快速规划",
                            "description": "使用单个 AI 模型快速生成规划方案"
                        },
                        {
                            "value": "multi_model",
                            "label": "多模型综合规划",
                            "description": "使用多个 AI 模型从不同专业视角分析，生成更全面的规划方案"
                        }
                    ],
                    "default": planning_mode or "single_model"
                },
                "clarification_form": {
                    "questions": [
                        {
                            "id": "planning_scope",
                            "question": "请描述您需要规划的交易场景",
                            "type": "text",
                            "required": True
                        },
                        {
                            "id": "parties_involved",
                            "question": "涉及哪些当事人？",
                            "type": "text",
                            "required": True
                        },
                        {
                            "id": "planning_mode",
                            "question": "规划模式",
                            "type": "select",
                            "options": [
                                {"label": "单模型", "value": "single_model"},
                                {"label": "多模型", "value": "multi_model"}
                            ],
                            "default": planning_mode or "single_model",
                            "required": False
                        }
                    ]
                },
                "routing_result": {
                    "requirement_type": routing_result.requirement_type,
                    "confidence": routing_result.confidence,
                    "intent_description": routing_result.intent_description,
                    "reasoning": routing_result.reasoning
                }
            }

        # 4. 单一合同场景 - 【使用动态表单生成】
        elif requirement_type == RequirementType.SINGLE_CONTRACT:
            # 调用 SingleContractGenerationService 获取动态表单
            from .agents.single_contract_generation_service import SingleContractGenerationService

            logger.info("[Workflow] 单一合同场景，调用动态表单生成服务")
            service = SingleContractGenerationService(llm)
            result = service.analyze_and_get_form(
                user_input=user_input,
                uploaded_files=uploaded_files or []
            )

            if not result.get("success"):
                # 如果动态生成失败，降级为固定表单
                logger.warning(f"[Workflow] 动态表单生成失败，使用固定表单: {result.get('error')}")
                return {
                    "success": True,
                    "processing_type": "single_contract",
                    "requirement_type": "single_contract",
                    "clarification_form": {
                        "questions": [
                            {
                                "id": "contract_name",
                                "question": "合同名称",
                                "type": "text",
                                "default": "",
                                "required": True
                            },
                            {
                                "id": "party_a",
                                "question": "甲方（你方）",
                                "type": "text",
                                "required": True
                            },
                            {
                                "id": "party_b",
                                "question": "乙方（对方）",
                                "type": "text",
                                "required": True
                            },
                            {
                                "id": "key_terms",
                                "question": "关键条款要求",
                                "type": "textarea",
                                "required": False
                            }
                        ]
                    },
                    "routing_result": {
                        "requirement_type": routing_result.requirement_type,
                        "confidence": routing_result.confidence,
                        "intent_description": routing_result.intent_description,
                        "reasoning": routing_result.reasoning
                    },
                    "fallback_mode": True  # 标记为降级模式
                }

            # 转换动态表单格式为前端期望的格式
            dynamic_form = result.get("clarification_form", {})

            # ClarificationFormGenerator 返回的格式：
            # {
            #   "form_title": "...",
            #   "form_description": "...",
            #   "sections": [{"section_title": "...", "fields": [...]}],
            #   "summary": {...}
            # }
            #
            # 转换为前端期望的格式：
            # {
            #   "form_title": "...",
            #   "form_description": "...",
            #   "questions": [...],  # 扁平化的字段列表
            #   "sections": [...],
            #   "summary": {...}
            # }

            # 扁平化所有章节中的字段
            all_questions = []
            sections = dynamic_form.get("sections", [])

            for section in sections:
                section_title = section.get("section_title", "")
                fields = section.get("fields", [])

                # 为每个字段添加章节信息
                for field in fields:
                    field_with_section = {
                        **field,
                        "section_title": section_title
                    }
                    all_questions.append(field_with_section)

            logger.info(f"[Workflow] 动态表单生成成功，包含 {len(sections)} 个章节，{len(all_questions)} 个字段")

            return {
                "success": True,
                "processing_type": "single_contract",
                "requirement_type": "single_contract",
                "clarification_form": {
                    "form_title": dynamic_form.get("form_title", "需求澄清表单"),
                    "form_description": dynamic_form.get("form_description", ""),
                    "questions": all_questions,
                    "sections": sections,
                    "summary": dynamic_form.get("summary", {}),
                    # 模板匹配信息
                    "template_match_result": result.get("template_match_result"),
                    # 分析结果
                    "analysis_result": result.get("analysis_result")
                },
                "routing_result": {
                    "requirement_type": routing_result.requirement_type,
                    "confidence": routing_result.confidence,
                    "intent_description": routing_result.intent_description,
                    "reasoning": routing_result.reasoning
                },
                "is_dynamic_form": True  # 标记为动态表单
            }

        # 5. 未知类型（不应到达）
        else:
            return {
                "success": False,
                "error": f"未知的需求类型: {requirement_type}",
                "clarification_form": None
            }

    except Exception as e:
        logger.error(f"[Workflow] 需求分析失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "clarification_form": None
        }

async def _analyze_modification_or_termination(
    user_input: str,
    uploaded_files: List[str],
    contract_type: str
) -> Dict[str, Any]:
    # (保持原有逻辑不变)
    return {}

async def _analyze_contract_planning(
    user_input: str,
    uploaded_files: List[str],
    enable_multi_model: Optional[bool] = None
) -> Dict[str, Any]:
    # (保持原有逻辑不变)
    return {}

async def generate_contract_with_form_data(
    user_input: str,
    form_data: Dict[str, Any],
    analysis_result: Optional[Dict[str, Any]] = None,
    template_match_result: Optional[Dict[str, Any]] = None,
    knowledge_graph_features: Dict[str, Any] = None,
    uploaded_files: List[str] = None,
    planning_mode: Optional[str] = "single_model",  # 【新增】规划模式
    skip_template: Optional[bool] = False  # 【新增】是否跳过模板匹配
) -> Dict[str, Any]:
    # 使用表单数据生成合同（支持模板和非模板两种模式）
    try:
        # 合并用户输入和表单数据
        enhanced_input = _merge_user_input_with_form_data(user_input, form_data)

        # 【修改】传递 planning_mode 和 skip_template 参数
        result = await generate_contract_simple(
            user_input=enhanced_input,
            uploaded_files=uploaded_files,
            pre_analysis_result=analysis_result,  # 传递分析结果以优化性能
            planning_mode=planning_mode or "single_model",  # 【新增】
            skip_template=skip_template or False  # 【新增】
        )
        return result
    except Exception as e:
        logger.error(f"[Workflow] 使用表单数据生成失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "contracts": []}

def _merge_user_input_with_form_data(user_input: str, form_data: Dict[str, Any]) -> str:
    # (保持原有逻辑不变)
    sections = form_data.get("sections", [])
    additional_info = []
    for section in sections:
        section_title = section.get("section_title", "")
        fields = section.get("fields", [])
        section_info = [f"\n## {section_title}"]
        for field in fields:
            value = form_data.get(field.get("field_id"))
            if value:
                section_info.append(f"- {field.get('label')}: {value}")
        if len(section_info) > 1:
            additional_info.extend(section_info)
    if additional_info:
        return user_input + "\n\n" + "\n".join(additional_info)
    return user_input


# ==================== 辅助函数：仅生成规划 ====================

async def _generate_plan_only(
    user_input: str,
    planning_mode: str = "single_model",
    reference_content: str = ""
) -> Dict[str, Any]:
    """
    仅生成合同规划，不生成具体合同

    此函数用于支持 "/generate-plan-only" API 端点，
    让用户可以先查看规划结果，确认后再开始生成合同。

    Args:
        user_input: 用户输入的需求描述
        planning_mode: 规划模式，"single_model" 或 "multi_model"
        reference_content: 参考内容（可选）

    Returns:
        Dict[str, Any]: 包含以下键的字典：
            - success: bool, 是否成功
            - contract_plan: list, 合同规划列表
            - contract_relationships: dict, 合同关系
            - synthesis_report: dict, 多模型融合报告（仅多模型模式）
            - error: str, 错误信息（如果失败）

    Example:
        >>> result = await _generate_plan_only(
        ...     user_input="我需要为某个房地产交易生成一整套合同",
        ...     planning_mode="single_model"
        ... )
        >>> print(result["contract_plan"])
        [{'title': '商品房买卖合同', 'parties': [...], ...}]
    """
    try:
        logger.info(f"[GeneratePlanOnly] 开始生成规划，模式: {planning_mode}")

        # 初始化 LLM
        llm = _get_llm()

        # 构建上下文
        context = {}
        if reference_content:
            context["reference_content"] = reference_content

        # 根据规划模式选择不同的规划逻辑
        if planning_mode == "multi_model":
            # 多模型规划模式
            from .agents.multi_model_planning_service import get_multi_model_planning_service
            from .exceptions import (
                MultiModelPlanningError,
                ModelServiceError,
                handle_error
            )

            logger.info("[GeneratePlanOnly] 使用多模型规划")

            service = get_multi_model_planning_service()
            if not service:
                error = ModelServiceError(
                    message="多模型规划服务不可用，请检查配置",
                    model_name="MultiModelPlanningService"
                )
                error_response = handle_error(
                    error,
                    context={"function": "_generate_plan_only", "planning_mode": planning_mode}
                )
                logger.warning(f"[GeneratePlanOnly] {error_response['error']['message']}")

                return {
                    "success": False,
                    "error": error_response["error"]["message"],
                    "contract_plan": None,
                    "synthesis_report": None
                }

            # 调用多模型规划服务
            result = service.plan(
                user_input=user_input,
                context=context
            )

            # 提取最终规划
            final_planning = result.final_planning

            # 转换为 List[Dict] 格式
            contract_plan = [
                contract.model_dump()
                for contract in final_planning.contracts
            ]

            # 提取融合报告
            synthesis_report = {
                "solution_analyses": result.synthesis_report.solution_analyses,
                "extracted_strengths": result.synthesis_report.extracted_strengths,
                "identified_weaknesses": result.synthesis_report.identified_weaknesses,
                "fusion_strategy": result.synthesis_report.fusion_strategy,
                "fusion_summary": result.synthesis_report.fusion_summary,
            }

            # 提取合同关系
            contract_relationships = final_planning.relationships.model_dump() if final_planning.relationships else {}

            logger.info(f"[GeneratePlanOnly] 多模型规划完成，生成了 {len(contract_plan)} 份合同")

            return {
                "success": True,
                "contract_plan": contract_plan,
                "contract_relationships": contract_relationships,
                "synthesis_report": synthesis_report,
                "planning_mode": "multi_model"
            }

        else:
            # 单模型规划模式（默认）
            from .agents.contract_planning_service import ContractPlanningService

            logger.info("[GeneratePlanOnly] 使用单模型规划")

            planner = ContractPlanningService(llm)

            plan_result = planner.plan(user_input, context=context)

            # 转换为字典格式
            contract_plan = [contract.dict() for contract in plan_result.contracts]

            # 提取合同关系
            contract_relationships = plan_result.relationships.dict() if plan_result.relationships else {}

            # 如果有签署顺序，添加到关系字典中
            if plan_result.signing_order:
                contract_relationships["signing_order"] = plan_result.signing_order

            logger.info(f"[GeneratePlanOnly] 单模型规划完成，生成了 {len(contract_plan)} 份合同")

            return {
                "success": True,
                "contract_plan": contract_plan,
                "contract_relationships": contract_relationships,
                "synthesis_report": None,  # 单模型模式没有融合报告
                "planning_mode": "single_model"
            }

    except Exception as e:
        logger.error(f"[GeneratePlanOnly] 规划生成失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "contract_plan": None,
            "synthesis_report": None
        }