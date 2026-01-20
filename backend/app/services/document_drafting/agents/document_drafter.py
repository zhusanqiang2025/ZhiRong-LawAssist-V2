# backend/app/services/document_drafting/agents/document_drafter.py
"""
文书起草 Agent

功能：
1. 根据需求分析结果起草各类文书内容
2. 支持函件类（律师函、催告函等）和司法文书类（起诉状、答辩状等）
3. 生成规范的 Markdown 格式内容
4. 支持基于专业模板的增强起草
5. 使用模板改写模式（以模板为骨架，根据需求改写）
"""
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class DocumentDrafterAgent:
    """
    文书起草 Agent

    根据用户需求和分析结果，起草完整的法律文书内容
    支持函件类和司法文书类两大类型
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.system_prompt = self._build_system_prompt()

    def draft_with_template(
        self,
        analysis_result: Dict,
        template_content: str,
        strategy: Dict,
        reference_content: str = "",
        knowledge_graph_features: Dict = None
    ) -> Tuple[str, Optional[Dict]]:
        """
        使用模板起草文书（核心方法）

        核心逻辑：以模板为骨架，根据用户需求改写内容

        Args:
            analysis_result: 需求分析结果（包含 key_info, document_type 等）
            template_content: 模板内容（Markdown 格式）
            strategy: 生成策略信息
            reference_content: 参考资料内容
            knowledge_graph_features: 知识图谱法律特征

        Returns:
            Tuple[str, Optional[Dict]]: (文书内容, 模板信息)
        """
        try:
            # 构建基础提示词
            base_prompt = self._build_base_prompt(analysis_result)

            # 构建模板信息
            document_type = analysis_result.get("document_type", "未知文书")
            template_info = {
                "name": strategy.get("template_name", f"{document_type}模板"),
                "category": strategy.get("template_category", "文书模板"),
                "match_source": "local",
                "description": f"使用 {document_type} 的本地 Markdown 模板"
            }

            # 构建模板改写提示词
            enhanced_prompt = f"""{base_prompt}

---

## 📋 文书模板改写任务

请基于以下文书模板进行改写：

### 改写要求
1. **以模板为骨架**：完全保留模板的章节结构和条款框架
2. **替换关键信息**：根据用户需求替换模板中的占位符和通用内容
3. **调整具体条款**：根据用户的具体情况修改条款细节
4. **保持专业性**：维持模板的法律严谨性和规范表达
5. **内容完整**：确保用户提供的所有关键信息都体现在文书中

### 改写工作流程

请严格按照以下步骤进行改写：

#### 第一步：理解模板结构
仔细分析下方的文书模板，理解其：
- 章节结构和条款顺序
- 专业法律术语的使用方式
- 关键条款的表述方式

#### 第二步：提取用户需求
从上方的"用户需求信息"中提取：
- 文书主体信息（原告/被告、收件人等）
- 核心事实和理由
- 具体请求和要求
- 时间、地点等关键信息

#### 第三步：执行改写
**重要：以模板为骨架进行改写，而非重新生成**

1. **保留结构**：完全保留模板的章节顺序和框架
2. **替换主体**：将模板中的占位符替换为用户提供的具体信息
3. **修改内容**：根据用户需求调整具体条款内容
4. **增加细节**：如有特殊要求，在相应章节增加细节
5. **保持专业性**：维持模板的法律严谨性和专业表达

### 待改写的文书模板

```
{template_content}
```

---

"""

            # 添加知识图谱法律特征（如果有）
            if knowledge_graph_features:
                legal_features = knowledge_graph_features.get("legal_features")
                if legal_features:
                    enhanced_prompt += f"""
## 📚 知识图谱法律特征

系统已为您匹配到该类文书的标准法律特征，请在改写时参考：

### 法律特征
- **交易性质**：{legal_features.get('transaction_nature', 'N/A')}
- **文书标的**：{legal_features.get('contract_object', 'N/A')}
- **起草立场**：{legal_features.get('stance', 'N/A')}

### 适用场景
{knowledge_graph_features.get('usage_scenario', 'N/A')}

**请确保改写的文书符合上述法律特征和适用场景。**

---

"""

            # 添加参考资料（如果有）
            if reference_content:
                enhanced_prompt += f"""
## 参考资料

{reference_content}

"""

            enhanced_prompt += """
