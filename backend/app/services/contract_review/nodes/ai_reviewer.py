import json
import logging
import os
import httpx
from typing import Dict, Any, Optional, List, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

# 引入内部依赖 (注意相对路径，假设本文件在 nodes/ 目录下)
from ..state import AgentState
from ..schemas import ReviewOutput, ContractProfile, LegalRelationshipAnalysis
from ..rule_assembler import rule_assembler

logger = logging.getLogger(__name__)

# ================= 配置区 =================
API_KEY = os.getenv("LANGCHAIN_API_KEY", "your-api-key")
API_BASE_URL = os.getenv("LANGCHAIN_API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

def get_model(json_mode=False):
    """初始化 LLM 模型"""
    # 使用 httpx 忽略 SSL 证书问题 (沿用你之前的配置)
    http_client = httpx.Client(verify=False, trust_env=False)
    
    return ChatOpenAI(
        model=MODEL_NAME,
        api_key=API_KEY,
        base_url=API_BASE_URL,
        temperature=0.1, # 保持低温度以确保逻辑严谨
        http_client=http_client,
        # 只有支持 json_object 的模型才开启此选项
        model_kwargs={"response_format": {"type": "json_object"}} if json_mode else {}
    )

# ================= Stage 1: 合同法律画像 (Profile) =================

def execute_stage_1(text: str, metadata: dict) -> dict:
    """
    第一阶段：识别合同的基础法律属性（非风险判断）
    """
    logger.info("--- [Stage 1] Start: Contract Profiling ---")
    try:
        llm = get_model(json_mode=True)
        parser = PydanticOutputParser(pydantic_object=ContractProfile)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一名资深合同律师。你的任务是【识别合同的法律属性】，为后续审查建立基础。
            
            请基于合同内容及元数据，重点判断：
            1. **合同类型**：具体的法律定性（如劳动合同、承揽合同、技术开发合同）。
            2. **持续性服务**：是否涉及长期的、持续性的服务提供？
            3. **复合性**：是否为包含多种法律关系的混合合同？
            4. **人身依附性**：甲方对乙方是否存在强管理、强控制特征（区别劳动与劳务的关键）？

            元数据参考：{metadata}
            
            要求：
            - 仅输出客观属性，不要进行风险判断。
            - 不得包含修改建议。
            - 必须严格遵循 JSON 格式。
            
            {format_instructions}"""),
            ("user", "合同内容摘要（前6000字）：\n{text}")
        ])
        
        chain = prompt | llm | parser
        # 截取前 6000 字通常足够判断属性，节省 Token
        result = chain.invoke({
            "text": text[:6000], 
            "metadata": json.dumps(metadata, ensure_ascii=False),
            "format_instructions": parser.get_format_instructions()
        })
        
        logger.info(f"--- [Stage 1] Completed. Type: {result.contract_type} ---")
        return result.dict()
        
    except Exception as e:
        logger.error(f"[Stage 1 Error] 法律画像分析失败: {e}")
        # 容错：返回空字典，不阻断流程
        return {}

# ================= Stage 2: 法律关系与适用法 (Relationships) =================

def execute_stage_2(text: str, profile: dict) -> dict:
    """
    第二阶段：基于画像判断法律关系及核心风险方向
    """
    logger.info("--- [Stage 2] Start: Legal Relationship Analysis ---")
    try:
        llm = get_model(json_mode=True)
        parser = PydanticOutputParser(pydantic_object=LegalRelationshipAnalysis)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一名法理学专家。请基于【合同法律画像】，判断法律关系与适用法律问题。
            
            当前法律画像：{profile}
            
            请重点分析：
            1. **劳动关系风险**：是否存在被司法机关认定为事实劳动关系的风险？(High/Medium/Low)
            2. **侵权风险**：是否存在侵权责任高发风险？
            3. **法律适用**：主要适用哪些法律（如民法典、劳动法、著作权法等）？
            
            要求：
            - 严禁输出修改建议。
            - 必须严格遵循 JSON 格式。
            
            {format_instructions}"""),
            ("user", "合同内容摘要：\n{text}")
        ])
        
        chain = prompt | llm | parser
        result = chain.invoke({
            "text": text[:6000],
            "profile": json.dumps(profile, ensure_ascii=False),
            "format_instructions": parser.get_format_instructions()
        })
        
        logger.info(f"--- [Stage 2] Completed. Labor Risk: {result.labor_relation_risk} ---")
        return result.dict()
        
    except Exception as e:
        logger.error(f"[Stage 2 Error] 法律关系判断失败: {e}")
        return {}

