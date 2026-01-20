# backend/app/services/contract_generation/agents/single_contract_generation_service.py
"""
单一合同生成服务（全新合同场景）

核心功能：
整合单一合同场景下全新合同生成的完整流程：
1. 基于用户输入信息在合同模板库进行模板匹配
2. 输出模板匹配情况及需求澄清表单，由用户确认
3. 如果匹配到合同模板，且用户也确认使用模板改写合同，则由AI基于用户需求，在匹配的合同模板基础上改写合同
4. 如果没有匹配到合同模板，或者用户选择不选用模板改写，则由AI基于用户输入信息+补充的需求澄清表单来写合同

使用场景：
- 仅在用户需求被判定为"单一合同" → "全新合同"时使用
"""

import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI

from .clarification_form_generator import ClarificationFormGenerator
from .models import RequirementType, SingleContractType

logger = logging.getLogger(__name__)


# ==================== 结果数据模型 ====================

class TemplateMatchAndFormResult(Dict[str, Any]):
    """模板匹配和澄清表单结果"""
    # 是否成功
    success: bool

    # 需求分析结果
    analysis_result: Optional[Dict[str, Any]]

    # 模板匹配结果
    template_match_result: Optional[Dict[str, Any]]

    # 需求澄清表单
    clarification_form: Optional[Dict[str, Any]]

    # 错误信息
    error: Optional[str]


class ContractGenerationResult(Dict[str, Any]):
    """合同生成结果"""
    # 是否成功
    success: bool

    # 生成的合同内容
    contract_content: Optional[str]

    # 使用的模板信息（如果使用了模板）
    template_info: Optional[Dict[str, Any]]

    # 错误信息
    error: Optional[str]


# ==================== 单一合同生成服务 ====================

