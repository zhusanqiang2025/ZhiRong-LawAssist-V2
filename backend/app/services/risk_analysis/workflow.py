# backend/app/services/risk_analysis/workflow.py

"""
风险评估 LangGraph 工作流

基于 LangGraph 的风险评估流程编排
"""

import logging
import uuid
import asyncio
import json
from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime
from dataclasses import asdict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.risk_analysis import RiskAnalysisSession, RiskAnalysisStatus, RiskItem
from app.services.unified_document_service import get_unified_document_service, StructuredDocumentResult
from app.services.risk_analysis.document_preorganization import get_document_preorganization_service, PreorganizedDocuments
from app.services.risk_analysis.rule_assembler import get_risk_rule_assembler
from app.services.risk_analysis.multi_model_analyzer import get_multi_model_analyzer
from app.core.config import settings

logger = logging.getLogger(__name__)


# ==================== 辅助函数 ====================

async def send_ws_progress(session_id: str, node: str, status: str, message: str = "", progress: float = 0.0):
    """
    发送 WebSocket 进度消息（异步）

    重要：优雅处理 WebSocket 断连，避免 Broken Pipe 错误导致任务崩溃
    Args:
        session_id: 会话 ID
        node: 节点名称 (documentPreorganization, multiModelAnalysis, reportGeneration)
        status: 状态 (pending, processing, completed, failed)
        message: 进度消息
        progress: 进度百分比 0-1
    """
    try:
        from app.api.websocket import manager
        # 检查连接是否存在
        if not manager.is_connected(session_id):
            # 连接不存在，静默跳过（后台模式）
            logger.debug(f"[WS] 会话 {session_id} 无活跃连接，跳过进度推送（后台模式）")
            return

        # 发送进度
        await manager.send_progress(session_id, {
            "type": "node_progress",
            "node": node,
            "status": status,
            "message": message,
            "progress": progress
        })
    except Exception as e:
        # 捕获所有异常，避免导致任务失败
        # 常见异常：BrokenPipeError, ConnectionResetError, RuntimeError
        logger.debug(f"[WS] 进度推送失败（会话可能已断开）: {type(e).__name__}")
        # 不要抛出异常，让任务继续执行
        pass


# ==================== 状态定义 ====================

class RiskAnalysisState(TypedDict):
    """风险评估状态"""
    # 输入
    session_id: str
    user_input: str
    document_paths: List[str]
    package_id: Optional[str]  # 可选：None 表示通用评估模式
    stop_after_preorganization: Optional[bool]  # 是否在预整理后停止

    # 第一阶段：文档处理
    raw_documents: Optional[List[StructuredDocumentResult]]  # UnifiedDocumentService 输出
    preorganized_docs: Optional[PreorganizedDocuments]  # 预整理输出

    # 第二阶段：规则组装
    assembled_rules: Optional[List[Dict[str, Any]]]
    analysis_mode: Optional[str]  # "general" 或 "package_based"
    selected_model: Optional[str]  # 单模型分析时指定的模型名称（如 "deepseek"）

    # --- 新增：用于传递增强分析结果 ---
    enhanced_analysis_data: Optional[Dict[str, Any]]  # 来自 enhanced_document_analysis
    # ---------------------------------------

    context: Optional[Dict[str, Any]]  # 分析上下文

    # 第三阶段：AI分析
    analysis_results: Optional[Dict[str, Any]]  # 重命名以避免与 model_ 冲突

    # 输出
    final_report: Optional[str]
    final_result: Optional[Dict[str, Any]]  # 最终综合结果
    aggregated: Optional[Dict[str, Any]]  # 中间汇总结果
    status: str
    error: Optional[str]


# ==================== 节点函数 ====================

async def process_documents_node(state: RiskAnalysisState) -> Dict[str, Any]:
    """节点1：处理文档（基础提取）"""
    session_id = state['session_id']
    # 发送 WebSocket 进度：开始处理文档
    await send_ws_progress(
        session_id, "documentPreorganization", "processing",
        "正在处理文档，提取内容...", 0.05
    )
    logger.info(f"[{state['session_id']}] 开始处理文档...")
    doc_service = get_unified_document_service()

    try:
        results = await doc_service.batch_process_async(
            state["document_paths"],
            extract_content=True,
            extract_metadata=True,
            max_concurrent=3
        )

        # 过滤成功的文档
        successful_docs = [r for r in results if r.status == "success"]

        if not successful_docs:
            logger.error(f"[{state['session_id']}] 文档处理全部失败")
            return {
                "raw_documents": [],
                "status": "failed",
                "error": "文档处理全部失败"
            }

        logger.info(f"[{state['session_id']}] 文档处理完成: {len(successful_docs)}/{len(results)} 成功")

        return {
            "raw_documents": successful_docs,
            "status": "documents_processed"
        }

    except Exception as e:
        logger.error(f"[{state['session_id']}] 文档处理异常: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": f"文档处理异常: {str(e)}"
        }


