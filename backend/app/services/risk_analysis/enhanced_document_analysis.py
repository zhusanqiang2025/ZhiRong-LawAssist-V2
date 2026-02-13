# backend/app/services/risk_analysis/enhanced_document_analysis.py

import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.common.unified_document_service import StructuredDocumentResult
from app.schemas.risk_analysis_preorganization import (
    DocumentCategory, 
    PreorganizedDocuments,
    DocumentSummary
)

logger = logging.getLogger(__name__)

# ==================== 数据模型 (优化版) ====================

@dataclass
class PartyProfile:
    """主体画像"""
    name: str
    role: str  # 甲方/乙方/担保方/审计方等
    obligations: List[str]  # 核心义务
    rights: List[str]       # 核心权利
    risk_exposure: str      # 风险敞口描述

@dataclass
class TransactionTimeline:
    """交易时间线事件"""
    date: str
    event: str
    source_doc: str
    type: str  # 签署/履行/违约/变更

@dataclass
class EnhancedAnalysisResult:
    """增强分析结果 - 也就是'交易全景图'"""
    # 1. 交易核心
    transaction_summary: str        # 交易故事 (Narrative)
    contract_status: str            # 磋商/履约/争议/终止

    # 2. 主体分析
    parties: List[PartyProfile]     # 各方画像

    # 3. 动态演进
    timeline: List[TransactionTimeline]  # 关键事件时间线
    doc_relationships: List[Dict]   # 结构化的文档关系 (用于前端画图)

    # 4. 争议焦点 (如有)
    dispute_focus: Optional[str]

    # 5. 架构图 (如有)
    architecture_diagram: Optional[Dict[str, Any]] = None  # 股权/投资架构图数据

# ==================== 增强分析服务 ====================

class EnhancedDocumentAnalysisService:
    """
    增强型文档分析服务 (Level 2)
    
    不再重复做基础提取，而是基于 Level 1 的结果进行 '推理' 和 '综合'。
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    async def analyze_documents(
        self,
        documents: List[StructuredDocumentResult],
        preorganized_data: PreorganizedDocuments, # [关键修改] 接收 Level 1 的结果
        user_context: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> EnhancedAnalysisResult:
        """
        基于预整理数据进行深度推理
        """
        logger.info(f"[EnhancedAnalysis] 开始深度分析")

        async def update_progress(step: str, prog: float, msg: str):
            if progress_callback:
                await progress_callback(step, prog, msg)

        # 准备上下文数据 (从预整理结果中提取，避免重复 Token)
        # 我们将 Summaries 拼接成一个大的 Context
        context_str = self._build_context_from_summaries(preorganized_data)

        # 1. 交易全景与主体分析 (LLM 一次性推理)
        await update_progress("macro_analysis", 0.50, "正在构建交易全景图...")
        macro_result = await self._analyze_transaction_macro(context_str, user_context)

        # 2. 时间线与关系梳理
        await update_progress("timeline_analysis", 0.65, "正在梳理时间线与文档关系...")
        timeline_result = await self._analyze_timeline_and_relations(context_str, preorganized_data)

        # 3. 整合结果
        await update_progress("finalize", 0.75, "增强分析整合完成")
        
        return EnhancedAnalysisResult(
            transaction_summary=macro_result.get("transaction_summary", "无法生成综述"),
            contract_status=macro_result.get("contract_status", "未知"),
            parties=[PartyProfile(**p) for p in macro_result.get("parties", [])],
            dispute_focus=macro_result.get("dispute_focus"),
            timeline=[TransactionTimeline(**t) for t in timeline_result.get("timeline", [])],
            doc_relationships=timeline_result.get("relationships", [])
        )

    # ==================== 内部逻辑 ====================

    def _build_context_from_summaries(self, preorganized: PreorganizedDocuments) -> str:
        """将 Level 1 的摘要转换为 LLM 可读的 Context"""
        lines = []
        for path, summary in preorganized.document_summaries.items():
            fname = path.split('/')[-1]
            # 找到对应的分类
            cat = "未知类型"
            for c, paths in preorganized.document_classification.items():
                if path in paths:
                    cat = c
                    break
            
            lines.append(f"### 文档: {fname} ({cat})")
            lines.append(f"- 核心内容: {summary.summary}")
            lines.append(f"- 关键主体: {', '.join(summary.key_parties)}")
            lines.append(f"- 风险信号: {', '.join(summary.risk_signals)}")
            lines.append("")
        
        return "\n".join(lines)[:15000] # 截断防止超长

    async def _analyze_transaction_macro(self, context: str, user_req: str) -> Dict[str, Any]:
        """宏观分析：交易故事、主体画像、状态判断"""
        prompt = f"""作为首席法务官，请基于以下文档摘要集，对本次交易/案件进行宏观分析。

用户背景: {user_req or "无"}

文档摘要集:
{context}

请输出 JSON (严格遵循格式):
{{
    "transaction_summary": "300字以内的交易/案件叙事性综述。例如：'A公司与B公司于2023年签署设备采购合同，但在履行过程中因质量问题发生争议...'",
    "contract_status": "从以下选择其一: [磋商阶段, 正常履约中, 履约瑕疵, 实质性违约, 合同终止, 诉讼/仲裁中]",
    "dispute_focus": "如果存在争议，简述争议焦点；否则返回 null",
    "parties": [
        {{
            "name": "主体全称",
            "role": "在交易中的角色 (如: 供货方)",
            "obligations": ["核心义务1", "核心义务2"],
            "rights": ["核心权利1"],
            "risk_exposure": "该主体面临的主要风险 (如: 回款风险)"
        }}
    ]
}}
"""
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            return json.loads(self._clean_json(response.content))
        except Exception as e:
            logger.error(f"[EnhancedAnalysis] 宏观分析失败: {e}")
            return {}

    async def _analyze_timeline_and_relations(self, context: str, preorganized: PreorganizedDocuments) -> Dict[str, Any]:
        """微观分析：时间线与文档间关系"""
        prompt = f"""请基于文档摘要，梳理时间线和文档间的逻辑关系。

文档摘要集:
{context}

任务要求:
1. 提取所有关键事件及其日期。
2. 识别文档间的引用、修订、补充关系。

请输出 JSON:
{{
    "timeline": [
        {{"date": "YYYY-MM-DD", "event": "事件描述", "source_doc": "来源文件名", "type": "签署/履行/违约/其他"}}
    ],
    "relationships": [
        {{"source": "文件名A", "target": "文件名B", "type": "补充/修订/附件/解除/冲突", "reason": "简述理由"}}
    ]
}}
"""
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            data = json.loads(self._clean_json(response.content))
            
            # 后处理：确保 timeline 按时间排序
            timeline = data.get("timeline", [])
            timeline.sort(key=lambda x: x.get("date", "0000"))
            
            return {
                "timeline": timeline,
                "relationships": data.get("relationships", [])
            }
        except Exception as e:
            logger.error(f"[EnhancedAnalysis] 时间线分析失败: {e}")
            return {}

    def _clean_json(self, text: str) -> str:
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        return text.strip()

# ==================== 工厂函数 ====================

def get_enhanced_document_analysis_service(llm: ChatOpenAI) -> EnhancedDocumentAnalysisService:
    return EnhancedDocumentAnalysisService(llm)