class SingleContractGenerationService:
    """
    单一合同生成服务（全新合同场景）

    整合以下组件：
    - ContractIntentAnalyzer: 合同意图分析
    - StructuralTemplateMatcher: 模板匹配
    - ClarificationFormGenerator: 澄清表单生成
    - ContractDrafterAgent: 合同起草
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.form_generator = ClarificationFormGenerator(llm)

        # 延迟导入其他组件（避免循环依赖）
        self._intent_analyzer = None
        self._template_matcher = None
        self._drafter = None

    def _get_intent_analyzer(self):
        """获取意图分析器"""
        if self._intent_analyzer is None:
            from .contract_intent_analyzer import get_contract_intent_analyzer
            self._intent_analyzer = get_contract_intent_analyzer(self.llm)
        return self._intent_analyzer

    def _get_template_matcher(self):
        """获取模板匹配器"""
        if self._template_matcher is None:
            from ..structural import get_structural_template_matcher
            from app.database import get_db

            # 获取数据库会话
            db = next(get_db())
            self._template_matcher = get_structural_template_matcher(db)
        return self._template_matcher

    def _get_drafter(self):
        """获取合同起草器"""
        if self._drafter is None:
            from .contract_drafter import ContractDrafterAgent
            self._drafter = ContractDrafterAgent(self.llm)
        return self._drafter

    def _load_legal_features_from_knowledge_graph(self, contract_type: str) -> Dict[str, Any]:
        """
        从知识图谱加载法律特征

        Args:
            contract_type: 合同类型名称

        Returns:
            法律特征字典，如果未找到则返回空字典
        """
        try:
            from app.services.common.contract_knowledge_db_service import contract_knowledge_db_service

            kg = contract_knowledge_db_service

            # 先尝试精确匹配
            definition = kg.get_by_name(contract_type)

            # 如果精确匹配失败，尝试模糊搜索
            if not definition:
                search_results = kg.search_by_keywords(contract_type)
                if search_results:
                    # 使用第一个结果（数据库版本直接返回列表）
                    definition = search_results[0]
                    logger.info(f"[_load_legal_features_from_knowledge_graph] 模糊匹配: '{contract_type}' -> '{definition['name']}'")

            if definition and definition.get("legal_features"):
                features_dict = definition["legal_features"]
                logger.info(f"[_load_legal_features_from_knowledge_graph] 从知识图谱加载法律特征成功: {definition['name']}")
                logger.info(f"  - transaction_nature: {features_dict.get('transaction_nature')}")
                logger.info(f"  - contract_object: {features_dict.get('contract_object')}")
                logger.info(f"  - stance: {features_dict.get('stance')}")
                return features_dict
            else:
                logger.warning(f"[_load_legal_features_from_knowledge_graph] 知识图谱中未找到合同类型: {contract_type}")
                # 返回空特征字典（而不是 None），避免后续代码报错
                return {}
        except Exception as e:
            logger.error(f"[_load_legal_features_from_knowledge_graph] 加载法律特征失败: {e}", exc_info=True)
            return {}

    def analyze_and_get_form(
        self,
        user_input: str,
        uploaded_files: List[str] = None,
        context: Dict[str, Any] = None
    ) -> TemplateMatchAndFormResult:
        """
        第一步：分析需求并获取澄清表单

        流程：
        1. 使用 ContractIntentAnalyzer 分析用户意图，识别合同类型
        2. 使用 StructuralTemplateMatcher 进行模板匹配
        3. 使用 ClarificationFormGenerator 生成需求澄清表单（包含模板选择确认）

        Args:
            user_input: 用户的自然语言输入
            uploaded_files: 上传的文件列表（可选）
            context: 额外上下文信息（可选）

        Returns:
            TemplateMatchAndFormResult: 包含分析结果、模板匹配结果和澄清表单
        """
        try:
            logger.info("[SingleContractGenerationService] 开始分析需求并生成澄清表单")

            # Step 1: 意图分析
            intent_analyzer = self._get_intent_analyzer()
            intent_result = intent_analyzer.analyze(user_input, context)

            # 检查意图分析结果
            if intent_result is None:
                logger.error("[SingleContractGenerationService] 意图分析返回 None")
                raise ValueError("意图分析失败：返回结果为空")

            # Step 1.5: 从知识图谱加载法律特征
            legal_features = self._load_legal_features_from_knowledge_graph(intent_result.contract_type)

            # 构建分析结果（与 RequirementAnalyzer 格式兼容）
            analysis_result = {
                "processing_type": "single_contract",
                "contract_classification": {
                    "contract_type": intent_result.contract_type,
                    "primary_type": intent_result.contract_type,
                },
                "legal_features": legal_features,  # 添加法律特征
                "key_info": {
                    "合同类型": intent_result.contract_type,
                    **(intent_result.key_elements or {}),
                },
                "needs_clarification": intent_result.needs_clarification,
                "clarification_questions": intent_result.clarification_questions,
            }

            logger.info(f"[SingleContractGenerationService] 加载法律特征: nature={legal_features.get('transaction_nature')}, object={legal_features.get('contract_object')}, stance={legal_features.get('stance')}")

            # Step 2: 模板匹配
            matcher = self._get_template_matcher()
            template_match_result = matcher.match(analysis_result, user_id=None)

            # 转换为字典格式
            template_match_dict = {
                "template_id": template_match_result.template_id,
                "template_name": template_match_result.template_name,
                "template_file_url": template_match_result.template_file_url,
                "match_level": template_match_result.match_level.value,
                "match_reason": template_match_result.match_reason,
                "structural_differences": template_match_result.structural_differences,
                "mismatch_reasons": template_match_result.mismatch_reasons,
            }

            logger.info(f"[SingleContractGenerationService] 模板匹配: {template_match_result.match_level.value} - {template_match_result.template_name}")

            # Step 3: 生成澄清表单
            clarification_form = self.form_generator.generate_form(
                user_input=user_input,
                analysis_result=analysis_result,
                template_match_result=template_match_dict,
                knowledge_graph_features=None
            )

            logger.info("[SingleContractGenerationService] 分析和表单生成完成")

            return TemplateMatchAndFormResult({
                "success": True,
                "analysis_result": analysis_result,
                "template_match_result": template_match_dict,
                "clarification_form": clarification_form,
                "error": None,
            })

        except Exception as e:
            logger.error(f"[SingleContractGenerationService] 分析失败: {str(e)}", exc_info=True)
            return TemplateMatchAndFormResult({
                "success": False,
                "analysis_result": None,
                "template_match_result": None,
                "clarification_form": None,
                "error": str(e),
            })

    def generate_contract(
        self,
        user_input: str,
        form_data: Dict[str, Any],
        analysis_result: Dict[str, Any],
        template_match_result: Dict[str, Any],
        uploaded_files: List[str] = None
    ) -> ContractGenerationResult:
        """
        第二步：根据表单数据生成合同

        根据用户在澄清表单中的选择：
        - 如果选择使用模板 → 基于模板改写
        - 如果选择不使用模板 → AI从零生成

        Args:
            user_input: 用户原始输入
            form_data: 用户填写的表单数据
            analysis_result: 需求分析结果
            template_match_result: 模板匹配结果
            uploaded_files: 上传的文件列表（可选）

        Returns:
            ContractGenerationResult: 生成的合同内容和相关信息
        """
        try:
            logger.info("[SingleContractGenerationService] 开始生成合同")

            # 从表单数据中提取用户选择的合同立场
            user_selected_stance = form_data.get("contract_stance", "neutral")
            stance_mapping = {
                "party_a": "甲方",
                "party_b": "乙方",
                "neutral": "中立"
            }
            stance_text = stance_mapping.get(user_selected_stance, "中立")
            logger.info(f"[SingleContractGenerationService] 用户选择立场: {stance_text} ({user_selected_stance})")

            # 更新分析结果中的立场信息
            if "legal_features" in analysis_result:
                analysis_result["legal_features"]["stance"] = stance_text
            if "key_info" in analysis_result:
                analysis_result["key_info"]["立场"] = stance_text

            # 检查用户是否选择使用模板（通过按钮选择）
            use_template = form_data.get("use_template", "skip")
            logger.info(f"[SingleContractGenerationService] 用户模板选择: {use_template}")

            # 合并用户输入和表单数据
            enhanced_input = self._merge_input_with_form(user_input, form_data)

            # 获取模板内容（如果用户选择使用）
            template_content = None
            template_info = None

            if use_template == "use" and template_match_result.get("match_level") != "none":
                # 加载模板内容
                template_content = self._load_template_content(template_match_result)
                template_info = {
                    "template_id": template_match_result.get("template_id"),
                    "template_name": template_match_result.get("template_name"),
                    "match_level": template_match_result.get("match_level"),
                }

            # 生成合同
            drafter = self._get_drafter()

            if template_content:
                # 基于模板改写
                logger.info(f"[SingleContractGenerationService] 使用模板改写: {template_info['template_name']}")
                contract_content = self._draft_with_template(
                    drafter,
                    analysis_result,
                    template_content,
                    enhanced_input,
                    template_match_result
                )
            else:
                # AI从零生成
                logger.info("[SingleContractGenerationService] AI从零生成合同")
                contract_content = self._draft_from_scratch(
                    drafter,
                    analysis_result,
                    enhanced_input,
                    template_match_result,
                    user_input,
                    form_data
                )

            logger.info("[SingleContractGenerationService] 合同生成完成")

            return ContractGenerationResult({
                "success": True,
                "contract_content": contract_content,
                "template_info": template_info,
                "error": None,
            })

        except Exception as e:
            logger.error(f"[SingleContractGenerationService] 合同生成失败: {str(e)}", exc_info=True)
            return ContractGenerationResult({
                "success": False,
                "contract_content": None,
                "template_info": None,
                "error": str(e),
            })

    def _merge_input_with_form(self, user_input: str, form_data: Dict[str, Any]) -> str:
        """合并用户输入和表单数据"""
        sections = form_data.get("sections", [])
        additional_info = []

        for section in sections:
            section_title = section.get("section_title", "")
            fields = section.get("fields", [])

            section_info = [f"\n## {section_title}"]
            for field in fields:
                field_id = field.get("field_id")
                label = field.get("label")

                # 从表单数据中获取值（可能在根级别或在 sections 下）
                value = form_data.get(field_id)

                if value and str(value).strip():  # 只添加有值的字段
                    section_info.append(f"- {label}: {value}")

            if len(section_info) > 1:
                additional_info.extend(section_info)

        if additional_info:
            return user_input + "\n\n" + "\n".join(additional_info)
        return user_input

    def _load_template_content(self, template_match_result: Dict[str, Any]) -> Optional[str]:
        """加载模板内容"""
        try:
            from ..structural.template_store import TemplateStore
            store = TemplateStore()

            template_id = template_match_result.get("template_id")
            if template_id:
                template = store.get_template_by_id(template_id)
                if template:
                    return template.content

            return None

        except Exception as e:
            logger.warning(f"[SingleContractGenerationService] 加载模板内容失败: {e}")
            return None

    def _draft_with_template(
        self,
        drafter,
        analysis_result: Dict[str, Any],
        template_content: str,
        enhanced_input: str,
        template_match_result: Dict[str, Any]
    ) -> str:
        """基于模板起草合同"""
        # 构建策略
        strategy = {
            "generation_type": "template_based",
            "use_template": True,
            "template_match_level": template_match_result.get("match_level"),
        }

        # 使用 drafter 的模板起草方法
        # 注意：这里需要适配现有的接口
        # 如果 ContractDrafterAgent 有 _draft_with_template_new 方法，使用它
        if hasattr(drafter, '_draft_with_template_new'):
            content, _ = drafter._draft_with_template_new(
                analysis_result=analysis_result,
                template_content=template_content,
                strategy=strategy,
                reference_content=enhanced_input,
                knowledge_graph_features=None
            )
            return content
        else:
            # 降级方案：使用通用的 draft 方法
            return drafter.draft(
                requirement={
                    **analysis_result,
                    "user_input": enhanced_input,
                    "template_content": template_content,
                }
            )

    def _draft_from_scratch(
        self,
        drafter,
        analysis_result: Dict[str, Any],
        enhanced_input: str,
        template_match_result: Dict[str, Any],
        user_input: str = None,
        form_data: Dict[str, Any] = None
    ) -> str:
        """
        从零起草合同（支持两阶段生成）

        Args:
            drafter: 合同起草器实例
            analysis_result: 需求分析结果
            enhanced_input: 增强的用户输入
            template_match_result: 模板匹配结果
            user_input: 原始用户输入（用于两阶段生成）
            form_data: 表单数据（用于两阶段生成）

        Returns:
            str: 生成的合同内容
        """
        # ✨ 选择生成策略
        strategy = self._select_generation_strategy(analysis_result, template_match_result)

        # ✨ 如果启用两阶段生成
        if strategy.get("use_two_stage"):
            logger.info("[SingleContractGenerationService] 使用两阶段生成")
            try:
                from .two_stage_contract_drafter import get_two_stage_drafter

                two_stage_drafter = get_two_stage_drafter()

                # 构建知识图谱特征
                knowledge_graph_features = {
                    "legal_features": analysis_result.get("legal_features", {}),
                    "usage_scenario": analysis_result.get("key_info", {}).get("适用场景", ""),
                    "legal_basis": analysis_result.get("legal_features", {}).get("法律依据", []),
                }

                # 两阶段生成
                contract_content = two_stage_drafter.draft_with_two_stages(
                    analysis_result=analysis_result,
                    knowledge_graph_features=knowledge_graph_features,
                    user_input=user_input or enhanced_input,
                    form_data=form_data or {}
                )

                logger.info("[SingleContractGenerationService] 两阶段生成完成")
                return contract_content

            except Exception as e:
                logger.error(f"[SingleContractGenerationService] 两阶段生成失败: {e}，降级到单次生成", exc_info=True)
                # 降级到单次生成
                pass

        # 单次 AI 生成（原有逻辑）
        strategy["generation_type"] = "ai_generated"

        # 使用 drafter 的从零起草方法
        if hasattr(drafter, 'draft_from_scratch'):
            return drafter.draft_from_scratch(
                analysis_result=analysis_result,
                reference_content=enhanced_input,
                strategy=strategy,
                knowledge_graph_features=None
            )
        else:
            # 降级方案：使用通用的 draft 方法
            return drafter.draft(
                requirement={
                    **analysis_result,
                    "user_input": enhanced_input,
                }
            )

    def _select_generation_strategy(
        self,
        analysis_result: Dict[str, Any],
        template_match_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        选择生成策略

        Args:
            analysis_result: 需求分析结果
            template_match_result: 模板匹配结果

        Returns:
            Dict: 生成策略配置
        """
        from ..strategy.generation_strategy import get_strategy_selector

        selector = get_strategy_selector()

        # 使用策略选择器选择策略
        strategy = selector.select_strategy(
            match_result=template_match_result,
            analysis_result=analysis_result
        )

        # 转换为字典格式
        return strategy.to_dict()


def get_single_contract_generation_service(llm: ChatOpenAI) -> SingleContractGenerationService:
    """获取单一合同生成服务实例"""
    return SingleContractGenerationService(llm)
