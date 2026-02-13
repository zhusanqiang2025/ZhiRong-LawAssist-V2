# backend/app/services/common/document_preorganization.py
"""
通用文档预整理服务

综合风险评估和案件分析模块的优点,提供统一的文档预整理能力:

从风险评估模块继承:
1. 文档分类 (CONTRACT, FINANCIAL_REPORT, COURT_DOCUMENT等)
2. 质量评估 (completeness, clarity)
3. 智能摘要 (summary, key_parties, key_dates, key_amounts, risk_signals)
4. 关系分析 (supplement, amendment, related, equivalent)
5. 重复检测 (MD5, 文件名相似度)
6. 重要性排序
7. 跨文档信息提取

从案件分析模块继承:
1. 当事人提取 (plaintiff, defendant, court, third_party)
2. 置信度评分
3. 时间线构建
4. 争议点提取
"""

import logging
import hashlib
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.common.unified_document_service import StructuredDocumentResult

logger = logging.getLogger(__name__)


# ==================== Schema 定义 ====================

class DocumentCategory(str, Enum):
    """统一的文档分类枚举"""
    # 基础类型 (来自风险评估模块)
    CONTRACT = "contract"
    FINANCIAL_REPORT = "financial_report"
    BUSINESS_LICENSE = "business_license"
    ID_DOCUMENT = "id_document"
    COURT_DOCUMENT = "court_document"
    TAX_DOCUMENT = "tax_document"
    SHAREHOLDER = "shareholder"
    OTHER = "other"

    # 诉讼文书类型 (来自案件分析模块)
    LAWYER_LETTER = "lawyer_letter"           # 律师函
    DEMAND_LETTER = "demand_letter"           # 催款通知
    COMPLAINT = "complaint"                   # 起诉状
    JUDGMENT = "judgment"                     # 判决书
    RULING = "ruling"                         # 裁定书
    ARBITRATION_AWARD = "arbitration_award"   # 仲裁裁决书
    MEDIATION_RECORD = "mediation_record"     # 调解笔录

    # 咨询模块特定类型
    EXECUTION_NOTICE = "execution_notice"     # 执行通知书
    CASE_ACCEPTANCE = "case_acceptance"       # 受理案件通知书
    LEGAL_OPINION = "legal_opinion"          # 法律意见书


@dataclass
class DocumentSummary:
    """文档摘要"""
    file_path: str
    summary: str
    key_parties: List[str] = field(default_factory=list)
    key_dates: List[str] = field(default_factory=list)
    key_amounts: List[str] = field(default_factory=list)
    risk_signals: List[str] = field(default_factory=list)


@dataclass
class DocumentQuality:
    """文档质量评估"""
    overall_score: float
    completeness: float
    clarity: float
    missing_fields: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


@dataclass
class DocumentRelationship:
    """文档关系"""
    source_doc: str
    target_doc: str
    relationship_type: str  # supplement, amendment, related, equivalent
    confidence: float
    reason: str


@dataclass
class PartyInfo:
    """当事人信息 (来自案件分析模块)"""
    name: str
    role: str  # plaintiff, defendant, court, third_party
    confidence: float


@dataclass
class PreorganizedDocuments:
    """预整理结果"""
    raw_documents: List[Dict[str, Any]]
    document_classification: Dict[str, List[str]]
    quality_scores: Dict[str, DocumentQuality]
    document_summaries: Dict[str, DocumentSummary]
    document_relationships: List[DocumentRelationship]
    duplicates: List[List[str]]
    ranked_documents: List[str]

    # 跨文档分析
    cross_doc_info: Dict[str, Any]

    # 当事人提取 (来自案件分析模块)
    all_parties: List[PartyInfo]

    # 时间线 (来自案件分析模块)
    timeline: List[Dict[str, Any]]


# ==================== 通用文档预整理服务 ====================

