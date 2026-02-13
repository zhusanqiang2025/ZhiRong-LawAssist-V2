# backend/app/api/v1/endpoints/litigation_analysis.py
"""
案件分析模块 API 端点 (重构版)

适配了新的 Schema 定义和 Workflow 逻辑。
"""

import uuid
import logging
import json
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Form, 
    BackgroundTasks, WebSocket, WebSocketDisconnect, Query
)
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from app.api import deps
from app.models.user import User
from app.models.litigation_analysis import (
    LitigationAnalysisSession,
    LitigationCasePackage,
)
from app.schemas.litigation_analysis import (
    # 核心请求响应
    LitigationAnalysisRequest,
    LitigationAnalysisSessionResponse,
    LitigationPreorganizationResult,
    LitigationAnalysisSessionsListResponse,
    LitigationCasePackagesListResponse,
    LitigationCasePackageResponse,
    
    # 枚举
    AnalysisStatusEnum,
    CaseTypeEnum,
    CasePositionEnum,
    AnalysisScenarioEnum,
    
    # 业务实体 (用于 Type Hint)
    LitigationDocumentAnalysis,
    DocumentRelationship,
    QualityAssessment,
    CrossDocumentInfo
)
from app.core.config import settings

# 引入新版服务
from app.services.litigation_analysis.workflow import (
    run_litigation_analysis_workflow,
    run_stage2_analysis
)
from app.services.litigation_analysis.case_rule_assembler import CaseRuleAssembler
from app.services.litigation_analysis.enhanced_case_preorganization import (
    get_enhanced_case_preorganization_service
)
from app.services.common.unified_document_service import UnifiedDocumentService, StructuredDocumentResult

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== 1. 案件类型包管理 (CRUD) ====================

@router.get("/packages", response_model=LitigationCasePackagesListResponse)
async def list_case_packages(
    case_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    db: Session = Depends(deps.get_db)
):
    query = db.query(LitigationCasePackage)
    if is_active is not None:
        query = query.filter(LitigationCasePackage.is_active == is_active)
    if case_type:
        query = query.filter(LitigationCasePackage.case_type == case_type)
    if category:
        query = query.filter(LitigationCasePackage.package_category == category)

    packages = query.order_by(LitigationCasePackage.created_at.desc()).all()
    # Pydantic v2: from_attributes=True
    return {"packages": [LitigationCasePackageResponse.model_validate(pkg) for pkg in packages]}


@router.get("/packages/{package_id}", response_model=LitigationCasePackageResponse)
async def get_case_package(package_id: str, db: Session = Depends(deps.get_db)):
    package = db.query(LitigationCasePackage).filter(
        LitigationCasePackage.package_id == package_id
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail=f"规则包不存在: {package_id}")
    return LitigationCasePackageResponse.model_validate(package)


# ==================== 2. 文档上传 ====================