async def preorganize_documents_node(state: RiskAnalysisState) -> Dict[str, Any]:
    """节点2：预整理文档（专业助理节点）- 增强版"""
    session_id = state['session_id']

    # 发送 WebSocket 进度：开始处理
    await send_ws_progress(
        session_id, "documentPreorganization", "processing",
        "正在进行文档预整理...", 0.05
    )

    logger.info(f"[{session_id}] 开始预整理文档...")

    if not state.get("raw_documents"):
        await send_ws_progress(session_id, "documentPreorganization", "failed", "没有可用的文档", 0)
        return {"status": "no_documents", "error": "没有可用的文档"}

    llm = ChatOpenAI(
        model=settings.MODEL_NAME or "Qwen3-235B-A22B-Thinking-2507",
        api_key=settings.LANGCHAIN_API_KEY,
        base_url=settings.LANGCHAIN_API_BASE_URL,
        temperature=0
    )

    # 定义进度回调函数
    async def progress_callback(step: str, progress: float, message: str):
        """进度回调，实时发送进度更新"""
        await send_ws_progress(session_id, "documentPreorganization", "processing", message, progress)

    try:
        # ========================================================
        # 步骤1：基础预整理（分类、质量评估、基础摘要）
        # ========================================================
        # 进度范围：0.1 - 0.45
        await send_ws_progress(session_id, "documentPreorganization", "processing",
                               "正在进行文档分类和质量评估...", 0.1)

        preorg_service = get_document_preorganization_service(llm)
        preorganized = await preorg_service.preorganize(
            documents=state["raw_documents"],
            user_context=state.get("user_input"),
            progress_callback=progress_callback
        )

        # ========================================================
        # 步骤2：增强分析（交易全景、主体画像、时间线）
        # ========================================================
        # 进度范围：0.45 - 0.75
        await send_ws_progress(session_id, "documentPreorganization", "processing",
                               "正在构建交易全景图...", 0.45)

        from app.services.risk_analysis.enhanced_document_analysis import get_enhanced_document_analysis_service
        enhanced_analysis_service = get_enhanced_document_analysis_service(llm)

        # 【核心修改】：传入 preorganized_data 避免重复计算
        enhanced_analysis = await enhanced_analysis_service.analyze_documents(
            documents=state["raw_documents"],
            preorganized_data=preorganized,
            user_context=state.get("user_input"),
            progress_callback=progress_callback
        )

        # ========================================================
        # 步骤3：法律特征增强（架构图等）
        # ========================================================
        # 进度范围：0.75 - 0.95
        await send_ws_progress(session_id, "documentPreorganization", "processing",
                               "正在绘制法律架构图...", 0.75)

        extra_features = await preorg_service.enhance_preorganization_result(
            documents=state["raw_documents"],
            summaries=preorganized.document_summaries,
            classification=preorganized.document_classification
        )

        await send_ws_progress(session_id, "documentPreorganization", "completed",
                               "文档预整理完成", 1.0)

        logger.info(f"[{session_id}] 文档预整理完成（含增强分析）")

        # ========================================================
        # 数据序列化与发送 (更新适配新的数据结构)
        # ========================================================
        try:
            from app.api.websocket import manager
            # 序列化基础预整理数据 - 使用 Pydantic model_dump() 保留所有字段
            preorganized_data = {
                "document_summaries": {
                    path: summary.model_dump(mode='json', exclude_none=False)
                    for path, summary in preorganized.document_summaries.items()
                },
                "document_classification": preorganized.document_classification,
                "ranked_documents": preorganized.ranked_documents
            }

            # 序列化增强分析数据 (适配 EnhancedAnalysisResult 结构)
            enhanced_analysis_data_for_ws = {
                "transaction_summary": enhanced_analysis.transaction_summary,
                "contract_status": enhanced_analysis.contract_status,
                "dispute_focus": enhanced_analysis.dispute_focus,
                # 使用 asdict 转换 dataclass 对象
                "parties": [asdict(p) for p in enhanced_analysis.parties],
                "timeline": [asdict(t) for t in enhanced_analysis.timeline],
                "relationships": enhanced_analysis.doc_relationships,
                # 新增：将架构图数据包含在 enhanced_analysis 中
                "architecture_diagram": extra_features.get("architecture_diagram") if extra_features else None
            }

            await manager.send_progress(session_id, {
                "type": "preorganization_completed",
                "has_result": True,
                "can_proceed": True,
                "preorganized_data": preorganized_data,
                "enhanced_analysis": enhanced_analysis_data_for_ws,
                "enhanced_data": extra_features  # 架构图、法律特征等
            })
            logger.info(f"[WS] 发送preorganization_completed消息成功: {session_id}")
        except Exception as e:
            logger.error(f"[WS] 发送preorganization_completed消息失败: {e}")

        # ========================================================
        # 保存预整理结果到数据库
        # ========================================================
        try:
            from app.database import SessionLocal
            from app.models.risk_analysis_preorganization import RiskAnalysisPreorganization
            db = SessionLocal()
            try:
                # 检查是否已存在记录
                existing_record = db.query(RiskAnalysisPreorganization).filter(
                    RiskAnalysisPreorganization.session_id == session_id
                ).first()

                if not existing_record:
                    # 将新的数据结构映射到 DB 字段
                    preorg_record = RiskAnalysisPreorganization(
                        session_id=session_id,
                        # 映射：交易综述 -> 用户需求摘要(或创建新字段)
                        user_requirement_summary=enhanced_analysis.transaction_summary,
                        # 映射：基础摘要信息 - preorganized_data["document_summaries"] 已经是字典
                        documents_info=json.dumps(preorganized_data.get("document_summaries", {}), ensure_ascii=False),
                        # 映射：时间线 -> 事实摘要
                        fact_summary=json.dumps([asdict(t) for t in enhanced_analysis.timeline], ensure_ascii=False),
                        # 映射：法律特征
                        contract_legal_features=extra_features.get("contract_legal_features"),
                        # 映射：文档关系
                        contract_relationships=enhanced_analysis.doc_relationships,
                        # 映射：架构图
                        architecture_diagram=extra_features.get("architecture_diagram"),
                        # 新增：保存完整的 enhanced_analysis 数据
                        enhanced_analysis_json=json.dumps({
                            "transaction_summary": enhanced_analysis.transaction_summary,
                            "contract_status": enhanced_analysis.contract_status,
                            "dispute_focus": enhanced_analysis.dispute_focus,
                            "parties": [asdict(p) for p in enhanced_analysis.parties],
                            "timeline": [asdict(t) for t in enhanced_analysis.timeline],
                            "doc_relationships": enhanced_analysis.doc_relationships,
                            # 新增：包含架构图数据
                            "architecture_diagram": extra_features.get("architecture_diagram") if extra_features else None
                        }, ensure_ascii=False),
                        is_confirmed=False
                    )
                    db.add(preorg_record)
                    db.commit()
                    logger.info(f"[RiskAnalysisWorkflow] 预整理结果已保存到数据库: {session_id}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[RiskAnalysisWorkflow] 保存预整理结果失败: {e}", exc_info=True)

        # ========================================================
        # --- 修改点：返回时包含 enhanced_analysis_data ---
        # ========================================================
        # 将 enhanced_analysis 对象转换为字典，并合并 extra_features
        # 使用 asdict 转换 dataclass
        enhanced_data_dict = {
            "transaction_summary": enhanced_analysis.transaction_summary,
            "contract_status": enhanced_analysis.contract_status,
            "dispute_focus": enhanced_analysis.dispute_focus,
            "parties": [asdict(p) for p in enhanced_analysis.parties],
            "timeline": [asdict(t) for t in enhanced_analysis.timeline],
            "relationships": enhanced_analysis.doc_relationships,
            # 合并架构图等额外特征
            "architecture_diagram": extra_features.get("architecture_diagram") if extra_features else None
        }

        return {
            "preorganized_docs": preorganized,
            "enhanced_analysis_data": enhanced_data_dict,  # <--- 新增返回字段
            "status": "preorganization_completed"
        }
        # ----------------------------------------------

    except Exception as e:
        logger.error(f"[{session_id}] 文档预整理失败: {e}", exc_info=True)
        await send_ws_progress(session_id, "documentPreorganization", "failed",
                               f"预整理失败: {str(e)}", 0)
        return {
            "preorganized_docs": None,
            "status": "preorganization_failed"
        }


