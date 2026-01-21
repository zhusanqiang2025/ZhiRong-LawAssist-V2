# backend/app/services/litigation_analysis/workflow.py
# Part 1: Imports, State, and Pre-processing Nodes
"""
案件分析工作流 - LangGraph 编排 (重构版 - 适配统一预整理)

核心更新：
1. 统一调用 EnhancedCasePreorganizationService，移除基础版分支。
2. 数据流转适配前端 '交易全景' 组件结构，修复展示问题。
3. 强化 WebSocket 进度推送和错误处理。
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, TypedDict, Literal
from dataclasses import asdict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.unified_document_service import UnifiedDocumentService
# 使用统一的增强版服务
from app.services.litigation_analysis.enhanced_case_preorganization import (
    get_enhanced_case_preorganization_service
)
from app.services.litigation_analysis.case_rule_assembler import CaseRuleAssembler
from app.services.litigation_analysis.evidence_analyzer import EvidenceAnalyzer
from app.services.litigation_analysis.timeline_generator import TimelineGenerator
from app.services.litigation_analysis.strategy_generator import StrategyGenerator
from app.services.litigation_analysis.multi_model_analyzer import MultiModelAnalyzer
from app.services.litigation_analysis.report_generator import ReportGenerator

logger = logging.getLogger(__name__)


class LitigationAnalysisState(TypedDict):
    """案件分析状态"""
    # ============ 输入数据 ============
    session_id: str
    user_input: Optional[str]
    document_paths: List[str]
    case_package_id: str
    
    # 业务参数
    case_type: str          
    case_position: Optional[str]     # 阶段1时可能为 None
    analysis_scenario: Optional[str] # 阶段1时可能为 None
    
    # 配置
    analysis_mode: str      
    selected_model: Optional[str]

    # ============ 处理结果 ============
    raw_documents: Optional[List[Any]]
    
    # 统一后的增强数据结构，包含 document_summaries, enhanced_analysis_compatible 等
    preorganized_case: Optional[Dict[str, Any]] 

    assembled_rules: Optional[List[str]]        
    timeline: Optional[Dict[str, Any]]          
    evidence_analysis: Optional[Dict[str, Any]] 
    model_results: Optional[Dict[str, Any]]     
    strategies: Optional[List[Dict[str, Any]]]  
    draft_documents: Optional[List[Dict[str, Any]]] 
    final_report: Optional[str]                 
    report_json: Optional[Dict[str, Any]]       

    # ============ 状态控制 ============
    status: str
    error: Optional[str]


# ==================== 辅助函数 ====================

async def send_ws_progress(session_id: str, node: str, status: str, message: str = "", progress: float = 0.0):
    """发送 WebSocket 进度（增强诊断版）"""
    try:
        from app.api.websocket import manager

        # 检查连接是否存在（避免Broken Pipe）
        if not manager.is_connected(session_id):
            logger.warning(f"[{session_id}] ⚠️ WebSocket 未连接，无法发送进度: node={node}, status={status}, message={message}")
            return

        logger.debug(f"[{session_id}] 发送进度: node={node}, status={status}, progress={progress}, message={message}")
        await manager.send_progress(session_id, {
            "type": "node_progress",
            "node": node,
            "status": status,
            "message": message,
            "progress": progress
        })
    except Exception as e:
        logger.error(f"[{session_id}] 发送进度失败: node={node}, error={e}")
        # 静默失败，不影响主流程
        pass

def check_error_status(state: LitigationAnalysisState) -> Literal["continue", "end"]:
    """熔断机制"""
    if state.get("error"):
        logger.warning(f"[{state.get('session_id')}] 工作流熔断: {state['error']}")
        return "end"
    return "continue"


# ==================== 工作流节点 ====================

async def process_documents_node(state: LitigationAnalysisState) -> Dict[str, Any]:
    """节点1: 文档处理"""
    if state.get("raw_documents"):
        return {"status": "documents_ready"}

    logger.info(f"[{state['session_id']}] 开始处理文档")
    await send_ws_progress(state['session_id'], "process_documents", "processing", "正在解析文档内容...", 0.1)
    
    try:
        doc_service = UnifiedDocumentService()
        results = await doc_service.batch_process_async(
            state["document_paths"],
            extract_content=True,
            extract_metadata=True
        )
        successful_docs = [r for r in results if r.status == 'success']
        
        if not successful_docs:
            raise ValueError("没有成功解析的文档，请检查文件格式")

        return {
            "raw_documents": successful_docs,
            "status": "documents_processed"
        }
    except Exception as e:
        return {"error": f"文档处理失败: {str(e)}", "status": "failed"}


async def preorganize_case_node(state: LitigationAnalysisState) -> Dict[str, Any]:
    """
    节点2: 统一预整理 (Unified Preorganization)
    
    无论是否选择了角色，都调用 Enhanced Service。
    未选角色时，默认为 '中立' 视角，生成案件全景。
    """
    session_id = state['session_id']
    
    # 1. 检查复用 (如果用户已经确认过并重新进入)
    if state.get("preorganized_case") and state.get("preorganized_case", {}).get("is_confirmed"):
        logger.info(f"[{session_id}] 复用已确认的预整理数据")
        return {"status": "preorganization_ready"}

    # 2. 准备参数
    case_position = state.get('case_position')
    analysis_scenario = state.get('analysis_scenario')
    
    logger.info(f"[{session_id}] 开始预整理 | 视角: {case_position or '自动识别(中立)'}")

    try:
        from app.core.llm_config import get_qwen_llm
        llm = get_qwen_llm()

        # 验证 LLM 是否正确初始化
        if llm is None:
            error_msg = "LLM 服务初始化失败：未配置有效的 API Key"
            logger.error(f"[{session_id}] {error_msg}")
            await send_ws_progress(session_id, "preorganize", "failed", error_msg, 0)
            return {"error": error_msg, "status": "failed"}

        service = get_enhanced_case_preorganization_service(llm)
        logger.info(f"[{session_id}] LLM 服务初始化成功，准备预整理")

        # 定义回调
        async def progress_callback(step: str, progress: float, message: str):
            await send_ws_progress(session_id, "preorganize", "processing", message, progress)

        # 3. 执行分析 (统一入口)
        preorganized_result = await service.preorganize_enhanced(
            documents=state["raw_documents"],
            case_type=state["case_type"],
            case_position=case_position, # 如果为None，Service内部处理为中立视角
            analysis_scenario=analysis_scenario,
            user_context=state.get("user_input"),
            progress_callback=progress_callback
        )

        # 4. 数据推送 (关键：对齐前端组件)
        # 前端组件 RiskAnalysisPageV2 复用了风险评估的 EnhancedAnalysisDisplay
        # 所以我们需要构造 compatible_data 放入 enhanced_analysis 字段
        try:
            from app.api.websocket import manager
            
            # 提取兼容数据 (transaction_summary, parties, timeline)
            compatible_data = preorganized_result.get("enhanced_analysis_compatible", {})
            
            # 构造 WebSocket Payload
            payload = {
                "type": "preorganization_completed",
                "has_result": True,
                "can_proceed": True,
                
                # 基础列表数据 (用于文件列表展示)
                "preorganized_data": {
                    "document_summaries": preorganized_result.get("document_summaries", {}),
                    "case_type": state["case_type"]
                },
                
                # 核心：放入 enhanced_analysis 字段，这是前端组件的数据源
                "enhanced_analysis": compatible_data, 
                
                # 冗余一份到 enhanced_data 以防万一
                "enhanced_data": compatible_data 
            }
            
            if manager.is_connected(session_id):
                await manager.send_progress(session_id, payload)
                logger.info(f"[{session_id}] 预整理数据已推送前端")
                
        except Exception as e:
            logger.warning(f"[{session_id}] WebSocket 推送异常: {e}")

        # 5. 保存到数据库 (可选，用于断点续传)
        # 这里为了简化，暂不包含 DB 保存代码，由 Controller 层处理或在此处添加 Model 保存逻辑

        return {
            "preorganized_case": preorganized_result,
            "status": "preorganization_completed"
        }

    except Exception as e:
        logger.error(f"[{session_id}] 预整理失败: {e}", exc_info=True)
        await send_ws_progress(session_id, "preorganize", "failed", f"失败: {str(e)}", 0)
        return {"error": str(e), "status": "failed"}


async def assemble_case_rules_node(state: LitigationAnalysisState) -> Dict[str, Any]:
    """节点3: 组装规则"""
    session_id = state['session_id']
    # 如果没有场景（阶段1），使用默认场景
    scenario = state.get("analysis_scenario") or "pre_litigation"

    logger.info(f"[{session_id}] 加载规则库 (场景: {scenario})")

    # 发送进度更新
    await send_ws_progress(session_id, "assemble_case_rules", "processing", "正在组装案件规则...", 0.25)

    try:
        assembler = CaseRuleAssembler()

        # 适配：确保传入 context 的数据是扁平或可读的
        pre_data = state.get("preorganized_case", {})

        # 添加类型检查和容错处理
        if not isinstance(pre_data, dict):
            logger.warning(f"[{session_id}] preorganized_case 不是字典类型: {type(pre_data)}")
            pre_data = {}

        # 确保 enhanced_analysis_compatible 是字典
        enhanced_info = pre_data.get("enhanced_analysis_compatible") if isinstance(pre_data, dict) else None
        if not isinstance(enhanced_info, dict):
            enhanced_info = {}

        rules = assembler.assemble_rules(
            package_id=state["case_package_id"],
            context={
                "case_type": state["case_type"],
                "case_position": state.get("case_position") or "unknown",
                "scenario": scenario,
                "preorganized": pre_data,
                "user_input": state.get("user_input"),
                # 传递增强数据辅助规则选择
                "enhanced_info": enhanced_info
            }
        )

        # 发送完成进度
        await send_ws_progress(session_id, "assemble_case_rules", "completed", "规则组装完成", 0.35)

        return {"assembled_rules": rules, "status": "rules_assembled"}

    except Exception as e:
        logger.error(f"规则组装失败: {e}")
        # 规则组装失败不应熔断，返回空规则即可
        await send_ws_progress(session_id, "assemble_case_rules", "failed", f"规则组装失败: {str(e)}", 0.35)
        return {"assembled_rules": [], "status": "rules_failed_ignorable"}
# backend/app/services/litigation_analysis/workflow.py
# Part 2: Analysis Nodes, Drafting, and Graph Construction

async def analyze_evidence_node(state: LitigationAnalysisState) -> Dict[str, Any]:
    """节点4: 证据分析"""
    session_id = state['session_id']
    logger.info(f"[{session_id}] 开始分析证据")

    # 发送进度更新
    await send_ws_progress(session_id, "analyze_evidence", "processing", "正在分析证据...", 0.45)

    try:
        analyzer = EvidenceAnalyzer()

        # 数据适配：将 document_summaries 转换为列表格式供分析器使用
        pre_data = state.get("preorganized_case", {})

        # 添加类型检查
        if not isinstance(pre_data, dict):
            logger.warning(f"[{session_id}] preorganized_case 不是字典类型: {type(pre_data)}")
            doc_summaries = {}
        else:
            doc_summaries = pre_data.get("document_summaries", {})

        # 确保 doc_summaries 是字典
        if not isinstance(doc_summaries, dict):
            logger.warning(f"[{session_id}] document_summaries 不是字典类型: {type(doc_summaries)}")
            doc_summaries = {}

        # 构造 EvidenceAnalyzer 期望的输入格式
        # 假设 EvidenceAnalyzer 接受 list 形式的文档信息
        formatted_docs = {
            "document_analyses": [
                {
                    "file_name": v.get("document_title", k), # 优先用标题
                    "file_type": v.get("document_subtype", "unknown"),
                    "content_summary": v.get("summary", ""),
                    "key_dates": v.get("key_dates", [])
                }
                for k, v in doc_summaries.items()
            ]
        }

        analysis = await analyzer.analyze(
            documents=formatted_docs,
            case_type=state["case_type"],
            context={
                "rules": state.get("assembled_rules", []),
                "scenario": state.get("analysis_scenario", "pre_litigation")
            }
        )

        # 发送完成进度
        await send_ws_progress(session_id, "analyze_evidence", "completed", "证据分析完成", 0.55)

        return {"evidence_analysis": analysis, "status": "evidence_analyzed"}

    except Exception as e:
        logger.error(f"证据分析失败: {e}")
        await send_ws_progress(session_id, "analyze_evidence", "failed", f"证据分析失败: {str(e)}", 0.55)
        return {"error": f"证据分析失败: {str(e)}", "status": "failed"}


async def multi_model_analyze_node(state: LitigationAnalysisState) -> Dict[str, Any]:
    """节点5: 综合推演 (调用多模型)"""
    session_id = state['session_id']
    logger.info(f"[{session_id}] 开始多模型综合推演")

    # 发送进度
    await send_ws_progress(session_id, "multi_model_analyze", "processing", "AI 正在进行多模型深度推演...", 0.1)

    try:
        # 1. 构建上下文 (已包含案件全景和争议焦点)
        # 注意：enhanced_data（案件全景）已被 _build_litigation_context 整合进 context
        context = _build_litigation_context(state)

        # 2. 初始化分析器 (在此处传入模式配置)
        analyzer = MultiModelAnalyzer(
            mode=state.get('analysis_mode', 'multi'),
            selected_model=state.get('selected_model')
        )

        # 3. 执行分析
        # ✅ 修复：移除错误的关键字参数，正确映射已有参数
        results = await analyzer.analyze_parallel(
            context=context,
            rules=state.get("assembled_rules", []),
            session_id=session_id,
            case_type=state["case_type"],
            case_position=state["case_position"],
            # 传入真正的证据分析结果（非案件全景）
            evidence_analysis=state.get("evidence_analysis", {}),
            # 传入分析场景
            scenario=state.get("analysis_scenario", "pre_litigation")
        )

        await send_ws_progress(session_id, "multi_model_analyze", "completed", "推演完成", 1.0)

        return {
            "model_results": results,
            "status": "model_analyzed"
        }
    except Exception as e:
        logger.error(f"模型推演失败: {e}", exc_info=True)
        # 失败时发送进度通知
        await send_ws_progress(session_id, "multi_model_analyze", "failed", f"推演失败: {str(e)}", 0)
        return {"error": f"模型推演失败: {str(e)}", "status": "failed"}


async def generate_strategies_node(state: LitigationAnalysisState) -> Dict[str, Any]:
    """节点6: 生成策略（增强版：容错处理）"""
    session_id = state['session_id']
    logger.info(f"[{session_id}] 开始生成诉讼策略")

    # 发送进度更新
    await send_ws_progress(session_id, "generate_strategies", "processing", "正在生成诉讼策略...", 0.75)

    try:
        # 1. 检查上游是否失败
        model_results = state.get("model_results", {})
        if model_results.get("status") == "failed" or "error" in model_results:
            logger.warning(f"[{session_id}] 上游分析失败，使用基础策略")
            strategies = _get_basic_strategies_for_failed_analysis(
                state.get("case_type", "未知案件"),
                state.get("analysis_scenario", "pre_litigation")
            )
        else:
            # 2. 正常流程
            generator = StrategyGenerator()
            strategies = await generator.generate(
                case_strength=model_results,
                evidence=state.get("evidence_analysis", {}),
                case_type=state["case_type"],
                case_position=state["case_position"],
                scenario=state["analysis_scenario"]
            )

        # 发送完成进度
        await send_ws_progress(session_id, "generate_strategies", "completed", "策略生成完成", 0.85)

        return {
            "strategies": strategies,
            "status": "strategies_generated"
        }
    except Exception as e:
        logger.error(f"策略生成失败: {e}", exc_info=True)
        # 返回基础策略而非错误，避免工作流熔断
        strategies = _get_basic_strategies_for_failed_analysis(
            state.get("case_type", "未知案件"),
            state.get("analysis_scenario", "pre_litigation")
        )
        await send_ws_progress(session_id, "generate_strategies", "completed", "策略生成完成（基础版）", 0.85)
        return {
            "strategies": strategies,
            "status": "strategies_generated_fallback"
        }


def _get_basic_strategies_for_failed_analysis(case_type: str, scenario: str) -> List[Dict]:
    """当分析失败时返回的基础策略"""
    if scenario == "defense":
        return [{
            "strategy_id": "BASIC_DEF_01",
            "title": "审查材料并准备答辩",
            "type": "balanced",
            "description": f"针对【{case_type}】案件，建议首先仔细审查原告提交的材料。",
            "steps": [
                {"step_name": "核对起诉状", "description": "检查原告主张的事实和证据", "executor": "律师", "deadline": "收到后3日内"},
                {"step_name": "准备答辩状", "description": "针对原告主张逐一答辩", "executor": "律师", "deadline": "答辩期内"}
            ],
            "expected_outcome": "有效抗辩",
            "risk_mitigation": "避免缺席审判",
            "recommendation_score": 5
        }]
    else:
        return [{
            "strategy_id": "BASIC_PRE_01",
            "title": "完善证据准备",
            "type": "conservative",
            "description": f"针对【{case_type}】案件，建议首先完善证据链。",
            "steps": [
                {"step_name": "梳理证据", "description": "按法律要件整理证据", "executor": "当事人", "deadline": "立即"},
                {"step_name": "法律咨询", "description": "咨询专业律师", "executor": "当事人", "deadline": "5日内"}
            ],
            "expected_outcome": "明确诉讼方向",
            "risk_mitigation": "避免证据不足",
            "recommendation_score": 4
        }]


async def generate_drafts_node(state: LitigationAnalysisState) -> Dict[str, Any]:
    """
    节点7: 生成法律文书草稿
    """
    session_id = state['session_id']
    case_position = state.get('case_position')
    analysis_scenario = state.get('analysis_scenario')

    # 如果信息不全，跳过
    if not case_position or not analysis_scenario:
        return {"draft_documents": [], "status": "drafts_skipped"}

    logger.info(f"[{session_id}] 开始生成文书草稿 (角色: {case_position}, 场景: {analysis_scenario})")

    try:
        await send_ws_progress(session_id, "generate_drafts", "processing", "正在生成法律文书...", 0.1)

        # 动态导入避免循环依赖
        from app.services.document_drafting.agents.document_drafter import DocumentDrafterAgent
        from app.services.document_templates import TemplateManager

        # 确定需要的文书类型
        document_types = _get_required_document_types(case_position, analysis_scenario)
        
        if not document_types:
            return {"draft_documents": [], "status": "no_drafts_needed"}

        drafter = DocumentDrafterAgent()
        template_manager = TemplateManager()
        draft_documents = []

        # 准备数据源
        analysis_result = _build_drafting_analysis_result(state)
        reference_content = _build_reference_content(state)

        for idx, doc_type_info in enumerate(document_types, 1):
            doc_type = doc_type_info['type']
            doc_name = doc_type_info['name']
            
            try:
                # 获取模板
                template_content = await template_manager.get_template(doc_type)
                if not template_content:
                    continue

                # 生成
                content, metadata = drafter.draft_with_template(
                    analysis_result=analysis_result,
                    template_content=template_content,
                    strategy={"mode": "template_rewrite", "temperature": 0.3},
                    reference_content=reference_content
                )

                draft_documents.append({
                    "document_type": doc_type,
                    "document_name": doc_name,
                    "content": content,
                    "generated_at": datetime.now().isoformat()
                })
                
                # 进度更新
                await send_ws_progress(
                    session_id, "generate_drafts", "processing", 
                    f"已生成: {doc_name}", 0.1 + (idx/len(document_types))*0.8
                )

            except Exception as e:
                logger.error(f"文书 {doc_name} 生成失败: {e}")

        await send_ws_progress(session_id, "generate_drafts", "completed", "文书生成完成", 1.0)
        
        return {
            "draft_documents": draft_documents,
            "status": "drafts_generated"
        }

    except Exception as e:
        logger.error(f"文书生成节点异常: {e}")
        return {"draft_documents": [], "status": "drafts_failed"}


async def generate_report_node(state: LitigationAnalysisState) -> Dict[str, Any]:
    """节点8: 生成最终报告"""
    session_id = state['session_id']
    logger.info(f"[{session_id}] 生成最终报告")

    # 发送进度更新
    await send_ws_progress(session_id, "generate_report", "processing", "正在生成最终报告...", 0.92)

    try:
        generator = ReportGenerator()

        # 提取模型摘要
        model_res = state.get("model_results", {})
        final_summary = ""
        if isinstance(model_res, dict) and "final_result" in model_res:
             final_summary = model_res["final_result"].get("summary", "")

        report_data = {
            "scenario": state["analysis_scenario"],
            "case_summary": final_summary,
            "rules": state.get("assembled_rules", []),
            "evidence_analysis": state.get("evidence_analysis"),
            "timeline": state.get("timeline"),
            "model_results": model_res,
            "strategies": state.get("strategies"),
            "draft_documents": state.get("draft_documents", []),
            "case_type": state["case_type"],
            "case_position": state["case_position"]
        }

        report_md, report_json = generator.generate(report_data)

        # 发送完成进度
        await send_ws_progress(session_id, "generate_report", "completed", "报告生成完成", 0.98)

        return {
            "final_report": report_md,
            "report_json": report_json,
            "status": "completed"
        }
    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        await send_ws_progress(session_id, "generate_report", "failed", f"报告生成失败: {str(e)}", 0.98)
        return {"error": str(e), "status": "failed"}


# ==================== 辅助逻辑：文书生成支持 ====================

def _get_required_document_types(position: str, scenario: str) -> List[Dict]:
    """确定文书类型"""
    mapping = {
        ("plaintiff", "pre_litigation"): [
            {"type": "civil_complaint", "name": "民事起诉状"},
            {"type": "evidence_list", "name": "证据清单"}
        ],
        ("defendant", "defense"): [
            {"type": "defense_statement", "name": "民事答辩状"}
        ],
        ("applicant", "arbitration"): [
            {"type": "arbitration_application", "name": "仲裁申请书"}
        ]
    }
    return mapping.get((position, scenario), [])

def _build_drafting_analysis_result(state: LitigationAnalysisState) -> Dict:
    """构造文书起草输入数据"""
    pre_data = state.get("preorganized_case", {})
    enhanced = pre_data.get("enhanced_analysis_compatible", {})
    
    return {
        "case_type": state.get("case_type"),
        "case_position": state.get("case_position"),
        "parties": enhanced.get("parties", []), # 适配新结构
        "timeline": enhanced.get("timeline", []),
        "case_summary": enhanced.get("transaction_summary", ""),
        "claims": {}, # 需进一步从 strategies 提取
    }

def _build_reference_content(state: LitigationAnalysisState) -> str:
    """构造参考资料字符串"""
    parts = []
    if state.get("user_input"):
        parts.append(f"用户陈述: {state['user_input']}")
    
    pre = state.get("preorganized_case", {})
    if "enhanced_analysis_compatible" in pre:
        summary = pre["enhanced_analysis_compatible"].get("transaction_summary", "")
        parts.append(f"案件综述: {summary}")
        
    return "\n\n".join(parts)

def _build_litigation_context(state: LitigationAnalysisState) -> str:
    """
    构造多模型分析的 Context (增强版)

    确保包含完整的案件事实信息：
    - 案件摘要
    - 文档列表及详细摘要
    - 证据分析要点
    - 规则库匹配结果
    """
    parts = []

    # ==================== 1. 基础信息 ====================
    parts.append("=" * 60)
    parts.append("【案件基础信息】")
    parts.append(f"案件类型: {state['case_type']}")
    parts.append(f"我方地位: {state.get('case_position', '未知')}")
    parts.append(f"分析场景: {state.get('analysis_scenario', 'pre_litigation')}")

    if state.get("user_input"):
        parts.append(f"\n用户陈述:\n{state['user_input']}")

    # ==================== 2. 案件全景摘要 ====================
    pre = state.get("preorganized_case", {})
    if pre and isinstance(pre, dict):
        # 提取摘要（Pre-org Summary）
        summary = pre.get("summary", "")
        if summary:
            parts.append("\n" + "=" * 60)
            parts.append("【案情摘要】")
            parts.append(summary)

        # 提取增强分析数据（案件全景）
        enhanced = pre.get("enhanced_analysis_compatible", {})
        if enhanced and isinstance(enhanced, dict):
            trans_summary = enhanced.get("transaction_summary", "")
            if trans_summary:
                parts.append("\n【交易全景】")
                parts.append(trans_summary)

            dispute_focus = enhanced.get("dispute_focus", "")
            if dispute_focus:
                parts.append("\n【争议焦点】")
                parts.append(dispute_focus)

            # ====== 新增：主体画像 ======
            parties = enhanced.get("parties", [])
            if parties and isinstance(parties, list):
                parts.append("\n【主体画像】")
                for party in parties:
                    if isinstance(party, dict):
                        name = party.get("name", "未知")
                        role = party.get("role", "未知")
                        description = party.get("description", "")
                        parts.append(f"- {name} ({role})")
                        if description:
                            parts.append(f"  {description}")

            # ====== 新增：完整时间线 ======
            timeline = enhanced.get("timeline", [])
            if timeline and isinstance(timeline, list):
                parts.append("\n【案件时间线】")
                for event in timeline:
                    if isinstance(event, dict):
                        date = event.get("date", "")
                        description = event.get("description", "")
                        if date or description:
                            parts.append(f"- {date}: {description}")

    # ==================== 3. 文档详细摘要 ====================
    if pre and isinstance(pre, dict):
        doc_summaries = pre.get("document_summaries", {})
        if doc_summaries and isinstance(doc_summaries, dict) and len(doc_summaries) > 0:
            parts.append("\n" + "=" * 60)
            parts.append(f"【文档证据详情】(共 {len(doc_summaries)} 份)")

            for file_id, doc_info in doc_summaries.items():
                if not isinstance(doc_info, dict):
                    continue

                doc_title = doc_info.get("document_title", doc_info.get("file_name", file_id))
                doc_type = doc_info.get("document_subtype", doc_info.get("file_type", "未知"))
                summary = doc_info.get("summary", "")
                key_facts = doc_info.get("key_facts", [])
                key_dates = doc_info.get("key_dates", [])
                key_amounts = doc_info.get("key_amounts", [])
                raw_preview = doc_info.get("raw_preview", "")  # 新增：原文预览

                parts.append(f"\n--- {doc_title} ({doc_type}) ---")

                if summary:
                    parts.append(f"摘要: {summary}")

                if key_facts:
                    parts.append("关键事实:")
                    for fact in key_facts:  # 移除 [:10] 限制，全量提取
                        parts.append(f"  • {fact}")

                if key_dates:
                    parts.append("关键日期:")
                    for date in key_dates:  # 移除 [:10] 限制
                        parts.append(f"  • {date}")

                if key_amounts:
                    parts.append("关键金额:")
                    for amount in key_amounts:  # 移除 [:10] 限制
                        parts.append(f"  • {amount}")

                # ====== 新增：原文预览 ======
                if raw_preview:
                    parts.append(f"\n原文预览 (前3000字):")
                    parts.append(raw_preview)

    # ==================== 4. 证据分析发现 ====================
    evidence_analysis = state.get("evidence_analysis", {})
    if evidence_analysis and isinstance(evidence_analysis, dict):
        parts.append("\n" + "=" * 60)
        parts.append("【证据分析发现】")

        analysis_points = evidence_analysis.get("analysis_points", [])
        if analysis_points and isinstance(analysis_points, list):
            parts.append(f"发现 {len(analysis_points)} 个证据问题:")
            for point in analysis_points:  # 移除 [:15] 限制
                if isinstance(point, dict):
                    desc = point.get("description", point.get("issue", str(point)))
                    parts.append(f"  • {desc}")
                else:
                    parts.append(f"  • {point}")

        admissibility = evidence_analysis.get("admissibility_assessment", "")
        if admissibility:
            parts.append(f"\n证据可采性评估: {admissibility}")

        evidence_gaps = evidence_analysis.get("evidence_gaps", [])
        if evidence_gaps:
            parts.append("\n证据缺口:")
            for gap in evidence_gaps:  # 移除 [:10] 限制
                parts.append(f"  • {gap}")

    # ==================== 5. 原始文档内容补充（可选） ====================
    raw_docs = state.get("raw_documents", [])
    if raw_docs and isinstance(raw_docs, list):
        parts.append("\n" + "=" * 60)
        parts.append("【原始文档内容摘录】")

        for doc in raw_docs[:3]:  # 最多取前3个文档
            if hasattr(doc, 'content') and doc.content:
                content_preview = doc.content[:2000] if len(doc.content) > 2000 else doc.content
                file_name = getattr(doc, 'file_name', doc.file_id)
                parts.append(f"\n--- {file_name} (内容摘录) ---")
                parts.append(content_preview)
                parts.append("...(内容已截断)")

    # ==================== 6. 规则库匹配结果（供参考）====================
    rules = state.get("assembled_rules", [])
    if rules and isinstance(rules, list):
        parts.append("\n" + "=" * 60)
        parts.append(f"【适用法律规则】(共 {len(rules)} 条)")
        for i, rule in enumerate(rules, 1):  # 移除 [:10] 限制
            parts.append(f"{i}. {rule}")

    # 合并所有部分
    full_context = "\n".join(parts)

    # 记录日志以便调试
    logger.info(f"[{state.get('session_id')}] 构建分析 Context | 长度: {len(full_context)} 字符")

    return full_context


# ==================== 图构建与执行 ====================

def build_litigation_analysis_graph(skip_preorganization: bool = False, skip_drafts: bool = False):
    """
    构建 LangGraph (修复版)
    
    修复: 解决 Stage 2 模式下孤岛节点导致的 "Node not reachable" 错误。
    """
    builder = StateGraph(LitigationAnalysisState)

    # ==================== 1. 注册核心分析节点 (所有阶段都需要) ====================
    builder.add_node("assemble_case_rules", assemble_case_rules_node)
    builder.add_node("analyze_evidence", analyze_evidence_node)
    builder.add_node("multi_model_analyze", multi_model_analyze_node)
    builder.add_node("generate_strategies", generate_strategies_node)

    # 只在需要时注册文书生成节点
    if not skip_drafts:
        builder.add_node("generate_drafts", generate_drafts_node)

    builder.add_node("generate_report", generate_report_node)

    # ==================== 2. 根据阶段注册预处理节点 ====================
    if not skip_preorganization:
        # 仅在阶段 1 (全流程) 添加这些节点
        builder.add_node("process_documents", process_documents_node)
        builder.add_node("preorganize_case", preorganize_case_node)

        # 定义阶段 1 的入口和流转
        builder.set_entry_point("process_documents")
        builder.add_edge("process_documents", "preorganize_case")
        
        # 预整理 -> 规则组装 (带熔断)
        builder.add_conditional_edges(
            "preorganize_case", 
            check_error_status, 
            {"continue": "assemble_case_rules", "end": END}
        )
    else:
        # 阶段 2 (深度分析)：跳过预整理，直接从规则组装开始
        builder.set_entry_point("assemble_case_rules")

    # ==================== 3. 定义核心分析流转 ====================
    
    # 规则组装 -> 证据分析
    builder.add_edge("assemble_case_rules", "analyze_evidence")
    
    # 证据分析 -> 多模型推演 (带熔断)
    builder.add_conditional_edges(
        "analyze_evidence", 
        check_error_status,
        {"continue": "multi_model_analyze", "end": END}
    )
                                  
    # 多模型推演 -> 策略生成 (带熔断)
    builder.add_conditional_edges(
        "multi_model_analyze", 
        check_error_status,
        {"continue": "generate_strategies", "end": END}
    )

    # ==================== 4. 定义后续流转 (文书与报告) ====================

    if skip_drafts:
        # 跳过文书，直接生成报告
        builder.add_edge("generate_strategies", "generate_report")
    else:
        # 生成文书 -> 生成报告
        builder.add_edge("generate_strategies", "generate_drafts")
        builder.add_edge("generate_drafts", "generate_report")

    # 结束
    builder.add_edge("generate_report", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


async def run_litigation_analysis_workflow(
    session_id: str,
    user_input: Optional[str],
    document_paths: List[str],
    case_package_id: str,
    case_type: str,
    case_position: Optional[str], # Allow None for stage 1
    analysis_scenario: Optional[str] = "pre_litigation",
    preorganized_case: Optional[Dict[str, Any]] = None,
    analysis_mode: str = "multi",
    selected_model: Optional[str] = None,
    skip_preorganization: bool = False,
    skip_drafts: bool = False
) -> Dict[str, Any]:
    """
    工作流入口
    """
    logger.info(f"[{session_id}] 启动工作流")

    initial_state: LitigationAnalysisState = {
        "session_id": session_id,
        "user_input": user_input,
        "document_paths": document_paths,
        "case_package_id": case_package_id,
        "case_type": case_type,
        "case_position": case_position,
        "analysis_scenario": analysis_scenario,
        "analysis_mode": analysis_mode,
        "selected_model": selected_model,
        "preorganized_case": preorganized_case,
        
        "raw_documents": None,
        "assembled_rules": None,
        "timeline": None,
        "evidence_analysis": None,
        "model_results": None,
        "strategies": None,
        "draft_documents": None,
        "final_report": None,
        "report_json": None,
        "status": "started",
        "error": None
    }

    app = build_litigation_analysis_graph(skip_preorganization, skip_drafts)
    
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        result = await app.ainvoke(initial_state, config)
        return result
    except Exception as e:
        logger.error(f"[{session_id}] 工作流执行异常: {e}", exc_info=True)
        return {"error": str(e), "status": "crashed"}

# Stage 2 入口保持类似逻辑，只需设置 skip_preorganization=True
# ==================== Stage 2 入口函数 (补全) ====================

async def run_stage2_analysis(
    session_id: str,
    preorganized_case: Dict[str, Any],
    case_position: str,
    analysis_scenario: str,
    case_package_id: str,
    case_type: str,
    user_input: Optional[str] = None,
    analysis_mode: str = "multi",
    selected_model: Optional[str] = None
) -> Dict[str, Any]:
    """
    执行阶段2：全案分析

    这是用户确认预整理数据并选择角色和场景后调用的分析流程。
    特点：
    1. 跳过文档处理和预整理 (skip_preorganization=True)
    2. 直接利用传入的 preorganized_case
    3. 根据 case_position 和 analysis_scenario 进行深度推演
    """
    logger.info(
        f"[{session_id}] 启动阶段2分析 | "
        f"角色: {case_position} | 场景: {analysis_scenario}"
    )

    # 🛡️ 核心修复：防闪退等待
    # 无论任务跑得多快，先等前端把电话接通
    from app.api.websocket import manager

    logger.info(f"[{session_id}] 正在等待前端建立 WebSocket 连接...")
    websocket_connected = False

    for attempt in range(50):  # 最多等 5 秒
        if manager.is_connected(session_id):
            logger.info(f"[{session_id}] ✅ WebSocket 连接已确认 (尝试 {attempt + 1}/50)，开始执行任务！")
            websocket_connected = True
            break
        await asyncio.sleep(0.1)

    if not websocket_connected:
        logger.warning(f"[{session_id}] ⚠️ WebSocket 连接超时（5秒），任务将继续执行但可能无法接收实时进度")

    return await run_litigation_analysis_workflow(
        session_id=session_id,
        user_input=user_input,
        document_paths=[],  # 阶段2不需要重新读取原始文档路径
        case_package_id=case_package_id,
        case_type=case_type,
        case_position=case_position,
        analysis_scenario=analysis_scenario,
        preorganized_case=preorganized_case,
        analysis_mode=analysis_mode,
        selected_model=selected_model,
        skip_preorganization=True,  # 关键：跳过预整理节点，直接进入规则组装
        skip_drafts=True  # 关键：跳过自动文书生成，由用户手动触发
    )