class UniversalDocumentPreorganizationService:
    """
    通用文档预整理服务

    综合风险评估和案件分析模块的优点
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    async def preorganize(
        self,
        documents: List[StructuredDocumentResult],
        user_context: Optional[str] = None,
        mode: str = "general"  # general, litigation, consultation
    ) -> PreorganizedDocuments:
        """
        预整理文档集合

        Args:
            documents: UnifiedDocumentService 提取的文档列表
            user_context: 用户提供的上下文信息
            mode: 预整理模式 (影响分析深度)

        Returns:
            PreorganizedDocuments: 预整理后的文档集合
        """
        logger.info(f"[UniversalDocumentPreorganizationService] 开始预整理 {len(documents)} 个文档")

        # 1. 文档分类 (继承自风险评估模块)
        classification = await self._classify_documents(documents, user_context)
        logger.info(f"[UniversalDocumentPreorganizationService] 分类完成: {classification}")

        # 2. 质量评估 (继承自风险评估模块)
        quality_scores = await self._assess_quality(documents, classification)
        logger.info(f"[UniversalDocumentPreorganizationService] 质量评估完成")

        # 3. 智能摘要 (继承自风险评估模块)
        summaries = await self._generate_summaries(documents, classification)
        logger.info(f"[UniversalDocumentPreorganizationService] 摘要生成完成")

        # 4. 关系分析 (继承自风险评估模块)
        relationships = await self._analyze_relationships(documents, summaries)
        logger.info(f"[UniversalDocumentPreorganizationService] 关系分析完成: 发现 {len(relationships)} 个关系")

        # 5. 重复检测 (继承自风险评估模块)
        duplicates = await self._detect_duplicates(documents)
        if duplicates:
            logger.info(f"[UniversalDocumentPreorganizationService] 发现 {len(duplicates)} 对重复文档")

        # 6. 重要性排序 (继承自风险评估模块)
        ranked = self._rank_documents(documents, classification, quality_scores, relationships)
        logger.info(f"[UniversalDocumentPreorganizationService] 文档排序完成")

        # 7. 跨文档信息提取 (继承自风险评估模块)
        cross_doc_info = self._extract_cross_document_info(summaries, relationships)
        logger.info(f"[UniversalDocumentPreorganizationService] 跨文档信息提取完成")

        # 8. 当事人提取 (继承自案件分析模块)
        all_parties = await self._extract_parties(documents, summaries, classification)
        logger.info(f"[UniversalDocumentPreorganizationService] 当事人提取完成: {len(all_parties)} 个")

        # 9. 时间线构建 (继承自案件分析模块)
        logger.info(f"[UniversalDocumentPreorganizationService] 准备构建时间线, summaries类型: {type(summaries)}")
        timeline = await self._build_timeline(documents, summaries, relationships, classification)
        logger.info(f"[UniversalDocumentPreorganizationService] 时间线构建完成: {len(timeline)} 个事件")

        return PreorganizedDocuments(
            raw_documents=[self._doc_to_dict(doc) for doc in documents],
            document_classification={cat.value: paths for cat, paths in classification.items()},
            quality_scores=quality_scores,
            document_summaries=summaries,
            document_relationships=relationships,
            duplicates=duplicates,
            ranked_documents=ranked,
            cross_doc_info=cross_doc_info,
            all_parties=all_parties,
            timeline=timeline
        )

    # ==================== 文档分类 ====================

    async def _classify_documents(
        self,
        documents: List[StructuredDocumentResult],
        user_context: Optional[str]
    ) -> Dict[DocumentCategory, List[str]]:
        """
        使用 LLM 对文档进行分类

        分类维度包括基础类型、诉讼文书类型、咨询特定类型
        """
        classification: Dict[DocumentCategory, List[str]] = {
            category: [] for category in DocumentCategory
        }

        for doc in documents:
            # 使用文件名 + 内容前1000字符进行分类
            sample_text = doc.content[:1000] if len(doc.content) > 1000 else doc.content
            file_name = doc.metadata.get("filename", "unknown")

            # 构建分类提示
            category = await self._classify_single_document(sample_text, file_name, user_context)

            classification[category].append(doc.metadata.get("file_path", ""))

        return classification

    async def _classify_single_document(
        self,
        sample_text: str,
        file_name: str,
        user_context: Optional[str]
    ) -> DocumentCategory:
        """对单个文档进行分类"""

        prompt = f"""请分析以下文档的类型。

