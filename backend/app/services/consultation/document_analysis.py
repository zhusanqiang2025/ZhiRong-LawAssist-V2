# backend/app/services/consultation/document_analysis.py
"""
智能咨询模块 - 文档分析服务

基于通用文档预整理服务,添加咨询特定功能:
1. 法律问题提取 (从文档中识别潜在法律问题)
2. 争议焦点识别 (识别文件中的矛盾点)
3. 证据链梳理 (梳理证据之间的逻辑关系)
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.common.document_preorganization import (
    UniversalDocumentPreorganizationService,
    PreorganizedDocuments,
    DocumentSummary
)
from app.services.unified_document_service import StructuredDocumentResult

logger = logging.getLogger(__name__)


@dataclass
class EvidenceLink:
    """证据链连接"""
    from_doc: str
    to_doc: str
    link_type: str  # basis, contradicts, supports, clarifies
    description: str


@dataclass
class EvidenceChain:
    """证据链"""
    key_facts: List[str]
    evidence_links: List[EvidenceLink]
    contradictions: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)


class ConsultationDocumentAnalysisService:
    """
    咨询模块文档分析服务

    在通用预整理服务基础上,添加咨询特定功能
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.preorganizer = UniversalDocumentPreorganizationService(llm)

    async def analyze_for_consultation(
        self,
        documents: List[StructuredDocumentResult],
        user_question: str,
        classification: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        为咨询场景分析文档

        Args:
            documents: UnifiedDocumentService 提取的文档列表
            user_question: 用户问题
            classification: 律师助理的分类结果

        Returns:
            {
                # 通用预整理结果
                "document_classification": {...},
                "document_summaries": {...},
                "timeline": [...],
                "document_relationships": [...],
                "all_parties": [...],
                "cross_doc_info": {...},

                # 咨询特定结果
                "legal_issues": [...],
                "dispute_points": [...],
                "evidence_chain": {...}
            }
        """
        logger.info(f"[ConsultationDocumentAnalysisService] 开始分析 {len(documents)} 个文档")

        # 1. 调用通用预整理服务
        logger.info(f"[ConsultationDocumentAnalysisService] 调用通用预整理服务...")
        preorganized = await self.preorganizer.preorganize(
            documents=documents,
            user_context=user_question,
            mode="consultation"
        )
        logger.info(f"[ConsultationDocumentAnalysisService] 通用预整理完成, summaries类型: {type(preorganized.document_summaries)}")

        # 2. 提取法律问题
        legal_issues = await self._extract_legal_issues(
            documents,
            preorganized,
            user_question
        )
        logger.info(f"[ConsultationDocumentAnalysisService] 提取法律问题: {len(legal_issues)} 个")

        # 3. 识别争议焦点
        dispute_points = await self._identify_dispute_points(
            documents,
            preorganized,
            classification or {}
        )
        logger.info(f"[ConsultationDocumentAnalysisService] 识别争议焦点: {len(dispute_points)} 个")

        # 4. 梳理证据链
        evidence_chain = await self._build_evidence_chain(
            documents,
            preorganized.document_relationships,
            preorganized
        )
        logger.info(f"[ConsultationDocumentAnalysisService] 梳理证据链: {len(evidence_chain.evidence_links)} 个连接")

        return {
            "document_classification": preorganized.document_classification,
            "document_summaries": {
                file_path: {
                    "file_path": summary.file_path,
                    "summary": summary.summary,
                    "key_parties": summary.key_parties,
                    "key_dates": summary.key_dates,
                    "key_amounts": summary.key_amounts,
                    "risk_signals": summary.risk_signals
                }
                for file_path, summary in preorganized.document_summaries.items()
            },
            "timeline": preorganized.timeline,
            "document_relationships": [
                {
                    "source_doc": rel.source_doc,
                    "target_doc": rel.target_doc,
                    "relationship_type": rel.relationship_type,
                    "confidence": rel.confidence,
                    "reason": rel.reason
                }
                for rel in preorganized.document_relationships
            ],
            "all_parties": [
                {
                    "name": party.name,
                    "role": party.role,
                    "confidence": party.confidence
                }
                for party in preorganized.all_parties
            ],
            "cross_doc_info": preorganized.cross_doc_info,

            # 咨询特定结果
            "legal_issues": legal_issues,
            "dispute_points": dispute_points,
            "evidence_chain": {
                "key_facts": evidence_chain.key_facts,
                "evidence_links": [
                    {
                        "from": link.from_doc,
                        "to": link.to_doc,
                        "type": link.link_type,
                        "description": link.description
                    }
                    for link in evidence_chain.evidence_links
                ],
                "contradictions": evidence_chain.contradictions,
                "gaps": evidence_chain.gaps
            }
        }

    async def _extract_legal_issues(
        self,
        documents: List[StructuredDocumentResult],
        preorganized: PreorganizedDocuments,
        user_question: str
    ) -> List[str]:
        """
        提取法律问题

        从文档中识别潜在的法律问题,包括:
        - 权利义务争议
        - 程序问题
        - 证据问题
        - 法律适用问题
        """
        # 如果没有文档,返回空列表
        if not documents:
            return []

        # 构建上下文
        context_parts = []
        context_parts.append(f"**用户问题**: {user_question}")

        # 添加文件摘要
        if preorganized.document_summaries:
            context_parts.append("\n**文件摘要**:")
            for file_path, summary in preorganized.document_summaries.items():
                # 从 summary 对象中获取文件名
                if isinstance(summary, dict):
                    file_name = summary.get("document_title") or summary.get("file_path", "").split('/')[-1] or "未知文档"
                    summary_text = summary.get("summary", "")
                else:
                    # 兼容 DocumentSummary 对象
                    file_name = getattr(summary, "document_title", None) or getattr(summary, "file_path", "").split('/')[-1] or "未知文档"
                    summary_text = getattr(summary, "summary", "")

                context_parts.append(f"- {file_name}: {summary_text}")
                if isinstance(summary, dict):
                    risk_signals = summary.get("risk_signals", [])
                else:
                    risk_signals = getattr(summary, "risk_signals", [])
                if risk_signals:
                    context_parts.append(f"  风险信号: {', '.join(risk_signals)}")

        # 添加时间线
        if preorganized.timeline:
            context_parts.append("\n**时间线**:")
            for event in preorganized.timeline[:5]:  # 最多5个事件
                context_parts.append(f"- {event.get('date', '未知日期')}: {event.get('event', '未知事件')}")

        context_str = "\n".join(context_parts)

        prompt = f"""基于以下信息,识别潜在的法律问题。

{context_str}

请识别并列出所有潜在的法律问题,包括但不限于:
1. 权利义务争议
2. 程序问题
3. 证据问题
4. 法律适用问题
5. 期限问题
6. 管辖权问题

返回 JSON 数组格式：
[
  "法律问题1",
  "法律问题2",
  ...
]

严格按照 JSON 数组格式输出,不要包含其他内容。"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="你是一位资深律师,擅长从法律文书和事实中识别潜在法律问题。"),
                HumanMessage(content=prompt)
            ])

            # 解析 JSON 数组
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                issues = json.loads(json_match.group(0))
                if isinstance(issues, list):
                    return issues

            # 如果解析失败,尝试按行分割
            lines = response.content.strip().split('\n')
            issues = []
            for line in lines:
                line = line.strip()
                # 移除序号和符号
                line = re.sub(r'^\d+[\.\)]\s*', '', line)
                line = re.sub(r'^[-\*]\s*', '', line)
                line = line.strip('"\'')
                if line and len(line) > 5:  # 过滤太短的行
                    issues.append(line)

            return issues[:10]  # 最多返回10个问题

        except Exception as e:
            logger.warning(f"[ConsultationDocumentAnalysisService] 法律问题提取失败: {e}")
            # 降级:从风险信号中提取
            issues = []
            for summary in preorganized.document_summaries.values():
                if summary.risk_signals:
                    issues.extend(summary.risk_signals)
            return list(set(issues))[:10]

    async def _identify_dispute_points(
        self,
        documents: List[StructuredDocumentResult],
        preorganized: PreorganizedDocuments,
        classification: Dict[str, Any]
    ) -> List[str]:
        """
        识别争议焦点

        识别文件中的矛盾点、争议点、分歧点
        """
        # 如果只有一个或没有文档,争议焦点较少
        if len(documents) < 2:
            return []

        # 构建上下文
        context_parts = []

        # 添加文档摘要
        for file_path, summary in preorganized.document_summaries.items():
            # 从 summary 对象中获取文件名
            if isinstance(summary, dict):
                file_name = summary.get("document_title") or summary.get("file_path", "").split('/')[-1] or "未知文档"
                summary_text = summary.get("summary", "")
                parties = summary.get("key_parties", [])
            else:
                # 兼容 DocumentSummary 对象
                file_name = getattr(summary, "document_title", None) or getattr(summary, "file_path", "").split('/')[-1] or "未知文档"
                summary_text = getattr(summary, "summary", "")
                parties = getattr(summary, "key_parties", [])

            context_parts.append(f"**{file_name}**:\n{summary_text}")
            if parties:
                context_parts.append(f"当事人: {', '.join(parties)}")
            context_parts.append("")

        # 添加文档关系
        if preorganized.document_relationships:
            context_parts.append("**文档关系**:")
            for rel in preorganized.document_relationships:
                context_parts.append(f"- {rel.source_doc} -> {rel.target_doc}: {rel.reason}")

        context_str = "\n".join(context_parts)

        prompt = f"""基于以下多文档的信息,识别争议焦点和矛盾点。

{context_str}

请识别并列出所有争议焦点,包括:
1. 事实认定分歧
2. 法律适用争议
3. 程序争议
4. 证据矛盾
5. 当事人主张冲突

返回 JSON 数组格式：
[
  "争议焦点1",
  "争议焦点2",
  ...
]

严格按照 JSON 数组格式输出,不要包含其他内容。"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="你是一位资深律师,擅长从多份法律文书中识别争议焦点。"),
                HumanMessage(content=prompt)
            ])

            # 解析 JSON 数组
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                disputes = json.loads(json_match.group(0))
                if isinstance(disputes, list):
                    return disputes

            # 如果解析失败,返回空列表
            return []

        except Exception as e:
            logger.warning(f"[ConsultationDocumentAnalysisService] 争议焦点识别失败: {e}")
            return []

    async def _build_evidence_chain(
        self,
        documents: List[StructuredDocumentResult],
        relationships: List,
        preorganized: PreorganizedDocuments
    ) -> EvidenceChain:
        """
        梳理证据链

        构建证据之间的逻辑关系,识别矛盾和缺口
        """
        # 1. 提取关键事实
        key_facts = []

        for file_path, summary in preorganized.document_summaries.items():
            # 从摘要中提取事实
            if summary.summary:
                key_facts.append(f"{file_path}: {summary.summary}")

        # 2. 构建证据连接
        evidence_links = []

        for rel in relationships:
            # 根据关系类型推断连接类型
            link_type = "supports"  # 默认

            if rel.relationship_type == "equivalent":
                link_type = "clarifies"
            elif rel.relationship_type == "amendment":
                link_type = "contradicts"
            elif rel.relationship_type == "supplement":
                link_type = "supports"
            elif rel.relationship_type == "related":
                link_type = "basis"

            evidence_links.append(EvidenceLink(
                from_doc=rel.source_doc,
                to_doc=rel.target_doc,
                link_type=link_type,
                description=rel.reason
            ))

        # 3. 识别矛盾
        contradictions = []
        for link in evidence_links:
            if link.link_type == "contradicts":
                contradictions.append(f"{link.from_doc} 与 {link.to_doc} 存在矛盾")

        # 4. 识别缺口 (可选,这里简单处理)
        gaps = []
        if len(documents) > 1 and len(evidence_links) == 0:
            gaps.append("文档之间缺乏明确的关联关系")

        return EvidenceChain(
            key_facts=key_facts,
            evidence_links=evidence_links,
            contradictions=contradictions,
            gaps=gaps
        )


# ==================== 工厂函数 ====================

def get_consultation_document_analysis_service(llm: ChatOpenAI) -> ConsultationDocumentAnalysisService:
    """获取咨询文档分析服务实例"""
    return ConsultationDocumentAnalysisService(llm)
