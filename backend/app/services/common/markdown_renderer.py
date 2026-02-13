# backend/app/services/markdown_renderer.py
"""
Markdown 渲染服务
将 Markdown 格式的文本渲染为干净的 HTML，用于前端显示
"""
import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class MarkdownRenderer:
    """
    Markdown 渲染器

    功能：
    1. 将 Markdown 标题转换为 HTML
    2. 将列表转换为 HTML
    3. 清理 AI 输出的特殊字符
    4. 保持格式但移除 Markdown 符号
    """

    # 需要清理的特殊字符
    SPECIAL_CHARS = {
        '≈': '约',
        '≤': '≤',
        '≥': '≥',
    }

    def render(self, markdown_text: str) -> str:
        """
        将 Markdown 文本渲染为 HTML

        Args:
            markdown_text: Markdown 格式的文本

        Returns:
            HTML 格式的文本
        """
        if not markdown_text:
            return ""

        # 预处理
        text = self._preprocess(markdown_text)

        # 渲染各个元素
        text = self._render_headers(text)
        text = self._render_lists(text)
        text = self._render_bold(text)
        text = self._render_code_blocks(text)
        text = self._render_horizontal_rules(text)
        text = self._render_paragraphs(text)

        return text

    def _preprocess(self, text: str) -> str:
        """
        预处理文本

        Args:
            text: 原始文本

        Returns:
            预处理后的文本
        """
        # 替换特殊字符
        for char, replacement in self.SPECIAL_CHARS.items():
            text = text.replace(char, replacement)

        # 替换 HTML <br> 标签为换行
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

        # 替换其他 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)

        return text

    def _render_headers(self, text: str) -> str:
        """
        渲染标题

        # 一级标题 → <h1>一级标题</h1>
        ## 二级标题 → <h2>二级标题</h2>
        ### 三级标题 → <h3>三级标题</h3>

        Args:
            text: 文本

        Returns:
            渲染后的文本
        """
        lines = text.split('\n')
        result = []

        for line in lines:
            # 一级标题
            if line.startswith('# ') and not line.startswith('## '):
                title = line[2:].strip()
                result.append(f'<h1>{title}</h1>')
            # 二级标题
            elif line.startswith('## ') and not line.startswith('### '):
                title = line[3:].strip()
                result.append(f'<h2>{title}</h2>')
            # 三级标题
            elif line.startswith('### '):
                title = line[4:].strip()
                result.append(f'<h3>{title}</h3>')
            else:
                result.append(line)

        return '\n'.join(result)

    def _render_lists(self, text: str) -> str:
        """
        渲染列表

        - 无序列表 → <ul><li>项目</li></ul>
        1. 有序列表 → <ol><li>项目</li></ol>

        Args:
            text: 文本

        Returns:
            渲染后的文本
        """
        lines = text.split('\n')
        result = []
        in_unordered_list = False
        in_ordered_list = False

        for line in lines:
            # 无序列表项
            if line.startswith(('- ', '* ', '• ')):
                item_text = line[2:].strip()
                if not in_unordered_list:
                    result.append('<ul>')
                    in_unordered_list = True
                result.append(f'<li>{item_text}</li>')
            # 有序列表项
            elif re.match(r'^\d+\.\s+', line):
                item_text = re.sub(r'^\d+\.\s+', '', line).strip()
                if not in_ordered_list:
                    result.append('<ol>')
                    in_ordered_list = True
                result.append(f'<li>{item_text}</li>')
            else:
                # 关闭列表
                if in_unordered_list:
                    result.append('</ul>')
                    in_unordered_list = False
                if in_ordered_list:
                    result.append('</ol>')
                    in_ordered_list = False
                result.append(line)

        # 关闭未关闭的列表
        if in_unordered_list:
            result.append('</ul>')
        if in_ordered_list:
            result.append('</ol>')

        return '\n'.join(result)

    def _render_bold(self, text: str) -> str:
        """
        渲染粗体

        **粗体** → <strong>粗体</strong>

        Args:
            text: 文本

        Returns:
            渲染后的文本
        """
        # 处理 **粗体**
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        return text

    def _render_code_blocks(self, text: str) -> str:
        """
        渲染代码块

        ```代码``` → <pre>代码</pre>

        Args:
            text: 文本

        Returns:
            渲染后的文本
        """
        # 简单处理代码块
        text = re.sub(r'```(.+?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
        return text

    def _render_horizontal_rules(self, text: str) -> str:
        """
        渲染水平线

        --- → <hr>

        Args:
            text: 文本

        Returns:
            渲染后的文本
        """
        text = re.sub(r'^---$', '<hr>', text, flags=re.MULTILINE)
        text = re.sub(r'^\*\*\*$', '<hr>', text, flags=re.MULTILINE)
        return text

    def _render_paragraphs(self, text: str) -> str:
        """
        渲染段落

        将连续的文本行包装在 <p> 标签中

        Args:
            text: 文本

        Returns:
            渲染后的文本
        """
        lines = text.split('\n')
        result = []
        in_paragraph = False
        paragraph_lines = []

        for line in lines:
            # 跳过空行和已有标签的行
            if not line.strip():
                if in_paragraph:
                    result.append(f'<p>{"".join(paragraph_lines)}</p>')
                    paragraph_lines = []
                    in_paragraph = False
                continue

            if line.strip().startswith('<'):
                # 已有 HTML 标签，直接添加
                if in_paragraph:
                    result.append(f'<p>{"".join(paragraph_lines)}</p>')
                    paragraph_lines = []
                    in_paragraph = False
                result.append(line)
            else:
                # 普通文本行
                if not in_paragraph:
                    in_paragraph = True
                paragraph_lines.append(f' {line.strip()}')

        # 处理最后一个段落
        if in_paragraph:
            result.append(f'<p>{"".join(paragraph_lines)}</p>')

        return '\n'.join(result)

    def render_to_clean_text(self, markdown_text: str) -> str:
        """
        将 Markdown 渲染为纯文本（移除 Markdown 符号）

        Args:
            markdown_text: Markdown 格式的文本

        Returns:
            纯文本
        """
        if not markdown_text:
            return ""

        text = markdown_text

        # 移除标题符号
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

        # 移除粗体符号
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)

        # 移除列表符号
        text = re.sub(r'^[\-\*\•]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

        # 移除代码块符号
        text = re.sub(r'```', '', text)

        # 移除水平线
        text = re.sub(r'^[\-\*]{3,}$', '', text, flags=re.MULTILINE)

        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()


# 单例实例
_renderer_instance = None


def get_markdown_renderer() -> MarkdownRenderer:
    """获取 Markdown 渲染器单例"""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = MarkdownRenderer()
        logger.info("[MarkdownRenderer] Markdown 渲染器初始化完成")
    return _renderer_instance
