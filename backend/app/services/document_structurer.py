# backend/app/services/document_structurer.py
"""
AI 驱动的文档结构化服务
将 AI 生成的内容转换为规范的法律文档格式
"""
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DocumentSection:
    """文档章节"""
    level: int  # 1=一级标题, 2=二级标题, 3=三级标题
    title: str
    content: str
    subsections: List['DocumentSection']

    def __post_init__(self):
        if self.subsections is None:
            self.subsections = []


@dataclass
class ContractParty:
    """合同方信息"""
    role: str  # 甲方/乙方/丙方等
    name: str
    fields: Dict[str, str]  # 地址、联系人等


@dataclass
class DocumentStructure:
    """文档结构"""
    doc_type: str  # contract, letter, judicial
    title: str
    parties: List[ContractParty]
    sections: List[DocumentSection]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "doc_type": self.doc_type,
            "title": self.title,
            "parties": [{"role": p.role, "name": p.name, "fields": p.fields} for p in self.parties],
            "sections": [self._section_to_dict(s) for s in self.sections],
            "metadata": self.metadata
        }

    def _section_to_dict(self, section: DocumentSection) -> Dict:
        """递归转换章节"""
        return {
            "level": section.level,
            "title": section.title,
            "content": section.content,
            "subsections": [self._section_to_dict(s) for s in section.subsections]
        }