@router.post("/upload")
async def upload_case_documents(
    session_id: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
):
    session = db.query(LitigationAnalysisSession).filter(
        LitigationAnalysisSession.session_id == session_id,
        LitigationAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    import os
    from pathlib import Path

    uploaded_file_ids = []
    upload_dir = Path(settings.UPLOAD_DIR) / "litigation_analysis" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        file_id = str(uuid.uuid4())
        file_path = upload_dir / f"{file_id}_{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        uploaded_file_ids.append(str(file_path))

    # 更新数据库
    if not session.document_ids:
        session.document_ids = []
    # SQL Alchemy array append
    session.document_ids = session.document_ids + uploaded_file_ids
    db.commit()

    return {
        "session_id": session_id,
        "uploaded_count": len(uploaded_file_ids),
        "file_ids": uploaded_file_ids
    }


# ==================== 3. 阶段1：预整理 (Preorganize) ====================

@router.post("/preorganize")
async def preorganize_litigation_documents(
    files: List[UploadFile] = File(...),
    case_type: str = Form(default="合同纠纷"),
    user_context: Optional[str] = Form(None),
):
    """
    预整理入口 (Stage 1)

    上传文件 -> 统一文档处理 -> 增强预整理 (中立视角)
    """
    import tempfile
    import os

    temp_dir = tempfile.mkdtemp(prefix="lit_pre_")
    file_paths = []

    try:
        # 1. 保存临时文件
        for file in files:
            path = os.path.join(temp_dir, file.filename)
            with open(path, "wb") as f:
                f.write(await file.read())
            file_paths.append(path)

        logger.info(f"[预整理] 开始处理 {len(files)} 个文件，类型: {case_type}")

        # 2. 调用 UnifiedDocumentService
        doc_service = UnifiedDocumentService()
        processed_docs = await doc_service.batch_process_async(file_paths)
        successful_docs = [d for d in processed_docs if d.status == 'success']

        if not successful_docs:
            raise HTTPException(status_code=400, detail="文档解析全部失败")

        logger.info(f"[预整理] 文档解析成功: {len(successful_docs)}/{len(files)}")

        # 3. 调用 EnhancedPreorganizationService
        # 注意：不指定 case_position，默认为中立视角
        from app.core.llm_config import get_qwen3_llm as get_qwen3_llm
        llm = get_qwen3_llm()

        # 验证 LLM 初始化
        if llm is None:
            error_detail = "LLM 服务未初始化，请检查 API Key 配置"
            logger.error(f"[预整理] {error_detail}")
            raise HTTPException(status_code=500, detail=error_detail)

        logger.info(f"[预整理] LLM 服务初始化成功")

        service = get_enhanced_case_preorganization_service(llm)

        result = await service.preorganize_enhanced(
            documents=successful_docs,
            case_type=case_type,
            user_context=user_context
        )

        logger.info(f"[预整理] 预整理完成，生成案件全景")

        # 4. 构造返回 (适配 LitigationPreorganizationResult Schema)
        # 注意：Service 返回的是 Dict，FastAPI 会自动验证
        # 我们需要确保 Service 返回的 Dict 结构符合 Schema
        
        # 为了前端兼容性，我们手动构造一下最外层结构
        # Service 返回的 result 已经包含了 document_summaries 等前端需要的字段
        
        return {
            "session_id": f"pre_{uuid.uuid4()}",
            "processed_at": datetime.now(),
            "summary": result.get("summary", ""),
            # 透传 Service 的结果，包含 enhanced_analysis_compatible
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[预整理] 预整理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"预整理失败: {str(e)}")
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# ==================== 4. 阶段2：全案分析 (Analyze) ====================

@router.post("/analyze")
async def analyze_litigation_case_stage2(
    preorganized_data: str = Form(...), # 前端传 JSON 字符串
    case_position: str = Form(...),
    analysis_scenario: str = Form(...),
    case_package_id: str = Form(...),
    case_type: str = Form(default="合同纠纷"),
    user_input: Optional[str] = Form(None),
    analysis_mode: str = Form(default="multi"),
    selected_model: Optional[str] = Form(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    阶段2入口：确认预整理结果后启动深度分析
    """
    # 0. 生成 session_id（提前生成以便日志使用）
    session_id = str(uuid.uuid4())

    # 1. 解析 JSON 数据
    try:
        pre_data_dict = json.loads(preorganized_data)
        logger.info(f"[{session_id}] 解析 preorganized_data 成功，类型: {type(pre_data_dict)}")
        if isinstance(pre_data_dict, dict):
            logger.info(f"[{session_id}] preorganized_data 包含键: {list(pre_data_dict.keys())[:5]}")
        else:
            logger.error(f"[{session_id}] preorganized_data 解析后不是字典: {str(pre_data_dict)[:100]}")
    except json.JSONDecodeError as e:
        logger.error(f"[{session_id}] JSON 解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"preorganized_data JSON 格式错误: {e}")

    # 2. 创建会话
    session = LitigationAnalysisSession(
        session_id=session_id,
        user_id=current_user.id,
        status=AnalysisStatusEnum.PENDING.value,
        case_type=case_type,
        case_position=case_position,
        user_input=user_input,
        package_id=case_package_id,
        document_ids=[] # 阶段2暂不关联原始文件ID，或者从 pre_data 中提取
    )
    db.add(session)
    db.commit()

    # 3. 异步启动 Workflow (Stage 2)
    # 封装为后台任务
    async def run_task():
        db_local = None
        try:
            # 执行分析工作流并获取结果
            result = await run_stage2_analysis(
                session_id=session_id,
                preorganized_case=pre_data_dict,
                case_position=case_position,
                analysis_scenario=analysis_scenario,
                case_package_id=case_package_id,
                case_type=case_type,
                user_input=user_input,
                analysis_mode=analysis_mode,
                selected_model=selected_model
            )

            # === 保存结果到数据库 ===
            from app.database import get_db
            db_gen = get_db()
            db_local = next(db_gen)

            session = db_local.query(LitigationAnalysisSession).filter(
                LitigationAnalysisSession.session_id == session_id
            ).first()

            if session and not result.get("error"):
                # 提取工作流结果并保存
                session.status = "completed"
                session.completed_at = datetime.utcnow()

                # 保存分析结果
                if "final_report" in result:
                    session.report_json = result.get("report_json")
                    session.case_summary = result.get("final_report")

                if "model_results" in result:
                    session.model_results = result["model_results"]
                    # 提取胜诉概率
                    if isinstance(result["model_results"], dict):
                        session.win_probability = result["model_results"].get("final_strength", 0.0)

                if "strategies" in result:
                    session.strategies = result["strategies"]

                if "timeline" in result:
                    if isinstance(result["timeline"], dict):
                        session.timeline_events = result["timeline"].get("events", [])
                    else:
                        session.timeline_events = result["timeline"]

                if "evidence_analysis" in result:
                    session.evidence_assessment = result["evidence_analysis"]

                if "legal_issues" in result:
                    session.legal_issues = result["legal_issues"]

                if "risk_warnings" in result:
                    session.risk_warnings = result["risk_warnings"]

                db_local.commit()
                logger.info(f"[{session_id}] ✅ 分析结果已保存到数据库")

                # 发送 WebSocket 完成消息
                from app.api.websocket import manager
                if manager.is_connected(session_id):
                    await manager.send_progress(session_id, {
                        "type": "complete",
                        "status": "completed",
                        "message": "分析完成",
                        "progress": 1.0
                    })
                    logger.info(f"[{session_id}] ✅ 已发送完成消息到 WebSocket")
                else:
                    logger.warning(f"[{session_id}] ⚠️ WebSocket 未连接，无法发送完成消息")

            elif result.get("error"):
                if session:
                    session.status = "failed"
                    db_local.commit()
                logger.error(f"[{session_id}] ❌ 分析失败: {result['error']}")

        except Exception as e:
            logger.error(f"[{session_id}] ❌ 异步任务失败: {e}", exc_info=True)
            # 尝试更新数据库状态为失败
            try:
                if not db_local:
                    from app.database import get_db
                    db_gen = get_db()
                    db_local = next(db_gen)

                if db_local:
                    session = db_local.query(LitigationAnalysisSession).filter(
                        LitigationAnalysisSession.session_id == session_id
                    ).first()
                    if session:
                        session.status = "failed"
                        db_local.commit()
            except Exception as db_error:
                logger.error(f"[{session_id}] ❌ 更新失败状态时出错: {db_error}")
        finally:
            if db_local:
                db_local.close()

    import asyncio
    asyncio.create_task(run_task())

    return {
        "session_id": session_id,
        "status": "pending",
        "message": "分析任务已启动"
    }


# ==================== 5. WebSocket (实时进度) ====================

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    from app.api.websocket import manager

    # 1. 建立连接
    # 注意：确保参数顺序正确 (websocket, session_id)
    await manager.connect(websocket, session_id)
    logger.info(f"WebSocket connected: {session_id}")

    # 2. 定义发送协程 (Producer)
    async def send_messages():
        try:
            while True:
                # 阻塞等待队列消息，无消息时挂起，不消耗 CPU
                # manager.get_message 内部使用了 asyncio.Queue.get()
                message = await manager.get_message(session_id)
                if message:
                    await websocket.send_json(message)
                    logger.debug(f"Sent to {session_id}: {message.get('type')}")
        except Exception as e:
            logger.error(f"Send loop error: {e}")

    # 3. 定义接收协程 (Consumer)
    async def receive_messages():
        try:
            while True:
                # 阻塞等待前端消息
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except:
                    pass
        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {session_id}")
            # 客户端断开，抛出异常以取消发送协程
            raise

    # 4. 并发运行
    try:
        # 只要接收协程断开（客户端关闭），整体退出
        # 发送协程作为守护任务运行
        sender_task = asyncio.create_task(send_messages())
        receiver_task = asyncio.create_task(receive_messages())

        # 等待接收协程结束（即客户端断开）
        await receiver_task

    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        # 清理
        sender_task.cancel()
        await manager.disconnect(session_id)
        logger.info(f"WebSocket cleaned up: {session_id}")


# ==================== 6. 结果查询 ====================

@router.get("/result/{session_id}")
async def get_case_result(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """获取案件分析结果"""
    session = db.query(LitigationAnalysisSession).filter(
        LitigationAnalysisSession.session_id == session_id,
        LitigationAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 构造完整的响应，包含所有分析结果
    result = {
        "session_id": session.session_id,
        "status": session.status,
        "case_type": session.case_type,
        "case_position": session.case_position,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "created_at": session.created_at.isoformat() if session.created_at else None,

        # 基本信息
        "user_input": session.user_input,
        "package_id": session.package_id,

        # 分析结果摘要
        "case_summary": session.case_summary,
        "case_overview": session.case_overview,
        "win_probability": session.win_probability,

        # 详细分析结果（JSON 字段）
        "case_strength": session.case_strength,
        "evidence_assessment": session.evidence_assessment,
        "legal_issues": session.legal_issues,
        "strategies": session.strategies,
        "risk_warnings": session.risk_warnings,
        "recommendations": session.recommendations,

        # 可视化数据
        "timeline_events": session.timeline_events,
        "evidence_chain": session.evidence_chain,
        "case_diagrams": session.case_diagrams,

        # 多模型分析结果
        "model_results": session.model_results,
        "selected_model": session.selected_model,

        # 报告
        "report_md": session.report_md,
        "report_json": session.report_json,

        # 文档关联
        "document_ids": session.document_ids,
    }

    return result


# ==================== 7. 报告下载 ====================

@router.get("/preorganization-report/{session_id}")
async def download_preorganization_report(
    session_id: str,
    format: str = Query('docx', description='报告格式：docx 或 pdf'),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    下载案件预整理报告

    生成并下载包含以下内容的报告：
    - 案件全景（交易摘要、合同状态）
    - 主体画像（各方权利义务）
    - 时间线
    - 文档详细分析
    """
    # 1. 验证会话权限
    session = db.query(LitigationAnalysisSession).filter(
        LitigationAnalysisSession.session_id == session_id,
        LitigationAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 2. 获取预整理数据（从 case_overview 字段）
    try:
        if session.case_overview:
            if isinstance(session.case_overview, str):
                preorganization_data = json.loads(session.case_overview)
            else:
                preorganization_data = session.case_overview
        else:
            raise HTTPException(
                status_code=400,
                detail="预整理数据不存在，请先完成文档预整理"
            )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="预整理数据格式错误")

    # 3. 生成报告
    from app.services.litigation_analysis.litigation_preorganization_report_generator import (
        get_litigation_preorganization_report_generator
    )
    generator = get_litigation_preorganization_report_generator()

    # 添加案件类型信息
    preorganization_data['case_type'] = session.case_type

    report_path = generator.generate(session_id, preorganization_data, format)

    # 4. 返回文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"案件预整理报告_{session.case_type}_{timestamp}.{format}"

    media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' \
                 if format == 'docx' else 'application/pdf'

    from fastapi.responses import FileResponse
    return FileResponse(
        report_path,
        filename=filename,
        media_type=media_type
    )


@router.get("/report/{session_id}/download")
async def download_analysis_report(
    session_id: str,
    format: str = Query('docx', description='报告格式：docx 或 pdf'),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    下载案件分析报告

    生成并下载包含以下内容的报告：
    - 核心结论（胜诉率）
    - 案件摘要
    - 证据评估
    - 争议焦点
    - 诉讼策略
    - 风险提示
    - 详细分析报告
    """
    # 1. 验证会话
    session = db.query(LitigationAnalysisSession).filter(
        LitigationAnalysisSession.session_id == session_id,
        LitigationAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status != 'completed':
        raise HTTPException(status_code=400, detail="分析尚未完成")

    # 2. 准备报告数据
    report_data = {
        "session_id": session.session_id,
        "case_type": session.case_type,
        "case_position": session.case_position,
        "win_probability": session.win_probability,
        "case_summary": session.case_summary,
        "evidence_assessment": session.evidence_assessment,
        "legal_issues": session.legal_issues,
        "strategies": session.strategies,
        "risk_warnings": session.risk_warnings,
        "recommendations": session.recommendations,
        "timeline_events": session.timeline_events,
        "final_report": session.report_md or session.case_summary,
        "model_results": session.model_results
    }

    # 3. 生成报告
    from app.services.litigation_analysis.litigation_analysis_report_generator import (
        get_litigation_analysis_report_generator
    )
    generator = get_litigation_analysis_report_generator()

    report_path = generator.generate(session_id, report_data, format)

    # 4. 返回文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"案件分析报告_{session.case_type}_{timestamp}.{format}"

    media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' \
                 if format == 'docx' else 'application/pdf'

    from fastapi.responses import FileResponse
    return FileResponse(
        report_path,
        filename=filename,
        media_type=media_type
    )


@router.get("/sessions")
async def list_litigation_sessions(
    status: Optional[str] = Query(None, description="状态过滤: pending, processing, completed, failed"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    获取当前用户的案件分析会话列表

    参考风险评估模块的实现，支持状态过滤和分页
    """
    # 基础查询：过滤当前用户
    base_query = db.query(LitigationAnalysisSession).filter(
        LitigationAnalysisSession.user_id == current_user.id
    )

    # 状态过滤
    query = base_query
    if status:
        query = query.filter(LitigationAnalysisSession.status == status)

    # 按创建时间倒序
    query = query.order_by(LitigationAnalysisSession.created_at.desc())

    # 分页
    total = query.count()
    sessions = query.limit(limit).offset(offset).all()

    # 统计计数
    completed_count = base_query.filter(LitigationAnalysisSession.status == "completed").count()
    incomplete_count = total - completed_count

    # 构造返回数据（与风险评估模块保持一致的格式）
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "title": s.user_input or s.case_summary or f"{s.case_type}案件分析",
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "case_type": s.case_type,
                "case_position": s.case_position,
                "is_completed": s.status == "completed"
            }
            for s in sessions
        ],
        "total": total,
        "incomplete_count": incomplete_count,
        "completed_count": completed_count
    }


@router.delete("/sessions/{session_id}")
async def delete_litigation_session(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    删除案件分析会话

    参考风险评估模块的删除接口实现
    """
    session = db.query(LitigationAnalysisSession).filter(
        LitigationAnalysisSession.session_id == session_id,
        LitigationAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    db.delete(session)
    db.commit()

    return {"message": "会话已删除"}