# ================= Stage 3: 风险与责任审查 (Review) =================

def execute_stage_3(
    text: str,
    stance: str,
    profile: dict,
    relationships: dict,
    user_rules: list = None,
    transaction_structures: list = None  # ⭐ 新增: 交易结构列表
) -> ReviewOutput:
    """
    第三阶段：加载规则包，进行最终审查

    Args:
        text: 合同文本
        stance: 审查立场
        profile: 合同画像
        relationships: 法律关系分析
        user_rules: 用户自定义规则
        transaction_structures: 用户选择的交易结构列表 (新增)
    """
    logger.info("--- [Stage 3] Start: Deep Risk Review ---")

    # 1. 动态组装规则包 (Rule Pack)
    # 这里的 rule_assembler 会读取 JSON 配置并结合 knowledge graph 特征(如有)
    # 目前 profile 中暂无 legal_features，assembler 会使用 defaults 或基础映射
    rule_pack_text = rule_assembler.assemble_prompt_context(
        legal_features=profile, # 暂时将 profile 传进去，未来对接 KnowledgeGraph 后传 features
        stance=stance,
        user_custom_rules=user_rules,
        transaction_structures=transaction_structures  # ⭐ 新增: 传递交易结构
    )
    
    # 2. 构建上下文
    context = f"""
    【前置判断依据】
    1. 合同法律画像: {json.dumps(profile, ensure_ascii=False)}
    2. 法律关系定性: {json.dumps(relationships, ensure_ascii=False)}
    """
    
    # 3. 调用 LLM - ⭐ 使用鲁棒的解析器
    from ..json_parser import create_robust_parser

    # 根据模型能力决定是否启用JSON模式
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
    use_json_mode = not any(keyword in model_name.lower()
                           for keyword in ["deepseek", "qwen", "baichuan", "yi", "chatglm"])

    llm = get_model(json_mode=use_json_mode)
    parser = create_robust_parser(ReviewOutput)

    if use_json_mode:
        # JSON模式：严格格式要求
        system_template = """你是一名资深律师。请从 {stance} 立场，严格依据【审查执行指令集】对合同进行风险审查。

        {context}

        ========================================
        【审查执行指令集 (Rule Pack)】
        请逐条对照以下规则进行检查：

        {rule_pack_text}
        ========================================

        审查输出要求：
        1. **逻辑闭环**：风险点必须有条款依据，不得凭空捏造。
        2. **劳动风险联动**：如果前置判断提示有劳动关系风险，必须在审查中作为高风险项列出。
        3. **落地建议**：针对每个问题，必须给出具体的修改建议（Revision）或警告（Alert）。
        4. **格式严格**：必须输出符合 Schema 的 JSON 数据。

        {format_instructions}"""
    else:
        # 文本模式：更宽松的格式要求
        system_template = """你是一名资深律师。请从 {stance} 立场，严格依据【审查执行指令集】对合同进行风险审查。

        {context}

        ========================================
        【审查执行指令集 (Rule Pack)】
        请逐条对照以下规则进行检查：

        {rule_pack_text}
        ========================================

        审查输出要求：
        1. **逻辑闭环**：风险点必须有条款依据，不得凭空捏造。
        2. **劳动风险联动**：如果前置判断提示有劳动关系风险，必须在审查中作为高风险项列出。
        3. **落地建议**：针对每个问题，必须给出具体的修改建议（Revision）或警告（Alert）。
        4. **输出格式**：请以JSON格式输出，包含 summary 和 issues 列表。

        输出结构示例：
        {{
          "summary": "审查总结",
          "issues": [
            {{
              "issue_type": "风险类型",
              "quote": "相关条款原文",
              "explanation": "风险说明",
              "suggestion": "修改建议",
              "legal_basis": "法律依据",
              "severity": "严重程度(Critical/High/Medium/Low)",
              "action_type": "操作类型(Revision/Alert)"
            }}
          ]
        }}
        """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("user", "合同全文：\n{text}")
    ])

    chain = prompt | llm | parser

    # Stage 3 需要阅读全文（或大部分内容）以发现细节问题
    # 这里放宽 token 限制到 12000 字符 (约 6k tokens)
    invoke_args = {
        "stance": stance,
        "context": context,
        "rule_pack_text": rule_pack_text,
        "text": text[:12000],
    }
    if use_json_mode:
        invoke_args["format_instructions"] = parser.get_format_instructions()

    result = chain.invoke(invoke_args)

    logger.info(f"--- [Stage 3] Completed. Issues Found: {len(result.issues)} ---")
    return result