**文件名**: {file_name}

**内容片段**:
{sample_text}

**可选用户上下文**: {user_context or "无"}

请从以下类型中选择最合适的一个：
1. contract - 合同协议
2. financial_report - 财务报表
3. business_license - 营业执照/工商信息
4. id_document - 身份证件
5. court_document - 法院文书
6. tax_document - 税务文件
7. shareholder - 股权文件
8. lawyer_letter - 律师函
9. demand_letter - 催款通知
10. complaint - 起诉状
11. judgment - 判决书
12. ruling - 裁定书
13. arbitration_award - 仲裁裁决书
14. mediation_record - 调解笔录
15. execution_notice - 执行通知书
16. case_acceptance - 受理案件通知书
17. legal_opinion - 法律意见书
18. other - 其他

只返回类型名称（如 "contract"），不要其他内容。"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="你是一个专业的文档分类助手。"),
                HumanMessage(content=prompt)
            ])

            category_str = response.content.strip().lower().replace(" ", "_")

            try:
                category = DocumentCategory(category_str)
            except ValueError:
                # LLM 返回了无效的类型，使用关键词匹配作为降级方案
                category = self._fallback_classify(sample_text, file_name)

            return category

        except Exception as e:
            logger.warning(f"[UniversalDocumentPreorganizationService] 分类失败 {file_name}: {e}")
            # 降级到基于关键词的分类
            return self._fallback_classify(sample_text, file_name)

    def _fallback_classify(self, content: str, filename: str) -> DocumentCategory:
        """基于关键词的降级分类"""
        content_lower = content.lower()
        filename_lower = filename.lower()

        # 关键词映射 (按优先级排序)
        keywords = [
            # 咨询特定类型
            (DocumentCategory.EXECUTION_NOTICE, ["执行通知", "执行通知书", "执行令"]),
            (DocumentCategory.CASE_ACCEPTANCE, ["受理案件", "案件受理", "受理通知书"]),
            (DocumentCategory.LEGAL_OPINION, ["法律意见书", "法律意见"]),

            # 诉讼文书类型
            (DocumentCategory.ARBITRATION_AWARD, ["仲裁裁决", "仲裁书"]),
            (DocumentCategory.JUDGMENT, ["判决书", "民事判决", "刑事判决"]),
            (DocumentCategory.RULING, ["裁定书", "民事裁定", "刑事裁定"]),
            (DocumentCategory.COMPLAINT, ["起诉状", "民事起诉状", "起诉书"]),
            (DocumentCategory.LAWYER_LETTER, ["律师函", "律师通知"]),
            (DocumentCategory.DEMAND_LETTER, ["催款", "催告", "催收"]),
            (DocumentCategory.MEDIATION_RECORD, ["调解", "调解笔录"]),

            # 基础类型
            (DocumentCategory.CONTRACT, ["合同", "协议", "contract", "agreement", "补充协议"]),
            (DocumentCategory.FINANCIAL_REPORT, ["财务", "报表", "审计", "资产负债", "利润表", "现金流量"]),
            (DocumentCategory.BUSINESS_LICENSE, ["营业执照", "工商", "统一社会信用代码"]),
            (DocumentCategory.ID_DOCUMENT, ["身份证", "护照", "id card", "身份证明"]),
            (DocumentCategory.COURT_DOCUMENT, ["法院", "诉讼", "仲裁", "法庭"]),
            (DocumentCategory.TAX_DOCUMENT, ["税务", "税收", "完税证明", "纳税申报"]),
            (DocumentCategory.SHAREHOLDER, ["股东", "股权", "出资", "股份", "投资"]),
        ]

        # 检查关键词
        for category, kw_list in keywords:
            if any(kw in content_lower or kw in filename_lower for kw in kw_list):
                return category

        return DocumentCategory.OTHER

    # ==================== 质量评估 ====================

    async def _assess_quality(
        self,
        documents: List[StructuredDocumentResult],
        classification: Dict[DocumentCategory, List[str]]
    ) -> Dict[str, DocumentQuality]:
        """
        评估文档质量

        评估维度：
        - 完整度（completeness）：文档是否完整，有无明显缺失
        - 清晰度（clarity）：针对扫描件，文字是否清晰可读
        - 缺失字段（missing_fields）：关键信息缺失
        - 质量问题（issues）：具体的质量问题列表
        """
        quality_scores = {}

        for doc in documents:
            completeness = 0.9  # 默认值
            clarity = 0.9
            missing_fields = []
            issues = []

            # 检查内容长度
            if len(doc.content) < 50:
                completeness = 0.3
                issues.append("文档内容过短，可能不完整")
            elif len(doc.content) < 200:
                completeness = 0.6
                issues.append("文档内容较短，请确认完整性")

            # 检查处理方法
            processing_method = doc.processing_method or ""
            if "ocr" in processing_method.lower():
                clarity = 0.8
                issues.append("文档通过 OCR 识别，可能存在识别错误")

            # 检查警告信息
            if doc.warnings:
                issues.extend(doc.warnings)
                completeness -= len(doc.warnings) * 0.1

            # 基于文档类型的特定检查
            doc_category = self._get_doc_category(doc.metadata.get("file_path", ""), classification)
            if doc_category == DocumentCategory.CONTRACT:
                required_keywords = ["甲方", "乙方", "签字", "日期"]
                for kw in required_keywords:
                    if kw not in doc.content:
                        missing_fields.append(f"缺少关键要素: {kw}")
                        completeness -= 0.1

            # 确保分数在 0-1 范围内
            completeness = max(0.0, min(1.0, completeness))
            clarity = max(0.0, min(1.0, clarity))
            overall_score = (completeness + clarity) / 2

            file_path = doc.metadata.get("file_path", "")
            quality_scores[file_path] = DocumentQuality(
                overall_score=overall_score,
                completeness=completeness,
                clarity=clarity,
                missing_fields=missing_fields,
                issues=issues
            )

        return quality_scores

    def _get_doc_category(
        self,
        file_path: str,
        classification: Dict[DocumentCategory, List[str]]
    ) -> DocumentCategory:
        """获取文档的分类"""
        for category, paths in classification.items():
            if file_path in paths:
                return category
        return DocumentCategory.OTHER

    # ==================== 智能摘要 ====================

    async def _generate_summaries(
        self,
        documents: List[StructuredDocumentResult],
        classification: Dict[DocumentCategory, List[str]]
    ) -> Dict[str, DocumentSummary]:
        """
        为每个文档生成智能摘要

        提取内容：
        - 摘要（2-3句话概括文档核心内容）
        - 关键当事人
        - 关键日期
        - 关键金额
        - 风险信号（异常条款、风险点等）
        """
        summaries = {}

        for doc in documents:
            doc_category = self._get_doc_category(doc.metadata.get("file_path", ""), classification)
            file_path = doc.metadata.get("file_path", "")

            if doc_category == DocumentCategory.ID_DOCUMENT:
                # 身份证件不需要复杂摘要
                summaries[file_path] = DocumentSummary(
                    file_path=file_path,
                    summary="身份证明文件"
                )
                continue

            # 限制内容长度以控制 token 使用
            content_sample = doc.content[:2000] if len(doc.content) > 2000 else doc.content
            file_name = doc.metadata.get("filename", "unknown")

            summary = await self._generate_single_summary(content_sample, file_name, doc_category, file_path)
            summaries[file_path] = summary

        return summaries

    async def _generate_single_summary(
        self,
        content_sample: str,
        file_name: str,
        doc_category: DocumentCategory,
        file_path: str
    ) -> DocumentSummary:
        """为单个文档生成摘要"""

        prompt = f"""请为以下文档生成智能摘要。

**文件名**: {file_name}
**文档类型**: {doc_category.value}

**内容**:
{content_sample}

请提取以下信息（JSON 格式）：
{{
  "summary": "2-3句话概括文档核心内容",
  "key_parties": ["当事人1", "当事人2"],
  "key_dates": ["重要日期1", "重要日期2"],
  "key_amounts": ["金额1", "金额2"],
  "risk_signals": ["风险信号1", "风险信号2"]
}}

如果某个字段没有信息，返回空数组。严格按照 JSON 格式输出。"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="你是一个专业的文档摘要助手，擅长提取关键信息。"),
                HumanMessage(content=prompt)
            ])

            # 解析 JSON
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                summary_data = json.loads(json_match.group(0))
                return DocumentSummary(
                    file_path=file_path,
                    summary=summary_data.get("summary", "无法生成摘要"),
                    key_parties=summary_data.get("key_parties", []),
                    key_dates=summary_data.get("key_dates", []),
                    key_amounts=summary_data.get("key_amounts", []),
                    risk_signals=summary_data.get("risk_signals", [])
                )
            else:
                raise ValueError("无法解析 JSON")

        except Exception as e:
            logger.warning(f"[UniversalDocumentPreorganizationService] 摘要生成失败 {file_path}: {e}")
            # 降级：简单摘要
            return DocumentSummary(
                file_path=file_path,
                summary=f"文档（{len(content_sample)} 字符）",
                key_parties=[],
                key_dates=[],
                key_amounts=[],
                risk_signals=[]
            )

    # ==================== 关系分析 ====================

    async def _analyze_relationships(
        self,
        documents: List[StructuredDocumentResult],
        summaries: Dict[str, DocumentSummary]
    ) -> List[DocumentRelationship]:
        """
        分析文档间的关系

        关系类型：
        - supplement: 补充协议/附件
        - amendment: 修订协议
        - related: 相关文档（如同一交易的不同文件）
        - equivalent: 等同/重复文档
        """
        relationships = []

        if len(documents) < 2:
            return relationships

        # 构建文档信息摘要
        doc_info = []
        for doc in documents:
            file_path = doc.metadata.get("file_path", "")
            summary = summaries.get(file_path)
            doc_info.append({
                "path": file_path,
                "filename": doc.metadata.get("filename", "unknown"),
                "summary": summary.summary if summary else "",
                "parties": summary.key_parties if summary else [],
                "dates": summary.key_dates if summary else []
            })

        # 使用 LLM 批量分析关系
        prompt = f"""请分析以下文档之间的关系。

