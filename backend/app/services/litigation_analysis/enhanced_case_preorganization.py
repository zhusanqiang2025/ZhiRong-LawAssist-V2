# backend/app/services/litigation_analysis/enhanced_case_preorganization.py
"""
增强版案件文档预整理服务 (Unified Case Preorganization Service)

核心改进：
1. 统一入口：不再区分基础/增强服务，根据上下文自动调整视角。
2. 深度适配：针对起诉、仲裁、执行等不同文书类型，使用高度定制的 Prompt。
3. 前端对齐：输出结构直接适配 RiskAnalysisPageV2 的展示组件。
"""

import logging
import json
import asyncio
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from langchain_core.messages import SystemMessage, HumanMessage
from app.services.unified_document_service import StructuredDocumentResult

logger = logging.getLogger(__name__)

# ==================== 数据模型 ====================

@dataclass
class DocumentAnalysisResult:
    """单文档分析结果"""
    file_path: str
    file_name: str
    doc_type: str
    summary: str
    document_title: str  # 从文件内容中提取的标题
    key_dates: List[str]
    key_facts: List[str]  # 关键法律事实
    key_amounts: List[str]  # 关键金额信息
    parties: List[Dict[str, str]]
    claims_or_defenses: List[str]
    risk_signals: List[str]
    # 额外元数据，用于生成全景图
    extra_meta: Dict[str, Any]
    # 原文预览（前3000字），用于下游分析
    raw_preview: str = ""

# ==================== 核心服务类 ====================