async def assemble_rules_node(state: RiskAnalysisState) -> Dict[str, Any]:
    """节点3：组装规则（基于预整理结果）"""
    logger.info(f"[{state['session_id']}] 开始组装规则...")
    db = SessionLocal()

    try:
        package_id = state.get("package_id")

        # 通用评估模式：没有规则包
        if not package_id:
            logger.info(f"[{state['session_id']}] 通用评估模式，不使用规则包")
            # 构建基础上下文
            raw_docs = state.get("raw_documents") or []
            context = {
                "user_input": state["user_input"],
                "classification": {},
                "cross_doc_info": {},
                "document_count": len(raw_docs) if raw_docs else 0
            }
            # 如果有预整理结果，使用预整理数据
            preorganized = state.get("preorganized_docs")
            if preorganized:
                if hasattr(preorganized, 'document_classification'):
                    context["classification"] = preorganized.document_classification
                if hasattr(preorganized, 'cross_doc_info'):
                    context["cross_doc_info"] = preorganized.cross_doc_info

            return {
                "assembled_rules": [],
                "context": context,
                "analysis_mode": "general",
                "status": "rules_assembled"
            }

        # 规则包评估模式：使用规则包
        # 构建上下文
        context = {
            "user_input": state["user_input"],
            "classification": {},
            "cross_doc_info": {}
        }

        # 如果有预整理结果，使用预整理数据
        preorganized = state.get("preorganized_docs")
        if preorganized:
            if hasattr(preorganized, 'document_classification'):
                context["classification"] = preorganized.document_classification
            if hasattr(preorganized, 'cross_doc_info'):
                context["cross_doc_info"] = preorganized.cross_doc_info
        else:
            # 降级：使用原始文档
            raw_docs = state.get("raw_documents") or []
            context["document_count"] = len(raw_docs) if raw_docs else 0

        assembler = get_risk_rule_assembler(db)
        rules = assembler.assemble_rules(
            package_id=package_id,
            context=context
        )

        logger.info(f"[{state['session_id']}] 规则组装完成: {len(rules)} 条规则")

        return {
            "assembled_rules": rules,
            "context": context,
            "analysis_mode": "package_based",
            "status": "rules_assembled"
        }

    except Exception as e:
        logger.error(f"[{state['session_id']}] 规则组装失败: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": f"规则组装失败: {str(e)}"
        }
    finally:
        db.close()


