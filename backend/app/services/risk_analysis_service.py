# backend/app/services/risk_analysis_service.py
"""
风险评估核心服务

负责：
1. 文档解析（依赖 UnifiedDocumentService）
2. 预分析（LLM 提取实体、生成摘要）
3. 规则引擎扫描（内置 + 自定义规则）
4. LLM 深度分析
5. 生成报告
"""

import logging
import uuid
import json
import re
from typing import Dict, List, Optional, Any, Callable
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.risk_analysis import (
    RiskAnalysisSession, RiskItem, RiskAnalysisRule,
    RiskAnalysisStatus, RiskLevel
)
from app.services.unified_document_service import get_unified_document_service
from app.services.risk_analysis.document_preorganization import get_document_preorganization_service

logger = logging.getLogger(__name__)


class RiskAnalysisService:
    """风险评估服务

    核心流程：
    1. 文档解析（依赖 UnifiedDocumentService）
    2. 预分析（LLM 提取实体、生成摘要）
    3. 规则引擎扫描（内置 + 自定义规则）
    4. LLM 深度分析
    5. 生成报告
    """

    def __init__(self, db: Session):
        self.db = db
        self.document_service = get_unified_document_service()

    def create_session(
        self,
        user_id: int,
        scene_type: str,
        user_description: Optional[str] = None,
        document_ids: Optional[List[str]] = None
    ) -> RiskAnalysisSession:
        """创建新的风险分析会话"""
        session = RiskAnalysisSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            scene_type=scene_type,
            user_description=user_description,
            document_ids=document_ids,
            status=RiskAnalysisStatus.PENDING.value
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        logger.info(f"创建风险分析会话: {session.session_id}, 场景: {scene_type}")
        return session

    async def analyze_documents(
        self,
        session_id: str,
        document_paths: List[str],
        scene_type: str,
        user_description: Optional[str] = None,
        enable_custom_rules: bool = False,
        user_id: Optional[int] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """执行风险分析

        Args:
            session_id: 会话 ID
            document_paths: 文档路径列表
            scene_type: 分析场景
            user_description: 用户描述
            enable_custom_rules: 是否启用自定义规则
            user_id: 用户 ID
            progress_callback: 进度回调函数

        Returns:
            分析结果字典
        """
        # 1. 获取会话
        session = self.db.query(RiskAnalysisSession).filter(
            RiskAnalysisSession.session_id == session_id
        ).first()

        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        try:
            # 2. 文档解析阶段
            logger.info(f"开始文档解析，共 {len(document_paths)} 个文件")
            await self._update_progress(session, "parsing", 0.1, "正在解析文档...", progress_callback)

            # 检查是否有已处理的文档结果（从上传阶段保存的）
            if hasattr(session, 'document_processing_results') and session.document_processing_results:
                logger.info(f"[DOC_PREORG] 发现已处理的文档结果，共 {len(session.document_processing_results)} 个文件")
                # 使用已处理的文档结果
                parsed_docs = []
                for filename, proc_result in session.document_processing_results.items():
                    # 重新加载文档以获取完整结构化数据
                    file_path = proc_result.get("file_path")
                    if file_path:
                        try:
                            result = self.document_service.process_document_structured(file_path)
                            parsed_docs.append({
                                "path": file_path,
                                "content": result.content,
                                "metadata": result.metadata,
                                "structure": {
                                    "paragraphs": result.paragraphs,
                                    "tables": result.tables,
                                    "parties": result.parties
                                }
                            })
                            logger.info(f"[DOC_PREORG] 从缓存加载文档: {filename}")
                        except Exception as e:
                            logger.warning(f"[DOC_PREORG] 重新加载文档失败: {file_path}, 错误: {str(e)}")
                            continue
            else:
                # 原有逻辑：解析文档
                parsed_docs = []
                for doc_path in document_paths:
                    try:
                        result = self.document_service.process_document_structured(doc_path)
                        parsed_docs.append({
                            "path": doc_path,
                            "content": result.content,
                            "metadata": result.metadata,
                            "structure": {
                                "paragraphs": result.paragraphs,
                                "tables": result.tables,
                                "parties": result.parties
                            }
                        })
                    except Exception as e:
                        logger.warning(f"文档解析失败: {doc_path}, 错误: {str(e)}")
                        # 继续处理其他文档
                        continue

            if not parsed_docs:
                raise ValueError("没有成功解析任何文档")

            # 2.5 文档预整理阶段（节点2：专业助理节点）
            logger.info(f"[DOC_PREORG] 开始文档预整理")
            await self._update_progress(session, "preorganizing", 0.2, "正在进行文档预整理...", progress_callback)

            try:
                # 获取LLM实例
                from app.core.llm_config import get_deepseek_llm
                llm = get_deepseek_llm()

                # 获取DocumentPreorganizationService
                preorg_service = get_document_preorganization_service(llm)

                # 将parsed_docs转换为StructuredDocumentResult格式
                from app.services.unified_document_service import StructuredDocumentResult, DocumentProcessingStatus
                structured_docs = []
                for doc in parsed_docs:
                    # 构建StructuredDocumentResult对象
                    structured_doc = StructuredDocumentResult(
                        status=DocumentProcessingStatus.SUCCESS,
                        content=doc["content"],
                        metadata=doc["metadata"],
                        paragraphs=doc["structure"].get("paragraphs", []),
                        tables=doc["structure"].get("tables", []),
                        headings=[],  # 可选，如果不需要可以留空
                        parties=doc["structure"].get("parties", []),
                        signatures=[],  # 可选
                        processing_method="v1_analysis",
                        from_cache=False
                    )
                    structured_docs.append(structured_doc)

                # 执行预整理
                preorganized = await preorg_service.preorganize(
                    documents=structured_docs,
                    user_context=user_description
                )

                logger.info(f"[DOC_PREORG] 预整理完成:")
                logger.info(f"[DOC_PREORG] - 文档分类: {preorganized.document_classification}")
                logger.info(f"[DOC_PREORG] - 质量评分: {len(preorganized.quality_scores)} 个文档")
                logger.info(f"[DOC_PREORG] - 智能摘要: {len(preorganized.document_summaries)} 个文档")
                logger.info(f"[DOC_PREORG] - 文档关系: {len(preorganized.document_relationships)} 个关系")
                if preorganized.duplicates:
                    logger.info(f"[DOC_PREORG] - 重复文档: {len(preorganized.duplicates)} 对")

                # 保存预整理结果到会话
                session.document_preorganization = {
                    "classification": preorganized.document_classification,
                    "quality_scores": preorganized.quality_scores,
                    "summaries": [s.dict() for s in preorganized.document_summaries],
                    "relationships": [r.dict() for r in preorganized.document_relationships],
                    "duplicates": preorganized.duplicates or [],
                    "ranked_docs": preorganized.ranked_documents,
                    "cross_doc_info": preorganized.cross_doc_info or {}
                }
                self.db.commit()

            except Exception as e:
                logger.warning(f"[DOC_PREORG] 文档预整理失败，将跳过此步骤: {str(e)}", exc_info=True)
                # 预整理失败不影响后续流程
                session.document_preorganization = {"error": str(e)}
                self.db.commit()

            # 3. 预分析阶段（LLM 摘要和实体提取）
            logger.info("开始预分析阶段")
            await self._update_progress(session, "analyzing", 0.3, "正在进行预分析...", progress_callback)

            pre_analysis = await self._preanalyze_documents(
                parsed_docs, scene_type, user_description
            )

            # 4. 规则引擎扫描
            logger.info("开始规则引擎扫描")
            await self._update_progress(session, "analyzing", 0.5, "正在应用规则引擎...", progress_callback)

            rule_results = await self._apply_rule_engine(
                parsed_docs, scene_type, enable_custom_rules, user_id
            )

            # 5. LLM 深度分析
            logger.info("开始 LLM 深度分析")
            await self._update_progress(session, "analyzing", 0.7, "正在进行深度分析...", progress_callback)

            llm_results = await self._deep_analysis_with_llm(
                parsed_docs, pre_analysis, rule_results, scene_type
            )

            # 6. 整合结果并生成报告
            logger.info("生成最终报告")
            await self._update_progress(session, "analyzing", 0.9, "正在生成报告...", progress_callback)

            final_result = await self._generate_final_report(
                session, pre_analysis, rule_results, llm_results
            )

            # 7. 更新会话状态
            session.status = RiskAnalysisStatus.COMPLETED.value
            session.completed_at = datetime.utcnow()
            session.summary = final_result["summary"]
            session.risk_distribution = final_result["distribution"]
            session.total_confidence = final_result["confidence"]
            session.report_md = final_result["report_md"]
            session.report_json = final_result["report_json"]
            self.db.commit()

            await self._update_progress(session, "completed", 1.0, "分析完成", progress_callback)

            logger.info(f"风险分析完成: {session_id}, 共发现 {len(final_result['report_json']['risks'])} 个风险点")
            return final_result

        except Exception as e:
            logger.error(f"风险分析失败: {str(e)}", exc_info=True)
            session.status = RiskAnalysisStatus.FAILED.value
            self.db.commit()
            raise

    async def _preanalyze_documents(
        self,
        parsed_docs: List[Dict],
        scene_type: str,
        user_description: Optional[str]
    ) -> Dict[str, Any]:
        """预分析：LLM 提取摘要和实体"""
        try:
            from app.core.llm_config import get_deepseek_llm
            llm = get_deepseek_llm()

            combined_content = "\n\n".join([doc["content"] for doc in parsed_docs])

            # 限制内容长度
            content_preview = combined_content[:10000]

            prompt = f"""你是专业的法律文档分析师。请对以下文档进行预分析：

分析场景：{scene_type}
用户描述：{user_description or '无'}

文档内容：
{content_preview}

请输出 JSON 格式（不要包含其他内容）：
{{
    "summary": "文档摘要（100字以内）",
    "entities": ["实体1", "实体2"],
    "key_terms": ["关键条款1", "关键条款2"],
    "document_type": "文档类型"
}}
"""

            response = await llm.ainvoke(prompt)

            # 尝试解析 JSON
            try:
                # 清理响应中的 markdown 代码块标记
                clean_response = response.content.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response[7:]
                if clean_response.startswith("```"):
                    clean_response = clean_response[3:]
                if clean_response.endswith("```"):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()

                return json.loads(clean_response)
            except json.JSONDecodeError:
                logger.warning(f"LLM 返回的不是有效 JSON: {response.content[:200]}")
                return {
                    "summary": "文档预分析完成",
                    "entities": [],
                    "key_terms": [],
                    "document_type": scene_type
                }

        except Exception as e:
            logger.error(f"预分析失败: {str(e)}")
            return {
                "summary": "预分析失败",
                "entities": [],
                "key_terms": [],
                "document_type": scene_type
            }

    async def _apply_rule_engine(
        self,
        parsed_docs: List[Dict],
        scene_type: str,
        enable_custom_rules: bool,
        user_id: Optional[int]
    ) -> List[Dict]:
        """应用规则引擎进行风险扫描"""
        # 查询适用的规则
        query = self.db.query(RiskAnalysisRule).filter(
            RiskAnalysisRule.scene_type == scene_type,
            RiskAnalysisRule.is_active == True
        )

        if enable_custom_rules and user_id:
            query = query.filter(
                (RiskAnalysisRule.rule_category == "universal") |
                (RiskAnalysisRule.creator_id == user_id)
            )
        else:
            query = query.filter(RiskAnalysisRule.rule_category == "universal")

        rules = query.all()
        logger.info(f"应用 {len(rules)} 条规则进行扫描")

        rule_results = []
        for doc in parsed_docs:
            content = doc["content"]
            for rule in rules:
                # 关键词匹配
                if rule.keywords:
                    for keyword in rule.keywords:
                        if keyword in content:
                            rule_results.append({
                                "rule_id": rule.id,
                                "rule_name": rule.name,
                                "matched_keyword": keyword,
                                "risk_level": rule.default_risk_level or "medium",
                                "source": "rule_engine",
                                "risk_type": rule.risk_type
                            })

                # 正则表达式匹配
                if rule.pattern:
                    try:
                        if re.search(rule.pattern, content):
                            rule_results.append({
                                "rule_id": rule.id,
                                "rule_name": rule.name,
                                "matched_pattern": rule.pattern,
                                "risk_level": rule.default_risk_level or "medium",
                                "source": "rule_engine",
                                "risk_type": rule.risk_type
                            })
                    except re.error:
                        logger.warning(f"规则 {rule.name} 的正则表达式无效: {rule.pattern}")

        logger.info(f"规则引擎检测到 {len(rule_results)} 个风险点")
        return rule_results

    async def _deep_analysis_with_llm(
        self,
        parsed_docs: List[Dict],
        pre_analysis: Dict,
        rule_results: List[Dict],
        scene_type: str
    ) -> List[Dict]:
        """LLM 深度分析"""
        try:
            from app.core.llm_config import get_deepseek_llm
            llm = get_deepseek_llm()

            combined_content = "\n\n".join([doc["content"] for doc in parsed_docs])
            content_preview = combined_content[:8000]

            # 构建规则结果摘要
            rule_summary = "\n".join([
                f"- {rr['rule_name']}: {rr.get('matched_keyword', rr.get('matched_pattern', ''))}"
                for rr in rule_results[:10]
            ])

            prompt = f"""你是专业的中国法律顾问。请进行深度风险分析：

分析场景：{scene_type}
文档摘要：{pre_analysis.get('summary', '')}
规则引擎已检测风险：
{rule_summary}

文档内容：
{content_preview}

请识别所有潜在风险（包括规则引擎未检测到的），输出纯 JSON 格式（不要包含其他内容）：
{{
    "risks": [
        {{
            "title": "风险标题",
            "description": "详细描述",
            "risk_level": "high/medium/low",
            "confidence": 0.85,
            "reasons": ["理由1", "理由2"],
            "suggestions": ["建议1", "建议2"]
        }}
    ]
}}

注意：
1. risk_level 只能是 high, medium, low 之一
2. confidence 是 0 到 1 之间的数字
3. 如果没有发现风险，返回空的 risks 数组
"""

            response = await llm.ainvoke(prompt)

            # 解析 JSON
            try:
                clean_response = response.content.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response[7:]
                if clean_response.startswith("```"):
                    clean_response = clean_response[3:]
                if clean_response.endswith("```"):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()

                result = json.loads(clean_response)
                risks = result.get("risks", [])

                # 过滤和验证风险项
                valid_risks = []
                for risk in risks:
                    if isinstance(risk, dict) and all(k in risk for k in ["title", "description", "risk_level"]):
                        # 确保风险等级有效
                        if risk["risk_level"] not in ["high", "medium", "low"]:
                            risk["risk_level"] = "medium"
                        # 确保置信度有效
                        if "confidence" not in risk or not isinstance(risk["confidence"], (int, float)):
                            risk["confidence"] = 0.7
                        # 确保 reasons 和 suggestions 存在
                        if "reasons" not in risk or not isinstance(risk["reasons"], list):
                            risk["reasons"] = []
                        if "suggestions" not in risk or not isinstance(risk["suggestions"], list):
                            risk["suggestions"] = []

                        valid_risks.append(risk)

                logger.info(f"LLM 深度分析发现 {len(valid_risks)} 个风险点")
                return valid_risks

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"LLM 返回的不是有效 JSON: {str(e)}, 响应: {response[:200]}")
                return []

        except Exception as e:
            logger.error(f"LLM 深度分析失败: {str(e)}")
            return []

    async def _generate_final_report(
        self,
        session: RiskAnalysisSession,
        pre_analysis: Dict,
        rule_results: List[Dict],
        llm_results: List[Dict]
    ) -> Dict[str, Any]:
        """生成最终报告"""
        # 合并规则和 LLM 结果
        all_risks = []

        # 规则引擎结果
        for rr in rule_results:
            # 检查是否已有类似风险（避免重复）
            is_duplicate = any(
                r["title"] == rr["rule_name"] and r["source_type"] == "llm"
                for r in all_risks
            )
            if not is_duplicate:
                all_risks.append({
                    "title": rr["rule_name"],
                    "description": f"检测到关键词：{rr.get('matched_keyword', rr.get('matched_pattern', ''))}",
                    "risk_level": rr["risk_level"],
                    "confidence": 0.9,  # 规则匹配置信度较高
                    "reasons": ["规则引擎检测"],
                    "suggestions": ["建议仔细审查相关条款"],
                    "source_type": "rule",
                    "source_rules": [rr["rule_id"]]
                })

        # LLM 结果
        for lr in llm_results:
            all_risks.append({
                "title": lr["title"],
                "description": lr["description"],
                "risk_level": lr["risk_level"],
                "confidence": lr["confidence"],
                "reasons": lr["reasons"],
                "suggestions": lr["suggestions"],
                "source_type": "llm",
                "source_rules": None
            })

        # 保存风险项到数据库
        for risk_data in all_risks:
            risk_item = RiskItem(
                session_id=session.id,
                title=risk_data["title"],
                description=risk_data["description"],
                risk_level=risk_data["risk_level"],
                confidence=risk_data["confidence"],
                reasons=risk_data["reasons"],
                suggestions=risk_data["suggestions"],
                source_type=risk_data["source_type"],
                source_rules=risk_data.get("source_rules")
            )
            self.db.add(risk_item)

        self.db.commit()

        # 计算风险分布
        distribution = {"high": 0, "medium": 0, "low": 0}
        total_confidence = 0
        for risk in all_risks:
            level = risk["risk_level"]
            if level in distribution:
                distribution[level] += 1
            total_confidence += risk["confidence"]

        avg_confidence = total_confidence / len(all_risks) if all_risks else 0

        # 生成 Markdown 报告
        report_md = self._generate_markdown_report(all_risks, distribution, pre_analysis)

        return {
            "summary": f"发现 {len(all_risks)} 个风险点",
            "distribution": distribution,
            "confidence": avg_confidence,
            "report_md": report_md,
            "report_json": {"risks": all_risks}
        }

    def _generate_markdown_report(
        self,
        risks: List[Dict],
        distribution: Dict[str, int],
        pre_analysis: Dict
    ) -> str:
        """生成 Markdown 格式报告"""
        md_lines = [
            "# 风险评估报告",
            "",
            "## 文档摘要",
            pre_analysis.get("summary", ""),
            "",
            "## 风险分布",
            f"- 高风险：{distribution.get('high', 0)} 个",
            f"- 中风险：{distribution.get('medium', 0)} 个",
            f"- 低风险：{distribution.get('low', 0)} 个",
            "",
            "## 详细风险清单",
            ""
        ]

        for i, risk in enumerate(risks, 1):
            level_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk["risk_level"], "⚪")
            md_lines.extend([
                f"### {level_emoji} {i}. {risk['title']}",
                "",
                f"**描述：** {risk['description']}",
                f"**风险等级：** {risk['risk_level'].upper()}",
                f"**置信度：** {risk['confidence']:.1%}",
                f"**来源：** {'规则引擎' if risk['source_type'] == 'rule' else 'AI 分析'}",
                "",
                "**理由：**"
            ])
            for reason in risk.get("reasons", []):
                md_lines.append(f"- {reason}")

            md_lines.extend([
                "",
                "**建议：**"
            ])
            for suggestion in risk.get("suggestions", []):
                md_lines.append(f"- {suggestion}")
            md_lines.append("")

        md_lines.extend([
            "---",
            "",
            "**免责声明：** 本评估仅供参考，不能替代专业律师意见。"
        ])

        return "\n".join(md_lines)

    async def _update_progress(
        self,
        session: RiskAnalysisSession,
        status: str,
        progress: float,
        message: str,
        callback: Optional[Callable]
    ):
        """更新进度并通知"""
        session.status = status
        self.db.commit()

        if callback:
            await callback({
                "session_id": session.session_id,
                "status": status,
                "progress": progress,
                "message": message
            })

    def get_session_by_id(self, session_id: str, user_id: int) -> Optional[RiskAnalysisSession]:
        """根据 session_id 和 user_id 获取会话"""
        return self.db.query(RiskAnalysisSession).filter(
            RiskAnalysisSession.session_id == session_id,
            RiskAnalysisSession.user_id == user_id
        ).first()

    def get_session_with_items(self, session_id: str, user_id: int) -> Optional[RiskAnalysisSession]:
        """获取会话及其风险项"""
        return self.db.query(RiskAnalysisSession).filter(
            RiskAnalysisSession.session_id == session_id,
            RiskAnalysisSession.user_id == user_id
        ).first()


# 便捷函数
def get_risk_analysis_service(db: Session) -> RiskAnalysisService:
    """获取风险评估服务实例"""
    return RiskAnalysisService(db)