class EnhancedCasePreorganizationService:
    """统一案件预整理服务"""

    def __init__(self, llm_service):
        self.llm = llm_service
        self._semaphore = asyncio.Semaphore(5)

    async def preorganize_enhanced(
        self,
        documents: List[StructuredDocumentResult],
        case_type: str = "通用案件",
        case_position: Optional[str] = None,
        analysis_scenario: Optional[str] = None,
        user_context: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """执行预整理（主入口）"""
        logger.info(f"[CasePreorg] 开始预整理 {len(documents)} 个文档 | 视角: {case_position or '中立'}")

        async def update_progress(step: str, prog: float, msg: str):
            if progress_callback:
                await progress_callback(step, prog, msg)

        # 1. 智能分类
        await update_progress("classify", 0.10, "正在识别法律文书类型...")
        doc_classifications = self._classify_documents_by_filename(documents)

        # 2. 并行深度提取
        await update_progress("extract", 0.20, "正在提取案情关键要素...")
        doc_analyses = await self._analyze_documents_parallel(
            documents, doc_classifications, case_type, update_progress
        )

        # 3. 构建案件全景
        await update_progress("synthesize", 0.60, "正在梳理案件脉络与争议焦点...")
        panorama = await self._generate_case_panorama(
            doc_analyses, case_type, user_context, case_position
        )

        # 4. 文档关系分析
        await update_progress("relationships", 0.85, "正在分析文书关联...")
        relationships = await self._analyze_relationships(doc_analyses)

        # 5. 组装最终结果
        # 修复：使用唯一的键避免文件覆盖
        summaries = {}
        for idx, res in enumerate(doc_analyses):
            # 优先用 file_path，如果为空则用 file_name + 索引确保唯一性
            key = res.file_path if res.file_path else f"doc_{idx}_{res.file_name}"

            # 修复 document_title 优先级问题
            # 优先使用 LLM 从内容提取的 document_title，其次使用文档类型标签
            if res.document_title and res.document_title not in ["unknown", "Unknown", ""]:
                document_title = res.document_title
            else:
                # 使用文档类型的中文标签作为标题
                type_labels = {
                    "arbitration_application": "仲裁申请书",
                    "arbitration_award": "仲裁裁决书",
                    "arbitration_notice": "仲裁通知书",
                    "arbitration_doc": "仲裁文书",
                    "execution_application": "执行申请书",
                    "execution_order": "执行裁定书",
                    "execution_notice": "执行通知书",
                    "execution_doc": "执行文书",
                    "preservation_application": "保全申请书",
                    "complaint": "起诉状",
                    "defense": "答辩状",
                    "appeal": "上诉状",
                    "judgment": "判决书",
                    "ruling": "裁定书",
                    "mediation": "调解书",
                    "evidence": "证据材料",
                    "contract": "合同/协议",
                    "lawyer_letter": "律师函",
                    "correspondence": "往来函件"
                }
                document_title = type_labels.get(res.doc_type, "法律文书")

            summaries[key] = {
                "file_path": res.file_path,
                "summary": res.summary,
                "document_title": document_title,
                "document_subtype": res.doc_type,
                "risk_signals": res.risk_signals,
                "key_dates": res.key_dates,
                "key_facts": res.key_facts,  # 新增：关键法律事实
                "key_amounts": res.key_amounts,  # 新增：关键金额信息
                "key_parties": [p["name"] for p in res.parties],
                "raw_preview": res.raw_preview  # 新增：原文预览
            }

        final_result = {
            "document_summaries": summaries,
            "enhanced_analysis_compatible": {
                "transaction_summary": panorama.get("case_narrative", ""),
                "contract_status": panorama.get("procedural_status", "未知阶段"),
                "dispute_focus": panorama.get("core_dispute", ""),
                "parties": panorama.get("party_profiles", []),
                "timeline": panorama.get("timeline", []),
                "doc_relationships": relationships
            },
            "case_type": case_type,
            "case_position": case_position,
            "analysis_scenario": analysis_scenario
        }

        await update_progress("completed", 1.0, "预整理完成")
        return final_result

    # ==================== 1. 文档分类 (细粒度) ====================

    def _classify_documents_by_filename(self, documents: List[StructuredDocumentResult]) -> Dict[str, str]:
        """
        基于文件名的快速分类
        涵盖：诉讼、仲裁、执行、证据、合同、函件
        """
        mapping = {}
        for doc in documents:
            name = doc.metadata.get("filename", "").lower()
            path = doc.metadata.get("file_path", "")
            dtype = "other"

            # 1. 仲裁/劳动争议
            if "仲裁" in name or "劳动" in name:
                if "申请" in name: dtype = "arbitration_application"
                elif "裁决" in name: dtype = "arbitration_award"
                elif "通知" in name: dtype = "arbitration_notice"
                else: dtype = "arbitration_doc"
            
            # 2. 强制执行/保全
            elif "执行" in name:
                if "申请" in name: dtype = "execution_application"
                elif "裁定" in name: dtype = "execution_order"
                elif "通知" in name: dtype = "execution_notice"
                else: dtype = "execution_doc"
            elif "保全" in name:
                dtype = "preservation_application"

            # 3. 民事诉讼 - 起诉/答辩
            elif any(k in name for k in ["起诉", "诉状", "complaint"]): dtype = "complaint"
            elif any(k in name for k in ["答辩", "defense"]): dtype = "defense"
            elif any(k in name for k in ["上诉", "appeal"]): dtype = "appeal"
            
            # 4. 法院裁判
            elif any(k in name for k in ["判决", "judgment"]): dtype = "judgment"
            elif any(k in name for k in ["裁定", "ruling"]): dtype = "ruling"
            elif "调解书" in name: dtype = "mediation"
            
            # 5. 证据材料
            elif any(k in name for k in ["证据", "清单", "evidence"]): dtype = "evidence"
            
            # 6. 基础合同/函件
            elif any(k in name for k in ["合同", "协议", "contract"]): dtype = "contract"
            elif any(k in name for k in ["律师函", "催告"]): dtype = "lawyer_letter"
            elif any(k in name for k in ["函", "通知", "notice"]): dtype = "correspondence"
            
            mapping[path] = dtype
        return mapping

    # ==================== 2. 并行深度提取 (含详细 Prompt) ====================

    async def _analyze_documents_parallel(
        self, 
        documents: List[StructuredDocumentResult],
        classifications: Dict[str, str],
        case_type: str,
        progress_cb
    ) -> List[DocumentAnalysisResult]:
        tasks = []
        for doc in documents:
            path = doc.metadata.get("file_path", "")
            dtype = classifications.get(path, "other")
            tasks.append(self._analyze_single_doc(doc, dtype, case_type))
        
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def _analyze_single_doc(
        self, 
        doc: StructuredDocumentResult, 
        dtype: str, 
        case_type: str
    ) -> Optional[DocumentAnalysisResult]:
        """分析单个文档，使用高度定制的 Prompt"""
        filename = doc.metadata.get("filename", "unknown")
        content = doc.content[:8000]

        # --- Prompt 策略中心 ---
        # 这里保留并优化了原代码中的详细 Prompt，确保提取的专业性
        
        base_instruction = "提取核心法律事实、关键日期、金额及当事人。"
        
        type_prompts = {
            # === 仲裁类 ===
            "arbitration_application": """
                角色：【仲裁律师】
                重点提取：
                1. 申请人与被申请人（注意劳动仲裁中的用人单位/劳动者身份）
                2. 具体的仲裁请求（金额、恢复劳动关系等）
                3. 事实与理由的核心逻辑
                4. 管辖依据（仲裁条款/劳动合同履行地）
            """,
            "arbitration_award": """
                角色：【仲裁员助理】
                重点提取：
                1. 裁决结果（支持/驳回的比例）
                2. 仲裁庭认定的关键事实
                3. 裁决依据的法律或合同条款
                4. 是否为终局裁决
            """,
            
            # === 执行类 ===
            "execution_application": """
                角色：【执行律师】
                重点提取：
                1. 申请执行的依据（判决书/仲裁裁决书案号）
                2. 被执行人的财产线索描述
                3. 申请执行的具体金额和款项性质
            """,
            "execution_order": """
                角色：【执行法官】
                重点提取：
                1. 查封/冻结/扣押的具体财产
                2. 执行异议的处理结果
                3. 是否终结本次执行
            """,

            # === 诉讼类 ===
            "complaint": """
                角色：【资深诉讼律师】
                重点提取：
                1. 原告的完整诉讼请求（拆解为具体项）
                2. 事实与理由中的因果关系链条
                3. 违约/侵权的关键时间节点
                4. 法律适用依据
            """,
            "defense": """
                角色：【被告代理人】
                重点提取：
                1. 针对原告请求的逐项反驳意见
                2. 提出的新事实或抗辩事由（如时效、管辖）
                3. 是否承认部分事实
            """,
            "judgment": """
                角色：【法官助理】
                重点提取：
                1. "本院认为"部分的核心逻辑
                2. 判决主文（确切的给付金额/义务）
                3. 诉讼费承担比例
                4. 认定的争议焦点
            """,

            # === 证据/合同 ===
            "evidence": """
                角色：【质证律师】
                重点提取：
                1. 证据名称与页码
                2. 证明目的（想要证明什么事实）
                3. 证据的三性（真实性/合法性/关联性）初步扫描
            """,
            "contract": """
                角色：【非诉律师】
                重点提取：
                1. 核心交易条款（标的、价格、交付）
                2. 违约责任与解除条件
                3. 争议解决条款（仲裁还是诉讼？管辖地？）
            """
        }

        specific_instruction = type_prompts.get(dtype, base_instruction)

        prompt = f"""你是一名法律助手。请分析这份【{case_type}】案件中的【{dtype}】文件。

文件名: {filename}
任务目标: {specific_instruction}

文档内容片段:
{content}

请严格返回 JSON 格式：
{{
    "summary": "100字以内的核心摘要，说明这是谁发起的什么程序，核心诉求是什么。",
    "document_title": "从文件内容中提取的文档标题，如'民事起诉状'、'仲裁裁决书'、'判决书'等（优先使用文件内容中的真实标题，而非文件名）",
    "parties": [{{"name": "主体名", "role": "申请人/被申请人/原告/被告"}}],
    "key_dates": ["YYYY-MM-DD 事件描述"],
    "key_facts": ["关键法律事实1（如违约行为、侵权事实、合同条款等）", "关键法律事实2"],
    "key_amounts": ["金额描述（如：合同金额100万元、欠款50万元、违约金20万元等）"],
    "claims_or_defenses": ["请求1", "抗辩1"],
    "risk_signals": ["程序瑕疵", "证据不足", "时效风险"],
    "extra_meta": {{ "key": "value" }}
}}
"""
        # 注意：extra_meta 用于存储特定文书的专有字段，如案号、法院名等

        try:
            async with self._semaphore:
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])

                # 记录原始响应用于调试
                logger.debug(f"[{filename}] LLM 原始响应长度: {len(response.content)}")

                cleaned_json = self._clean_json(response.content)
                logger.debug(f"[{filename}] 清理后 JSON 长度: {len(cleaned_json)}")

                try:
                    data = json.loads(cleaned_json)
                except json.JSONDecodeError as je:
                    # JSON 解析失败，记录详细错误
                    logger.error(f"[{filename}] JSON 解析失败: {je}")
                    logger.error(f"[{filename}] 清理后的 JSON 前 500 字符: {cleaned_json[:500]}")
                    # 尝试提取可能的 JSON 片段
                    raise

                return DocumentAnalysisResult(
                    file_path=doc.metadata.get("file_path", ""),
                    file_name=filename,
                    doc_type=dtype,
                    summary=data.get("summary", "无法生成摘要"),
                    document_title=data.get("document_title", ""),  # 从内容提取的标题
                    key_dates=data.get("key_dates", []),
                    key_facts=data.get("key_facts", []),  # 新增：关键法律事实
                    key_amounts=data.get("key_amounts", []),  # 新增：关键金额信息
                    parties=data.get("parties", []),
                    claims_or_defenses=data.get("claims_or_defenses", []),
                    risk_signals=data.get("risk_signals", []),
                    extra_meta=data.get("extra_meta", {}),
                    raw_preview=content[:3000]  # 新增：保存前3000字原文用于下游分析
                )
        except Exception as e:
            logger.error(f"文档分析失败 {filename}: {e}", exc_info=True)
            return DocumentAnalysisResult(
                file_path=doc.metadata.get("file_path", ""),
                file_name=filename,
                doc_type=dtype,
                summary=f"自动分析失败: {filename}",
                document_title="",  # 失败时使用空标题
                key_dates=[],
                key_facts=[],  # 新增
                key_amounts=[],  # 新增
                parties=[],
                claims_or_defenses=[],
                risk_signals=[],
                extra_meta={},
                raw_preview=content[:3000]  # 新增：即使分析失败也保存原文
            )

    # ==================== 3. 案件全景生成 (整合层) ====================

    async def _generate_case_panorama(
        self,
        analyses: List[DocumentAnalysisResult],
        case_type: str,
        user_context: str,
        position: Optional[str]
    ) -> Dict[str, Any]:
        """
        生成案件全景综述
        """
        docs_summary = "\n".join([
            f"- [{doc.doc_type}] {doc.file_name}: {doc.summary}" 
            for doc in analyses
        ])
        
        perspective = f"作为{position}的代理律师" if position else "作为中立的法律顾问"

        prompt = f"""{perspective}，请基于以下案件材料，梳理案情全景。

案件类型: {case_type}
用户背景: {user_context or "无"}

文档列表:
{docs_summary}

请输出 JSON 格式：
{{
    "case_narrative": "300字以内的案情综述。按时间顺序描述纠纷起因、程序进展（诉讼/仲裁/执行）。例如：'申请人A与被申请人B存在劳动争议，A向XX仲裁委提起仲裁...'",
    "procedural_status": "当前程序阶段 (如：劳动仲裁审理中 / 一审待开庭 / 申请执行中)",
    "core_dispute": "核心争议焦点",
    "party_profiles": [
        {{
            "name": "主体名",
            "role": "申请人/原告/...",
            "obligations": ["核心请求 (如: 支付工资、赔偿金)"],
            "rights": ["主要抗辩理由"],
            "risk_exposure": "主要风险点"
        }}
    ],
    "timeline": [
        {{"date": "YYYY-MM-DD", "event": "事件", "source_doc": "来源文件", "type": "程序/事实"}}
    ]
}}
"""
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            cleaned = self._clean_json(response.content)
            result = json.loads(cleaned)

            # 验证必需字段
            required_fields = ["case_narrative", "procedural_status", "core_dispute", "party_profiles", "timeline"]
            for field in required_fields:
                if field not in result:
                    logger.warning(f"[案件全景] 缺少必需字段: {field}")
                    result[field] = [] if field in ["party_profiles", "timeline"] else ""

            return result
        except json.JSONDecodeError as e:
            logger.error(f"[案件全景] JSON 解析失败: {e}, 原始内容: {response.content[:200]}...")
            return {
                "case_narrative": "无法生成案情综述（JSON 解析失败）",
                "procedural_status": "未知",
                "core_dispute": "无法确定争议焦点",
                "party_profiles": [],
                "timeline": []
            }
        except Exception as e:
            logger.error(f"[案件全景] 生成失败: {e}", exc_info=True)
            return {
                "case_narrative": "无法生成案情综述",
                "procedural_status": "未知",
                "core_dispute": "无法确定争议焦点",
                "party_profiles": [],
                "timeline": []
            }

    # ==================== 4. 关系分析 ====================

    async def _analyze_relationships(self, analyses: List[DocumentAnalysisResult]) -> List[Dict]:
        """文档关系分析"""
        relationships = []
        for i, doc1 in enumerate(analyses):
            for doc2 in analyses[i+1:]:
                rel_type = None
                
                # 仲裁裁决 -> 申请执行
                if "award" in doc1.doc_type and "execution" in doc2.doc_type:
                    rel_type = "enforces"
                
                # 判决/裁决 vs 起诉/申请
                elif ("judgment" in doc1.doc_type or "award" in doc1.doc_type) and \
                     ("complaint" in doc2.doc_type or "application" in doc2.doc_type):
                    rel_type = "ruling_on"
                
                # 证据 vs 申请/起诉
                elif "evidence" in doc1.doc_type and ("complaint" in doc2.doc_type or "application" in doc2.doc_type):
                    rel_type = "supports"
                
                # 答辩 vs 申请/起诉
                elif "defense" in doc1.doc_type and ("complaint" in doc2.doc_type or "application" in doc2.doc_type):
                    rel_type = "refutes"

                if rel_type:
                    relationships.append({
                        "doc1_name": doc1.file_name,
                        "doc2_name": doc2.file_name,
                        "relationship_type": rel_type,
                        "reasoning": "根据文书程序逻辑推断"
                    })
        return relationships

    def _clean_json(self, text: str) -> str:
        """清理 LLM 返回的 JSON 文本（增强版）"""
        if not text:
            return "{}"

        # 移除 markdown 代码块标记
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # 尝试提取第一个完整的 JSON 对象
        try:
            # 查找第一个 { 和最后一个 }
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                text = text[start:end+1]

            # 修复常见的 JSON 格式问题
            # 1. 修复未转义的反斜杠
            text = text.replace('\\', '\\\\')

            # 2. 移除可能的注释（虽然 JSON 不支持注释，但 LLM 可能会添加）
            text = re.sub(r'//.*?\n', '\n', text)
            text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

            # 3. 修复尾随逗号（如 {"a": 1,} -> {"a": 1}）
            text = re.sub(r',\s*([}\]])', r'\1', text)

            # 4. 移除控制字符
            text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')

            return text
        except Exception as e:
            logger.warning(f"[JSON清理] 清理失败: {e}, 返回原始内容")
            # 如果清理失败，至少尝试提取原始的 JSON 部分
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                return text[start:end+1]
            return text

# 工厂函数
def get_enhanced_case_preorganization_service(llm_service) -> EnhancedCasePreorganizationService:
    return EnhancedCasePreorganizationService(llm_service)