async def multi_model_analyze_node(state: RiskAnalysisState) -> Dict[str, Any]:
    """节点4：多模型并行分析（支持单/多模型切换）"""
    session_id = state['session_id']

    # 从 state 获取配置
    rules = state.get("assembled_rules")
    analysis_mode = state.get("analysis_mode", "multi")  # 默认为 multi
    selected_model = state.get("selected_model")  # 单模型时指定的模型名 (如 "deepseek")

    mode_text = f"单模型 ({selected_model})" if analysis_mode == "single" else "多模型综合"

    # 定义进度回调函数，用于 MultiModelAnalyzer
    async def progress_callback(step: str, progress: float, message: str):
        """进度回调，将进度转换为 multiModelAnalysis 节点的进度"""
        # MultiModelAnalyzer 的进度范围是 75%-95%，映射到 multiModelAnalysis 节点的 40%-95%
        # progress 0.76-0.95 → 节点进度 0.40-0.95
        node_progress = 0.40 + (progress - 0.75) * (0.95 - 0.40) / (0.95 - 0.75)
        node_progress = max(0.40, min(0.95, node_progress))  # 限制在 0.40-0.95 范围内
        await send_ws_progress(
            session_id, "multiModelAnalysis", "processing",
            message, node_progress
        )

    # 异步节点中可以直接 await
    await send_ws_progress(
        session_id, "multiModelAnalysis", "processing",
        f"正在进行智能分析 [{mode_text}]...", 0.40
    )

    logger.info(f"[{session_id}] 开始分析: {mode_text}")

    # 构建上下文
    preorganized = state.get("preorganized_docs")
    raw_docs = state.get("raw_documents", [])
    evaluation_stance = state.get("evaluation_stance")  # ✅ 新增：获取评估立场

    # ✅ 新增：追踪日志 - 确认立场是否被传递
    if evaluation_stance:
        logger.info(f"[{session_id}] ✅ 检测到评估立场: {evaluation_stance[:100]}...")
    else:
        logger.warning(f"[{session_id}] ⚠️ 未提供评估立场（evaluation_stance 为空）")

    if preorganized and hasattr(preorganized, 'document_summaries'):
        summaries = []
        for path, summary in preorganized.document_summaries.items():
            summaries.append(f"文档: {path}\n摘要: {summary.summary}")
        context = "\n\n".join(summaries)
    else:
        context = "\n\n".join([doc.content for doc in raw_docs])

    # ✅ 新增：注入评估立场到上下文
    if evaluation_stance:
        logger.info(f"[{session_id}] 📝 正在注入评估立场到 LLM 上下文...")
        context = f"""**重要提示：本次风险评估应采用以下立场进行分析**
{evaluation_stance}

请在分析过程中始终基于上述立场，重点关注该立场下的风险点和建议。

---

{context}
"""
        logger.info(f"[{session_id}] ✅ 评估立场已注入，上下文长度: {len(context)} 字符")
    else:
        if state.get("user_input"):
            context = f"## 用户需求\n{state['user_input']}\n\n## 文档内容\n{context}"

    # ========================================================
    # --- 修改点：优先获取 enhanced_analysis_data ---
    # ========================================================
    # 这是 preorganize_documents_node 新增的字段，包含了完整的增强分析结果
    enhanced_data = state.get("enhanced_analysis_data")

    # 如果没有新的数据，降级使用旧的 cross_doc_info (兼容性处理)
    if not enhanced_data and preorganized and hasattr(preorganized, 'cross_doc_info'):
        enhanced_data = preorganized.cross_doc_info
    # ---------------------------------------

    try:
        analyzer = get_multi_model_analyzer()
        # 调用分析器 (传入新的参数)
        result = await analyzer.analyze_parallel(
            context=context,
            rules=rules or [],
            session_id=state["session_id"],
            analysis_mode=analysis_mode,  # <--- 传入模式
            selected_model=selected_model,  # <--- 传入选定的模型
            enhanced_data=enhanced_data,
            progress_callback=progress_callback  # <--- 传入进度回调
        )

        if result.get("error"):
            await send_ws_progress(session_id, "multiModelAnalysis", "failed",
                                   result.get("error", "分析失败"), 0.6)
            return {
                "status": "failed",
                "error": result["error"]
            }

        final_result = result.get("final_result", {})
        aggregated = result.get("aggregated", {})

        await send_ws_progress(session_id, "multiModelAnalysis", "completed",
                               "智能分析完成", 0.7)

        return {
            "analysis_results": result,
            "final_result": final_result,
            "aggregated": aggregated,
            "status": "analysis_completed"
        }

    except Exception as e:
        logger.error(f"[{session_id}] 分析失败: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


async def generate_report_node(state: RiskAnalysisState) -> Dict[str, Any]:
    """节点5：生成最终报告（增强版：整体评估 + 优先级排序 + 来源视角）"""
    session_id = state['session_id']

    # 异步节点中可以直接 await
    await send_ws_progress(
        session_id, "reportGeneration", "processing",
        "正在生成风险评估报告...", 0.8
    )

    logger.info(f"[{session_id}] 开始生成报告...")

    # 获取最终综合结果
    final_result = state.get("final_result")
    if not final_result:
        await send_ws_progress(session_id, "reportGeneration", "failed",
                               "没有可用的分析结果", 0.8)
        return {
            "status": "failed",
            "error": "没有可用的分析结果"
        }

    # 获取整体评估
    overall_assessment = final_result.get("overall_assessment", {})
    risk_level = overall_assessment.get("risk_level", "medium")
    core_risks = overall_assessment.get("core_risks", [])
    handling_recommendation = overall_assessment.get("recommendation", "建议优先处理高风险项，逐步降低整体风险水平")

    # 获取风险项
    risk_items = final_result.get("risk_items", [])

    # 按优先级排序风险项
    sorted_risks = _sort_risks_by_priority(risk_items)

    await send_ws_progress(session_id, "reportGeneration", "processing",
                           "正在整理风险清单...", 0.9)

    # ✅ 新增：获取评估立场并注入到报告
    evaluation_stance = state.get("evaluation_stance")

    # 构建 Markdown 报告
    report_lines = [
        "# 风险评估报告\n",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**总体置信度**: {final_result.get('total_confidence', 0):.1%}\n"
    ]

    # ✅ 增强版：如果提供了评估立场，在报告开头显著显示
    if evaluation_stance:
        report_lines.extend([
            "## 🎯 评估立场\n",
            f"\n{evaluation_stance}\n",
            "---\n",
            "### ⚠️ 重要说明",
            f"\n**本报告完全基于上述「{evaluation_stance[:30]}...」立场进行分析**。所有风险识别、评级和建议均从该视角出发，可能与其他立场下的评估结果存在差异。",
            "建议读者：",
            f"1. 结合自身实际情况理解本报告的风险判断",
            f"2. 如需不同立场下的风险评估（如对方视角、中立第三方视角），请重新指定立场并分析",
            f"3. 重点关注与该立场相关的核心风险点\n",
            "---\n"
        ])

    report_lines.extend([
        "## 一、整体评估\n",
        f"**风险等级**: {_format_risk_level(risk_level)}",
        f"**应对建议**: {handling_recommendation}\n"
    ])

    # 核心风险概述
    if core_risks:
        report_lines.append("**核心风险**:")
        for risk in core_risks:
            report_lines.append(f"- {risk}")
        report_lines.append("")

    # 总体摘要
    summary = final_result.get("summary", "")
    if summary:
        report_lines.extend([
            "**总体摘要**:",
            summary,
            "\n---\n"
        ])

    # 风险分布统计
    report_lines.append("## 二、风险分布统计\n")

    # 计算分布
    distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for risk in risk_items:
        level = risk.get("risk_level", "low").lower()
        if level in distribution:
            distribution[level] += 1

    report_lines.extend([
        f"- 🔴 高风险（含严重）：{distribution.get('critical', 0) + distribution.get('high', 0)} 个",
        f"- 🟡 中风险：{distribution.get('medium', 0)} 个",
        f"- 🟢 低风险：{distribution.get('low', 0)} 个",
        "\n---\n",
        "## 三、优先级排序风险清单\n"
    ])

    # 按优先级分组展示
    high_risks = [r for r in sorted_risks if r.get("risk_level") in ["critical", "high"]]
    medium_risks = [r for r in sorted_risks if r.get("risk_level") == "medium"]
    low_risks = [r for r in sorted_risks if r.get("risk_level") == "low"]

    # 高风险
    if high_risks:
        report_lines.extend([
            "### 🔴 优先级1 - 高风险（需立即处理）\n"
        ])
        for i, risk in enumerate(high_risks, 1):
            report_lines.extend(_format_risk_item(risk, i))

    # 中风险
    if medium_risks:
        report_lines.extend([
            "### 🟡 优先级2 - 中风险（建议处理）\n"
        ])
        for i, risk in enumerate(medium_risks, 1):
            report_lines.extend(_format_risk_item(risk, i))

    # 低风险
    if low_risks:
        report_lines.extend([
            "### 🟢 优先级3 - 低风险（可关注）\n"
        ])
        for i, risk in enumerate(low_risks, 1):
            report_lines.extend(_format_risk_item(risk, i))

    # 综合建议
    report_lines.extend([
        "\n---\n",
        "## 四、综合建议\n",
        _generate_comprehensive_suggestions(sorted_risks),
        "\n---\n",
        "## 免责声明\n",
        "本评估仅供参考，不能替代专业律师意见。",
        "建议在做出任何商业决策前，咨询具有资质的专业人士。"
    ])

    final_report = "\n".join(report_lines)

    # 发送完成进度
    await send_ws_progress(session_id, "reportGeneration", "completed",
                           "风险评估报告生成完成", 1.0)
    logger.info(f"[{session_id}] 报告生成完成")

    return {
        "final_report": final_report,
        "final_result": final_result,
        "status": "completed"
    }


# ==================== 报告生成辅助函数 ====================

def _format_risk_level(level: str) -> str:
    """格式化风险等级"""
    emoji_map = {
        "high": "🔴 高",
        "medium": "🟡 中",
        "low": "🟢 低"
    }
    return emoji_map.get(level, f"{level}")


def _sort_risks_by_priority(risks: List[Dict]) -> List[Dict]:
    """按优先级对风险进行排序"""

    def priority_score(risk):
        score = 0.0
        # 风险等级权重
        level_weights = {"critical": 100, "high": 80, "medium": 60, "low": 40}
        level = risk.get("risk_level", "low").lower()
        score += level_weights.get(level, 40)

        # 置信度权重
        score += risk.get("confidence", 0) * 20

        # 多模型共识加分
        source_count = risk.get("source_models_count", 1)
        if source_count > 1:
            score += 10 * (source_count - 1)

        return score

    return sorted(risks, key=priority_score, reverse=True)


def _format_risk_item(risk: Dict, index: int) -> List[str]:
    """格式化单个风险项"""
    level = risk.get("risk_level", "unknown").upper()
    emoji = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🟢"
    }.get(level, "⚪")

    # 来源视角映射
    source_models = risk.get("source_models", [])
    perspectives_map = {
        "deepseek": "规则执行",
        "gpt_oss": "结构分析",
        "qwen3_235b": "深度分析"
    }
    perspectives = [perspectives_map.get(m, m) for m in source_models if m in perspectives_map]
    source_text = ", ".join(perspectives) if perspectives else "AI 分析"

    lines = [
        f"#### {emoji} {index}. {risk.get('title', '未命名')}",
        "",
        f"**描述：** {risk.get('description', '无描述')}",
        f"**风险等级：** {level}",
        f"**置信度：** {risk.get('confidence', 0):.1%}",
        f"**来源视角：** {source_text}",
        "",
        "**理由：**"
    ]

    for reason in risk.get("reasons", []):
        lines.append(f"- {reason}")

    lines.extend([
        "",
        "**建议：**"
    ])

    for suggestion in risk.get("suggestions", []):
        lines.append(f"- {suggestion}")

    lines.append("")
    return lines


