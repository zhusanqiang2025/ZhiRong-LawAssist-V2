# backend/app/services/contract_generation/agents/requirement_analyzer.py

import logging
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# 导入合同意图分析器
try:
    from .contract_intent_analyzer import get_contract_intent_analyzer
    INTENT_ANALYZER_AVAILABLE = True
except ImportError:
    INTENT_ANALYZER_AVAILABLE = False
    logger.warning("[RequirementAnalyzer] 合同意图分析器不可用")

# 导入知识图谱（数据库版本）
try:
    from app.services.common.contract_knowledge_db_service import contract_knowledge_db_service
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False
    logger.warning("[RequirementAnalyzer] 知识图谱不可用")


class RequirementAnalyzer:
    """
    合同需求分析器（基于知识图谱）

    核心流程：
    1. 使用 LLM 理解用户意图，识别合同类型
    2. 从知识图谱获取该合同类型的完整法律特征
    3. 返回结构化分析结果供模板匹配使用

    这是对之前 V2/V3 特征提取器的完全重构
    - 不再使用固定的"三维/四维法律特征"
    - 而是基于知识图谱的合同类型分类体系
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        Args:
            llm: 用于意图分析的 LLM 实例
        """
        self.llm = llm
        self.intent_analyzer = None
        self.knowledge_graph = None

        # 初始化意图分析器
        if INTENT_ANALYZER_AVAILABLE and llm:
            try:
                self.intent_analyzer = get_contract_intent_analyzer(llm)
                logger.info("[RequirementAnalyzer] 合同意图分析器已启用")
            except Exception as e:
                logger.warning(f"[RequirementAnalyzer] 合同意图分析器初始化失败: {e}")

        # 初始化知识图谱（数据库版本）
        if KNOWLEDGE_GRAPH_AVAILABLE:
            try:
                self.knowledge_graph = contract_knowledge_db_service
                logger.info("[RequirementAnalyzer] 知识图谱（数据库版本）已加载")
            except Exception as e:
                logger.warning(f"[RequirementAnalyzer] 知识图谱加载失败: {e}")

    def analyze(self, user_input: str) -> Dict[str, Any]:
        """
        主入口 - 分析用户需求

        核心流程：
        1. 理解用户意图 → 识别合同类型
        2. 从知识图谱获取该合同类型的法律特征
        3. 返回结构化分析结果

        Args:
            user_input: 用户自然语言输入

        Returns:
            analysis_result: 结构化分析结果
        """
        logger.info("[RequirementAnalyzer] 开始分析用户需求")

        # 判断处理类型
        processing_type = self._determine_processing_type(user_input)

        # ==================== 第一步：理解用户意图 ====================
        if self.intent_analyzer:
            try:
                intent_result = self.intent_analyzer.analyze(user_input)
                contract_type = intent_result.contract_type
                key_elements = intent_result.key_elements
                needs_clarification = intent_result.needs_clarification
                clarification_questions = intent_result.clarification_questions

                logger.info(f"[RequirementAnalyzer] 意图识别成功: {contract_type}")
                logger.info(f"[RequirementAnalyzer] 关键要素: {key_elements}")
            except Exception as e:
                logger.warning(f"[RequirementAnalyzer] 意图识别失败: {e}，使用降级方案")
                contract_type = self._fallback_extract_contract_type(user_input)
                key_elements = {}
                needs_clarification = False
                clarification_questions = []
        else:
            # 降级方案：使用规则提取
            contract_type = self._fallback_extract_contract_type(user_input)
            key_elements = {}
            needs_clarification = False
            clarification_questions = []

        # ==================== 第二步：从知识图谱获取法律特征 ====================
        legal_features_from_kg = None
        if self.knowledge_graph and contract_type:
            try:
                # 从知识图谱（数据库）查找合同类型定义
                contract_def = self.knowledge_graph.get_by_name(contract_type)

                if contract_def and contract_def.get("legal_features"):
                    # 数据库版本返回字典格式，直接使用
                    legal_features_from_kg = contract_def["legal_features"]
                    logger.info(f"[RequirementAnalyzer] 从知识图谱获取法律特征成功: {contract_type}")
                else:
                    # 如果没找到，尝试模糊搜索
                    search_results = self.knowledge_graph.search_by_keywords(contract_type)
                    if search_results:
                        best_match = search_results[0]  # 取第一个（相关性最高的）
                        if best_match.get("legal_features"):
                            legal_features_from_kg = best_match["legal_features"]
                            logger.info(f"[RequirementAnalyzer] 知识图谱模糊匹配: {best_match['name']}")
            except Exception as e:
                logger.warning(f"[RequirementAnalyzer] 从知识图谱获取法律特征失败: {e}")

        # ==================== 第三步：构建分析结果 ====================
        analysis_result = {
            "processing_type": processing_type,
            # 合同分类
            "contract_classification": {
                "contract_type": contract_type,  # 识别的具体合同类型
                "primary_type": contract_type,     # 主合同类型（与具体类型相同）
            },
            # 法律特征（来自知识图谱）
            "legal_features": legal_features_from_kg or {},
            # 关键信息（用于显示）
            "key_info": {
                "合同类型": contract_type,
                **key_elements,
            },
            # 是否需要澄清
            "needs_clarification": needs_clarification,
            "clarification_questions": clarification_questions,
        }

        logger.info(f"[RequirementAnalyzer] 分析完成: {contract_type}")
        return analysis_result

    # =========================
    # 辅助方法
    # =========================

    def _determine_processing_type(self, text: str) -> str:
        """
        判断合同处理类型（使用 LLM 语义理解）

        判断标准基于：
        优先级1：合同变更 (contract_modification) - 对已签署合同的条款进行调整
        优先级2：合同解除 (contract_termination) - 提前终止已签署合同的效力
        优先级3：合同规划 (contract_planning) - 多份独立法律关系的文件组合
        优先级4：单一合同 (single_contract) - 单一法律关系的合同生成

        Returns:
            "contract_modification": 合同变更（对现有合同条款进行调整）
            "contract_termination": 合同解除（提前终止现有合同）
            "contract_planning": 合同规划（多份合同）
            "single_contract": 单一合同生成（默认）
        """
        # 使用 LLM 语义分析，判断所有四种类型
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            from langchain_openai import ChatOpenAI
            import os
            import json

            llm = ChatOpenAI(
                model=os.getenv("MODEL_NAME", "deepseek-chat"),
                api_key=os.getenv("OPENAI_API_KEY") or os.getenv("LANGCHAIN_API_KEY"),
                base_url=os.getenv("OPENAI_API_BASE") or os.getenv("LANGCHAIN_API_BASE_URL"),
                temperature=0
            )

            prompt = f"""你是一位资深的法律专家，精通《中华人民共和国民法典》合同编。请根据以下标准，判断用户的需求属于哪种合同处理类型。

## 用户需求
{text}

## 判断标准（按优先级排序）

### 优先级1：合同变更 (contract_modification)
**定义**：对已经签署生效的合同的部分条款进行调整、修改或补充。

**判断依据**：
1. **明确提到变更相关词汇**：变更、修改、补充、修订、调整、改签
2. **存在已签署合同作为基础**：用户提到"原合同"、"现有合同"、"之前签的"
3. **调整的是合同条款**：如付款方式、交付时间、服务范围等具体条款的修改
4. **合同继续有效**：只是部分条款变化，主合同关系仍然存在

**典型场景**：
- "要把原合同的付款期限从30天改成60天"
- "变更软件开发合同的交付内容"
- "补充协议增加服务项目"
- "调整合同中的违约金比例"

### 优先级2：合同解除 (contract_termination)
**定义**：提前终止已签署合同的效力，结束合同关系。

**判断依据**：
1. **明确提到解除相关词汇**：解除、终止、撤销、废止、不再继续
2. **存在已签署合同作为基础**：用户提到"原合同"、"现有合同"
3. **合同关系结束**：不再是调整条款，而是彻底结束合同
4. **可能涉及解除后的安排**：费用结算、违约责任、争议解决

**典型场景**：
- "要解除与XX公司签订的技术服务合同"
- "提前终止租赁合同"
- "协商一致解除劳动合同"
- "对方违约，我要解除合同"

**如何区分变更 vs 解除**：
- 变更：合同继续有效，只是条款调整
- 解除：合同关系结束，权利义务终止

### 优先级3：合同规划 (contract_planning)
**定义**：需要生成多份独立的法律文件，涉及多个法律关系或分阶段实施。

**判断依据**（满足任一即可）：
1. **存在多个独立法律关系**：如同时包含股权转让+技术许可+高管雇佣+竞业禁止（依据：《民法典》第470条）
2. **存在阶段性或附条件生效结构**：如"先签意向书（含排他条款）→ 尽调后签正式SPA → 交割后签过渡期服务协议"（依据：《九民纪要》第45条）
3. **涉及法定或监管要求的文件分离**：如外商并购需单独签署SPA+合资合同+章程并分别报批/备案；或知识产权转让需单独办理登记（《专利法》第10条）
4. **当事人明确要求或行业惯例要求分离**：如投融资交易中的"Term Sheet + SPA + SHA + VIE协议"标准包；或建设工程的"施工合同+安全生产协议+廉政协议"
5. **存在冲突利益或保密隔离需求**：如并购中核心技术人员另签留任协议（避免披露薪酬细节）

**强信号**：
- "先…再…"、"分阶段"、"配套协议"、"一整套"、"尽调后签署"、"报批文件"、"VIE"、"SPA/SHA"、"交割条件"
- 明确提到多个文件名（如"可转债合同、章程、股转决议"）
- 股权重塑、资产重组、并购、投融资等复杂交易

### 优先级4：单一合同 (single_contract)
**定义**：生成一份新的合同，涉及单一法律关系。

**判断依据**（需全部满足）：
1. **法律关系单一**：仅涉及一个主给付义务（如买卖、承揽、委托、租赁等典型合同关系）
2. **权利义务可一次性约定**：所有当事人的权利、义务、责任可在同一份文件中完整、清晰地设定
3. **无独立生效/履行阶段**：不存在需分步签署、分步生效、或某部分协议需以另一协议履行为前提的情形
4. **无监管强制要求分离**：不涉及因行政监管（如外商投资、股权变更登记、知识产权许可备案等）而必须拆分为多份法律文件的情形

**典型场景**：
- 甲乙双方签订软件开发合同
- 甲、乙、丙三方签订一份带连带担保的借款合同
- 股东会决议与股权转让协议合并为一份文件

**强信号**：
- "一份合同搞定"、"全部写在一起"、"统一约定"、"无其他文件"

## 判断流程
请按以下优先级顺序判断：

1. **第一步**：检查是否为合同变更
   - 是否提到变更相关词汇？
   - 是否调整已签署合同的条款？
   - 合同是否继续有效？
   - 如果是 → 返回 contract_modification

2. **第二步**：检查是否为合同解除
   - 是否提到解除相关词汇？
   - 是否要结束已签署合同的关系？
   - 如果是 → 返回 contract_termination

3. **第三步**：检查是否为合同规划
   - 是否涉及多个独立法律关系？
   - 是否需要分阶段实施？
   - 是否涉及监管要求的文件分离？
   - 如果是 → 返回 contract_planning

4. **第四步**：默认为单一合同
   - 返回 single_contract

## 输出要求
请严格按照以下 JSON 格式返回（不要添加任何其他文字）：
{{
    "type": "contract_modification 或 contract_termination 或 contract_planning 或 single_contract",
    "reason": "判断理由（引用上述标准，简要说明为什么选择该类型）",
    "analysis": {{
        "priority_checked": "你检查的优先级顺序（如：先检查变更，再检查解除...）",
        "key_signals": ["识别到的关键词或信号"],
        "legal_basis": "法律依据或理由"
    }}
}}

判断时请：
1. 严格按照优先级顺序判断
2. 仔细分析用户描述的权利义务结构
3. 区分"变更条款"与"解除合同"的本质差异
4. 参考《民法典》《九民纪要》等相关法律依据
"""

            response = llm.invoke([
                SystemMessage(content="你是资深的法律专家，精通中国合同法及相关司法解释。请严格按照JSON格式返回结果。"),
                HumanMessage(content=prompt)
            ])

            result_text = response.content.strip()

            # 尝试解析 JSON（处理可能的 markdown 代码块）
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            analysis = json.loads(result_text)
            detected_type = analysis.get("type", "single_contract")
            reason = analysis.get("reason", "")

            logger.info(f"[RequirementAnalyzer] LLM 分析处理类型: {detected_type}")
            logger.info(f"[RequirementAnalyzer] 判断理由: {reason}")
            logger.info(f"[RequirementAnalyzer] 详细分析: {analysis.get('analysis', {})}")

            # 验证返回值是否合法（支持所有四种类型）
            valid_types = ["contract_modification", "contract_termination", "contract_planning", "single_contract"]
            if detected_type in valid_types:
                return detected_type
            else:
                logger.warning(f"[RequirementAnalyzer] LLM 返回了未知类型: {detected_type}，使用默认值")
                return "single_contract"

        except Exception as e:
            logger.warning(f"[RequirementAnalyzer] LLM 分析失败: {e}，使用规则降级方案")

            # 降级方案：按优先级使用关键词/规则判断
            import re

            # 优先级1：检查合同变更
            modification_keywords = ["变更", "修改", "补充", "修订", "调整", "改签"]
            modification_context = ["原合同", "现有合同", "之前签的", "已签署"]
            for kw in modification_keywords:
                if kw in text:
                    # 检查是否有原合同的上下文
                    if any(ctx in text for ctx in modification_context):
                        logger.info(f"[RequirementAnalyzer] 降级方案检测到变更场景，关键词: {kw}")
                        return "contract_modification"

            # 优先级2：检查合同解除
            termination_keywords = ["解除", "终止", "撤销", "废止", "不再继续"]
            for kw in termination_keywords:
                if kw in text:
                    # 检查是否有原合同的上下文
                    if any(ctx in text for ctx in modification_context):
                        logger.info(f"[RequirementAnalyzer] 降级方案检测到解除场景，关键词: {kw}")
                        return "contract_termination"

            # 优先级3：检查合同规划
            planning_strong_signals = [
                "先.*再.*", "分阶段", "配套协议", "一整套", "整套法律文件",
                "尽调后签署", "报批文件", "交割条件", "意向书.*正式协议",
                "VIE", "SPA.*SHA", "股权重塑", "资产重组",  # 移除 "并购交易"（过于宽泛）
                "可转债.*章程.*决议",  # 明确提到多个文件
                "Term Sheet", "投资协议.*股东协议",
                # 更精确的多文件组合模式
                "增资协议.*股东协议", "股权转让.*章程修改", "并购.* SPA.* SHA",
                "借款协议.*担保协议.*质押",  # 明确提到至少两个不同类型的协议
            ]

            for pattern in planning_strong_signals:
                if re.search(pattern, text, re.IGNORECASE):
                    logger.info(f"[RequirementAnalyzer] 降级方案检测到规划场景，匹配信号: {pattern}")
                    return "contract_planning"

            # 检查是否明确提到多个不同类型的文件
            file_type_indicators = ["协议", "合同", "章程", "决议", "文件", "备忘录", "承诺书"]
            segments = text.replace("、", " ").replace("，", " ").replace(",", " ").replace("和", " ").split()
            file_type_segments = [seg for seg in segments if any(ind in seg for ind in file_type_indicators)]

            # 如果提到 3 个或更多文件类型，很可能是规划场景
            if len(file_type_segments) >= 3:
                logger.info(f"[RequirementAnalyzer] 降级方案检测到多个文件类型，数量: {len(file_type_segments)}")
                return "contract_planning"

            # 检查是否有"单一合同"的强信号
            single_signals = ["一份合同搞定", "全部写在一起", "统一约定", "无其他文件", "合并为一份"]
            for signal in single_signals:
                if signal in text:
                    logger.info(f"[RequirementAnalyzer] 降级方案检测到单一合同场景，匹配信号: {signal}")
                    return "single_contract"

            # 默认为单一合同
            return "single_contract"

    def _fallback_extract_contract_type(self, text: str) -> str:
        """
        降级方案：使用规则提取合同类型

        当意图分析器不可用或失败时使用
        """
        # 关键词到合同类型的映射
        keyword_mapping = {
            # 股权相关
            "股权": "股权转让合同",
            "股份转让": "股权转让合同",
            "股权收购": "股权收购合同",
            "增资": "增资扩股协议",

            # 软件开发
            "软件开发": "软件开发合同",
            "委托开发": "委托开发合同",
            "网站开发": "软件开发合同",
            "APP开发": "软件开发合同",

            # 技术相关
            "技术开发": "技术开发合同",
            "技术转让": "技术转让合同",
            "技术服务": "技术服务合同",
            "技术咨询": "技术咨询合同",

            # 采购相关
            "设备采购": "设备采购合同",
            "采购": "设备采购合同",
            "供货": "货物买卖合同",
            "买卖": "货物买卖合同",

            # 租赁相关
            "租赁": "租赁合同",
            "房屋租赁": "房屋租赁合同",
            "场地租赁": "场地租赁合同",

            # 借款相关
            "借款": "借款合同",
            "融资": "借款合同",
            "贷款": "借款合同",

            # 建设工程
            "施工": "建设工程施工合同",
            "装修": "装修工程合同",
            "工程": "建设工程施工合同",
        }

        # 按关键词长度排序（优先匹配更具体的关键词）
        sorted_keywords = sorted(keyword_mapping.items(), key=lambda x: len(x[0]), reverse=True)

        for keyword, contract_type in sorted_keywords:
            if keyword in text:
                return contract_type

        # 默认返回委托合同
        return "委托合同"

    def extract_modification_termination_info(
        self,
        user_input: str,
        reference_content: str = None,
        uploaded_files: List[str] = None
    ) -> Dict[str, Any]:
        """
        从用户输入和上传文件中提取合同变更/解除所需信息

        Args:
            user_input: 用户需求描述
            reference_content: 上传文件解析后的内容
            uploaded_files: 上传文件路径列表

        Returns:
            提取的结构化信息:
            {
                "processing_type": "contract_termination" | "contract_modification",
                "original_contract_info": {
                    "contract_name": str,
                    "signing_date": str,
                    "parties": [str, ...],
                    "contract_term": str,
                    "key_terms": { ... }
                },
                "termination_reason": str,  # 解除场景
                "post_termination_arrangements": { ... },  # 解除场景
                "modification_points": [ ... ],  # 变更场景
                "confidence": float
            }
        """
        import json
        from langchain.schema import HumanMessage, SystemMessage

        processing_type = self._determine_processing_type(user_input)

        # 只有变更或解除场景才执行提取
        if processing_type not in ["contract_modification", "contract_termination"]:
            return {}

        logger.info(f"[RequirementAnalyzer] 开始提取{processing_type}所需信息")

        # 构建提取提示词
        if processing_type == "contract_termination":
            system_prompt = """你是一位专业的合同审查专家，擅长从合同文本和用户描述中提取关键信息。

请从给定的信息中提取合同解除协议所需的关键信息，以 JSON 格式返回。"""
            user_prompt = f"""## 用户需求描述
{user_input}

## 原合同内容
{reference_content or '未提供'}

## 任务
请提取以下信息并以 JSON 格式返回：
{{
    "original_contract_info": {{
        "contract_name": "合同名称",
        "signing_date": "签订日期（如：2024年1月1日）",
        "parties": ["甲方", "乙方"],
        "contract_term": "合同期限描述",
        "key_terms": {{
            "payment": "付款方式摘要",
            "delivery": "交付方式摘要",
            "liability": "违约责任摘要"
        }}
    }},
    "termination_reason": "解除原因（从用户描述中提取或总结）",
    "post_termination_arrangements": {{
        "fee_settlement": "费用结算方式",
        "liability": "违约责任处理",
        "dispute_resolution": "争议解决方式"
    }},
    "confidence": 0.85
}}

如果某些信息无法从给定内容中提取，请使用合理的默认值或空字符串，并降低 confidence 值。
只返回 JSON，不要有其他文字。"""
        else:  # contract_modification
            system_prompt = """你是一位专业的合同审查专家，擅长从合同文本和用户描述中提取关键信息。

请从给定的信息中提取合同变更协议所需的关键信息，以 JSON 格式返回。"""
            user_prompt = f"""## 用户需求描述
{user_input}

## 原合同内容
{reference_content or '未提供'}

## 任务
请提取以下信息并以 JSON 格式返回：
{{
    "original_contract_info": {{
        "contract_name": "合同名称",
        "signing_date": "签订日期",
        "parties": ["甲方", "乙方"],
        "contract_term": "合同期限",
        "key_terms": {{
            "payment": "付款方式",
            "delivery": "交付方式",
            "liability": "违约责任"
        }}
    }},
    "modification_points": [
        {{
            "clause_number": "条款编号（如：第X条）",
            "clause_title": "条款标题",
            "original_content": "原条款内容摘要",
            "modified_content": "变更后内容（从用户描述中提取）",
            "reason": "变更原因"
        }}
    ],
    "confidence": 0.85
}}

如果无法确定具体变更点，请根据用户描述推断可能的变更内容。
只返回 JSON，不要有其他文字。"""

        try:
            # 使用 LLM 进行信息提取
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            # 解析 JSON 响应
            result_text = response.content.strip()

            # 尝试提取 JSON（处理可能的 markdown 代码块）
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            extracted_info = json.loads(result_text)
            extracted_info["processing_type"] = processing_type

            logger.info(f"[RequirementAnalyzer] 信息提取成功: {list(extracted_info.keys())}")
            return extracted_info

        except json.JSONDecodeError as e:
            logger.warning(f"[RequirementAnalyzer] JSON 解析失败: {e}")
            # 降级：返回基本结构
            return {
                "processing_type": processing_type,
                "original_contract_info": {
                    "contract_name": "待确认",
                    "signing_date": "待确认",
                    "parties": [],
                    "contract_term": "",
                    "key_terms": {}
                },
                "termination_reason" if processing_type == "contract_termination" else "modification_reason": user_input[:200],
                "confidence": 0.3
            }
        except Exception as e:
            logger.error(f"[RequirementAnalyzer] 信息提取失败: {e}", exc_info=True)
            return {}
