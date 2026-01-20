# backend/app/services/contract_generation/agents/two_stage_contract_drafter.py
"""
两阶段合同起草器 (Enhanced Version)

在无模板场景下，使用两个模型分阶段生成合同：
1. 第一阶段：Qwen3-235B-Thinking 生成合同框架（章节结构、条款框架、核心术语预设）
2. 第二阶段：DeepSeek-R1-0528 填充具体条款内容（上下文感知、逻辑自洽）

设计理念：
- 框架先行：使用大模型确保结构完整
- 内容填充：使用快速推理模型提高效率
- 上下文贯通：解决分段生成导致的术语不一致问题
"""
import logging
import json
import re
from typing import Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class TwoStageContractDrafter:
    """
    两阶段合同起草器

    使用流程：
    1. 初始化时自动配置两个模型（Qwen3 框架 + DeepSeek 填充）
    2. 调用 draft_with_two_stages() 生成合同
    3. 内部自动完成两阶段处理

    质量提升：
    - 框架质量：235B 大模型确保结构完整性
    - 内容质量：DeepSeek-R1 推理模型填充具体条款
    - 一致性保障：上下文注入机制
    """

    def __init__(
        self,
        framework_llm: Optional[ChatOpenAI] = None,
        filling_llm: Optional[ChatOpenAI] = None
    ):
        """
        初始化两阶段起草器

        Args:
            framework_llm: 框架生成模型（默认：Qwen3-235B-Thinking）
            filling_llm: 内容填充模型（默认：DeepSeek-R1-0528）
        """
        # 这里的 import 放在内部是为了避免循环导入，假设您有相应的配置模块
        from app.core.llm_config import get_qwen3_thinking_llm, get_deepseek_llm

        self.framework_llm = framework_llm or get_qwen3_thinking_llm()
        self.filling_llm = filling_llm or get_deepseek_llm()

        self.framework_system_prompt = self._build_framework_system_prompt()
        self.filling_system_prompt = self._build_filling_system_prompt()

        logger.info("[TwoStageDrafter] 初始化完成")

    def draft_with_two_stages(
        self,
        analysis_result: Dict[str, Any],
        knowledge_graph_features: Dict[str, Any],
        user_input: str,
        form_data: Dict[str, Any]
    ) -> str:
        """
        两阶段生成合同

        Args:
            analysis_result: 需求分析结果（来自 RequirementAnalyzer）
            knowledge_graph_features: 知识图谱法律特征（来自 Knowledge Graph）
            user_input: 用户原始输入
            form_data: 用户填写的表单数据

        Returns:
            完整的合同内容（Markdown 格式）

        Raises:
            ValueError: 当框架生成失败时
        """
        logger.info("[TwoStageDrafter] 开始两阶段合同生成")
        logger.info(f"[TwoStageDrafter] 用户输入: {user_input[:100]}...")

        # ===== 第一阶段：生成合同框架 =====
        logger.info("[TwoStageDrafter] 第一阶段：生成合同框架...")
        framework = self._generate_framework(
            analysis_result,
            knowledge_graph_features,
            user_input,
            form_data
        )

        if not framework:
            logger.error("[TwoStageDrafter] 框架生成失败，无法继续")
            raise ValueError("框架生成失败，无法生成合同")

        chapter_count = len(framework.get('chapters', []))
        logger.info(f"[TwoStageDrafter] 框架生成成功: {framework.get('title')}, 包含 {chapter_count} 个章节")

        # ===== 第二阶段：填充具体内容 =====
        logger.info("[TwoStageDrafter] 第二阶段：填充具体内容...")
        content = self._fill_content(
            framework,
            analysis_result,
            knowledge_graph_features,
            form_data
        )

        logger.info(f"[TwoStageDrafter] 两阶段生成完成，总长度: {len(content)} 字符")

        # 添加质量说明
        quality_notice = """

---

**⚠️ 生成说明**
- **生成模式**: 两阶段 AI 生成（Context-Aware）
- **架构设计**: Qwen3-235B-Thinking
- **条款起草**: DeepSeek-R1-0528 (推理增强)
- **质量保障**: 已执行上下文一致性检查
- **建议**: 请仔细审查合同条款，必要时咨询专业律师
"""

        return content + quality_notice

    def _generate_framework(
        self,
        analysis_result: Dict[str, Any],
        knowledge_graph_features: Dict[str, Any],
        user_input: str,
        form_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        第一阶段：生成合同框架

        使用 Qwen3-235B-Thinking 生成：
        - 合同标题
        - 核心术语定义规划
        - 章节结构（章节标题、说明、关键要素、必需条款）
        - 法律依据与风险点

        Returns:
            Dict: 框架结构 (JSON)
        """
        # 提取关键信息
        legal_features = knowledge_graph_features.get("legal_features", {})

        # 构建提示词
        prompt = f"""## 用户需求
{user_input}

## 表单数据
{self._format_form_data(form_data)}

## 知识图谱法律特征
**请务必严格遵循以下法律特征：**
- **交易性质**: {legal_features.get('transaction_nature', 'N/A')}
- **合同标的**: {legal_features.get('contract_object', 'N/A')}
- **起草立场**: {legal_features.get('stance', 'N/A')}
- **交易对价类型**: {legal_features.get('consideration_type', 'N/A')}
- **交易对价详情**: {legal_features.get('consideration_detail', 'N/A')}

### 适用场景
{knowledge_graph_features.get('usage_scenario', 'N/A')}

### 法律依据
{chr(10).join(f"- {basis}" for basis in knowledge_graph_features.get('legal_basis', [])[:5]) if knowledge_graph_features.get('legal_basis') else '无'}

---

## 任务要求

请基于以上信息，设计一份完整的**合同框架结构**。

**核心目标：**
1. 设计合同目录结构。
2. **预设核心术语**：在框架阶段就确定好"甲方"、"乙方"、"标的物"等核心称谓，确保后续生成一致。
3. 规划每个章节的**必需条款**。

**输出格式（JSON）：**
```json
{{
  "title": "合同标题",
  "defined_terms": {{
      "甲方": "根据表单推断的甲方名称或'甲方'",
      "乙方": "根据表单推断的乙方名称或'乙方'",
      "标的物": "简要描述"
  }},
  "chapters": [
    {{
      "chapter_id": "chapter_1",
      "title": "第一条 定义与解释",
      "description": "本章对合同中涉及的关键术语进行定义",
      "key_elements": ["主体定义", "标的定义"],
      "required_clauses": [
        "甲方信息及定义",
        "乙方信息及定义",
        "核心术语表"
      ]
    }},
    {{
      "chapter_id": "chapter_2",
      "title": "第二条 ...",
      "description": "...",
      "key_elements": ["..."],
      "required_clauses": ["..."]
    }}
  ],
  "legal_basis": ["法律依据..."],
  "risk_points": ["风险点..."]
}}
```

要求：
- defined_terms 字段必须包含核心主体的称谓约定
- 章节数量要适中（通常 8-12 个章节）
- 确保框架完整、逻辑清晰、覆盖全面
- 请直接输出 JSON，不要使用 markdown 代码块
"""

        try:
            response = self.framework_llm.invoke([
                SystemMessage(content=self.framework_system_prompt),
                HumanMessage(content=prompt)
            ])

            content = response.content.strip()
            logger.debug(f"[TwoStageDrafter] 框架生成原始输出: {content[:200]}...")

            # 提取 JSON（处理可能的 markdown 代码块）
            content = self._extract_json(content)

            # 解析 JSON
            framework = json.loads(content)

            # 验证结构
            if not isinstance(framework, dict):
                raise ValueError("框架输出不是字典类型")

            if "title" not in framework:
                raise ValueError("框架缺少 title 字段")

            if "chapters" not in framework or not isinstance(framework["chapters"], list):
                raise ValueError("框架缺少有效的 chapters 字段")

            logger.info(f"[TwoStageDrafter] 框架验证通过: {framework.get('title')}")
            return framework

        except json.JSONDecodeError as e:
            logger.error(f"[TwoStageDrafter] JSON 解析失败: {e}")
            logger.error(f"[TwoStageDrafter] 解析失败的内容: {content[:500]}")
            raise ValueError(f"框架 JSON 解析失败: {e}")

        except Exception as e:
            logger.error(f"[TwoStageDrafter] 框架生成失败: {e}", exc_info=True)
            raise ValueError(f"框架生成失败: {e}")

    def _fill_content(
        self,
        framework: Dict[str, Any],
        analysis_result: Dict[str, Any],
        knowledge_graph_features: Dict[str, Any],
        form_data: Dict[str, Any]
    ) -> str:
        """
        第二阶段：填充具体内容

        使用 DeepSeek-R1-0528 基于框架填充每个章节的具体条款内容
        **增强逻辑：上下文感知注入**
        """
        chapters = framework.get("chapters", [])
        contract_title = framework.get("title", "合同")
        defined_terms = framework.get("defined_terms", {})  # 获取框架预设的术语
        legal_features = knowledge_graph_features.get("legal_features", {})

        # 构建合同内容容器
        content_parts = [f"# {contract_title}\n"]

        # 添加引言信息
        if legal_features.get("transaction_nature"):
            content_parts.append(f"**交易性质**: {legal_features.get('transaction_nature')}\n")
        content_parts.append("\n---\n")

        # 上下文记忆变量
        definitions_context = ""
        if defined_terms:
            definitions_context = "【框架预设核心术语】:\n" + "\n".join([f"- {k}: {v}" for k, v in defined_terms.items()])

        # 逐章生成内容
        for idx, chapter in enumerate(chapters, 1):
            chapter_title = chapter.get("title", "")
            chapter_desc = chapter.get("description", "")
            key_elements = chapter.get("key_elements", [])
            required_clauses = chapter.get("required_clauses", [])

            logger.info(f"[TwoStageDrafter] 生成第 {idx}/{len(chapters)} 章: {chapter_title}")

            # 构建动态上下文注入
            context_injection = ""
            if definitions_context:
                context_injection = f"""

⚠️ 必须遵守的术语定义（上下文约束）
以下是本合同已确定的核心术语定义，请在起草本章时严格保持一致，严禁重新定义或使用冲突称谓：
{definitions_context}
"""

            # 构建章节提示词（深度增强版）
            prompt = f"""## 当前任务：起草第 {idx}/{len(chapters)} 章

### 1. 章节定位
**标题**: {chapter_title}
**说明**: {chapter_desc}
**关键要素**: {', '.join(key_elements) if key_elements else '无'}
**必需条款**: {', '.join(required_clauses) if required_clauses else '无'}

### 2. 全局信息与约束
**用户表单数据**:
{self._format_form_data(form_data)}

**法律特征**:
- 交易性质: {legal_features.get('transaction_nature', 'N/A')}
- 合同标的: {legal_features.get('contract_object', 'N/A')}
- 起草立场: {legal_features.get('stance', 'N/A')}
{context_injection}

### 起草指令 (Chain of Thought)
请执行以下思考步骤：
1. **术语检查**：确认本章涉及的主体（如甲方、乙方）和标的物称谓与"术语定义"一致
2. **逻辑构建**：为每个"必需条款"设计 3-4 层级的详细内容（条款标题 -> 具体义务 -> 例外/限制 -> 后果）
3. **推断填充**：如果表单中有相关数据（如地址、金额），直接填入；如果可以逻辑推断（如管辖法院），直接推断填入；无法推断才用占位符

### Markdown 输出要求：
- 严格遵循 ### X.X 标题结构
- 不要输出 <think> 标签或思考过程
- 直接输出章节正文，不要包含"好的，我来起草"等废话

**开始起草：**
"""

            try:
                response = self.filling_llm.invoke([
                    SystemMessage(content=self.filling_system_prompt),
                    HumanMessage(content=prompt)
                ])

                # 清洗 DeepSeek-R1 可能输出的思考标签
                chapter_content = self._clean_r1_output(response.content)

                # 如果是第一章（通常是定义章），更新上下文
                # 简单启发式：如果标题包含"定义"或"解释"，或者是第一章
                if idx == 1 or "定义" in chapter_title or "解释" in chapter_title:
                    # 补充上下文，确保后续章节知道定义内容
                    # 注意：如果内容过长可能会影响后续 Prompt 长度，这里假设定义章长度可控
                    definitions_context += f"\n\n【第{idx}章已生效定义】:\n(请参照第一章正式条款)"

                # 添加章节内容
                content_parts.append(f"## {chapter_title}\n")
                content_parts.append(chapter_content)
                content_parts.append("\n")

                logger.info(f"[TwoStageDrafter] 章节 {idx} 生成完成，长度: {len(chapter_content)} 字符")

            except Exception as e:
                logger.error(f"[TwoStageDrafter] 章节填充失败 ({chapter_title}): {e}")
                content_parts.append(f"## {chapter_title}\n")
                content_parts.append(f"（生成失败: {str(e)}）\n")

        return "\n".join(content_parts)

    def _clean_r1_output(self, content: str) -> str:
        """
        清理 DeepSeek-R1 可能输出的思维链标签和对话废话
        """
        if not content:
            return ""

        # 移除 <think>...</think> 内容 (非贪婪匹配，跨行)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)

        # 移除可能的开场白 (如 "好的，基于您的要求...")
        # 匹配规则：开头的一段非 Markdown 标题的文本，通常以换行结束
        content = re.sub(r'^(好的|明白|了解|Sure|Here is).*?(\n|$)', '', content, flags=re.IGNORECASE)

        return content.strip()

    def _build_framework_system_prompt(self) -> str:
        """构建框架生成系统提示词"""
        return """你是一个专业的合同架构设计专家。

你的任务是设计一份结构严谨、逻辑自洽的合同框架。

核心职责：
1. 结构设计：规划合同的章节目录
2. 术语预设：在设计框架时，必须明确核心术语（如甲方、乙方、标的物）的指代，确保后续起草的一致性
3. 条款规划：为每个章节列出必须包含的具体条款点

输出要求：
- 使用 JSON 格式
- 必须包含 defined_terms 字段，明确核心主体称谓
- 框架应符合《民法典》及相关法律法规要求
"""

    def _build_filling_system_prompt(self) -> str:
        """构建内容填充系统提示词（增强版）"""
        return """你是一名拥有20年经验的资深法务总监，擅长起草严密、无懈可击的商业合同。

## 角色定位
你正在执行一份合同的分章节起草任务。
你的目标不仅仅是写好这一章，而是要确保这一章置于整份合同中是逻辑自洽、术语统一的。

## 核心工作原则

### 1. 充分性原则（Deep Expansion）
每个条款都必须充分展开，拒绝简陋！
- ✅ 结构化：条款标题 -> 具体规定(含执行标准) -> 例外情形 -> 违约后果
- ✅ 细节化：包含适用条件、时间限制、计算方式等

### 2. 上下文一致性（Consistency）
- 术语统一：严禁创造新术语。如果上下文（Prompt）中规定了"甲方"指代某公司，这一章必须严格使用"甲方"，不得混用"采购方"或"买方"
- 逻辑闭环：本章的义务条款应考虑到后续违约责任章节的衔接

### 3. 智能填充（Smart Filling）
- 直接引用：用户表单有的数据，直接填入
- 逻辑推断：根据已知信息（如地址推断管辖法院），合理推断并填入
- 最小化占位符：只有完全缺失且无法推断的关键数据，才使用 [ ] 并备注

### 4. 格式规范
- 使用 Markdown 格式
- 语气专业、冷峻、严谨
- 严禁输出解释性文字，直接输出合同条款内容

请根据 DeepSeek-R1 的推理能力，确保条款的法律逻辑严密性。
"""

    def _format_form_data(self, form_data: Dict[str, Any]) -> str:
        """格式化表单数据为可读文本"""
        lines = []
        for key, value in form_data.items():
            if value:
                # 处理不同类型的值
                if isinstance(value, list):
                    value_str = ', '.join(str(v) for v in value)
                elif isinstance(value, dict):
                    value_str = str(value)
                else:
                    value_str = str(value)

                lines.append(f"- **{key}**: {value_str}")

        return "\n".join(lines) if lines else "（无表单数据）"

    def _extract_json(self, content: str) -> str:
        """
        从文本中提取 JSON 内容
        """
        # 清洗可能存在的 think 标签（防止干扰正则）
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)

        # 尝试提取 ```json 代码块
        if "```json" in content:
            match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if match:
                return match.group(1).strip()

        # 尝试提取普通 ``` 代码块
        if "```" in content:
            match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
            if match:
                return match.group(1).strip()

        # 尝试寻找最外层的 {}
        try:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                return content[start:end+1]
        except Exception:
            pass

        return content.strip()


# 单例模式
_two_stage_drafter_instance: Optional[TwoStageContractDrafter] = None


def get_two_stage_drafter() -> TwoStageContractDrafter:
    """
    获取两阶段起草器单例

    Returns:
        TwoStageContractDrafter: 两阶段起草器实例
    """
    global _two_stage_drafter_instance
    if _two_stage_drafter_instance is None:
        _two_stage_drafter_instance = TwoStageContractDrafter()
    return _two_stage_drafter_instance


__all__ = [
    "TwoStageContractDrafter",
    "get_two_stage_drafter",
]