class AIDocumentStructurer:
    """
    AI 文档结构化服务

    使用 AI 分析用户输入的文本，提取文档结构，
    然后使用专业模板渲染为规范的 Word 文档
    """

    def __init__(self, api_url: str = None, api_key: str = None, model: str = None):
        """
        初始化

        Args:
            api_url: AI API 地址
            api_key: API 密钥（可选）
            model: 模型名称
        """
        self.api_url = api_url
        self.api_key = api_key
        self.model = model or "deepseek-chat"

        # 从环境变量读取（如果未传入）
        if not self.api_url:
            from app.core.config import settings
            self.api_url = settings.DEEPSEEK_API_URL or settings.AI_POSTPROCESS_API_URL
            self.api_key = settings.DEEPSEEK_API_KEY or settings.AI_POSTPROCESS_API_KEY
            self.model = settings.DEEPSEEK_MODEL or settings.AI_POSTPROCESS_MODEL

        self.enabled = bool(self.api_url)

        if self.enabled:
            logger.info(f"AI 文档结构化服务已启用: {self.model}")
        else:
            logger.warning("AI 文档结构化服务未启用（缺少 API_URL 配置）")

    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self.enabled

    def extract_structure(self, content: str, doc_type_hint: str = None) -> Optional[DocumentStructure]:
        """
        从文本中提取文档结构

        Args:
            content: 用户输入的文本（可能是 AI 生成的内容）
            doc_type_hint: 文档类型提示 (contract/letter/judicial)

        Returns:
            DocumentStructure 对象，失败返回 None
        """
        if not self.enabled:
            logger.warning("AI 服务不可用，无法提取文档结构")
            return None

        try:
            prompt = self._build_structure_extraction_prompt(content, doc_type_hint)

            response = self._call_ai(prompt)

            if not response:
                return None

            # 解析 AI 返回的 JSON
            structure_data = self._parse_ai_response(response)

            if not structure_data:
                return None

            # 构建结构化对象
            return self._build_structure_from_dict(structure_data)

        except Exception as e:
            logger.error(f"文档结构提取失败: {str(e)}")
            return None

    def _build_structure_extraction_prompt(self, content: str, doc_type_hint: str = None) -> str:
        """构建结构提取提示词"""

        hint_text = f"\n提示：用户可能想要生成 {doc_type_hint} 类型的文档。" if doc_type_hint else ""

        return """你是一个专业的法律文书格式化专家。请分析以下文本，提取文档结构并返回标准格式。

原始内容：
```
""" + content[:8000] + """  # 限制长度避免超过 token 限制
```
""" + hint_text + """

请按照以下 JSON 格式返回，**只返回 JSON，不要其他说明文字**：

{
  "doc_type": "contract|letter|judicial|other",
  "title": "文档标题",
  "parties": [
    {
      "role": "甲方",
      "name": "名称或占位符",
      "fields": {"地址": "...", "联系人": "...", "电话": "..."}
    }
  ],
  "sections": [
    {
      "level": 1,
      "title": "章节标题",
      "content": "章节正文内容（如果有）",
      "subsections": [
        {
          "level": 2,
          "title": "子章节标题",
          "content": "子章节内容",
          "subsections": []
        }
      ]
    }
  ],
  "metadata": {
    "contract_number": "合同编号（如果有）",
    "date": "日期（如果有）",
    "keywords": ["关键词1", "关键词2"]
  }
}

注意：
1. level 1 是最高级标题（如"第一条"、"一、"），level 2 是次级标题
2. parties 提取合同方信息，如果没有则为空数组
3. content 保留该章节下的正文段落
4. 如果原文使用 Markdown 格式，请转换为上述结构
5. 保持原文的语义和完整性"""

    def _call_ai(self, prompt: str) -> Optional[str]:
        """调用 AI API"""
        try:
            import httpx

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # 优先使用 DeepSeek 兼容格式
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的法律文书格式化专家，擅长分析和结构化各类法律文档。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # 降低温度以获得更稳定的结果
                "max_tokens": 8000  # 增加以支持更长的合同结构
            }

            timeout = httpx.Timeout(180.0, connect=10.0)
            with httpx.Client(timeout=timeout) as client:
                # 构建 API 端点 URL
                # 如果 api_url 已经包含完整路径（如 /chat/completions），直接使用
                # 否则添加标准端点
                api_endpoint = self.api_url
                if not api_endpoint.endswith('/chat/completions'):
                    # 确保没有重复的 /v1
                    base_url = api_endpoint.rstrip('/')
                    if not base_url.endswith('/v1'):
                        api_endpoint = f"{base_url}/chat/completions"
                    else:
                        api_endpoint = f"{base_url}/chat/completions"

                logger.info(f"正在调用 AI API: {api_endpoint}")
                logger.info(f"请求模型: {self.model}")

                response = client.post(
                    api_endpoint,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                logger.info(f"AI API 响应成功，状态码: {response.status_code}")

                # 处理不同 API 格式
                if "choices" in result:
                    content = result["choices"][0]["message"]["content"]
                    logger.info(f"AI 返回内容长度: {len(content)} 字符")
                    return content
                elif "content" in result:
                    logger.info(f"AI 返回内容长度: {len(result['content'])} 字符")
                    return result["content"]
                else:
                    logger.warning(f"未知的 AI 响应格式: {list(result.keys())}")
                    return None

        except httpx.TimeoutException as e:
            logger.error(f"AI API 调用超时（超过180秒）: {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"AI API HTTP 错误: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"AI API 调用失败: {str(e)}")
            return None

    def _parse_ai_response(self, response: str) -> Optional[Dict]:
        """解析 AI 响应，提取 JSON"""
        # 记录原始响应用于调试
        logger.info(f"[DEBUG] AI 原始响应完整长度: {len(response)} 字符")
        logger.info(f"[DEBUG] AI 原始响应 (前500字符): {response[:500]}")
        logger.info(f"[DEBUG] AI 原始响应 (后500字符): {response[-500:]}")

        # 检查响应是否为空
        if not response or not response.strip():
            logger.error("AI 响应为空")
            return None

        try:
            # 尝试直接解析
            result = json.loads(response)
            logger.info(f"[DEBUG] JSON 直接解析成功，doc_type: {result.get('doc_type')}, title: {result.get('title')}")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"[DEBUG] JSON 直接解析失败: {str(e)}")
            logger.info(f"[DEBUG] 错误位置: line {e.lineno}, column {e.colno}")

            # 尝试提取 JSON 代码块
            import re
            json_match = re.search(r'```json\s*(.+?)\s*```', response, re.DOTALL)
            if json_match:
                try:
                    json_str = json_match.group(1)
                    logger.info(f"[DEBUG] 提取到 JSON 代码块，长度: {len(json_str)}")
                    result = json.loads(json_str)
                    logger.info(f"[DEBUG] JSON 代码块解析成功，doc_type: {result.get('doc_type')}")
                    return result
                except json.JSONDecodeError as e2:
                    logger.warning(f"[DEBUG] JSON 代码块解析失败: {str(e2)}")

            # 尝试提取花括号内容（从第一个 { 到最后一个 }）
            brace_start = response.find('{')
            if brace_start >= 0:
                brace_end = response.rfind('}')
                if brace_end > brace_start:
                    try:
                        json_str = response[brace_start:brace_end + 1]
                        logger.info(f"[DEBUG] 提取花括号内容，长度: {len(json_str)}")
                        logger.info(f"[DEBUG] 花括号内容 (前200字符): {json_str[:200]}")
                        result = json.loads(json_str)
                        logger.info(f"[DEBUG] 花括号提取解析成功，doc_type: {result.get('doc_type')}")
                        return result
                    except json.JSONDecodeError as e3:
                        logger.warning(f"[DEBUG] 花括号提取解析失败: {str(e3)}")
                        logger.info(f"[DEBUG] 尝试修复 JSON 中的常见问题...")

                        # 尝试修复常见的 JSON 问题
                        try:
                            # 移除尾部逗号
                            fixed_json = re.sub(r',\s*([}\]])', r'\1', json_str)
                            result = json.loads(fixed_json)
                            logger.info(f"[DEBUG] 修复尾部逗号后解析成功")
                            return result
                        except:
                            pass

            logger.error(f"无法解析 AI 响应为 JSON，响应内容 (前1000字符): {response[:1000]}")
            return None

    def _build_structure_from_dict(self, data: Dict) -> DocumentStructure:
        """从字典构建结构对象"""

        def build_sections(sections_data: List[Dict]) -> List[DocumentSection]:
            """递归构建章节"""
            sections = []
            for s in sections_data:
                section = DocumentSection(
                    level=s.get("level", 1),
                    title=s.get("title", ""),
                    content=s.get("content", ""),
                    subsections=build_sections(s.get("subsections", []))
                )
                sections.append(section)
            return sections

        def build_parties(parties_data: List[Dict]) -> List[ContractParty]:
            """构建合同方"""
            parties = []
            for p in parties_data:
                party = ContractParty(
                    role=p.get("role", ""),
                    name=p.get("name", ""),
                    fields=p.get("fields", {})
                )
                parties.append(party)
            return parties

        return DocumentStructure(
            doc_type=data.get("doc_type", "other"),
            title=data.get("title", "未命名文档"),
            parties=build_parties(data.get("parties", [])),
            sections=build_sections(data.get("sections", [])),
            metadata=data.get("metadata", {})
        )


# 单例
_structurer_instance: Optional[AIDocumentStructurer] = None


def get_structurer() -> AIDocumentStructurer:
    """获取文档结构化服务单例"""
    global _structurer_instance
    if _structurer_instance is None:
        _structurer_instance = AIDocumentStructurer()
    return _structurer_instance
