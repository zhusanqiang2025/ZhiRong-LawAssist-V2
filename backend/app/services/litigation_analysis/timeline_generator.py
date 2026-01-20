# backend/app/services/litigation_analysis/timeline_generator.py
"""
时间线生成器 (Timeline Generator)

职责：
1. 事实梳理：从案件文档中提取带有时间戳的关键事件。
2. 证据溯源：每个时间点必须标注来源文档（如：2023-01-01 签订合同 [来源：合同.pdf]）。
3. 叙事构建：生成清晰的案件发展脉络（Chronology）。
"""

import logging
import json
from typing import Dict, Any, List
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class TimelineEvent(BaseModel):
    """时间线事件模型"""
    date: str = Field(..., description="日期 (YYYY-MM-DD 或 YYYY-MM)")
    event: str = Field(..., description="事件简述")
    source_doc: str = Field(..., description="来源文档名称")
    importance: int = Field(..., description="重要程度 (1-3)")


class TimelineResult(BaseModel):
    """时间线结果"""
    events: List[TimelineEvent] = Field(..., description="事件列表")


class TimelineGenerator:
    """
    智能时间线生成器
    """

    def __init__(self):
        # 时间线提取只需要基础的理解能力，使用 DeepSeek 或 Qwen 均可
        self.llm = self._init_llm()

    def _init_llm(self) -> ChatOpenAI:
        if settings.DEEPSEEK_API_KEY:
            return ChatOpenAI(
                model="deepseek-chat",
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_API_URL,
                temperature=0.1 # 时间线必须精确，低温度
            )
        elif getattr(settings, "QWEN3_THINKING_ENABLED", False):
            return ChatOpenAI(
                model=settings.QWEN3_THINKING_MODEL,
                api_key=settings.QWEN3_THINKING_API_KEY,
                base_url=settings.QWEN3_THINKING_API_URL,
                temperature=0.1
            )
        else:
             return ChatOpenAI(api_key="dummy")

    async def generate(
        self,
        documents: Dict[str, Any],
        case_type: str
    ) -> Dict[str, Any]:
        """
        生成时间线

        Args:
            documents: 预整理后的案件信息 (preorganized_case)
            case_type: 案件类型
        """
        logger.info(f"[TimelineGenerator] 开始生成时间线 | 案由: {case_type}")

        try:
            # 1. 准备上下文
            # 提取文档摘要列表
            doc_summaries = []
            raw_docs = documents.get("document_analyses", [])
            for doc in raw_docs:
                name = doc.get("file_name", "未知文档")
                # 优先使用文档内提取的 key_dates
                dates = doc.get("key_dates", [])
                summary = doc.get("content_summary", "")
                doc_summaries.append(f"文档《{name}》: 提及日期 {dates}。内容摘要：{summary}")
            
            context = "\n".join(doc_summaries)

            # 2. 构建 Prompt
            system_prompt = "你是一位专业的法律书记员，擅长从复杂的案卷材料中梳理时间脉络。"
            user_prompt = f"""
请根据以下文档摘要，梳理案件的关键时间线。

【案由】{case_type}

【文档材料】
{context}

【要求】
1. 提取所有具有法律意义的时间节点（如签署日、转账日、违约日、起诉日）。
2. 格式统一为 YYYY-MM-DD。
3. 每个事件必须标注来源文档。
4. 按时间先后顺序排列。
5. 返回 JSON 格式。
"""

            # 3. 调用 LLM
            structured_llm = self.llm.with_structured_output(TimelineResult)
            result = await structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            # 4. 后处理 (排序)
            events = [e.dict() for e in result.events]
            events.sort(key=lambda x: x['date'])

            logger.info(f"[TimelineGenerator] 提取了 {len(events)} 个时间节点")
            return {"events": events}

        except Exception as e:
            logger.error(f"[TimelineGenerator] 时间线生成失败: {e}")
            # 返回空结构防止报错
            return {"events": []}