# ================= 主节点入口 (Node Entry) =================

def ai_reviewer_node(state: AgentState) -> AgentState:
    """
    LangGraph 节点：串行执行三阶段审查逻辑

    ⭐ 支持长文本分块处理
    - 分块模式: 使用滑动窗口逐块审查
    - 全文模式: 直接审查全文
    """
    print("\n🤖 [AI] 正在进行三阶段审查 (Profile -> Relation -> RuleBasedReview)...")

    contract_text = state.get("contract_text", "")
    metadata = state.get("metadata", {})
    stance = state.get("stance", "neutral")

    # ⭐ 获取分块信息
    chunks = state.get("chunks", [])
    chunk_mode = state.get("chunk_review_mode", False)

    if chunk_mode and chunks:
        logger.info(f"[AI Reviewer] 启用分块审查模式 - 分块数量: {len(chunks)}")

    # 获取用户自定义规则 (从 metadata 中透传，如果前端传了的话)
    user_rules = metadata.get("custom_rules", [])

    # ⭐ 新增: 获取交易结构 (从 metadata 中透传)
    transaction_structures = metadata.get("transaction_structures", [])
    if transaction_structures:
        logger.info(f"[AI Reviewer] 使用交易结构: {transaction_structures}")

    # ========== Step 1: 法律画像 ==========
    # ⭐ 分块模式: 使用第一块 + 合同摘要进行全局分析
    if chunk_mode and chunks:
        # 使用第一块进行画像分析
        first_chunk_text = chunks[0][0]

        # 添加合同上下文摘要,确保全局一致性
        context_summary = _generate_contract_summary(metadata, chunks)

        # 结合第一块和摘要进行分析
        analysis_text = f"""
【合同上下文摘要】
{context_summary}

【第一块内容】
{first_chunk_text}
"""

        profile = execute_stage_1(analysis_text, metadata)
        logger.info("[AI Reviewer] 分块模式: 基于第一块+摘要完成画像")
    else:
        # 全文模式
        profile = execute_stage_1(contract_text, metadata)

    # ========== Step 2: 法律关系 ==========
    # 即使 Step 1 失败返回空字典，Step 2 依然尝试运行（依靠 LLM 的通用能力兜底）
    if chunk_mode and chunks:
        # 分块模式: 基于第一块+摘要
        relationships = execute_stage_2(analysis_text, profile)
        logger.info("[AI Reviewer] 分块模式: 基于第一块+摘要完成法律关系分析")
    else:
        relationships = execute_stage_2(contract_text, profile)

    # ========== Step 3: 风险审查 (核心) ==========
    review_result = None
    status = "processing"

    try:
        if chunk_mode and chunks:
            # ⭐ 分块审查模式: 使用滑动窗口
            review_result = execute_stage_3_chunked_with_sliding_window(
                chunks=chunks,
                stance=stance,
                profile=profile,
                relationships=relationships,
                user_rules=user_rules,
                transaction_structures=transaction_structures
            )
            logger.info("[AI Reviewer] 分块审查完成")
        else:
            # 全文审查模式
            review_result = execute_stage_3(
                text=contract_text,
                stance=stance,
                profile=profile,
                relationships=relationships,
                user_rules=user_rules,
                transaction_structures=transaction_structures
            )
            logger.info("[AI Reviewer] 全文审查完成")

        status = "success"
    except Exception as e:
        logger.error(f"[Stage 3 Fatal Error] 最终审查失败: {e}", exc_info=True)
        status = "error"
        # 这里可以选择返回一个空的 ReviewOutput 对象，防止前端崩溃
        # review_result = ReviewOutput(summary="审查服务暂时不可用", issues=[])

    # --- 更新状态 ---
    return {
        **state,
        "contract_profile": profile,
        "legal_relationships": relationships,
        "review_result": review_result,
        "status": status
    }