文档列表：
{json.dumps(doc_info, ensure_ascii=False, indent=2)}

请识别文档间的关系，返回 JSON 数组：
[
  {{
    "source_doc": "文档路径1",
    "target_doc": "文档路径2",
    "relationship_type": "supplement|amendment|related|equivalent",
    "confidence": 0.9,
    "reason": "判断理由"
  }}
]

只返回有关系时，如果没有关系则返回空数组。严格按照 JSON 格式输出。"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="你是专业的文档关系分析助手。"),
                HumanMessage(content=prompt)
            ])

            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                rel_data = json.loads(json_match.group(0))
                for rel in rel_data:
                    relationships.append(DocumentRelationship(
                        source_doc=rel["source_doc"],
                        target_doc=rel["target_doc"],
                        relationship_type=rel["relationship_type"],
                        confidence=rel.get("confidence", 0.8),
                        reason=rel.get("reason", "")
                    ))

        except Exception as e:
            logger.warning(f"[UniversalDocumentPreorganizationService] 关系分析失败: {e}")

        return relationships

    # ==================== 重复检测 ====================

    async def _detect_duplicates(
        self,
        documents: List[StructuredDocumentResult]
    ) -> List[List[str]]:
        """
        检测重复或高度相似的文档

        方法：
        1. 基于文件名的相似度
        2. 基于内容 MD5 的完全重复
        3. 基于内容相似度的近似重复
        """
        duplicates = []

        # 1. 完全重复检测（MD5）
        md5_map = {}
        for doc in documents:
            content_md5 = hashlib.md5(doc.content.encode()).hexdigest()
            file_path = doc.metadata.get("file_path", "")
            if content_md5 in md5_map:
                duplicates.append([md5_map[content_md5], file_path])
            else:
                md5_map[content_md5] = file_path

        # 2. 文件名相似度检测
        for i, doc1 in enumerate(documents):
            for doc2 in documents[i+1:]:
                name1 = doc1.metadata.get("filename", "")
                name2 = doc2.metadata.get("filename", "")

                # 简单相似度：去除版本号、副本标记后比较
                clean_name1 = re.sub(r'_\d+|\(复制\)|\(副本\)|_copy', '', name1.lower())
                clean_name2 = re.sub(r'_\d+|\(复制\)|\(副本\)|_copy', '', name2.lower())

                path1 = doc1.metadata.get("file_path", "")
                path2 = doc2.metadata.get("file_path", "")

                if clean_name1 == clean_name2 and clean_name1:
                    # 检查是否已经在重复列表中
                    already_exists = any(
                        set([path1, path2]) == set(existing_pair)
                        for existing_pair in duplicates
                    )
                    if not already_exists:
                        duplicates.append([path1, path2])

        return duplicates

    # ==================== 重要性排序 ====================

    def _rank_documents(
        self,
        documents: List[StructuredDocumentResult],
        classification: Dict[DocumentCategory, List[str]],
        quality_scores: Dict[str, DocumentQuality],
        relationships: List[DocumentRelationship]
    ) -> List[str]:
        """
        对文档进行重要性排序

        排序规则：
        1. 诉讼文书 > 合同协议 > 财务报表 > 其他
        2. 质量分数高的优先
        3. 被其他文档引用的优先
        4. 文件大小（内容长度）适中的优先
        """
        doc_scores = {}

        for doc in documents:
            score = 0.0
            file_path = doc.metadata.get("file_path", "")

            # 1. 分类权重
            category = self._get_doc_category(file_path, classification)
            category_weights = {
                # 诉讼文书 (高优先级)
                DocumentCategory.JUDGMENT: 100,
                DocumentCategory.RULING: 95,
                DocumentCategory.ARBITRATION_AWARD: 100,
                DocumentCategory.COMPLAINT: 90,
                DocumentCategory.LAWYER_LETTER: 85,
                DocumentCategory.EXECUTION_NOTICE: 90,
                DocumentCategory.CASE_ACCEPTANCE: 85,

                # 合同协议 (高优先级)
                DocumentCategory.CONTRACT: 95,

                # 财务相关
                DocumentCategory.FINANCIAL_REPORT: 80,
                DocumentCategory.SHAREHOLDER: 75,
                DocumentCategory.TAX_DOCUMENT: 70,

                # 证件类
                DocumentCategory.BUSINESS_LICENSE: 60,
                DocumentCategory.ID_DOCUMENT: 50,

                # 其他
                DocumentCategory.COURT_DOCUMENT: 70,
                DocumentCategory.OTHER: 20
            }
            score += category_weights.get(category, 20)

            # 2. 质量分数
            quality = quality_scores.get(file_path)
            if quality:
                score += quality.overall_score * 50

            # 3. 被引用次数
            referenced_count = sum(1 for rel in relationships if rel.target_doc == file_path)
            score += referenced_count * 10

            # 4. 内容长度（适中最好）
            content_len = len(doc.content)
            if 1000 <= content_len <= 10000:
                score += 20
            elif content_len > 10000:
                score += 10

            doc_scores[file_path] = score

        # 按分数排序
        ranked = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)
        return ranked

    # ==================== 跨文档信息提取 ====================

    def _extract_cross_document_info(
        self,
        summaries: Dict[str, DocumentSummary],
        relationships: List[DocumentRelationship]
    ) -> Dict[str, Any]:
        """
        跨文档提取关键信息

        提取内容：
        - 所有涉及的公司/个人
        - 时间线
        - 交易总额
        - 关联关系
        """
        # 聚合所有当事人
        all_parties = set()
        for summary in summaries.values():
            all_parties.update(summary.key_parties)

        # 聚合所有日期
        all_dates = []
        for summary in summaries.values():
            all_dates.extend(summary.key_dates)

        # 聚合所有风险信号
        all_risks = []
        for summary in summaries.values():
            all_risks.extend(summary.risk_signals)

        return {
            "all_parties": list(all_parties),
            "all_dates": all_dates,
            "total_risk_signals": len(all_risks),
            "risk_signals": all_risks[:10],  # 最多返回10个
            "relationship_count": len(relationships)
        }

    # ==================== 当事人提取 ====================

    async def _extract_parties(
        self,
        documents: List[StructuredDocumentResult],
        summaries: Dict[str, DocumentSummary],
        classification: Dict[DocumentCategory, List[str]]
    ) -> List[PartyInfo]:
        """
        提取所有当事人信息

        返回：
        - 当事人姓名
        - 角色（原告、被告、法院、第三人）
        - 置信度
        """
        all_parties = []

        # 从摘要中提取
        for summary in summaries.values():
            for party_name in summary.key_parties:
                # 简单的角色推断
                role = "third_party"  # 默认为第三人
                confidence = 0.7

                # 根据关键词判断角色
                if "法院" in party_name or "仲裁" in party_name:
                    role = "court"
                    confidence = 0.9
                elif "原告" in summary.summary and party_name in summary.summary:
                    role = "plaintiff"
                    confidence = 0.8
                elif "被告" in summary.summary and party_name in summary.summary:
                    role = "defendant"
                    confidence = 0.8

                # 避免重复
                existing = next((p for p in all_parties if p.name == party_name), None)
                if existing:
                    if confidence > existing.confidence:
                        existing.role = role
                        existing.confidence = confidence
                else:
                    all_parties.append(PartyInfo(
                        name=party_name,
                        role=role,
                        confidence=confidence
                    ))

        return all_parties

    # ==================== 时间线构建 ====================

    async def _build_timeline(
        self,
        documents: List[StructuredDocumentResult],
        summaries: Dict[str, DocumentSummary],
        relationships: List[DocumentRelationship],
        classification: Dict[DocumentCategory, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        构建案件时间线

        返回：
        - 日期
        - 事件描述
        - 相关文档
        """
        timeline_events = []

        for doc in documents:
            file_path = doc.metadata.get("file_path", "")
            summary = summaries.get(file_path)

            if summary and summary.key_dates:
                file_name = doc.metadata.get("filename", "")
                for date_str in summary.key_dates:
                    # 根据文档类型推断事件
                    doc_category = self._get_doc_category(file_path, classification)

                    event_type = "文档生成"
                    if doc_category == DocumentCategory.JUDGMENT:
                        event_type = "判决"
                    elif doc_category == DocumentCategory.ARBITRATION_AWARD:
                        event_type = "仲裁裁决"
                    elif doc_category == DocumentCategory.COMPLAINT:
                        event_type = "起诉"
                    elif doc_category == DocumentCategory.EXECUTION_NOTICE:
                        event_type = "执行立案"
                    elif doc_category == DocumentCategory.CASE_ACCEPTANCE:
                        event_type = "案件受理"

                    timeline_events.append({
                        "date": date_str,
                        "event": f"{event_type} - {file_name}",
                        "document": file_name,
                        "doc_type": doc_category.value
                    })

        # 按日期排序
        timeline_events.sort(key=lambda x: x["date"])

        return timeline_events

    # ==================== 辅助方法 ====================

    def _doc_to_dict(self, doc: StructuredDocumentResult) -> Dict[str, Any]:
        """将 StructuredDocumentResult 转换为字典"""
        return {
            "status": doc.status,
            "content": doc.content,
            "metadata": doc.metadata,
            "processing_method": doc.processing_method,
            "warnings": doc.warnings or []
        }


# ==================== 工厂函数 ====================

def get_universal_document_preorganization_service(llm: ChatOpenAI) -> UniversalDocumentPreorganizationService:
    """获取通用文档预整理服务实例"""
    return UniversalDocumentPreorganizationService(llm)