def _generate_comprehensive_suggestions(risks: List[Dict]) -> str:
    """生成综合建议"""
    high_count = sum(1 for r in risks if r.get("risk_level") in ["critical", "high"])
    medium_count = sum(1 for r in risks if r.get("risk_level") == "medium")

    suggestions = []

    # 优先处理建议
    if high_count > 0:
        suggestions.append(f"1. **优先处理**：立即处理 {high_count} 个高风险项，这些风险可能对交易造成重大影响。")

    if medium_count > 0:
        suggestions.append(f"2. **后续处理**：建议在签署前处理 {medium_count} 个中风险项，降低潜在风险。")

    # 专业建议
    suggestions.append("3. **专业咨询**：对于复杂法律条款，建议咨询专业律师进行确认。")
    suggestions.append("4. **持续跟踪**：在合同履行过程中，持续关注已识别风险的演变。")

    return "\n".join(suggestions)


# ==================== 构建工作流 ====================

def should_continue_after_preorganization(state: RiskAnalysisState) -> str:
    """
    决定预整理后是否继续分析
    Returns:
        "continue" 或 "stop"
    """
    # 检查是否设置了停止标志
    if state.get("stop_after_preorganization"):
        logger.info(f"[{state['session_id']}] 预整理完成，停止工作流等待用户确认")
        return "stop"
    else:
        logger.info(f"[{state['session_id']}] 预整理完成，继续分析流程")
        return "continue"


def build_risk_analysis_graph():
    """构建风险评估工作流"""
    # 初始化图
    builder = StateGraph(RiskAnalysisState)

    # 添加节点
    builder.add_node("process_documents", process_documents_node)
    builder.add_node("preorganize_documents", preorganize_documents_node)
    builder.add_node("assemble_rules", assemble_rules_node)
    builder.add_node("multi_model_analyze", multi_model_analyze_node)
    builder.add_node("generate_report", generate_report_node)

    # 定义流程
    builder.set_entry_point("process_documents")
    builder.add_edge("process_documents", "preorganize_documents")

    # 预整理后的条件路由：根据 stop_after_preorganization 决定是否继续
    builder.add_conditional_edges(
        "preorganize_documents",
        should_continue_after_preorganization,
        {
            "continue": "assemble_rules",  # 继续分析
            "stop": END  # 停止等待用户确认
        }
    )

    builder.add_edge("assemble_rules", "multi_model_analyze")
    builder.add_edge("multi_model_analyze", "generate_report")
    builder.add_edge("generate_report", END)

    # 编译
    memory = MemorySaver()
    app = builder.compile(checkpointer=memory)

    return app


# ==================== 服务类 ====================