# ================= 辅助函数 =================

def _generate_contract_summary(metadata: Dict, chunks: list) -> str:
    """
    生成合同上下文摘要

    用途: 为全局分析提供合同的整体结构信息

    Args:
        metadata: 合同元数据
        chunks: 分块列表

    Returns:
        合同摘要 (包括: 当事人、标的、期限、分块结构等)
    """
    from ..utils import extract_section_keywords

    summary_parts = []

    # 1. 基本元数据
    if metadata.get('contract_name'):
        summary_parts.append(f"合同名称: {metadata['contract_name']}")

    if metadata.get('parties'):
        # 修复：处理 parties 字符串格式
        parties = metadata['parties']
        parties_info = ""

        if isinstance(parties, str):
            # 如果是字符串，直接使用
            parties_info = parties
        elif isinstance(parties, list):
            # 如果是列表，格式化显示
            parties_info = "; ".join([
                f"{p.get('role', '未知')}: {p.get('name', '未命名')}"
                for p in parties
            ])
        else:
            parties_info = str(parties)

        summary_parts.append(f"当事人: {parties_info}")

    if metadata.get('contract_amount'):
        summary_parts.append(f"合同金额: {metadata['contract_amount']}")

    # 2. 分块结构信息
    summary_parts.append(f"合同分块信息: 共 {len(chunks)} 块")

    # 3. 每块的简短描述 (使用关键词提取)
    chunk_descriptions = []
    for idx, (chunk_text, _) in enumerate(chunks):
        # 提取每块的关键词 (例如: 第X条, 第X节等)
        keywords = extract_section_keywords(chunk_text)
        chunk_descriptions.append(f"第{idx+1}块: {keywords}")

    summary_parts.append("分块内容: " + " | ".join(chunk_descriptions))

    return "\n".join(summary_parts)


def execute_stage_3_chunked_with_sliding_window(
    chunks: list,
    stance: str,
    profile: dict,
    relationships: dict,
    user_rules: list = None,
    transaction_structures: list = None
) -> ReviewOutput:
    """
    ⭐ 核心函数: 滑动窗口分块审查

    设计理念:
    - 使用滑动窗口确保相邻块之间的上下文连续性
    - 每个块包含: 前一块的尾部 + 当前块 + 下一块的头部
    - 这样可以识别跨块的风险点 (例如: 条款引用、逻辑冲突)

    Args:
        chunks: 分块列表 [(chunk_text, (start, end)), ...]
        stance: 审查立场
        profile: 合同画像
        relationships: 法律关系
        user_rules: 用户自定义规则
        transaction_structures: 交易结构

    Returns:
        ReviewOutput: 合并后的审查结果
    """
    from typing import List, Tuple

    all_items = []

    # 规则组装
    rule_pack_text = rule_assembler.assemble_prompt_context(
        legal_features=profile,
        stance=stance,
        user_custom_rules=user_rules,
        transaction_structures=transaction_structures
    )

    # ⭐ 滑动窗口参数
    window_overlap = 300  # 窗口重叠字符数

    logger.info(f"[Sliding Window] 开始分块审查 - 分块数: {len(chunks)}, 窗口重叠: {window_overlap}")

    # 逐块审查 (使用滑动窗口)
    for idx, (chunk_text, (start, end)) in enumerate(chunks):
        logger.info(f"[Sliding Window] 审查第 {idx+1}/{len(chunks)} 块 (位置 {start}-{end})")

        # ========== 构建滑动窗口上下文 ==========
        window_context = chunk_text

        # 添加前一块的尾部 (如果有)
        if idx > 0:
            prev_chunk_text = chunks[idx - 1][0]
            prev_tail = prev_chunk_text[-window_overlap:]
            window_context = f"[前块尾部]\n{prev_tail}\n\n[当前块]\n{window_context}"

        # 添加下一块的头部 (如果有)
        if idx < len(chunks) - 1:
            next_chunk_text = chunks[idx + 1][0]
            next_head = next_chunk_text[:window_overlap]
            window_context = f"{window_context}\n\n[下块头部]\n{next_head}"

        # ⭐ 审查当前窗口
        chunk_review = _review_single_window(
            window_text=window_context,
            chunk_position=(start, end),
            stance=stance,
            profile=profile,
            relationships=relationships,
            rule_pack_text=rule_pack_text,
            window_type="middle" if 0 < idx < len(chunks) - 1 else ("first" if idx == 0 else "last")
        )

        # 合并审查项
        if chunk_review and hasattr(chunk_review, 'issues'):
            all_items.extend(chunk_review.issues)
            logger.info(f"[Sliding Window] 第{idx+1}块发现 {len(chunk_review.issues)} 个风险点")

    # ========== 合并和去重 ==========
    merged_items = _merge_and_deduplicate_items(all_items)

    logger.info(f"[Sliding Window] 分块审查完成 - 原始项: {len(all_items)}, 合并后: {len(merged_items)}")

    return ReviewOutput(
        summary=f"共发现 {len(merged_items)} 个风险点 (分块审查: {len(chunks)} 块)",
        issues=merged_items
    )


