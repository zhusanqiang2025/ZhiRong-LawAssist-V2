# backend/app/services/risk_analysis/document_classifier.py
"""
法律文档结构化分类器 (优化统一版)

作为全系统的统一分类标准，支持风险评估所需的细粒度分类。
结合了规则预判和 LLM 深度语义分析。
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import re
import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage
# --- 新增导入：使用统一的 JSON 清洗工具 ---
from app.utils.json_helper import safe_parse_json
# ----------------------------------------

logger = logging.getLogger(__name__)


# ==================== 标准分类体系 (统一版) ====================

class DocumentCategory(str, Enum):
    """
    一级分类 (Macro Category)
    用于路由处理逻辑（如：合同走规则引擎，财报走财务模型）
    """
    CONTRACT = "contract"              # 合同协议
    FINANCIAL = "financial"            # 财务/税务
    LICENSE = "license"                # 证照/资质
    LEGAL_DOC = "legal_doc"            # 法律/诉讼文书
    CORRESPONDENCE = "correspondence"  # 函件/通知
    EVIDENCE = "evidence"              # 证据材料
    IDENTITY = "identity"              # 身份证明
    OTHER = "other"                    # 其他


class DocumentRole(str, Enum):
    """文档中的主体角色"""
    SENDER = "sender"         # 发函方/申请人
    RECIPIENT = "recipient"   # 收函方/被申请人
    BUYER = "buyer"           # 买方/甲方
    SELLER = "seller"         # 卖方/乙方
    LENDER = "lender"         # 出借人
    BORROWER = "borrower"     # 借款人
    UNKNOWN = "unknown"


@dataclass
class DocumentMetadata:
    """结构化的文档元数据"""
    category: DocumentCategory
    sub_category: str          # 二级分类（如：采购合同、营业执照、资产负债表）
    confidence: float          # 置信度 0-1
    # 核心元数据
    parties: List[str] = field(default_factory=list) # 涉及的所有主体
    key_dates: List[str] = field(default_factory=list)
    summary: str = ""
    # 风险标签 (新增)
    risk_tags: List[str] = field(default_factory=list) # 如：[缺页, 未签字, 扫描不清]
    # 原始 LLM 输出
    raw_llm_output: Dict[str, Any] = field(default_factory=dict)


# ==================== 提示词构建器 ====================

class DocumentClassificationPromptBuilder:
    """分类提示词构建器"""

    @classmethod
    def build_classification_prompt(cls, file_name: str, content: str) -> str:
        prompt = f"""作为资深法律助理，请对以下文档进行【结构化分类】和【元数据提取】。

文件名: {file_name}
内容摘要:
{content[:3000]}

请严格分析并输出 JSON：
{{
  "category": "一级分类，必选其一: [contract, financial, license, legal_doc, correspondence, evidence, identity, other]",
  "sub_category": "二级分类，请具体描述文档类型（如：房屋租赁合同、增值税发票、民事判决书、催款函）",
  "confidence": 0.95,
  "parties": ["主体1", "主体2"],
  "key_dates": ["YYYY-MM-DD (描述)"],
  "summary": "一句话概括：谁和谁就什么事项签署/发出了此文件",
  "risk_tags": ["从内容形式上识别的风险，如: 未签字、草稿版本、缺页、模糊不清"]
}}
"""
        return prompt

    @classmethod
    def map_to_standard_category(cls, llm_cat: str) -> DocumentCategory:
        """映射 LLM 输出到标准枚举"""
        try:
            return DocumentCategory(llm_cat.lower())
        except ValueError:
            # 模糊匹配容错
            mapping = {
                "合同": DocumentCategory.CONTRACT,
                "协议": DocumentCategory.CONTRACT,
                "财务": DocumentCategory.FINANCIAL,
                "报表": DocumentCategory.FINANCIAL,
                "发票": DocumentCategory.FINANCIAL,
                "证照": DocumentCategory.LICENSE,
                "执照": DocumentCategory.LICENSE,
                "函件": DocumentCategory.CORRESPONDENCE,
                "通知": DocumentCategory.CORRESPONDENCE,
                "诉讼": DocumentCategory.LEGAL_DOC,
                "判决": DocumentCategory.LEGAL_DOC,
                "身份证": DocumentCategory.IDENTITY
            }
            for k, v in mapping.items():
                if k in llm_cat: return v
            return DocumentCategory.OTHER


# ==================== 规则分类器 ====================

class RuleBasedClassifier:
    """基于规则的快速分类器 (Pre-filter)"""

    @staticmethod
    def classify_by_filename(filename: str) -> Optional[DocumentCategory]:
        name = filename.lower()
        if any(x in name for x in ["合同", "协议", "contract", "agreement"]):
            return DocumentCategory.CONTRACT
        if any(x in name for x in ["执照", "许可证", "license"]):
            return DocumentCategory.LICENSE
        if any(x in name for x in ["报表", "流水", "审计", "report", "statement"]):
            return DocumentCategory.FINANCIAL
        if any(x in name for x in ["函", "通知", "letter", "notice"]):
            return DocumentCategory.CORRESPONDENCE
        if any(x in name for x in ["判决", "裁定", "起诉状", "court"]):
            return DocumentCategory.LEGAL_DOC
        return None


# ==================== 主分类函数 (异步) ====================

async def classify_document_with_confidence(
    llm,
    file_name: str,
    content: str,
    use_rules_first: bool = True
) -> DocumentMetadata:
    """
    统一分类入口 (异步)
    Args:
        llm: LangChain LLM 实例
        file_name: 文件名
        content: 文档内容
        use_rules_first: 是否先尝试规则分类（建议 True）
    Returns:
        DocumentMetadata 对象
    """
    # 1. 构建 Prompt
    prompt = DocumentClassificationPromptBuilder.build_classification_prompt(file_name, content)

    try:
        # LLM 异步调用
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = response.content

        # --- 修改点：使用 safe_parse_json ---
        # 替代原有的 re.sub 清洗和 json.loads
        data = safe_parse_json(text)
        # ----------------------------------

        # 映射分类
        category = DocumentClassificationPromptBuilder.map_to_standard_category(data.get("category", ""))

        # 如果 LLM 没分出来，尝试用规则兜底
        if category == DocumentCategory.OTHER and use_rules_first:
            rule_cat = RuleBasedClassifier.classify_by_filename(file_name)
            if rule_cat:
                category = rule_cat

        return DocumentMetadata(
            category=category,
            sub_category=data.get("sub_category", "未知"),
            confidence=data.get("confidence", 0.6),
            parties=data.get("parties", []),
            key_dates=data.get("key_dates", []),
            summary=data.get("summary", ""),
            risk_tags=data.get("risk_tags", []),
            raw_llm_output=data
        )

    except Exception as e:
        logger.error(f"分类失败 {file_name}: {e}")
        # 降级返回
        rule_cat = RuleBasedClassifier.classify_by_filename(file_name) or DocumentCategory.OTHER
        return DocumentMetadata(
            category=rule_cat,
            sub_category="未知",
            confidence=0.0,
            summary="自动分析失败"
        )