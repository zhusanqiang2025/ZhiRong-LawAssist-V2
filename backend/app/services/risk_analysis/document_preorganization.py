# backend/app/services/risk_analysis/document_preorganization.py

import logging
import json
import re
import hashlib
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.unified_document_service import StructuredDocumentResult
from app.schemas.risk_analysis_preorganization import (
    DocumentCategory,  # 使用 Schema 中的枚举作为主数据结构
    DocumentQuality,
    DocumentRelationship,
    DocumentSummary,
    PreorganizedDocuments
)

# 假设你有图表生成服务
from app.services.risk_analysis.diagram_generator import DiagramGeneratorService, DiagramRequest, DiagramType, CompanyNode, ShareholderNode, EquityRelationship

# --- 新增导入：统一分类器和 JSON 工具 ---
from app.services.risk_analysis.document_classifier import classify_document_with_confidence, DocumentCategory as ClassifierCategory
from app.utils.json_helper import safe_parse_json

logger = logging.getLogger(__name__)


class DocumentPreorganizationService:
    """
    文档预整理服务（风险评估专用版）

    功能：
    1. 智能分类与质量体检
    2. 风险导向的结构化摘要提取
    3. 跨文档关系梳理
    4. 交易背景综述生成
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        # [P0.2] Concurrent control: limit to 5 concurrent LLM requests
        self._semaphore = asyncio.Semaphore(5)

    async def preorganize(
        self,
        documents: List[StructuredDocumentResult],
        user_context: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> PreorganizedDocuments:
        """
        预整理文档集合
        """
        logger.info(f"[RiskPreorg] 开始预整理 {len(documents)} 个文档")

        # 辅助函数：发送进度
        async def update_progress(step: str, progress: float, message: str):
            if progress_callback:
                await progress_callback(step, progress, message)

        # 1. 文档分类 (10-20%)
        await update_progress("classification", 0.15, "正在识别文档类型...")
        classification = await self._classify_documents(documents, user_context)

        # 2. 质量评估 (20-30%)
        await update_progress("quality", 0.25, "正在评估文档完整性与清晰度...")
        quality_scores = await self._assess_quality(documents, classification)

        # 3. 智能摘要 (30-60%) - 核心步骤
        await update_progress("summary", 0.40, "正在提取关键条款与风险信号...")
        summaries = await self._generate_risk_oriented_summaries(documents, classification)

        # 4. 实体归一化 (为关系分析做准备)
        normalized_entities = self._normalize_entities(summaries)

        # 5. 关系分析 (60-80%)
        await update_progress("relationship", 0.70, "正在梳理文档间的法律关系...")
        relationships = await self._analyze_relationships(documents, summaries)

        # 6. 重复检测
        duplicates = await self._detect_duplicates(documents)

        # 7. 重要性排序
        ranked = self._rank_documents(documents, classification, quality_scores, relationships)

        # 8. 跨文档信息提取 (80-90%)
        await update_progress("cross_doc", 0.85, "正在生成交易全景综述...")
        cross_doc_info = await self._generate_transaction_overview(
            summaries, relationships, normalized_entities, user_context
        )

        logger.info("[RiskPreorg] 基础预整理完成")

        return PreorganizedDocuments(
            raw_documents=[doc.to_dict() for doc in documents],
            document_classification={cat.value: paths for cat, paths in classification.items()},
            quality_scores=quality_scores,
            document_summaries=summaries,
            document_relationships=relationships,
            duplicates=duplicates,
            ranked_documents=ranked,
            cross_doc_info=cross_doc_info
        )

    # ==================== 核心逻辑方法 ====================

    async def _classify_documents(
        self,
        documents: List[StructuredDocumentResult],
        user_context: Optional[str]
    ) -> Dict[DocumentCategory, List[str]]:
        """
        分类文档：使用统一的 document_classifier 服务
        """
        classification = {cat: [] for cat in DocumentCategory}

        for doc in documents:
            file_path = doc.metadata.get("file_path", "")
            filename = doc.metadata.get("filename", "")

            try:
                # 调用统一分类器
                meta = await classify_document_with_confidence(
                    self.llm,
                    filename,
                    doc.content,
                    use_rules_first=True
                )

                # 映射分类器返回的 Category 到本地 Schema 的 DocumentCategory
                try:
                    # 获取枚举的值 (如 "contract")
                    cat_value = meta.category.value if hasattr(meta.category, 'value') else str(meta.category)
                    target_category = DocumentCategory(cat_value)
                except ValueError:
                    # 如果值不匹配，默认归为 OTHER
                    logger.warning(f"分类器返回未知类型: {meta.category}, 归类为 OTHER")
                    target_category = DocumentCategory.OTHER

                classification[target_category].append(file_path)

            except Exception as e:
                logger.error(f"文档 {filename} 分类失败: {e}")
                # 降级：尝试根据文件名简单判断
                fallback_cat = DocumentCategory.OTHER
                if "合同" in filename or "协议" in filename: fallback_cat = DocumentCategory.CONTRACT
                elif "执照" in filename: fallback_cat = DocumentCategory.BUSINESS_LICENSE
                classification[fallback_cat].append(file_path)

        return classification

    async def _generate_risk_oriented_summaries(
        self,
        documents: List[StructuredDocumentResult],
        classification: Dict[DocumentCategory, List[str]]
    ) -> Dict[str, DocumentSummary]:
        """
        生成风险导向的摘要 (优化版：并行处理)
        """
        summaries = {}
        logger.info(f"[RiskPreorg] 开始生成 {len(documents)} 个文档的摘要 (并行模式)")

        # 定义针对不同文档类型的 Prompt 策略
        prompts_map = {
            DocumentCategory.CONTRACT: f"""
                请作为一名【风控专家】分析此合同。提取以下信息（JSON格式）：
                1. **document_title**（重要）：文档内容的正式标题，如"股权转让协议"、"保密协议"、"采购合同"等
                - 位于文档开头第一行或前几行
                - 格式通常为："XX合同"、"XX协议"等
                - 如果文档没有明确标题，根据内容推断（如"设备采购合同"）
                2. **document_subtype**：具体合同类型，如：股权转让协议、增资协议、股东会决议、公司章程、保密协议、采购合同等
                3. **document_purpose**（1-2句话）：为什么创建这个文档？要解决什么问题？
                4. **party_positions**（如有）：各方的主要诉求或立场是什么？例如：甲方要求XX，乙方要求XX
                5. **summary**（2-3句话）：文档的核心信息或达成的共识
                6. **key_parties**：甲方、乙方及担保方全称
                7. **key_dates**：签署日、生效日、履行截止日
                8. **key_amounts**：交易总额、违约金比例
                9. **risk_signals**：提取高风险条款，如：
                - 单方解除权
                - 严苛的违约责任
                - 管辖法院在对方所在地
                - 知识产权归属不明
            """,
            DocumentCategory.FINANCIAL_REPORT: f"""
                请作为一名【审计师】分析此财务文档。提取以下信息（JSON格式）：
                1. **document_title**（重要）：文档内容的正式标题，如"2024年度审计报告"、"资产负债表"等
                - 位于文档开头第一行或前几行
                - 格式通常为："XX审计报告"、"XX财务报表"等
                2. **document_subtype**：具体财务报告类型，如：审计报告、财务报表、验资报告、评估报告等
                3. **document_purpose**（1-2句话）：为什么需要这个财务文档？
                4. **party_positions**：此字段对于财务报告通常不适用，可留空
                5. **summary**：报告期间及核心财务状况概述
                6. **key_parties**：被审计单位名称
                7. **key_dates**：报表截止日
                8. **key_amounts**：营收、净利润、负债总额
                9. **risk_signals**：提取异常指标，如：
                - 资不抵债
                - 经营性现金流为负
                - 审计意见为"非标准无保留意见"
            """,
            DocumentCategory.BUSINESS_LICENSE: f"""
                提取核心工商信息（JSON格式）：
                1. **document_title**（重要）：证照名称，如"营业执照"、"资质证书"等
                2. **document_subtype**：证照类型，如：营业执照、资质证书等
                3. **document_purpose**：此证照的用途
                4. **party_positions**：此字段对于证照通常不适用，可留空
                5. **summary**：公司基本情况（成立时间、注册资本）
                6. **key_parties**：公司名称、法人代表
                7. **key_dates**：成立日期、营业期限
                8. **key_amounts**：注册资本
                9. **risk_signals**：经营范围受限、注册资本未实缴（如能看出）、营业期限即将届满
            """,
            DocumentCategory.SHAREHOLDER: f"""
                请作为一名【公司法专家】分析此股东文件。提取以下信息（JSON格式）：
                1. **document_title**（重要）：文档内容的正式标题，如"股东会决议"、"股权转让协议"等
                - 位于文档开头第一行或前几行
                - 格式通常为："XX决议"、"XX协议"等
                2. **document_subtype**：具体文件类型，如：股东会决议、董事会决议、股权转让协议、公司章程等
                3. **document_purpose**（1-2句话）：为什么创建这个文档？要解决什么问题？
                4. **party_positions**（如有）：各方的主要诉求或立场是什么？例如：控股股东要求XX，小股东要求XX
                5. **summary**：文档的核心内容或达成的共识
                6. **key_parties**：涉及的股东、公司名称
                7. **key_dates**：会议日期、决议生效日期
                8. **key_amounts**：注册资本、持股比例、交易金额（如有）
                9. **risk_signals**：程序不合规、侵害小股东权益、违反章程等
            """
        }
        default_prompt = "作为法律助理，提取核心事实、当事人、日期、金额及潜在风险点。"

        # ==================== 并行处理逻辑 ====================
        tasks = []

        # 1. 准备任务：身份证件直接处理，其他文档创建异步任务
        for doc in documents:
            # 获取文件路径（复用之前修复的逻辑）
            raw_file_path = doc.metadata.get("file_path") or doc.metadata.get("original_filename")
            category = self._get_doc_category(raw_file_path, classification)

            # 身份证件简单处理（不需要 LLM，直接同步处理）
            if category == DocumentCategory.ID_DOCUMENT:
                summaries[raw_file_path] = DocumentSummary(
                    file_path=raw_file_path,
                    document_title="身份证明文件",
                    document_type_label=self._get_category_label(category),
                    document_subtype=None,
                    document_purpose=None,
                    party_positions=None,
                    summary="身份证明文件",
                    key_parties=[],
                    key_dates=[],
                    key_amounts=[],
                    risk_signals=[]
                )
                logger.info(f"[RiskPreorg] 已处理文档（身份证件）: {raw_file_path}")
                continue

            # 获取对应的 Prompt 指令
            instruction = prompts_map.get(category, default_prompt)

            # 创建异步任务
            tasks.append(self._summarize_single_document(doc, category, instruction))

        # 2. 并行执行所有 LLM 任务
        if tasks:
            logger.info(f"[RiskPreorg] 并行调用 LLM 处理 {len(tasks)} 个文档...")
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 3. 汇总结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"[RiskPreorg] 并行任务 {i} 失败: {result}")
                    continue

                if isinstance(result, DocumentSummary):
                    summaries[result.file_path] = result
                else:
                    logger.warning(f"[RiskPreorg] 任务 {i} 返回了未知类型: {type(result)}")

        logger.info(f"[RiskPreorg] 摘要生成完成，共 {len(summaries)} 个文档")
        return summaries

    # ==================== 新增辅助方法 ====================

    async def _summarize_single_document(
        self,
        doc: StructuredDocumentResult,
        category: DocumentCategory,
        instruction: str
    ) -> DocumentSummary:
        """
        处理单个文档的摘要生成（用于并行调用）
        """
        raw_file_path = doc.metadata.get("file_path") or doc.metadata.get("original_filename")
        content_sample = doc.content[:3000]  # 取前3000字符

        prompt = f"""
        文件名: {doc.metadata.get("filename")}
        文档类型: {category.value}
        {instruction}

        文档内容片段:
        {content_sample}

        请严格返回 JSON 格式：
        {{
            "document_title": "文档内容的正式标题（如：股权转让协议）",
            "document_subtype": "具体文档类型（如：股权转让协议、股东会决议等）",
            "document_purpose": "文档目的（1-2句话）",
            "party_positions": "各方诉求描述",
            "summary": "核心内容/结论（2-3句话）",
            "key_parties": ["..."],
            "key_dates": ["YYYY-MM-DD 说明"],
            "key_amounts": ["..."],
            "risk_signals": ["..."]
        }}
        """

        try:
            # 使用信号量控制并发
            async with self._semaphore:
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            # 使用 safe_parse_json 解析
            data = safe_parse_json(response.content)

            return DocumentSummary(
                file_path=raw_file_path,
                document_title=data.get("document_title"),
                document_type_label=self._get_category_label(category),
                document_subtype=data.get("document_subtype"),
                document_purpose=data.get("document_purpose"),
                party_positions=data.get("party_positions"),
                summary=data.get("summary", "无法生成摘要"),
                key_parties=data.get("key_parties", []),
                key_dates=data.get("key_dates", []),
                key_amounts=data.get("key_amounts", []),
                risk_signals=data.get("risk_signals", [])
            )
        except json.JSONDecodeError as e:
            logger.error(f"[RiskPreorg] JSON 解析失败 {raw_file_path}: {e}")
            return self._create_fallback_summary(raw_file_path, category, "JSON解析失败")
        except Exception as e:
            logger.warning(f"[RiskPreorg] 摘要生成异常 {raw_file_path}: {e}")
            return self._create_fallback_summary(raw_file_path, category, "自动分析失败")

    def _create_fallback_summary(self, file_path: str, category: DocumentCategory, error_msg: str) -> DocumentSummary:
        """生成降级摘要"""
        return DocumentSummary(
            file_path=file_path,
            document_title=None,
            document_type_label=self._get_category_label(category),
            document_subtype=None,
            document_purpose=None,
            party_positions=None,
            summary=error_msg,
            key_parties=[],
            key_dates=[],
            key_amounts=[],
            risk_signals=[]
        )

    async def _generate_transaction_overview(
        self,
        summaries: Dict[str, DocumentSummary],
        relationships: List[DocumentRelationship],
        entities: Dict[str, List[str]],
        user_context: Optional[str]
    ) -> Dict[str, Any]:
        """
        生成交易全景综述（Narrative）
        """
        # 构建 prompt 上下文
        docs_desc = []
        for path, s in summaries.items():
            fname = path.split('/')[-1]
            docs_desc.append(f"- 文件《{fname}》: {s.summary} (风险点: {len(s.risk_signals)}个)")

        context_str = "\n".join(docs_desc[:20])  # 限制数量防止超长

        prompt = f"""
        你是一名资深风控总监。请根据以下文档清单和摘要，为本次风险评估写一份【交易背景综述】。

        用户背景描述: {user_context or "无"}

        文档清单:
        {context_str}

        请分析并返回 JSON:
        {{
            "transaction_story": "用简练的商业语言描述这是什么交易（如：A公司向B公司采购设备，涉及总金额X元，并由C公司担保）。",
            "document_completeness_analysis": "现有文档是否构成了完整的交易闭环？缺失了什么关键文件（如：有主合同但缺附件，有决议但缺章程）？",
            "primary_risk_focus": "根据文档类型，本次审查应重点关注什么（如：重点关注知识产权条款、关注偿债能力等）。"
        }}
        """

        try:
            async with self._semaphore:
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            # 使用 safe_parse_json
            data = safe_parse_json(response.content)

            return {
                "transaction_story": data.get("transaction_story", ""),
                "document_completeness": data.get("document_completeness_analysis", ""),
                "primary_risk_focus": data.get("primary_risk_focus", ""),
                "all_parties": entities.get("all_parties", []),
                "total_risk_signals": sum(len(s.risk_signals) for s in summaries.values())
            }
        except Exception as e:
            logger.error(f"[RiskPreorg] 综述生成失败: {e}")
            return {}

    # ==================== 增强功能（Workflow中单独调用） ====================

    async def enhance_preorganization_result(
        self,
        documents: List[StructuredDocumentResult],
        summaries: Dict[str, DocumentSummary],
        classification: Dict[DocumentCategory, List[str]]
    ) -> Dict[str, Any]:
        """
        增强预整理结果：提取法律特征、生成架构图
        """
        logger.info("[RiskPreorg] 开始执行结果增强...")
        result = {
            "contract_legal_features": None,
            "architecture_diagram": None
        }

        # 1. 查询合同法律特征 (利用知识库或LLM)
        contract_docs = [d for d in documents if d.metadata.get("file_path") in classification.get(DocumentCategory.CONTRACT, [])]
        if contract_docs:
            result["contract_legal_features"] = await self._extract_legal_features(contract_docs[0])

        # 2. 生成股权架构图（新增三层验证）
        # 第一层: 预检查
        should_generate, reason = self._should_generate_architecture_diagram(
            classification, summaries
        )

        logger.info(f"[RiskPreorg] 架构图预检查结果: {should_generate}, 原因: {reason}")

        if should_generate:
            diagram_data = await self._detect_and_generate_architecture_diagram(
                documents, summaries
            )

            # 第二层: 数据质量验证
            if diagram_data and "metadata" in diagram_data:
                # 从metadata中获取原始提取数据进行验证
                extracted_data = diagram_data.get("metadata", {}).get("extracted_data", {})
                is_valid, validation_reason = self._validate_extracted_equity_data(extracted_data)

                if is_valid:
                    result["architecture_diagram"] = diagram_data
                    logger.info(f"[RiskPreorg] 架构图生成成功: {validation_reason}")
                else:
                    logger.warning(f"[RiskPreorg] 架构图数据验证失败: {validation_reason}")
                    result["architecture_diagram"] = None
            else:
                result["architecture_diagram"] = diagram_data
        else:
            logger.info(f"[RiskPreorg] 跳过架构图生成: {reason}")

        return result

    # ==================== 辅助/底层方法 ====================

    async def _analyze_relationships(self, documents, summaries) -> List[DocumentRelationship]:
        """简化的关系分析"""
        relationships = []
        for i, doc1 in enumerate(documents):
            name1 = doc1.metadata.get("filename", "")
            path1 = doc1.metadata.get("file_path", "")

            for doc2 in documents[i+1:]:
                name2 = doc2.metadata.get("filename", "")
                path2 = doc2.metadata.get("file_path", "")

                if name1 in name2 and any(k in name2 for k in ["补充", "附件", "Annex", "Supplement"]):
                    relationships.append(DocumentRelationship(
                        source_doc=path1, target_doc=path2,
                        relationship_type="supplement", confidence=0.8, reason="文件名包含关系"
                    ))
        return relationships

    async def _assess_quality(self, documents, classification) -> Dict[str, DocumentQuality]:
        """基础质量评估"""
        scores = {}
        for doc in documents:
            path = doc.metadata.get("file_path", "")
            issues = []
            completeness = 1.0

            if len(doc.content) < 100:
                issues.append("内容过短，可能识别失败")
                completeness = 0.2

            scores[path] = DocumentQuality(
                overall_score=completeness,
                completeness=completeness,
                clarity=1.0,
                missing_fields=[],
                issues=issues
            )
        return scores

    def _normalize_entities(self, summaries: Dict[str, DocumentSummary]) -> Dict[str, List[str]]:
        """实体名称归一化"""
        raw_parties = set()
        for s in summaries.values():
            for p in s.key_parties:
                clean_name = re.sub(r'\s*[\(（][甲乙丙丁戊担保].*?[\)）]', '', p).strip()
                if len(clean_name) > 1:
                    raw_parties.add(clean_name)
        return {"all_parties": list(raw_parties)}

    def _should_generate_architecture_diagram(
        self,
        classification: Dict[DocumentCategory, List[str]],
        summaries: Dict[str, DocumentSummary]
    ) -> tuple:
        """
        多因素判断是否应该生成股权架构图

        Returns:
            (should_generate, reason)
        """
        # 因素1: 文档类型检查
        shareholder_docs = classification.get(DocumentCategory.SHAREHOLDER, [])
        business_license_docs = classification.get(DocumentCategory.BUSINESS_LICENSE, [])

        if not shareholder_docs and not business_license_docs:
            return False, "没有股权相关文档类型"

        # 因素2: document_subtype检查（更精确的判断）
        equity_related_subtypes = [
            "股东会决议", "董事会决议", "股权转让协议",
            "增资协议", "公司章程", "股权质押",
            "股权变更", "验资报告", "投资协议"
        ]

        has_equity_subtype = any(
            s.document_subtype and any(sub in s.document_subtype for sub in equity_related_subtypes)
            for s in summaries.values()
        )

        if not has_equity_subtype:
            # 如果没有精确的subtype，则回退到关键词检查
            has_equity_keywords = any("股权" in s.summary for s in summaries.values())
            if not has_equity_keywords:
                return False, "文档子类型和摘要都不包含股权结构信息"

        # 因素3: 误报关键词过滤
        false_positive_patterns = [
            "模板", "范本", "示例", "样例",
            "仅供参考", "格式"
        ]

        for s in summaries.values():
            summary = s.summary
            if "股权" in summary:
                for pattern in false_positive_patterns:
                    if pattern in summary:
                        return False, f"包含误报关键词: {pattern}"

        # 因素4: 实体数量检查（至少需要2个实体）
        all_parties = set()
        for s in summaries.values():
            for p in s.key_parties:
                clean_name = re.sub(r'\s*[\(（][甲乙丙丁戊担保].*?[\)）]', '', p).strip()
                if len(clean_name) > 1:
                    all_parties.add(clean_name)

        if len(all_parties) < 2:
            return False, "关键方数量不足，无法构建股权关系"

        return True, f"通过预检查（{len(all_parties)}个关键方）"

    def _validate_extracted_equity_data(self, data: Dict[str, Any]) -> tuple:
        """
        验证提取的股权数据是否有效

        Returns:
            (is_valid, reason)
        """
        companies = data.get("companies", [])
        shareholders = data.get("shareholders", [])
        relationships = data.get("relationships", [])

        # 验证1: 基本数据存在性
        if not companies and not shareholders:
            return False, "未提取到任何公司或股东信息"

        # 验证2: 关系数量（至少需要1个关系）
        if not relationships:
            return False, "未提取到股权关系"

        # 验证3: 关系完整性（source和target必须存在）
        all_entities = [c.get("name", "") for c in companies] + \
                       [s.get("name", "") for s in shareholders]

        valid_relationships = 0
        for rel in relationships:
            source = rel.get("source", "")
            target = rel.get("target", "")

            if source in all_entities and target in all_entities:
                valid_relationships += 1

        if valid_relationships == 0:
            return False, "提取的股权关系无效（实体不匹配）"

        return True, f"数据验证通过（{valid_relationships}个有效关系）"

    async def _detect_and_generate_architecture_diagram(self, documents, summaries):
        """
        生成架构图数据

        通过 LLM 分析文档内容，提取真实的股权/投资结构信息
        """
        try:
            # 1. 收集所有关键方信息
            all_parties = set()
            for s in summaries.values():
                for p in s.key_parties:
                    clean_name = re.sub(r'\s*[\(（][甲乙丙丁戊担保].*?[\)）]', '', p).strip()
                    if len(clean_name) > 1:
                        all_parties.add(clean_name)

            # 2. 收集文档内容片段用于 LLM 分析
            doc_samples = []
            for doc in documents[:5]:  # 限制为前5个文档以控制 token 使用
                content_sample = doc.content[:2000]  # 每个文档取前2000字符
                filename = doc.metadata.get('filename', doc.metadata.get('file_path', '未知'))
                doc_samples.append(f"文档名：{filename}\n内容片段：{content_sample}\n")

            # 3. 构建股权结构提取提示
            prompt = f"""你是一个专业的公司股权结构分析专家。请分析以下文档内容，提取股权/投资结构信息。

