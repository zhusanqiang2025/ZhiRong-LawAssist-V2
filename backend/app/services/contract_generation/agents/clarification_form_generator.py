# backend/app/services/contract_generation/agents/clarification_form_generator.py
"""
需求澄清表单生成器

根据用户需求分析结果和模板匹配情况，AI生成动态需求澄清表单
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


class ClarificationFormGenerator:
    """
    需求澄清表单生成器

    基于以下信息生成需求澄清表单：
    1. 用户原始输入
    2. 需求分析结果（合同类型、法律特征）
    3. 模板匹配结果
    4. 知识图谱特征
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def generate_form(
        self,
        user_input: str,
        analysis_result: Dict[str, Any],
        template_match_result: Optional[Dict[str, Any]] = None,
        knowledge_graph_features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成需求澄清表单

        Args:
            user_input: 用户原始输入
            analysis_result: RequirementAnalyzer 分析结果
            template_match_result: 模板匹配结果
            knowledge_graph_features: 知识图谱法律特征

        Returns:
            {
                "form_title": "需求澄清表单",
                "form_description": "...",
                "sections": [...],
                "summary": {...}
            }
        """
        logger.info("[ClarificationFormGenerator] 开始生成需求澄清表单")

        # 构建上下文
        context = self._build_context(
            user_input, analysis_result, template_match_result, knowledge_graph_features
        )

        # 使用 LLM 生成表单
        form = self._generate_form_with_llm(context)

        # 确保表单包含立场选择章节
        form = self._ensure_stance_selection_section(form, template_match_result)

        logger.info(f"[ClarificationFormGenerator] 表单生成完成，包含 {len(form.get('sections', []))} 个章节")
        return form

    def _build_context(
        self,
        user_input: str,
        analysis_result: Dict[str, Any],
        template_match_result: Optional[Dict[str, Any]],
        knowledge_graph_features: Optional[Dict[str, Any]]
    ) -> str:
        """构建 LLM 上下文"""
        context_parts = []

        # 用户输入
        context_parts.append(f"## 用户输入\n{user_input}")

        # 合同类型分析
        contract_classification = analysis_result.get("contract_classification", {})
        key_info = analysis_result.get("key_info", {})

        context_parts.append("\n## 需求分析结果")
        context_parts.append(f"- 合同类型: {key_info.get('合同类型', '未知')}")
        context_parts.append(f"- 交易性质: {key_info.get('交易性质', '未知')}")
        context_parts.append(f"- 合同标的: {key_info.get('合同标的', '未知')}")
        context_parts.append(f"- 交易对价类型: {key_info.get('交易对价类型', '未知')}")
        context_parts.append(f"- 立场: {key_info.get('立场', '中立')}")

        # 法律特征
        legal_features = analysis_result.get("legal_features", {})
        if legal_features.get("transaction_characteristics"):
            context_parts.append(f"- 交易特征: {legal_features['transaction_characteristics']}")

        # 模板匹配结果
        if template_match_result:
            context_parts.append("\n## 模板匹配结果")
            context_parts.append(f"- 匹配级别: {template_match_result.get('match_level', 'none')}")
            context_parts.append(f"- 匹配模板: {template_match_result.get('template_name', '无')}")
            context_parts.append(f"- 匹配原因: {template_match_result.get('match_reason', '')}")

            if template_match_result.get("structural_differences"):
                context_parts.append(f"- 结构差异: {', '.join(template_match_result['structural_differences'])}")

        # 知识图谱特征
        if knowledge_graph_features:
            context_parts.append("\n## 知识图谱法律特征")
            kg_features = knowledge_graph_features.get("legal_features", {})
            if kg_features:
                context_parts.append(f"- 使用场景: {kg_features.get('usage_scenario', '')}")
                context_parts.append(f"- 法律依据: {', '.join(kg_features.get('legal_basis', []))}")

        return "\n".join(context_parts)

    def _generate_form_with_llm(self, context: str) -> Dict[str, Any]:
        """使用 LLM 生成表单结构"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的合同需求澄清表单生成器。

你的任务是根据用户需求和合同类型，智能生成一个结构化的需求澄清表单。

## 表单设计原则

1. **动态生成字段**：根据合同类型和用户已提供的信息，生成必要的补充字段
2. **避免固定字段**：不要使用固定的字段模板，每个合同类型应该有独特的字段
3. **目标导向**：表单的目标是收集足够信息以生成一份规范完整的合同

## 表单章节结构

表单应该包含以下章节（按顺序）：

1. **合同立场选择**（必填）
   - 字段类型：stance_selection
   - 让用户选择合同起草立场（甲方/乙方/中立）

2. **合同主体信息**（必填）
   - 根据合同类型确定需要哪些主体信息
   - 例如：借款合同需要"出借方"和"借款方"，租赁合同需要"出租方"和"承租方"

3. **合同标的/内容**（必填）
   - 根据合同类型确定
   - 例如：借款金额、租赁物、服务内容等

4. **交易对价**（根据合同类型）
   - 并非所有合同都需要
   - 例如：借款利息、租金金额、服务费用等

5. **履行条款**（必填）
   - 期限、地点、方式等

6. **其他条款**（可选）
   - 违约责任、保密条款、争议解决等

## 字段设计要求

- **从用户输入中提取已知信息**作为 default_value
- **必填字段 required=true**，可选字段 required=false
- **使用合适的字段类型**：text, number, date, textarea, select, radio, money
- **提供清晰的 placeholder 和 label**

## 输出格式

```json
{{
  "form_title": "XXX合同需求信息",
  "form_description": "请补充以下信息以完成合同生成",
  "sections": [
    {{
      "section_id": "stance_selection",
      "section_title": "合同立场",
      "fields": [
        {{
          "field_id": "contract_stance",
          "field_type": "stance_selection",
          "label": "请选择合同起草立场",
          "required": true,
          "default_value": "neutral",
          "options": [
            {{"value": "party_a", "label": "甲方立场"}},
            {{"value": "party_b", "label": "乙方立场"}},
            {{"value": "neutral", "label": "中立立场"}}
          ],
          "description": "AI将基于您选择的立场起草合同条款"
        }}
      ]
    }},
    {{
      "section_id": "parties",
      "section_title": "合同主体",
      "fields": [
        {{
          "field_id": "lender_name",
          "field_type": "text",
          "label": "出借方姓名",
          "placeholder": "请输入出借方姓名",
          "required": true,
          "default_value": "张三"
        }}
      ]
    }}
  ]
}}
```

请根据以下上下文生成表单："""),
            ("user", "{context}\n\n请直接输出需求澄清表单的 JSON 结构，不要使用 markdown 代码块。")
        ])

        try:
            response = self.llm.invoke(prompt.format_messages(context=context))
            content = response.content.strip()

            logger.info(f"[ClarificationFormGenerator] LLM 原始返回:\n{content[:500]}...")

            # 解析 JSON（处理可能的 markdown 代码块）
            import json
            import re

            # 移除可能的 markdown 代码块标记
            if "```json" in content:
                match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if match:
                    content = match.group(1)
                else:
                    logger.warning("[ClarificationFormGenerator] 找到 ```json 标记但无法提取内容")
            elif "```" in content:
                match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
                if match:
                    content = match.group(1)
                else:
                    logger.warning("[ClarificationFormGenerator] 找到 ``` 标记但无法提取内容")

            # 尝试解析 JSON
            try:
                form = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"[ClarificationFormGenerator] JSON 解析失败: {e}")
                logger.error(f"[ClarificationFormGenerator] 解析失败的内容:\n{content}")
                # 返回基础表单
                return self._get_fallback_form(context)

            # 验证表单结构
            if "sections" not in form:
                logger.warning("[ClarificationFormGenerator] LLM 返回的表单缺少 sections 字段")
                return self._get_fallback_form(context)

            # 添加摘要信息
            form = self._add_summary(form, context)

            logger.info(f"[ClarificationFormGenerator] 表单生成成功，包含 {len(form.get('sections', []))} 个章节")
            return form

        except Exception as e:
            logger.error(f"[ClarificationFormGenerator] LLM 生成失败: {e}", exc_info=True)
            # 返回基础表单
            return self._get_fallback_form(context)

    def _add_summary(self, form: Dict[str, Any], context: str) -> Dict[str, Any]:
        """添加表单摘要信息"""
        # 从上下文中提取关键信息
        import re

        summary = {
            "detected_contract_type": "未知",
            "template_match_level": "none",
            "template_name": "无",
            "missing_info": []
        }

        # 提取合同类型
        type_match = re.search(r'合同类型:\s*([^\n-]+)', context)
        if type_match:
            summary["detected_contract_type"] = type_match.group(1).strip()

        # 提取模板匹配信息
        level_match = re.search(r'匹配级别:\s*(\w+)', context)
        if level_match:
            summary["template_match_level"] = level_match.group(1).strip()

        name_match = re.search(r'匹配模板:\s*([^\n-]+)', context)
        if name_match:
            summary["template_name"] = name_match.group(1).strip()

        # 找出缺失信息（required 字段中没有 default_value 的）
        missing = []
        for section in form.get("sections", []):
            for field in section.get("fields", []):
                if field.get("required") and not field.get("default_value"):
                    missing.append(field.get("label", field.get("field_id")))
        summary["missing_info"] = missing

        form["summary"] = summary
        return form

    def _get_fallback_form(self, context: str) -> Dict[str, Any]:
        """获取备用表单（当 LLM 失败时）"""
        return {
            "form_title": "合同需求信息",
            "form_description": "请补充以下信息以完成合同生成",
            "sections": [
                {
                    "section_id": "parties",
                    "section_title": "合同主体",
                    "fields": [
                        {
                            "field_id": "party_a_name",
                            "field_type": "text",
                            "label": "甲方名称",
                            "placeholder": "请输入甲方全称",
                            "required": True,
                            "default_value": None
                        },
                        {
                            "field_id": "party_b_name",
                            "field_type": "text",
                            "label": "乙方名称",
                            "placeholder": "请输入乙方全称",
                            "required": True,
                            "default_value": None
                        }
                    ]
                },
                {
                    "section_id": "contract_content",
                    "section_title": "合同内容",
                    "fields": [
                        {
                            "field_id": "contract_amount",
                            "field_type": "money",
                            "label": "合同金额",
                            "placeholder": "请输入合同金额",
                            "required": True,
                            "default_value": None
                        },
                        {
                            "field_id": "start_date",
                            "field_type": "date",
                            "label": "开始日期",
                            "placeholder": "请选择合同开始日期",
                            "required": True,
                            "default_value": None
                        },
                        {
                            "field_id": "end_date",
                            "field_type": "date",
                            "label": "结束日期",
                            "placeholder": "请选择合同结束日期",
                            "required": True,
                            "default_value": None
                        }
                    ]
                }
            ],
            "summary": {
                "detected_contract_type": "未知",
                "template_match_level": "none",
                "template_name": "无",
                "missing_info": ["甲方名称", "乙方名称", "合同金额", "日期"]
            }
        }

    def _ensure_stance_selection_section(
        self,
        form: Dict[str, Any],
        template_match_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        确保表单包含合同立场选择章节

        如果 LLM 生成的表单没有立场选择章节，则在开头添加一个
        """
        # 检查是否已有立场选择章节
        for section in form.get("sections", []):
            if section.get("section_id") == "stance_selection":
                return form  # 已存在，无需添加

        # 从上下文中提取默认立场（如果有的话）
        import re
        default_stance = "neutral"  # 默认中立

        # 尝试从模板匹配结果中获取立场信息
        if template_match_result:
            template_stance = template_match_result.get("stance")
            if template_stance:
                if template_stance == "甲方":
                    default_stance = "party_a"
                elif template_stance == "乙方":
                    default_stance = "party_b"
                elif template_stance == "中立":
                    default_stance = "neutral"

        # 构建立场选择章节
        stance_selection_section = {
            "section_id": "stance_selection",
            "section_title": "合同立场",
            "fields": [
                {
                    "field_id": "contract_stance",
                    "field_type": "stance_selection",
                    "label": "请选择合同起草立场",
                    "placeholder": None,
                    "required": True,
                    "default_value": default_stance,
                    "options": [
                        {
                            "value": "party_a",
                            "label": "甲方立场（保护甲方权益）",
                            "description": "合同条款将倾向于保护甲方的利益"
                        },
                        {
                            "value": "party_b",
                            "label": "乙方立场（保护乙方权益）",
                            "description": "合同条款将倾向于保护乙方的利益"
                        },
                        {
                            "value": "neutral",
                            "label": "中立立场（公平平衡）",
                            "description": "合同条款将保持公平平衡，不偏向任何一方"
                        }
                    ],
                    "description": "选择立场后，AI将基于您选择的立场来起草合同条款，确保条款安排符合您的利益需求。"
                }
            ]
        }

        # 将立场选择章节插入到开头
        form["sections"] = [stance_selection_section] + form.get("sections", [])

        return form