def _review_single_window(
    window_text: str,
    chunk_position: Tuple[int, int],
    stance: str,
    profile: Dict,
    relationships: Dict,
    rule_pack_text: str,
    window_type: str  # "first" | "middle" | "last"
) -> Optional[ReviewOutput]:
    """
    审查单个滑动窗口

    Args:
        window_text: 窗口文本 (包含重叠上下文)
        chunk_position: 当前块在原文中的位置
        stance: 审查立场
        profile: 合同画像
        relationships: 法律关系
        rule_pack_text: 规则包
        window_type: 窗口类型

    Returns:
        ReviewOutput
    """
    # 构建上下文
    context = f"""
【前置判断依据】
1. 合同法律画像: {json.dumps(profile, ensure_ascii=False)}
2. 法律关系定性: {json.dumps(relationships, ensure_ascii=False)}

【审查规则包】
{rule_pack_text}

【待审查文本】
⚠️ 注意: 这是一个包含上下文的滑动窗口
- 当前块位置: {chunk_position}
- 窗口类型: {window_type}
- 请重点关注当前块内的风险,同时考虑上下文关联

{window_text}
"""

    # 构建Prompt - ⭐ 使用鲁棒的解析器，支持非JSON模式
    from ..json_parser import create_robust_parser

    # 根据模型能力决定是否启用JSON模式
    # 某些模型（如DeepSeek、Qwen）对JSON模式支持不佳，使用文本模式更稳定
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")

    # 对于国产模型，禁用JSON模式以提高稳定性
    use_json_mode = not any(keyword in model_name.lower()
                           for keyword in ["deepseek", "qwen", "baichuan", "yi", "chatglm"])

    llm = get_model(json_mode=use_json_mode)

    # 使用鲁棒的解析器
    parser = create_robust_parser(ReviewOutput)

    if use_json_mode:
        # JSON模式：严格格式要求
        system_prompt = """你是一位资深法律顾问。请审查以下合同窗口并输出JSON格式的审查结果。

关键要求:
1. 识别当前块中的风险点
2. 注意上下文关联 (例如: 条款引用、逻辑冲突)
3. 标注风险在当前块中的位置 (相对位置)
4. 风险类型使用标准分类
5. 必须输出符合JSON格式的结果

{format_instructions}
"""
    else:
        # 文本模式：更宽松的格式要求，通过解析器处理
        system_prompt = """你是一位资深法律顾问。请审查以下合同窗口。

关键要求:
1. 识别当前块中的风险点
2. 注意上下文关联 (例如: 条款引用、逻辑冲突)
3. 标注风险在当前块中的位置 (相对位置)
4. 风险类型使用标准分类

请以JSON格式输出结果，包含以下结构：
{{
  "summary": "审查总结",
  "issues": [
    {{
      "issue_type": "风险类型",
      "quote": "相关条款原文",
      "explanation": "风险说明",
      "suggestion": "修改建议",
      "legal_basis": "法律依据",
      "severity": "严重程度(Critical/High/Medium/Low)",
      "action_type": "操作类型(Revision/Alert)"
    }}
  ]
}}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{context}")
    ])

    chain = prompt | llm | parser

    try:
        invoke_args = {"context": context}
        if use_json_mode:
            invoke_args["format_instructions"] = parser.get_format_instructions()

        result = chain.invoke(invoke_args)
        return result
    except Exception as e:
        logger.error(f"[Window Review Error] 窗口审查失败: {e}")
        return ReviewOutput(summary=f"窗口审查失败: {str(e)}", issues=[])


def _merge_and_deduplicate_items(items: list) -> list:
    """
    ⭐ 关键函数: 合并和去重审查项

    策略:
    1. 按位置分组 (相邻的相似项可能是同一风险)
    2. 按issue_type分组 (相同类型的风险合并)
    3. 去除完全重复项
    4. 优先级排序 (Critical > High > Medium > Low)

    Args:
        items: 审查项列表

    Returns:
        合并后的审查项列表
    """
    if not items:
        return []

    # 1. 按类型去重 (完全相同内容的视为重复)
    seen_signatures = set()
    unique_items = []

    for item in items:
        # 生成项的唯一签名 (基于 issue_type + quote 的前50个字符)
        signature = f"{item.issue_type}_{item.quote[:50] if hasattr(item, 'quote') and item.quote else ''}"

        if signature not in seen_signatures:
            seen_signatures.add(signature)
            unique_items.append(item)

    logger.info(f"[Merge] 去重前: {len(items)}, 去重后: {len(unique_items)}")

    # 2. 按类型分组 (相似位置、相同类型的项)
    from collections import defaultdict
    item_groups = defaultdict(list)

    for item in unique_items:
        issue_type = item.issue_type if hasattr(item, 'issue_type') else "未知"
        item_groups[issue_type].append(item)

    # 3. 对每组进行合并
    merged_items = []

    for issue_type, group_items in item_groups.items():
        if len(group_items) == 1:
            merged_items.append(group_items[0])
        else:
            # 合并多个相似项
            merged_item = _merge_similar_items(group_items)
            merged_items.append(merged_item)

    # 4. 按严重程度排序
    severity_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

    merged_items.sort(
        key=lambda x: severity_order.get(
            x.severity if hasattr(x, 'severity') else "Medium",
            0
        ),
        reverse=True
    )

    logger.info(f"[Merge] 最终合并后: {len(merged_items)} 个审查项")

    return merged_items


def _merge_similar_items(items: list) -> Any:
    """
    合并相似的审查项

    策略:
    - 保留最严重程度的severity
    - 合并explanation (使用分隔符)
    - 合并suggestion (选择最全面的)

    Args:
        items: 相似的审查项列表

    Returns:
        合并后的审查项
    """
    # 选择最严重的项作为基础
    severity_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

    base_item = max(
        items,
        key=lambda x: severity_order.get(
            x.severity if hasattr(x, 'severity') else "Medium",
            0
        )
    )

    # 如果所有项都相同,直接返回
    if len(items) == 1:
        return base_item

    # 合并explanation
    explanations = []
    for item in items:
        if hasattr(item, 'explanation') and item.explanation:
            explanations.append(item.explanation)

    merged_explanation = " | ".join(explanations) if explanations else ""

    # 合并suggestion (选择最长的)
    suggestions = []
    for item in items:
        if hasattr(item, 'suggestion') and item.suggestion:
            suggestions.append(item.suggestion)

    merged_suggestion = max(suggestions, key=len) if suggestions else ""

    # 创建合并后的项 (使用 ReviewOutput 的内部类)
    # 这里我们直接修改 base_item 的属性
    if hasattr(base_item, 'explanation'):
        base_item.explanation = merged_explanation
    if hasattr(base_item, 'suggestion'):
        base_item.suggestion = merged_suggestion

    logger.debug(f"[Merge] 合并了 {len(items)} 个相似项 (类型: {base_item.issue_type if hasattr(base_item, 'issue_type') else '未知'})")

    return base_item