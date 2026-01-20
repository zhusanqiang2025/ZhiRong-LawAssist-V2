# backend/app/api/v1/endpoints/risk_analysis.py
"""
风险评估 API 路由

提供以下接口：
- POST /submit: 提交风险分析请求
- POST /upload: 上传文档
- POST /start/{session_id}: 开始分析
- GET /status/{session_id}: 获取分析状态
- GET /result/{session_id}: 获取完整结果
- WebSocket /ws/{session_id}: 实时进度推送
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, WebSocket, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
import os
import shutil
import logging

from app.api import deps
from app.models.user import User
from app.models.risk_analysis import RiskAnalysisSession
from app.schemas import (  # 修改：从 app.schemas 直接导入
    RiskAnalysisSubmitRequest,
    RiskAnalysisSessionResponse,
    RiskAnalysisDetailResponse,
    RiskAnalysisStatusResponse,
    RiskAnalysisUploadResponse,
    RiskAnalysisStartResponse
)
from app.services.risk_analysis_service import get_risk_analysis_service
from app.services.unified_document_service import get_unified_document_service
from app.api.websocket import manager
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/submit", response_model=dict)
async def submit_risk_analysis(
    request: RiskAnalysisSubmitRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    提交风险分析请求

    创建一个新的风险分析会话
    """
    try:
        service = get_risk_analysis_service(db)

        # 创建会话
        session = service.create_session(
            user_id=current_user.id,
            scene_type=request.scene_type,
            user_description=request.user_description,
            document_ids=request.document_ids
        )

        return {
            "session_id": session.session_id,
            "status": session.status,
            "message": "会话已创建，请上传文档后开始分析"
        }

    except Exception as e:
        logger.error(f"提交风险分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post("/upload", response_model=RiskAnalysisUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    上传分析文档并使用统一文档处理服务

    支持的格式：PDF, DOC, DOCX, TXT
    处理流程：
    1. 验证会话
    2. 保存文件到磁盘
    3. 通过 UnifiedDocumentService 处理文档
    4. 保存处理结果到会话元数据
    """
    logger.info(f"[UPLOAD] 收到上传请求 - 文件: {file.filename}, session_id: {session_id}")

    # 验证会话
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        logger.error(f"[UPLOAD] 会话不存在 - session_id: {session_id}")
        raise HTTPException(status_code=404, detail="会话不存在")

    logger.info(f"[UPLOAD] 会话验证通过 - status: {session.status}")

    # 验证文件类型
    allowed_extensions = {'.pdf', '.doc', '.docx', '.txt'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        logger.error(f"[UPLOAD] 不支持的文件格式 - {file_ext}")
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(allowed_extensions)}"
        )

    try:
        # 创建上传目录
        upload_dir = os.path.join(settings.UPLOAD_DIR, "risk_analysis", session_id)
        os.makedirs(upload_dir, exist_ok=True)
        logger.info(f"[UPLOAD] 上传目录: {upload_dir}")

        # 生成唯一文件名
        from datetime import datetime
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)

        # 保存文件
        logger.info(f"[UPLOAD] 正在保存文件到: {file_path}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = os.path.getsize(file_path)
        logger.info(f"[UPLOAD] 文件保存成功 - 大小: {file_size} bytes")

        # 调用统一文档处理服务
        logger.info(f"[UPLOAD] 开始调用统一文档处理服务")
        doc_service = get_unified_document_service()
        process_result = doc_service.process_document(
            file_path=file_path,
            extract_content=True,
            extract_metadata=True,
            use_cache=True
        )

        logger.info(f"[UPLOAD] 文档处理完成 - status: {process_result.status}, method: {process_result.processing_method}, from_cache: {process_result.from_cache}")

        # 更新会话 - 保存文件路径和处理结果
        if not session.document_ids:
            session.document_ids = []
        session.document_ids.append(file_path)

        # 保存处理结果到会话元数据
        if session.document_processing_results is None:
            session.document_processing_results = {}
        session.document_processing_results[safe_filename] = {
            "file_path": file_path,
            "processing_status": process_result.status.value,
            "content_length": len(process_result.content),
            "metadata": process_result.metadata,
            "processing_method": process_result.processing_method,
            "from_cache": process_result.from_cache,
            "warnings": process_result.warnings
        }

        db.commit()

        logger.info(f"[UPLOAD] 文件上传成功: {safe_filename}, 会话: {session_id}")

        return RiskAnalysisUploadResponse(
            file_id=safe_filename,
            file_path=file_path,
            message="文件上传成功"
        )

    except Exception as e:
        logger.error(f"[UPLOAD] 文件上传异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/start/{session_id}", response_model=RiskAnalysisStartResponse)
async def start_analysis(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    开始风险分析

    在后台执行分析任务，进度通过 WebSocket 推送
    """
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if not session.document_ids:
        raise HTTPException(status_code=400, detail="请先上传文档")

    if session.status != "pending":
        raise HTTPException(status_code=400, detail=f"会话状态不正确: {session.status}")

    # 后台执行分析
    async def run_analysis():
        # 创建新的数据库会话用于后台任务
        from app.database import SessionLocal
        db_bg = SessionLocal()
        try:
            service = get_risk_analysis_service(db_bg)

            async def progress_callback(data):
                # 通过 WebSocket 推送进度
                if session.websocket_id:
                    await manager.send_progress(session.websocket_id, data)

            await service.analyze_documents(
                session_id=session_id,
                document_paths=session.document_ids,
                scene_type=session.scene_type,
                user_description=session.user_description,
                enable_custom_rules=False,
                user_id=current_user.id,
                progress_callback=progress_callback
            )

        except Exception as e:
            logger.error(f"后台分析任务失败: {str(e)}")
            # 更新状态为失败
            session.status = "failed"
            db_bg.commit()

            # 尝试通知前端
            if session.websocket_id:
                await manager.send_progress(session.websocket_id, {
                    "session_id": session_id,
                    "status": "failed",
                    "progress": 0,
                    "message": f"分析失败: {str(e)}"
                })

        finally:
            db_bg.close()

    background_tasks.add_task(run_analysis)

    return RiskAnalysisStartResponse(
        message="分析已开始",
        session_id=session_id
    )


@router.get("/status/{session_id}", response_model=RiskAnalysisStatusResponse)
async def get_status(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取分析状态

    返回当前分析状态和摘要信息
    """
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return RiskAnalysisStatusResponse(
        session_id=session.session_id,
        status=session.status,
        summary=session.summary,
        risk_distribution=session.risk_distribution
    )


@router.get("/result/{session_id}", response_model=RiskAnalysisDetailResponse)
async def get_result(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取完整分析结果

    包含所有风险项和报告
    """
    service = get_risk_analysis_service(db)
    session = service.get_session_with_items(session_id, current_user.id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status != "completed":
        raise HTTPException(status_code=400, detail="分析尚未完成")

    return RiskAnalysisDetailResponse(
        id=session.id,
        session_id=session.session_id,
        status=session.status,
        scene_type=session.scene_type,
        user_description=session.user_description,
        summary=session.summary,
        risk_distribution=session.risk_distribution,
        total_confidence=session.total_confidence,
        report_md=session.report_md,
        created_at=session.created_at,
        completed_at=session.completed_at,
        risk_items=session.risk_items
    )


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    session_id: str,
    websocket: WebSocket,
    db: Session = Depends(deps.get_db)
):
    """
    WebSocket 进度推送端点

    前端连接此端点接收实时进度更新
    """
    try:
        # 验证会话
        session = db.query(RiskAnalysisSession).filter(
            RiskAnalysisSession.session_id == session_id
        ).first()

        if not session:
            await websocket.close(code=1008, reason="会话不存在")
            return

        # 生成 WebSocket 连接 ID
        websocket_id = f"ws_{session_id}_{id(websocket)}"
        session.websocket_id = websocket_id
        db.commit()

        # 接受连接
        await manager.connect(websocket_id, websocket)

        # 保持连接并接收心跳
        while True:
            try:
                # 等待客户端消息（可用于心跳）
                await websocket.receive_text()
            except Exception:
                break

    except Exception as e:
        logger.error(f"WebSocket 连接错误: {str(e)}")
    finally:
        manager.disconnect(websocket_id)
