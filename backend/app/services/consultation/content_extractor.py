# backend/app/services/consultation/content_extractor.py
"""
咨询内容提取服务
负责从对话历史中提取结构化信息，用于跨模块复用
"""
import logging
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from app.services.consultation.history_service import consultation_history_service
from app.core.llm_config import get_qwen3_llm, get_default_llm
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


class ExtractedContext(BaseModel):
    """提取的上下文信息"""
    target_module: str
    data: Dict[str, Any]
    summary: str
    entities: List[str]


class ConsultationContentExtractor:
    """咨询内容提取器"""

    def __init__(self):
        pass

    async def extract_context_for_module(
        self,
        session_id: str,
        target_module: str,
        user_id: int
    ) -> Optional[ExtractedContext]:
        """为特定模块提取上下文"""
        # 1. 获取对话历史
        history = await consultation_history_service.get_conversation(user_id, session_id)
        if not history or not history.get("messages"):
            logger.warning(f"[提取器] 会话不存在或无消息: {session_id}")
            return None

        messages = history["messages"]
        
        # 转换消息格式为文本
        conversation_text = ""
        for msg in messages:
            role = "用户" if msg["role"] == "user" else "律师"
            content = msg["content"]
            conversation_text += f"{role}: {content}\n\n"

        # 2. 根据目标模块选择 Prompt
        system_prompt = self._get_prompt_for_module(target_module)
        if not system_prompt:
            logger.warning(f"[提取器] 未知的目标模块: {target_module}")
            return None

        # 3. 调用 LLM 提取
        try:
            llm = get_qwen3_llm()
            logger.info(f"[提取器] 使用 Qwen3-Thinking 提取上下文: {target_module}")
        except:
            llm = get_default_llm()
            logger.info(f"[提取器] 使用默认 LLM 提取上下文: {target_module}")

        try:
            prompt_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"以下是法律咨询的对话记录：\n\n{conversation_text}\n\n请提取结构化信息。")
            ]

            response = await llm.ainvoke(prompt_messages)
            content = response.content

            # 解析 JSON
            data = self._parse_json_response(content)
            
            return ExtractedContext(
                target_module=target_module,
                data=data,
                summary=data.get("summary", "无摘要"),
                entities=data.get("parties", []) + data.get("key_entities", [])
            )

        except Exception as e:
            logger.error(f"[提取器] 提取失败: {e}", exc_info=True)
            return None

    def _get_prompt_for_module(self, target_module: str) -> str:
        """获取特定模块的提示词"""
        
        base_instruction = """你是专业的法律信息提取助手。请分析对话记录，提取出结构化信息，以便用户在后续流程中直接复用。
请严格按照 JSON 格式输出，不要包含 markdown 代码块标记。"""

        if target_module == 'contract_generation':
            return base_instruction + """
提取目标：合同生成所需的关键要素。

请提取以下字段（JSON）：
{
    "contract_type": "推测的合同类型",
    "parties": ["甲方名称", "乙方名称"],
    "subject_matter": "标的物/服务内容",
    "amount": "涉及金额 (如有)",
    "term": "期限 (如有)",
    "key_terms": ["关键条款1", "关键条款2"],
    "summary": "合同背景摘要"
}
"""
        elif target_module == 'document_drafting':
            return base_instruction + """
提取目标：法律文书起草所需的关键要素。

请提取以下字段（JSON）：
{
    "document_type": "文书类型 (如起诉状、律师函)",
    "plaintiff": "原告/申请人",
    "defendant": "被告/被申请人",
    "claims": ["诉讼请求1", "诉讼请求2"],
    "facts_reasoning": "事实与理由摘要",
    "summary": "案情摘要"
}
"""
        elif target_module == 'risk_assessment':
             return base_instruction + """
提取目标：风险评估所需的案情要素。

请提取以下字段（JSON）：
{
    "risk_type": "风险类型",
    "key_facts": ["事实1", "事实2"],
    "dispute_focus": "争议焦点",
    "existing_evidence": ["证据1", "证据2"],
    "summary": "案情摘要"
}
"""
        return ""

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """解析 JSON 响应"""
        import re
        try:
            # 尝试查找 JSON 块
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {}
        except:
            return {}

consultation_content_extractor = ConsultationContentExtractor()