请开始改写，输出完整的文书内容（Markdown 格式）。
"""

            # 调用 LLM
            response = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=enhanced_prompt)
            ])

            content = response.content.strip()
            logger.info(f"[DocumentDrafter] 文书起草完成，类型: {document_type}, 长度: {len(content)} 字符")

            return content, template_info

        except Exception as e:
            logger.error(f"[DocumentDrafter] 模板起草失败: {str(e)}", exc_info=True)
            return "", None

    def draft_from_scratch(
        self,
        analysis_result: Dict,
        reference_content: str = "",
        knowledge_graph_features: Dict = None
    ) -> str:
        """
        从零开始起草文书（不使用模板）

        Args:
            analysis_result: 需求分析结果
            reference_content: 参考资料内容
            knowledge_graph_features: 知识图谱法律特征

        Returns:
            Markdown 格式的文书内容
        """
        try:
            # 构建基础提示词
            base_prompt = self._build_base_prompt(analysis_result)

            # 添加知识图谱特征和参考资料
            enhanced_prompt = base_prompt

            if knowledge_graph_features:
                legal_features = knowledge_graph_features.get("legal_features")
                if legal_features:
                    enhanced_prompt += f"""

## 📚 知识图谱法律特征

- **交易性质**：{legal_features.get('transaction_nature', 'N/A')}
- **文书标的**：{legal_features.get('contract_object', 'N/A')}
- **起草立场**：{legal_features.get('stance', 'N/A')}
"""

            if reference_content:
                enhanced_prompt += f"""

## 参考资料

{reference_content}
"""

            enhanced_prompt += """

---

请根据以上信息起草一份完整的法律文书，使用 Markdown 格式。
"""

            # 调用 LLM
            response = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=enhanced_prompt)
            ])

            content = response.content.strip()
            logger.info(f"[DocumentDrafter] 从零起草完成，长度: {len(content)} 字符")

            return content

        except Exception as e:
            logger.error(f"[DocumentDrafter] 从零起草失败: {str(e)}", exc_info=True)
            return ""

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的法律文书起草专家。你的任务是根据用户需求起草完整的法律文书内容。

## 起草要求

### 内容要求
1. 文书完整、逻辑清晰
2. 用词准确、符合法律规范
3. 保护当事人合法权益
4. 引用法律条文准确
5. 结构规范、易于阅读

### 格式要求
使用 Markdown 格式，包含：
- 一级标题：文书名称（# 文书名称）
- 二级标题：主要部分（## 一、XXX）
- 三级标题：细分内容（### （一）XXX）
- 粗体：重要内容（**重要内容**）
- 列表：多项内容（1. 列表项）

### 文书结构
根据文书类型，通常包含：
1. 文书名称
2. 当事人信息
3. 诉讼请求/要求
4. 事实与理由
5. 法律依据
6. 结语/落款
7. 日期和签名

### 支持的文书类型

**函件类：**
- 律师函：用于催告、通知、警告等
- 催告函：催告履行义务
- 通知函：各类通知告知
- 法律意见书：专业法律意见

**司法文书类：**
- 民事起诉状：提起民事诉讼
- 答辩状：被告答辩
- 上诉状：不服判决提起上诉
- 证据清单：列举证据
- 申请书：各类程序申请
- 授权委托书：委托代理人

## 输出要求
- 只输出文书内容，不要解释说明
- 确保格式规范，便于转换为 Word 文档
- 使用标准的法律文书用语
"""

    def _build_base_prompt(self, analysis_result: Dict) -> str:
        """构建基础提示词"""
        key_info = analysis_result.get("key_info", {})
        document_type = analysis_result.get("document_type", "未知文书")

        prompt = f"""## 用户需求信息

文书类型：{document_type}

关键信息：
"""

        # 添加关键信息
        for key, value in key_info.items():
            prompt += f"- {key}：{value}\n"

        prompt += """

## 起草要求

请根据以上信息起草一份完整的法律文书。
"""

        return prompt

    def load_template_file(self, template_file: str) -> str:
        """
        加载模板文件内容

        Args:
            template_file: 模板文件名（如 lawyer_letter.md）

        Returns:
            模板文本内容
        """
        try:
            # 模板目录
            template_dir = Path(__file__).parent.parent.parent.parent / "templates" / "documents"
            template_path = template_dir / template_file

            if not template_path.exists():
                logger.warning(f"[DocumentDrafter] 模板文件不存在: {template_path}")
                return ""

            # 读取 Markdown 文件
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()

            logger.info(f"[DocumentDrafter] 成功加载模板: {template_file}, 长度: {len(content)} 字符")
            return content

        except Exception as e:
            logger.error(f"[DocumentDrafter] 加载模板失败: {str(e)}", exc_info=True)
            return ""
