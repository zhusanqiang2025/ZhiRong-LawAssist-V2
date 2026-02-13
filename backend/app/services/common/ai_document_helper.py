# backend/app/services/ai_document_helper.py
"""
AI 文档辅助处理模块

使用视觉语言模型（如 Qwen3-VL）辅助文档预处理：
1. 智能页码识别（区分页码与正文中的数字）
2. 段落边界判断（智能判断是否应该合并段落）
3. 页眉页脚识别
4. 特殊格式识别（批注、水印等）
"""
import os
import logging
import base64
import io
from typing import Dict, List, Optional, Tuple
from PIL import Image
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class AIDocumentHelper:
    """
    AI 文档辅助处理类

    支持双模型配置：
    - 视觉模型：用于文档页面图像分析（qwen3-vl:32b-thinking-q8_0）
    - 文本模型：用于段落分类等纯文本任务（Qwen3-235B-A22B-Thinking-2507）
    """

    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        model: str = None,
        # ⭐ 新增：文本分类模型配置
        text_model_url: str = None,
        text_model_key: str = None,
        text_model: str = None
    ):
        """
        初始化 AI 辅助处理类

        Args:
            api_url: 视觉模型 API 地址
            api_key: 视觉模型 API 密钥
            model: 视觉模型名称
            text_model_url: 文本分类模型 API 地址
            text_model_key: 文本分类模型 API 密钥
            text_model: 文本分类模型名称
        """
        # 视觉模型配置（用于图像分析）
        self.api_url = api_url
        self.api_key = api_key
        self.model = model or "qwen3-vl-32b"

        # ⭐ 文本分类模型配置（用于纯文本任务）
        self.text_model_url = text_model_url
        self.text_model_key = text_model_key
        self.text_model = text_model or "qwen3-235b"

        # 从环境变量读取配置（如果未传入）
        if not self.api_url:
            from app.core.config import settings
            self.api_url = settings.AI_POSTPROCESS_API_URL
            self.api_key = settings.AI_POSTPROCESS_API_KEY
            self.model = settings.AI_POSTPROCESS_MODEL

            # ⭐ 读取文本分类模型配置
            self.text_model_url = settings.AI_TEXT_CLASSIFICATION_API_URL
            self.text_model_key = settings.AI_TEXT_CLASSIFICATION_API_KEY
            self.text_model = settings.AI_TEXT_CLASSIFICATION_MODEL

        # 检查是否启用
        self.vision_enabled = bool(self.api_url)  # 视觉分析功能
        self.text_enabled = bool(self.text_model_url)  # 文本分类功能

        if self.vision_enabled:
            logger.info(f"[AI 视觉分析] 已启用: {self.model}, API: {self.api_url}")
        else:
            logger.info("[AI 视觉分析] 未启用（缺少 API_URL 配置）")

        if self.text_enabled:
            logger.info(f"[AI 文本分类] 已启用: {self.text_model}, API: {self.text_model_url}")
        else:
            logger.info("[AI 文本分类] 未启用（缺少文本分类模型配置）")

    def is_available(self) -> bool:
        """检查 AI 服务是否可用（任一模型可用即可）"""
        return self.vision_enabled or self.text_enabled

    def analyze_page_with_ai(self, docx_path: str, page_index: int = 0) -> Dict:
        """
        使用 AI 分析文档页面

        Args:
            docx_path: docx 文件路径
            page_index: 要分析的页码索引（从0开始）

        Returns:
            AI 分析结果字典，包含：
            - page_numbers: 页码位置列表
            - headers_footers: 页眉页脚内容
            - paragraph_boundaries: 段落边界建议
            - special_elements: 特殊元素（批注、水印等）
        """
        if not self.vision_enabled:
            return {"error": "AI 视觉分析服务未启用"}

        try:
            # 将文档页面转换为图像
            image_data = self._render_docx_page_as_image(docx_path, page_index)
            if not image_data:
                return {"error": "无法渲染文档页面"}

            # 构建 AI 请求（使用视觉模型）
            prompt = self._build_analysis_prompt()
            response = self._call_vision_model(image_data, prompt)

            return self._parse_ai_response(response)

        except Exception as e:
            logger.error(f"AI 分析失败: {str(e)}")
            return {"error": str(e)}

    def classify_paragraph_with_ai(self, paragraph_text: str, context: Dict) -> Dict:
        """
        使用 AI 分类段落内容

        Args:
            paragraph_text: 段落文本
            context: 上下文信息（位置、前后段落等）

        Returns:
            分类结果：
            - is_page_number: 是否为页码
            - is_header_footer: 是否为页眉页脚
            - should_merge_next: 是否应与下一段合并
            - confidence: 置信度
        """
        if not self.text_enabled:
            return {"error": "AI 文本分类服务未启用"}

        try:
            prompt = self._build_classification_prompt(paragraph_text, context)
            response = self._call_text_model(prompt)  # 使用文本分类模型

            return self._parse_classification_response(response)

        except Exception as e:
            logger.error(f"AI 分类失败: {str(e)}")
            return {"error": str(e)}

    def batch_classify_paragraphs(self, paragraphs: List[str], context: List[Dict]) -> List[Dict]:
        """
        批量分类多个段落（使用 AI 提高效率）

        Args:
            paragraphs: 段落文本列表
            context: 每个段落的上下文信息

        Returns:
            分类结果列表
        """
        if not self.text_enabled:
            return [{"error": "AI 文本分类服务未启用"} for _ in paragraphs]

        try:
            prompt = self._build_batch_classification_prompt(paragraphs, context)
            response = self._call_text_model(prompt)  # 使用文本分类模型

            return self._parse_batch_classification_response(response, len(paragraphs))

        except Exception as e:
            logger.error(f"AI 批量分类失败: {str(e)}")
            return [{"error": str(e)} for _ in paragraphs]

    def _render_docx_page_as_image(self, docx_path: str, page_index: int = 0) -> Optional[bytes]:
        """
        将 docx 页面渲染为图像

        Args:
            docx_path: docx 文件路径
            page_index: 页码索引

        Returns:
            图像数据（PNG 格式）
        """
        doc = None
        temp_pdf = None
        try:
            # 使用 PyMuPDF 渲染（需要先将 docx 转为 PDF 或直接渲染）
            # 这里简化处理：如果有 PDF 版本，优先使用 PDF
            pdf_path = docx_path.replace('.docx', '.pdf')
            if os.path.exists(pdf_path):
                doc = fitz.open(pdf_path)
            else:
                # 如果没有 PDF，尝试使用 docx 渲染
                # 这里需要将 docx 转为临时 PDF
                import subprocess
                temp_pdf = docx_path.replace('.docx', '_temp.pdf')
                subprocess.run([
                    'soffice', '--headless', '--convert-to', 'pdf',
                    '--outdir', os.path.dirname(docx_path),
                    docx_path
                ], check=False, capture_output=True)
                if os.path.exists(temp_pdf):
                    doc = fitz.open(temp_pdf)
                else:
                    return None

            if page_index >= doc.page_count:
                return None

            page = doc[page_index]
            # 渲染为图像（2倍缩放提高清晰度）
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")

            # 清理临时文件
            if temp_pdf and os.path.exists(temp_pdf):
                try:
                    os.remove(temp_pdf)
                except Exception:
                    pass

            return img_data

        except Exception as e:
            logger.error(f"Error rendering page: {e}")
            return None
        finally:
            # 确保文档对象被正确关闭
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    def _build_analysis_prompt(self) -> str:
        """构建文档分析提示词"""
        return """请分析这个文档页面，识别以下内容并返回 JSON 格式：

{
  "page_numbers": ["页码1", "页码2"],  // 识别出的页码文本
  "headers_footers": ["页眉内容", "页脚内容"],  // 页眉页脚文本
  "paragraph_boundaries": [5, 12, 20],  // 建议的段落边界索引
  "special_elements": [  // 特殊元素
    {"type": "watermark", "text": "水印内容"},
    {"type": "comment", "text": "批注内容"}
  ]
}

注意：
1. 页码通常是单独成行的数字或"第X页"、"Page X"等格式
2. 页眉页脚通常出现在页面顶部或底部
3. 段落边界是文档中自然的分段位置
4. 忽略表格中的数字，只识别真正的页码

只返回 JSON，不要其他说明文字。"""

    def _build_classification_prompt(self, paragraph_text: str, context: Dict) -> str:
        """构建段落分类提示词"""
        index = context.get('index', 0)
        total = context.get('total', 1)
        prev_text = context.get('prev_text', '')
        next_text = context.get('next_text', '')

        return f"""请分析以下段落内容，判断其性质：

段落文本：{paragraph_text}

上下文信息：
- 位置：第 {index + 1} 段，共 {total} 段
- 上一段：{prev_text[:100] if prev_text else '(无)'}...
- 下一段：{next_text[:100] if next_text else '(无)'}...

请判断并返回 JSON 格式：
{{
  "is_page_number": true/false,  // 是否为页码
  "is_header_footer": true/false,  // 是否为页眉页脚
  "should_merge_next": true/false,  // 是否应与下一段合并
  "confidence": 0.95,  // 置信度 (0-1)
  "reason": "判断理由"
}}

判断标准：
1. 页码：单独成行的数字、"第X页"、"Page X"、"- X -"等格式
2. 页眉页脚：出现在文档顶部或底部的重复内容
3. 段落合并：当前段未以句号结尾，且与下一段语义连贯

只返回 JSON，不要其他说明文字。"""

    def _build_batch_classification_prompt(self, paragraphs: List[str], context: List[Dict]) -> str:
        """构建批量分类提示词"""
        items = []
        for i, (para, ctx) in enumerate(zip(paragraphs, context)):
            items.append(f"""
{i + 1}. 文本：{para[:200]}...
   位置：第 {ctx.get('index', i) + 1} 段
""")

        return f"""请分析以下 {len(paragraphs)} 个段落，判断每个段落的性质：

{chr(10).join(items)}

请为每个段落返回 JSON 格式：
{{
  "index": 段落编号,
  "is_page_number": true/false,
  "is_header_footer": true/false,
  "confidence": 0.95
}}

返回格式：
[{{"index": 1, ...}}, {{"index": 2, ...}}, ...]

只返回 JSON 数组，不要其他说明文字。"""

    def _call_vision_model(self, image_data: bytes, prompt: str) -> str:
        """
        调用视觉模型（用于文档页面图像分析）

        Args:
            image_data: 图像数据（必需）
            prompt: 文本提示词

        Returns:
            AI 响应文本
        """
        try:
            import httpx
            import os

            # 构建请求头（根据配置选择认证方式）
            headers = {"Content-Type": "application/json"}

            # 支持多种认证方式
            auth_type = os.getenv("AI_AUTH_TYPE", "bearer").lower()  # bearer | api-key | none

            if self.api_key and auth_type == "bearer":
                # OpenAI 兼容模式
                headers["Authorization"] = f"Bearer {self.api_key}"
            elif self.api_key and auth_type == "api-key":
                # 私有化部署常见方式
                headers["x-api-key"] = self.api_key
            elif self.api_key and auth_type == "authorization":
                # 自定义 Authorization header
                headers["Authorization"] = self.api_key
            # auth_type == "none" 时不添加认证头

            # 构建 API URL（自动补全 /chat/completions 路径）
            api_url = self.api_url
            if not api_url.endswith("/chat/completions"):
                # 确保正确拼接路径
                api_url = api_url.rstrip("/") + "/chat/completions"

            # 构建请求（视觉模型需要图像）
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的文档分析助手，擅长识别文档结构、页码、段落边界等。"
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": f"data:image/png;base64,{base64.b64encode(image_data).decode('utf-8')}"}
                        ]
                    }
                ],
                "temperature": 0.1,  # 降低随机性，提高稳定性
                "max_tokens": 2000
            }

            # 发送请求
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"调用视觉模型失败: {str(e)}")
            raise

    def _call_text_model(self, prompt: str) -> str:
        """
        调用文本分类模型（用于段落分类等纯文本任务）

        Args:
            prompt: 文本提示词

        Returns:
            AI 响应文本
        """
        try:
            import httpx
            import os

            # 构建请求头
            headers = {"Content-Type": "application/json"}

            # 支持多种认证方式
            auth_type = os.getenv("AI_AUTH_TYPE", "bearer").lower()

            if self.text_model_key and auth_type == "bearer":
                headers["Authorization"] = f"Bearer {self.text_model_key}"
            elif self.text_model_key and auth_type == "api-key":
                headers["x-api-key"] = self.text_model_key
            elif self.text_model_key and auth_type == "authorization":
                headers["Authorization"] = self.text_model_key

            # 构建 API URL（自动补全 /chat/completions 路径）
            api_url = self.text_model_url
            if not api_url.endswith("/chat/completions"):
                # 确保正确拼接路径
                api_url = api_url.rstrip("/") + "/chat/completions"

            # 构建请求（纯文本，使用文本模型）
            payload = {
                "model": self.text_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的文档分析助手，擅长识别文档结构、段落分类、页码识别等。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2000
            }

            # 发送请求
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"调用文本模型失败: {str(e)}")
            raise

    def _parse_ai_response(self, response: str) -> Dict:
        """解析 AI 分析响应"""
        try:
            import json

            # 尝试提取 JSON
            if "```json" in response:
                json_start = response.index("```json") + 7
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.index("```") + 3
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
            else:
                # 尝试直接解析
                json_str = response.strip()

            return json.loads(json_str)

        except Exception as e:
            logger.error(f"解析 AI 响应失败: {str(e)}, 响应内容: {response[:200]}")
            return {"error": "解析 AI 响应失败"}

    def _parse_classification_response(self, response: str) -> Dict:
        """解析分类响应"""
        return self._parse_ai_response(response)

    def _parse_batch_classification_response(self, response: str, count: int) -> List[Dict]:
        """解析批量分类响应"""
        result = self._parse_ai_response(response)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "error" in result:
            return [{"error": result["error"]} for _ in range(count)]
        else:
            return [{"error": "无法解析响应"} for _ in range(count)]


# 单例实例
_ai_helper_instance = None


def get_ai_helper() -> AIDocumentHelper:
    """获取 AI 辅助处理单例"""
    global _ai_helper_instance
    if _ai_helper_instance is None:
        _ai_helper_instance = AIDocumentHelper()
    return _ai_helper_instance