class RiskAnalysisWorkflowService:
    """风险评估工作流服务"""

    def __init__(self, db: Session):
        self.db = db
        self.graph = build_risk_analysis_graph()

    async def run_analysis(
            self,
            session_id: str,
            user_input: str,
            document_paths: List[str],
            package_id: str,
            stop_after_preorganization: bool = False,
            analysis_mode: str = "multi",
            selected_model: Optional[str] = None
    ) -> bool:
        """
        运行风险评估工作流（异步版本）
        Args:
            session_id: 会话 ID
            user_input: 用户输入
            document_paths: 文档路径列表
            package_id: 规则包 ID
            stop_after_preorganization: 是否在预整理后停止（等待用户确认）
            analysis_mode: 分析模式，"multi"（多模型综合）或 "single"（单模型）
            selected_model: 单模型模式下指定的模型名称（如 "deepseek"）
        Returns:
            bool: 是否成功
        """
        logger.info(
            f"[RiskAnalysisWorkflow] 开始运行会话: {session_id}, stop_after_preorganization: {stop_after_preorganization}")

        # 更新会话状态
        session = self.db.query(RiskAnalysisSession).filter(
            RiskAnalysisSession.session_id == session_id
        ).first()

        if not session:
            logger.error(f"[RiskAnalysisWorkflow] 会话不存在: {session_id}")
            return False

        try:
            session.status = RiskAnalysisStatus.ANALYZING.value
            self.db.commit()

            # 准备初始状态
            initial_state: RiskAnalysisState = {
                "session_id": session_id,
                "user_input": user_input,
                "document_paths": document_paths,
                "package_id": package_id,  # 可以是 None
                "stop_after_preorganization": stop_after_preorganization,  # 设置停止标志
                "raw_documents": None,
                "preorganized_docs": None,
                "assembled_rules": None,
                "analysis_mode": analysis_mode,  # 传递分析模式
                "selected_model": selected_model,  # 传递选定的模型
                "enhanced_analysis_data": None,  # 初始化新字段
                "context": None,
                "analysis_results": None,
                "final_report": None,
                "final_result": None,
                "aggregated": None,
                "status": "processing",
                "error": None
            }

            # 运行工作流（条件路由会自动处理停止逻辑）
            config = {"configurable": {"thread_id": session_id}}
            result = await self.graph.ainvoke(initial_state, config)

            if stop_after_preorganization:
                # 预整理完成，等待用户确认
                logger.info(f"[RiskAnalysisWorkflow] 会话 {session_id} 预整理完成，等待用户确认")
                return True
            else:
                # 完整工作流运行完成，保存结果
                final_status = result.get("status", "failed")

                if final_status == "completed":
                    # 🚪 关键修复：使用独立的、干净的数据库连接（Stale Session 问题）
                    try:
                        with SessionLocal() as db:
                            # 重新查询会话（获取最新状态和主键ID）
                            session_ref = db.query(RiskAnalysisSession).filter(
                                RiskAnalysisSession.session_id == session_id
                            ).first()

                            if not session_ref:
                                logger.error(f"👉 [TRACK] 严重错误: 独立会话中找不到会话 {session_id}")
                                raise Exception(f"会话 {session_id} 不存在")

                            logger.error(f"👉 [TRACK] run_analysis 独立会话已获取会话，主键ID={session_ref.id}, session_id={session_id}")

                            # 更新状态字段
                            session_ref.status = RiskAnalysisStatus.COMPLETED.value
                            session_ref.report_md = result.get("final_report")

                            # 从 final_result 获取摘要和信心
                            final_result_data = result.get("final_result", {})
                            session_ref.summary = final_result_data.get("summary", "")

                            # 计算风险分布
                            risk_items = final_result_data.get("risk_items", [])
                            distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
                            for item in risk_items:
                                level = item.get("risk_level", "low").lower()
                                if level in distribution:
                                    distribution[level] += 1
                            session_ref.risk_distribution = distribution
                            session_ref.total_confidence = final_result_data.get("total_confidence", 0.7)
                            session_ref.completed_at = datetime.utcnow()

                            # 保存风险项（在独立会话中）
                            # 清空旧记录
                            db.query(RiskItem).filter(
                                RiskItem.session_id == session_ref.id  # 使用主键ID
                            ).delete()

                            # 插入新风险项
                            for item in risk_items:
                                # 获取来源模型信息
                                source_models = item.get("source_models", [])
                                source_type = "multi_model"
                                if len(source_models) == 1:
                                    source_type = f"multi_model_{source_models[0]}"

                                risk_item = RiskItem(
                                    session_id=session_ref.id,  # 使用主键ID
                                    title=item.get("title", "未命名"),
                                    description=item.get("description", ""),
                                    risk_level=item.get("risk_level", "medium"),
                                    confidence=item.get("confidence", 0.0),
                                    reasons=item.get("reasons", []),
                                    suggestions=item.get("suggestions", []),
                                    source_type=source_type,
                                    source_rules=None
                                )
                                db.add(risk_item)

                            # ✅ 提交独立会话（绝对可靠）
                            db.commit()
                            logger.error(f"👉 [TRACK] run_analysis 独立会话提交成功! 数据已落盘, session_id={session_id}, 主键ID={session_ref.id}, 风险项数={len(risk_items)}")

                        # 只有在确信数据落盘后，才通知前端
                        try:
                            from app.api.websocket import manager
                            await manager.send_progress(session_id, {"type": "complete"})
                            logger.info(f"[WS] 发送complete消息成功: {session_id}")
                        except Exception as e:
                            logger.error(f"[WS] 发送complete消息失败: {e}")

                        return True

                    except Exception as e:
                        logger.error(f"👉 [TRACK] run_analysis 独立会话提交异常: {e}, session_id={session_id}", exc_info=True)
                        # 回退到陈旧会话（最后的尝试）
                        session.status = RiskAnalysisStatus.FAILED.value
                        session.report_md = f"状态更新失败: {str(e)}"
                        self.db.commit()
                        return False
                else:
                    session.status = RiskAnalysisStatus.FAILED.value
                    session.report_md = result.get("error", "分析失败")
                    self.db.commit()
                    logger.error(f"[RiskAnalysisWorkflow] 会话 {session_id} 失败: {result.get('error')}")
                    return False

        except Exception as e:
            logger.error(f"[RiskAnalysisWorkflow] 会话 {session_id} 异常: {e}", exc_info=True)
            session.status = RiskAnalysisStatus.FAILED.value
            self.db.commit()
            return False

    async def continue_analysis_after_confirmation(
            self,
            session_id: str,
            analysis_mode: str = "multi",
            selected_model: Optional[str] = None,
            evaluation_stance: Optional[str] = None  # ✅ 新增：评估立场参数
    ) -> bool:
        """
        在用户确认预整理结果后继续分析
        Args:
            session_id: 会话 ID
            analysis_mode: 分析模式 ("single" 或 "multi")
            selected_model: 单模型模式下选择的模型名称
            evaluation_stance: 风险评估立场（投资人视角/卖方视角等）
        Returns:
            bool: 是否成功
        """
        logger.info(f"[RiskAnalysisWorkflow] 继续分析会话: {session_id}, mode: {analysis_mode}, stance: {evaluation_stance}")

        # 更新会话状态
        session = self.db.query(RiskAnalysisSession).filter(
            RiskAnalysisSession.session_id == session_id
        ).first()

        if not session:
            logger.error(f"[RiskAnalysisWorkflow] 会话不存在: {session_id}")
            return False

        try:
            # 准备继续分析
            # 方案:从数据库重新加载预整理结果,然后手动执行剩余节点

            # 从数据库获取预整理结果
            from app.models.risk_analysis_preorganization import RiskAnalysisPreorganization
            preorg_record = self.db.query(RiskAnalysisPreorganization).filter(
                RiskAnalysisPreorganization.session_id == session_id
            ).first()

            if not preorg_record:
                logger.error(f"[RiskAnalysisWorkflow] 未找到预整理记录: {session_id}")
                # 降级方案:尝试从checkpoint获取状态
                config = {"configurable": {"thread_id": session_id}}
                try:
                    current_snapshot = await self.graph.aget_state(config)
                    if not current_snapshot or not current_snapshot.values:
                        logger.error(f"[RiskAnalysisWorkflow] 无法获取会话 {session_id} 的状态")
                        return False
                    continue_state = dict(current_snapshot.values)
                except Exception as checkpoint_error:
                    logger.error(f"[RiskAnalysisWorkflow] checkpoint 获取失败: {checkpoint_error}")
                    return False
            else:
                # 从预整理记录重建状态
                logger.info(f"[RiskAnalysisWorkflow] 从预整理记录重建状态: {session_id}")

                # 将预整理记录的各个字段组合成preorganized_docs格式
                preorganized_docs = {
                    "user_requirement_summary": preorg_record.user_requirement_summary,
                    "documents_info": preorg_record.documents_info,
                    "fact_summary": preorg_record.fact_summary,
                    "contract_legal_features": preorg_record.contract_legal_features,
                    "contract_relationships": preorg_record.contract_relationships,
                    "architecture_diagram": preorg_record.architecture_diagram
                }

                # 尝试解析 enhanced_analysis_json
                enhanced_data_from_db = None
                if preorg_record.enhanced_analysis_json:
                    try:
                        enhanced_data_from_db = json.loads(preorg_record.enhanced_analysis_json)
                    except:
                        pass

                # 从数据库恢复 raw_documents（仅恢复元数据，确保 document_count 正确）
                raw_documents_from_db = []
                if session.document_processing_results:
                    if isinstance(session.document_processing_results, dict):
                        # 数据库格式：{filename: {file_path, status, metadata, ...}}
                        # 转换为列表，确保 len() 返回真实文档数量
                        raw_documents_from_db = list(session.document_processing_results.values())
                    elif isinstance(session.document_processing_results, list):
                        # 兼容旧数据格式
                        raw_documents_from_db = session.document_processing_results

                continue_state: RiskAnalysisState = {
                    "session_id": session_id,
                    "user_input": session.user_description or "",
                    "document_paths": session.document_ids or [],
                    "package_id": None,  # 用户确认时才选择规则包
                    "stop_after_preorganization": False,  # 移除停止标志
                    "raw_documents": raw_documents_from_db,  # 恢复文档列表，确保 len() 正确
                    "preorganized_docs": preorganized_docs,
                    "enhanced_analysis_data": enhanced_data_from_db,  # 恢复增强数据
                    "assembled_rules": None,
                    "analysis_mode": preorg_record.analysis_mode,
                    "selected_model": preorg_record.selected_model,
                    "evaluation_stance": evaluation_stance,  # ✅ 新增：传递评估立场
                    "context": None,
                    "analysis_results": None,
                    "final_report": None,
                    "final_result": None,
                    "aggregated": None,
                    "status": "processing",
                    "error": None
                }

            # 直接从 assemble_rules 节点开始执行（跳过已完成的节点）
            # 我们需要手动调用剩余的节点
            logger.info(f"[RiskAnalysisWorkflow] 会话 {session_id} 从规则组装节点继续分析")

            # 发送初始进度，重置进度条
            await send_ws_progress(session_id, "multiModelAnalysis", "pending", "准备继续分析...", 0.0)

            # 1. 规则组装
            result1 = await assemble_rules_node(continue_state)
            continue_state.update(result1)
            if continue_state.get("status") == "failed":
                raise Exception(continue_state.get("error", "规则组装失败"))

            # 2. 多模型分析
            analysis_mode_display = continue_state.get("analysis_mode", "multi")
            mode_text = "单模型" if analysis_mode_display == "single" else "多模型"
            logger.error(f"👉 [TRACK] 开始执行 {mode_text}分析节点, session_id={session_id}, mode={analysis_mode_display}")
            result2 = await multi_model_analyze_node(continue_state)
            logger.error(f"👉 [TRACK] {mode_text}分析节点返回, status={result2.get('status')}, session_id={session_id}")
            continue_state.update(result2)
            if continue_state.get("status") == "failed":
                logger.error(f"👉 [TRACK] {mode_text}分析失败, error={continue_state.get('error')}, session_id={session_id}")
                raise Exception(continue_state.get("error", f"{mode_text}分析失败"))

            # 3. 报告生成
            logger.error(f"👉 [TRACK] 开始执行 generate_report_node, session_id={session_id}")
            result3 = await generate_report_node(continue_state)
            logger.error(f"👉 [TRACK] generate_report_node 返回, status={result3.get('status')}, session_id={session_id}")
            continue_state.update(result3)

            # 最终结果
            result = continue_state

            # 保存结果
            final_status = result.get("status", "failed")
            logger.error(f"👉 [TRACK] final_status={final_status}, session_id={session_id}")

            if final_status == "completed":
                logger.error(f"👉 [TRACK] 进入 completed 分支，使用独立会话更新数据库, session_id={session_id}")

                # 🚪 关键修复：使用全新的、干净的数据库连接（Stale Session 问题）
                # self.db 可能是陈旧会话，commit 看似成功但数据未持久化
                try:
                    with SessionLocal() as db:
                        # 重新查询会话（获取最新状态和主键ID）
                        session_ref = db.query(RiskAnalysisSession).filter(
                            RiskAnalysisSession.session_id == session_id
                        ).first()

                        if not session_ref:
                            logger.error(f"👉 [TRACK] 严重错误: 独立会话中找不到会话 {session_id}")
                            raise Exception(f"会话 {session_id} 不存在")

                        logger.error(f"👉 [TRACK] 独立会话已获取会话，主键ID={session_ref.id}, session_id={session_id}")

                        # 更新状态字段
                        session_ref.status = RiskAnalysisStatus.COMPLETED.value
                        session_ref.report_md = result.get("final_report")

                        # 从 final_result 获取摘要和信心
                        final_result_data = result.get("final_result", {})
                        session_ref.summary = final_result_data.get("summary", "")

                        # 计算风险分布
                        risk_items = final_result_data.get("risk_items", [])
                        distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
                        for item in risk_items:
                            level = item.get("risk_level", "low").lower()
                            if level in distribution:
                                distribution[level] += 1
                        session_ref.risk_distribution = distribution
                        session_ref.total_confidence = final_result_data.get("total_confidence", 0.7)
                        session_ref.completed_at = datetime.utcnow()

                        # 保存风险项（在独立会话中）
                        # 清空旧记录
                        db.query(RiskItem).filter(
                            RiskItem.session_id == session_ref.id  # 使用主键ID
                        ).delete()

                        # 插入新风险项
                        for item in risk_items:
                            # 获取来源模型信息
                            source_models = item.get("source_models", [])
                            source_type = "multi_model"
                            if len(source_models) == 1:
                                source_type = f"multi_model_{source_models[0]}"

                            risk_item = RiskItem(
                                session_id=session_ref.id,  # 使用主键ID
                                title=item.get("title", "未命名"),
                                description=item.get("description", ""),
                                risk_level=item.get("risk_level", "medium"),
                                confidence=item.get("confidence", 0.0),
                                reasons=item.get("reasons", []),
                                suggestions=item.get("suggestions", []),
                                source_type=source_type,
                                source_rules=None
                            )
                            db.add(risk_item)

                        # ✅ 提交独立会话（绝对可靠）
                        db.commit()
                        logger.error(f"👉 [TRACK] 独立会话提交成功! 数据已落盘, session_id={session_id}, 主键ID={session_ref.id}, 风险项数={len(risk_items)}")

                    # 只有在确信数据落盘后，才通知前端
                    try:
                        from app.api.websocket import manager
                        await manager.send_progress(session_id, {"type": "complete"})
                        logger.info(f"[WS] 发送complete消息成功: {session_id}")
                    except Exception as e:
                        logger.error(f"[WS] 发送complete消息失败: {e}")

                    return True

                except Exception as e:
                    logger.error(f"👉 [TRACK] 独立会话提交异常: {e}, session_id={session_id}", exc_info=True)
                    # 回退到陈旧会话（最后的尝试）
                    session.status = RiskAnalysisStatus.FAILED.value
                    session.report_md = f"状态更新失败: {str(e)}"
                    self.db.commit()
                    return False
            else:
                logger.error(f"👉 [TRACK] final_status 不是 completed，跳过提交: final_status={final_status}, session_id={session_id}")
                # 保存错误信息
                session.status = RiskAnalysisStatus.FAILED.value
                session.report_md = result.get("error", "分析失败")
                self.db.commit()
                logger.error(f"[RiskAnalysisWorkflow] 会话 {session_id} 继续分析失败: status={final_status}")
                return False

        except Exception as e:
            logger.error(f"[RiskAnalysisWorkflow] 会话 {session_id} 继续分析异常: {e}", exc_info=True)
            session.status = RiskAnalysisStatus.FAILED.value
            self.db.commit()
            return False

    def _save_risk_items(self, session_id: int, final_result: Dict[str, Any]):
        """保存风险项到数据库（适配新的 final_result 格式）"""
        # 清空旧记录
        self.db.query(RiskItem).filter(
            RiskItem.session_id == session_id
        ).delete()

        # 从 final_result 获取风险项
        risk_items = final_result.get("risk_items", [])

        for item in risk_items:
            # 获取来源模型信息
            source_models = item.get("source_models", [])
            source_type = "multi_model"
            if len(source_models) == 1:
                source_type = f"multi_model_{source_models[0]}"

            risk_item = RiskItem(
                session_id=session_id,
                title=item.get("title", "未命名"),
                description=item.get("description", ""),
                risk_level=item.get("risk_level", "medium"),
                confidence=item.get("confidence", 0.0),
                reasons=item.get("reasons", []),
                suggestions=item.get("suggestions", []),
                source_type=source_type,
                source_rules=None
            )
            self.db.add(risk_item)

        logger.info(f"[RiskAnalysisWorkflow] 保存 {len(risk_items)} 个风险项")


# ==================== 便捷函数 ====================

async def run_risk_analysis_workflow(
        session_id: str,
        user_input: str,
        document_paths: List[str],
        package_id: str,
        analysis_mode: str = "multi",  # <--- 新增
        selected_model: Optional[str] = None  # <--- 新增
) -> bool:
    """
    运行风险评估工作流的便捷函数
    """
    db = SessionLocal()
    try:
        service = RiskAnalysisWorkflowService(db)
        return await service.run_analysis(
            session_id=session_id,
            user_input=user_input,
            document_paths=document_paths,
            package_id=package_id,
            analysis_mode=analysis_mode,  # 传递
            selected_model=selected_model  # 传递
        )
    finally:
        db.close()