已识别的相关方：
{', '.join(list(all_parties)[:10])}

文档内容：
{''.join(doc_samples)}

请严格按照以下 JSON 格式返回股权结构信息：
{{
    "companies": [
        {{"name": "公司全称", "is_target": true/false}}
    ],
    "shareholders": [
        {{"name": "股东/投资人名称", "type": "person"/"company"}}
    ],
    "relationships": [
        {{"source": "股东/投资方名称", "target": "被投资公司名称", "ratio": "持股比例或投资金额"}}
    ]
}}

注意：
1. source 指向 target（股东 -> 公司）
2. ratio 格式：如 "60%" 或 "1000万元"
3. 如果无法确定具体比例，可以标注"未知"
4. 只返回明确提到的股权关系，不要臆测
"""

            # 4. 调用 LLM 提取股权结构
            logger.info("[RiskPreorg] 开始使用 LLM 提取股权结构信息...")
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            extracted_data = safe_parse_json(response.content)

            if not extracted_data:
                logger.warning("[RiskPreorg] LLM 未返回有效数据，跳过架构图生成")
                return None

            # 5. 构建 DiagramRequest
            logger.info(f"[RiskPreorg] 提取到的股权结构: {extracted_data}")

            diagram_request = DiagramRequest(
                diagram_type=DiagramType.EQUITY_STRUCTURE,
                format="mermaid",
                title="股权结构示意图",
                companies=[
                    CompanyNode(name=c.get("name", ""), is_target=c.get("is_target", False))
                    for c in extracted_data.get("companies", [])
                ],
                shareholders=[
                    ShareholderNode(name=s.get("name", ""), type=s.get("type", "company"))
                    for s in extracted_data.get("shareholders", [])
                ],
                relationships=[
                    EquityRelationship(
                        source=r.get("source", ""),
                        target=r.get("target", ""),
                        ratio=r.get("ratio", "")
                    )
                    for r in extracted_data.get("relationships", [])
                ],
                additional_data={}
            )

            # 6. 调用 DiagramGeneratorService 生成图表
            diagram_service = DiagramGeneratorService()
            result = diagram_service.generate(diagram_request)

            logger.info(f"[RiskPreorg] 成功生成架构图，类型: {result.diagram_type}, 格式: {result.format}")

            return {
                "diagram_type": result.diagram_type.value,
                "format": result.format.value,
                "code": result.source_code,
                "title": result.title,
                "metadata": {
                    **result.metadata,
                    "extracted_data": extracted_data
                }
            }

        except Exception as e:
            logger.error(f"[RiskPreorg] 生成架构图失败: {e}", exc_info=True)
            # 返回空图表而非硬编码数据
            return {
                "diagram_type": "equity_structure",
                "format": "mermaid",
                "code": "graph TD;\nEmpty[无法生成架构图];",
                "title": "股权结构示意图（生成失败）",
                "metadata": {"error": str(e)}
            }

    async def _extract_legal_features(self, doc: StructuredDocumentResult) -> Dict[str, Any]:
        """提取单个合同的法律特征"""
        prompt = f"分析合同《{doc.metadata.get('filename')}》的法律属性（如：有名合同类型、是否涉外、适用法律）。返回JSON。"
        try:
            async with self._semaphore:
                res = await self.llm.ainvoke([HumanMessage(content=prompt)])
            return safe_parse_json(res.content)
        except:
            return {}

    async def _detect_duplicates(self, documents):
        """简单MD5查重"""
        seen = {}
        dupes = []
        for doc in documents:
            h = hashlib.md5(doc.content.encode('utf-8')).hexdigest()
            if h in seen:
                dupes.append([seen[h], doc.metadata.get("file_path")])
            else:
                seen[h] = doc.metadata.get("file_path")
        return dupes

    def _rank_documents(self, documents, classification, quality, relationships):
        """简单的排序"""
        weights = {
            DocumentCategory.CONTRACT: 10,
            DocumentCategory.FINANCIAL_REPORT: 8,
            DocumentCategory.BUSINESS_LICENSE: 6,
            DocumentCategory.OTHER: 1
        }

        def get_score(doc):
            path = doc.metadata.get("file_path")
            cat = self._get_doc_category(path, classification)
            return weights.get(cat, 1)

        sorted_docs = sorted(documents, key=get_score, reverse=True)
        ranked_paths = []
        for d in sorted_docs:
            path = d.metadata.get("file_path")
            if path:
                ranked_paths.append(path)
            else:
                filename = d.metadata.get("filename")
                if filename:
                    ranked_paths.append(filename)
                else:
                    ranked_paths.append(f"document_{sorted_docs.index(d)}")
        return ranked_paths

    def _get_category_label(self, category: DocumentCategory) -> str:
        """获取文档类型的中文标签"""
        labels = {
            DocumentCategory.CONTRACT: "合同",
            DocumentCategory.FINANCIAL_REPORT: "财务报告",
            DocumentCategory.BUSINESS_LICENSE: "营业执照",
            DocumentCategory.ID_DOCUMENT: "身份证明",
            DocumentCategory.COURT_DOCUMENT: "诉讼文件",
            DocumentCategory.TAX_DOCUMENT: "税务文件",
            DocumentCategory.SHAREHOLDER: "股东文件",
            DocumentCategory.OTHER: "其他"
        }
        return labels.get(category, "未分类")

    def _get_doc_category(self, path: str, classification: Dict) -> DocumentCategory:
        for cat, paths in classification.items():
            if path in paths:
                return cat
        return DocumentCategory.OTHER


# 工厂函数
def get_document_preorganization_service(llm: ChatOpenAI) -> DocumentPreorganizationService:
    return DocumentPreorganizationService(llm)