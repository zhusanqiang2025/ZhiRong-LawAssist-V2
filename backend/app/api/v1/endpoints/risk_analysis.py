# backend/app/api/v1/endpoints/risk_analysis_v2.py
"""
风险评估 API v2 路由（基于新架构）

新架构特性：
- 规则包选择
- 文档预整理（专业助理节点）
- 多模型并行分析
- 图表生成
"""

import logging
import os
import shutil
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, WebSocket, Body, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.models.risk_analysis import RiskAnalysisSession, RiskAnalysisStatus, RiskRulePackage
from app.models.risk_analysis_preorganization import RiskAnalysisPreorganization
from app.schemas.risk_analysis_preorganization import (
    DocumentPreorganizationRequest,
    DocumentPreorganizationResponse,
    PreorganizedDocuments
)
from app.schemas.risk_analysis_diagram import (
    DiagramRequest,
    DiagramResult,
    DiagramLLMGenerateRequest
)
from app.core.config import settings
from app.services.unified_document_service import get_unified_document_service
from app.services.risk_analysis import (
    get_document_preorganization_service,
    get_diagram_generator_service,
    get_risk_rule_assembler
)
from app.services.risk_analysis.workflow import run_risk_analysis_workflow
from app.services.preorganization_report_generator import get_preorganization_report_generator
from app.services.risk_analysis_report_generator import get_risk_analysis_report_generator
from langchain_openai import ChatOpenAI

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== Pydantic Schemas ====================

class RiskRulePackageCreate(BaseModel):
    """创建规则包请求"""
    package_name: str
    package_category: str
    description: Optional[str] = None
    applicable_scenarios: Optional[List[str]] = None
    target_entities: Optional[List[str]] = None
    rules: List[dict]
    is_active: Optional[bool] = True


class RiskRulePackageUpdate(BaseModel):
    """更新规则包请求"""
    package_name: Optional[str] = None
    package_category: Optional[str] = None
    description: Optional[str] = None
    applicable_scenarios: Optional[List[str]] = None
    target_entities: Optional[List[str]] = None
    rules: Optional[List[dict]] = None
    is_active: Optional[bool] = None


class PreorganizationResultRequest(BaseModel):
    """保存预整理结果请求"""
    user_requirement_summary: Optional[str] = None
    documents_info: Optional[list] = None
    fact_summary: Optional[dict] = None
    contract_legal_features: Optional[dict] = None
    contract_relationships: Optional[list] = None
    architecture_diagram: Optional[dict] = None


class ConfirmPreorganizationRequest(BaseModel):
    """确认预整理结果请求"""
    user_modifications: Optional[dict] = None


class SelectAnalysisModeRequest(BaseModel):
    """选择分析模式请求"""
    analysis_mode: str  # "single" 或 "multi"
    selected_model: Optional[str] = None  # 单模型时选择的模型名称
    evaluation_stance: Optional[str] = None  # ✅ 新增：风险评估立场


# ==================== 规则包管理 ====================

@router.get("/packages")
async def list_rule_packages(
    category: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    列出可用的规则包

    参数：
    - category: 可选的分类过滤器
    """
    assembler = get_risk_rule_assembler(db)
    packages = assembler.list_packages(category=category)

    return {
        "packages": [
            {
                "id": p.id,
                "package_id": p.package_id,
                "package_name": p.package_name,
                "package_category": p.package_category,
                "description": p.description,
                "version": p.version,
                "is_system": p.is_system,
                "is_active": p.is_active,
                "applicable_scenarios": p.applicable_scenarios,
                "target_entities": p.target_entities,
                "rules": p.rules if p.rules else [],
                "creator_id": p.creator_id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None
            }
            for p in packages
        ]
    }


@router.get("/packages/{package_id}")
async def get_rule_package_detail(
    package_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """获取规则包详情"""
    assembler = get_risk_rule_assembler(db)
    package = assembler.get_package(package_id)

    if not package:
        raise HTTPException(status_code=404, detail="规则包不存在")

    return {
        "id": package.id,
        "package_id": package.package_id,
        "package_name": package.package_name,
        "package_category": package.package_category,
        "description": package.description,
        "version": package.version,
        "is_system": package.is_system,
        "is_active": package.is_active,
        "applicable_scenarios": package.applicable_scenarios,
        "target_entities": package.target_entities,
        "rules": package.rules if package.rules else [],
        "creator_id": package.creator_id,
        "created_at": package.created_at.isoformat() if package.created_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None
    }


@router.post("/packages")
async def create_rule_package(
    request: RiskRulePackageCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    创建规则包（仅管理员）

    权限：仅超级管理员可创建系统预定义规则包
    """
    # 检查权限
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")

    # 检查 package_id 是否已存在
    existing = db.query(RiskRulePackage).filter(
        RiskRulePackage.package_id == request.package_name.lower().replace(' ', '_')
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="规则包ID已存在")

    # 创建规则包
    package = RiskRulePackage(
        package_id=request.package_name.lower().replace(' ', '_'),
        package_name=request.package_name,
        package_category=request.package_category,
        description=request.description,
        applicable_scenarios=request.applicable_scenarios,
        target_entities=request.target_entities,
        rules=request.rules,
        is_active=request.is_active,
        is_system=False,  # 用户创建的不是系统预定义
        creator_id=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(package)
    db.commit()
    db.refresh(package)

    logger.info(f"用户 {current_user.id} 创建规则包: {package.package_id}")

    return {
        "id": package.id,
        "package_id": package.package_id,
        "package_name": package.package_name,
        "package_category": package.package_category,
        "description": package.description,
        "version": package.version,
        "is_system": package.is_system,
        "is_active": package.is_active,
        "applicable_scenarios": package.applicable_scenarios,
        "target_entities": package.target_entities,
        "rules": package.rules if package.rules else [],
        "creator_id": package.creator_id,
        "created_at": package.created_at.isoformat() if package.created_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None
    }


@router.put("/packages/{package_id}")
async def update_rule_package(
    package_id: str,
    request: RiskRulePackageUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    更新规则包（仅管理员）

    权限：管理员可以修改所有规则包，包括系统预定义规则包
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")

    package = db.query(RiskRulePackage).filter(
        RiskRulePackage.package_id == package_id
    ).first()

    if not package:
        raise HTTPException(status_code=404, detail="规则包不存在")

    # 系统预定义规则包也可以被管理员修改
    # 更新字段
    if request.package_name is not None:
        package.package_name = request.package_name
    if request.package_category is not None:
        package.package_category = request.package_category
    if request.description is not None:
        package.description = request.description
    if request.applicable_scenarios is not None:
        package.applicable_scenarios = request.applicable_scenarios
    if request.target_entities is not None:
        package.target_entities = request.target_entities
    if request.rules is not None:
        package.rules = request.rules
    if request.is_active is not None:
        package.is_active = request.is_active

    package.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(package)

    logger.info(f"用户 {current_user.id} 更新规则包: {package.package_id}")

    return {
        "id": package.id,
        "package_id": package.package_id,
        "package_name": package.package_name,
        "package_category": package.package_category,
        "description": package.description,
        "version": package.version,
        "is_system": package.is_system,
        "is_active": package.is_active,
        "applicable_scenarios": package.applicable_scenarios,
        "target_entities": package.target_entities,
        "rules": package.rules if package.rules else [],
        "creator_id": package.creator_id,
        "created_at": package.created_at.isoformat() if package.created_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None
    }


@router.delete("/packages/{package_id}")
async def delete_rule_package(
    package_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    删除规则包（仅管理员）

    权限：管理员可以删除所有规则包，包括系统预定义规则包
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")

    package = db.query(RiskRulePackage).filter(
        RiskRulePackage.package_id == package_id
    ).first()

    if not package:
        raise HTTPException(status_code=404, detail="规则包不存在")

    # 系统预定义规则包也可以被管理员删除
    db.delete(package)
    db.commit()

    logger.info(f"用户 {current_user.id} 删除规则包: {package_id}")

    return {"message": "删除成功"}


@router.patch("/packages/{package_id}/status")
async def toggle_package_status(
    package_id: str,
    is_active: bool = Body(..., embed=True),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    切换规则包启用状态（仅管理员）

    权限：管理员可以切换所有规则包的状态
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")

    package = db.query(RiskRulePackage).filter(
        RiskRulePackage.package_id == package_id
    ).first()

    if not package:
        raise HTTPException(status_code=404, detail="规则包不存在")

    package.is_active = is_active
    package.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(package)

    logger.info(f"用户 {current_user.id} 切换规则包状态: {package_id} -> {is_active}")

    return {
        "id": package.id,
        "package_id": package.package_id,
        "package_name": package.package_name,
        "package_category": package.package_category,
        "description": package.description,
        "version": package.version,
        "is_system": package.is_system,
        "is_active": package.is_active,
        "applicable_scenarios": package.applicable_scenarios,
        "target_entities": package.target_entities,
        "rules": package.rules if package.rules else [],
        "creator_id": package.creator_id,
        "created_at": package.created_at.isoformat() if package.created_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None
    }


# ==================== 文档上传与会话创建 ====================

@router.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    上传文档

    支持批量上传，返回文档路径列表
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    # 生成临时上传 ID
    upload_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, "risk_analysis", "temp", upload_id)
    os.makedirs(upload_dir, exist_ok=True)

    uploaded_files = []

    try:
        for file in files:
            # 验证文件类型
            allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg'}
            file_ext = os.path.splitext(file.filename)[1].lower()

            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的文件格式: {file_ext}"
                )

            # 保存文件
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            safe_filename = f"{timestamp}_{file.filename}"
            file_path = os.path.join(upload_dir, safe_filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            uploaded_files.append(file_path)

        logger.info(f"用户 {current_user.id} 上传 {len(uploaded_files)} 个文件，upload_id: {upload_id}")

        return {
            "upload_id": upload_id,
            "file_count": len(uploaded_files),
            "file_paths": uploaded_files,
            "message": f"成功上传 {len(uploaded_files)} 个文件"
        }

    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/create-session")
async def create_session(
    upload_ids: Optional[List[str]] = Body(None, embed=True),
    package_id: Optional[str] = Body(None, embed=True),
    user_input: str = Body("", embed=True),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    创建分析会话

    参数：
    - upload_ids: 上传批次 ID 列表（可选，支持多文件上传）
    - package_id: 选择的规则包 ID（可选，不指定则基于用户输入进行通用评估）
    - user_input: 用户需求描述（纯文本分析时使用）
    """
    # 调试日志
    logger.info(f"=== 创建分析会话 ===")
    logger.info(f"接收参数 - upload_ids: {upload_ids}, package_id: {package_id}, user_input: {user_input[:100] if user_input else ''}...")

    assembler = get_risk_rule_assembler(db)

    # 确定使用的规则包和场景类型
    package = None
    scene_type = "general"  # 默认场景类型

    logger.info(f"package_id 值: {package_id}, 类型: {type(package_id)}")

    if package_id:
        # 用户指定了规则包，使用该规则包
        logger.info(f"用户指定了规则包: {package_id}，正在查找...")
        package = assembler.get_package(package_id)
        if package:
            scene_type = package.package_category
            logger.info(f"找到规则包: {package.package_name}, 类别: {scene_type}")
        else:
            logger.error(f"指定的规则包不存在: {package_id}")
            raise HTTPException(status_code=404, detail="指定的规则包不存在")
    else:
        # 用户未指定规则包，将基于用户输入进行通用评估
        scene_type = "general"
        logger.info(f"用户未指定规则包，将基于用户输入进行通用评估")

    # 确定场景类型和文档路径
    document_paths = []

    # 处理多个 upload_id（支持多文件上传）
    if upload_ids:
        for upload_id in upload_ids:
            upload_dir = os.path.join(settings.UPLOAD_DIR, "risk_analysis", "temp", upload_id)

            if not os.path.exists(upload_dir):
                logger.warning(f"upload_id {upload_id} 不存在，跳过")
                continue

            # 收集该批次的所有文件
            batch_files = [
                os.path.join(upload_dir, f)
                for f in os.listdir(upload_dir)
                if os.path.isfile(os.path.join(upload_dir, f))
            ]
            document_paths.extend(batch_files)
            logger.info(f"从 upload_id {upload_id} 收集到 {len(batch_files)} 个文件")

        logger.info(f"总共从 {len(upload_ids)} 个上传批次中收集到 {len(document_paths)} 个文件")

        if not document_paths:
            raise HTTPException(status_code=400, detail="没有找到有效的文档")
    else:
        # 纯文本分析，没有文件上传
        # 创建一个临时文本文件存储用户输入
        temp_dir = os.path.join(settings.UPLOAD_DIR, "risk_analysis", "temp", f"text_{current_user.id}")
        os.makedirs(temp_dir, exist_ok=True)

        temp_file = os.path.join(temp_dir, f"user_input_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(user_input)

        document_paths = [temp_file]
        logger.info(f"创建临时文本文件用于分析: {temp_file}")

    # 创建会话
    session = RiskAnalysisSession(
        session_id=str(uuid.uuid4()),
        user_id=current_user.id,
        status=RiskAnalysisStatus.PENDING.value,
        scene_type=scene_type,
        user_description=user_input,
        document_ids=document_paths,
        created_at=datetime.utcnow()
    )

    db.add(session)
    db.commit()

    logger.info(f"创建分析会话: {session.session_id}, 场景类型: {scene_type}, 规则包: {package.package_id if package else '无（通用评估）'}, 文档数: {len(document_paths)}")

    return {
        "session_id": session.session_id,
        "package_id": package.package_id if package else None,
        "package_name": package.package_name if package else None,
        "scene_type": scene_type,
        "analysis_mode": "规则包评估" if package else "通用评估（基于用户输入）",
        "document_count": len(document_paths),
        "status": session.status,
        "message": "会话创建成功" + (f"，使用规则包：{package.package_name}" if package else "，将基于用户输入进行通用评估")
    }


# ==================== 分析执行 ====================

@router.post("/start/{session_id}")
async def start_analysis(
    session_id: str,
    background_tasks: BackgroundTasks,
    stop_after_preorganization: bool = Body(False, embed=True),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    开始分析

    在后台执行新的工作流分析
    - 如果指定了规则包，使用规则包进行评估
    - 如果未指定规则包（scene_type=general），基于用户输入进行通用评估
    - stop_after_preorganization: 是否在预整理后停止（等待用户确认）
    """
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status != RiskAnalysisStatus.PENDING.value:
        raise HTTPException(status_code=400, detail=f"会话状态不正确: {session.status}")

    # 确定规则包ID
    package_id = None
    assembler = get_risk_rule_assembler(db)

    if session.scene_type == "general":
        # 通用评估模式，不使用规则包
        package_id = None
        logger.info(f"会话 {session_id} 使用通用评估模式（基于用户输入）")
    else:
        # 从 scene_type 推断 package_id
        packages = assembler.list_packages(category=session.scene_type)

        if not packages:
            raise HTTPException(status_code=400, detail=f"找不到场景类型 {session.scene_type} 对应的规则包")

        package_id = packages[0].package_id
        logger.info(f"会话 {session_id} 使用规则包：{package_id}")

    # 后台执行分析（异步版本）
    async def run_analysis_task():
        try:
            logger.info(f"[StartAnalysis] 会话 {session_id} 开始执行分析任务...")
            # 导入工作流服务
            from app.services.risk_analysis.workflow import RiskAnalysisWorkflowService

            workflow_service = RiskAnalysisWorkflowService(db)
            success = await workflow_service.run_analysis(
                session_id=session_id,
                user_input=session.user_description or "",
                document_paths=session.document_ids or [],
                package_id=package_id,  # None 表示通用评估
                stop_after_preorganization=stop_after_preorganization
            )

            if not success:
                logger.error(f"会话 {session_id} 分析失败")
            else:
                logger.info(f"[StartAnalysis] 会话 {session_id} 分析完成")

        except Exception as e:
            logger.error(f"会话 {session_id} 分析异常: {e}", exc_info=True)

    # 使用 asyncio.create_task 在后台运行
    # 注意：FastAPI 运行在 Uvicorn 上，已经有事件循环在运行
    try:
        import asyncio
        # 获取当前运行的事件循环
        loop = asyncio.get_running_loop()
        logger.info(f"[StartAnalysis] 获取到运行中的事件循环，创建后台任务...")
        # 在当前事件循环中创建任务
        loop.create_task(run_analysis_task())
    except RuntimeError as e:
        # 如果没有运行中的事件循环
        logger.error(f"[StartAnalysis] 事件循环错误: {e}")
        logger.info(f"[StartAnalysis] 尝试使用 asyncio.run...")
        import asyncio
        asyncio.run(run_analysis_task())

    return {
        "session_id": session_id,
        "status": "analyzing",
        "analysis_mode": "通用评估" if session.scene_type == "general" else f"规则包评估 ({session.scene_type})",
        "stop_after_preorganization": stop_after_preorganization,
        "message": "分析已开始" + ("，将在预整理后等待确认" if stop_after_preorganization else "")
    }


@router.post("/continue/{session_id}")
async def continue_analysis(
    session_id: str,
    background_tasks: BackgroundTasks,
    request: SelectAnalysisModeRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    继续分析（用户确认预整理结果后）

    Args:
        session_id: 会话 ID
        request: 包含 analysis_mode 和 selected_model

    从预整理后的节点继续执行分析
    """
    logger.error(f"👉 [TRACK] /continue 接口被调用, session_id={session_id}, analysis_mode={request.analysis_mode}, selected_model={request.selected_model}, evaluation_stance={request.evaluation_stance}")

    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证分析模式
    if request.analysis_mode not in ["single", "multi"]:
        raise HTTPException(status_code=400, detail="无效的分析模式，必须是 'single' 或 'multi'")

    # 单模型模式下必须指定模型
    if request.analysis_mode == "single" and not request.selected_model:
        raise HTTPException(status_code=400, detail="单模型模式下必须指定模型名称")

    # ✅ 保存评估立场到数据库
    session.evaluation_stance = request.evaluation_stance
    db.commit()

    # ✅ 增强日志：明确显示立场是否提供
    if request.evaluation_stance:
        logger.info(f"[ContinueAnalysis] ✅ 已保存评估立场到数据库: {request.evaluation_stance[:100]}...")
    else:
        logger.info(f"[ContinueAnalysis] ℹ️ 用户未提供评估立场（evaluation_stance 为空）")


    # 后台执行继续分析
    async def continue_analysis_task():
        try:
            logger.info(f"[ContinueAnalysis] 会话 {session_id} 开始继续分析，mode: {request.analysis_mode}...")
            # 导入工作流服务
            from app.services.risk_analysis.workflow import RiskAnalysisWorkflowService

            workflow_service = RiskAnalysisWorkflowService(db)
            success = await workflow_service.continue_analysis_after_confirmation(
                session_id=session_id,
                analysis_mode=request.analysis_mode,
                selected_model=request.selected_model,
                evaluation_stance=request.evaluation_stance  # ✅ 新增：传递评估立场
            )

            if not success:
                logger.error(f"会话 {session_id} 继续分析失败")
            else:
                logger.info(f"[ContinueAnalysis] 会话 {session_id} 继续分析完成")

        except Exception as e:
            logger.error(f"会话 {session_id} 继续分析异常: {e}", exc_info=True)

    # 使用 asyncio.create_task 在后台运行
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        logger.info(f"[ContinueAnalysis] 获取到运行中的事件循环，创建后台任务...")
        loop.create_task(continue_analysis_task())
    except RuntimeError as e:
        logger.error(f"[ContinueAnalysis] 事件循环错误: {e}")
        logger.info(f"[ContinueAnalysis] 尝试使用 asyncio.run...")
        import asyncio
        asyncio.run(continue_analysis_task())

    return {
        "session_id": session_id,
        "status": "analyzing",
        "analysis_mode": request.analysis_mode,
        "selected_model": request.selected_model,
        "message": "继续分析已开始"
    }


@router.get("/status/{session_id}")
async def get_status(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """获取分析状态"""
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "session_id": session.session_id,
        "status": session.status,
        "summary": session.summary,
        "risk_distribution": session.risk_distribution,
        "total_confidence": session.total_confidence,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None
    }


@router.get("/result/{session_id}")
async def get_result(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """获取完整分析结果"""
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status != RiskAnalysisStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="分析尚未完成")

    # 获取风险项
    from app.models.risk_analysis import RiskItem
    risk_items = db.query(RiskItem).filter(
        RiskItem.session_id == session.id
    ).all()

    return {
        "session_id": session.session_id,
        "status": session.status,
        "summary": session.summary,
        "risk_distribution": session.risk_distribution,
        "total_confidence": session.total_confidence,
        "report_md": session.report_md,
        "risk_items": [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "risk_level": item.risk_level,
                "confidence": item.confidence,
                "reasons": item.reasons,
                "suggestions": item.suggestions
            }
            for item in risk_items
        ],
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None
    }


# ==================== 文档预整理 ====================

@router.post("/preorganize", response_model=DocumentPreorganizationResponse)
async def preorganize_documents(
    request: DocumentPreorganizationRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    预整理文档（专业助理节点）

    对文档进行分类、质量评估、智能摘要、关系分析等
    """
    # 使用 UnifiedDocumentService 处理文档
    doc_service = get_unified_document_service()

    try:
        results = await doc_service.batch_process_async(
            request.document_paths,
            extract_content=True,
            extract_metadata=True,
            max_concurrent=3
        )

        # 过滤成功的文档
        successful_docs = [r for r in results if r.status == "success"]

        if not successful_docs:
            return DocumentPreorganizationResponse(
                preorganized_docs=PreorganizedDocuments(),
                status="failed",
                message="文档处理全部失败"
            )

        # 创建 LLM 实例
        llm = ChatOpenAI(
            model=settings.MODEL_NAME or "Qwen3-235B-A22B-Thinking-2507",
            api_key=settings.LANGCHAIN_API_KEY,
            base_url=settings.LANGCHAIN_API_BASE_URL,
            temperature=0
        )

        # 预整理
        preorg_service = get_document_preorganization_service(llm)
        preorganized = await preorg_service.preorganize(
            documents=successful_docs,
            user_context=request.user_context
        )

        return DocumentPreorganizationResponse(
            preorganized_docs=preorganized,
            status="success",
            message=f"成功预整理 {len(successful_docs)} 个文档"
        )

    except Exception as e:
        logger.error(f"文档预整理失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"预整理失败: {str(e)}")


# ==================== 图表生成 ====================

@router.post("/diagram/generate", response_model=DiagramResult)
async def generate_diagram(
    request: DiagramRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    生成图表

    支持股权结构图、股权穿透图、投资流程图、风险思维导图、关系图、时间线
    """
    try:
        generator = get_diagram_generator_service()
        result = generator.generate(request)
        return result
    except Exception as e:
        logger.error(f"图表生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"图表生成失败: {str(e)}")


@router.post("/diagram/generate-from-text", response_model=DiagramResult)
async def generate_diagram_from_text(
    request: DiagramLLMGenerateRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    从文本生成图表（LLM 提取 + 图表生成）

    LLM 自动提取图表数据，然后生成图表
    """
    try:
        # 创建 LLM 实例
        llm = ChatOpenAI(
            model=settings.MODEL_NAME or "Qwen3-235B-A22B-Thinking-2507",
            api_key=settings.LANGCHAIN_API_KEY,
            base_url=settings.LANGCHAIN_API_BASE_URL,
            temperature=0
        )

        # 使用 LLM 提取图表数据
        from langchain_core.messages import SystemMessage, HumanMessage
        import json
        import re

        prompt = f"""请从以下文本中提取股权结构信息，用于生成图表。

**文本**:
{request.text}

**图表类型**: {request.diagram_type.value}

请提取以下信息（JSON 格式）：
{{
  "title": "图表标题",
  "companies": [
    {{"name": "公司A", "registration_code": "...", "registered_capital": "..."}}
  ],
  "shareholders": [
    {{"name": "张三"}}
  ],
  "relationships": [
    {{"source": "张三", "target": "公司A", "ratio": "60%", "amount": "600万"}}
  ]
}}

严格按照 JSON 格式输出。"""

        response = llm.invoke([
            SystemMessage(content="你是专业的股权结构分析助手，擅长从文本中提取股权信息。"),
            HumanMessage(content=prompt)
        ])

        # 解析 JSON
        response_text = response.content if hasattr(response, 'content') else str(response)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

        if json_match:
            from app.schemas.risk_analysis_diagram import DiagramExtraction
            data = json.loads(json_match.group(0))

            # 构建图表请求
            diagram_request = DiagramRequest(
                diagram_type=request.diagram_type,
                format=request.format,
                title=data.get("title") or request.title,
                companies=[{"name": c["name"], **c} for c in data.get("companies", [])],
                shareholders=data.get("shareholders", []),
                relationships=data.get("relationships", [])
            )

            generator = get_diagram_generator_service()
            result = generator.generate(diagram_request)
            return result
        else:
            raise ValueError("无法从 LLM 响应中提取 JSON")

    except Exception as e:
        logger.error(f"从文本生成图表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"图表生成失败: {str(e)}")


# ==================== 历史任务管理 ====================

@router.get("/sessions")
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取用户的会话列表（包含未完成和已完成）

    返回：
    - sessions: 会话列表
    - total: 总数
    - incomplete_count: 未完成任务数
    - completed_count: 已完成任务数
    """
    # 基础查询
    base_query = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.user_id == current_user.id
    )

    # 按状态过滤（可选）
    query = base_query
    if status:
        query = query.filter(RiskAnalysisSession.status == status)

    # 按创建时间倒序
    query = query.order_by(RiskAnalysisSession.created_at.desc())

    # 分页
    total = query.count()
    sessions = query.limit(limit).offset(offset).all()

    # 转换为响应格式
    session_list = []
    for session in sessions:
        # 生成标题
        title = session.title or f"{session.scene_type} - {session.created_at.strftime('%Y-%m-%d %H:%M')}"

        # 获取文档数量
        doc_count = len(session.document_ids) if session.document_ids else 0

        # 判断是否完成
        is_completed = session.status == RiskAnalysisStatus.COMPLETED.value

        session_list.append({
            "session_id": session.session_id,
            "title": title,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "summary": session.summary,
            "risk_distribution": session.risk_distribution,
            "scene_type": session.scene_type,
            "document_count": doc_count,
            "is_completed": is_completed  # ✅ 新增：完成状态标记
        })

    # ✅ 计算未完成和已完成数量
    incomplete_count = base_query.filter(
        RiskAnalysisSession.status != RiskAnalysisStatus.COMPLETED.value
    ).count()
    completed_count = base_query.filter(
        RiskAnalysisSession.status == RiskAnalysisStatus.COMPLETED.value
    ).count()

    return {
        "sessions": session_list,
        "total": total,
        "incomplete_count": incomplete_count,  # ✅ 新增
        "completed_count": completed_count      # ✅ 新增
    }


@router.patch("/sessions/{session_id}/status")
async def update_session_status(
    session_id: str,
    status: Optional[str] = Body(None, embed=True),
    title: Optional[str] = Body(None, embed=True),
    is_unread: Optional[bool] = Body(None, embed=True),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    更新会话状态

    用于：
    - 用户中途退出时保存状态
    - 前端定期心跳更新
    - 标记为后台任务
    - 标记为已读
    """
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 更新状态
    if status is not None:
        session.status = status

    # 更新标题（如果提供）
    if title is not None:
        session.title = title

    # 更新未读状态
    if is_unread is not None:
        session.is_unread = is_unread

    # 更新时间
    session.updated_at = datetime.utcnow()

    # 如果完成，设置完成时间
    if status == RiskAnalysisStatus.COMPLETED.value:
        session.completed_at = datetime.utcnow()

    db.commit()

    return {
        "session_id": session_id,
        "status": session.status,
        "message": "状态已更新"
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    删除历史会话

    级联删除关联的风险项和预整理结果
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # 首先通过 session_id (字符串) 查找会话
        session = db.query(RiskAnalysisSession).filter(
            RiskAnalysisSession.session_id == session_id,
            RiskAnalysisSession.user_id == current_user.id
        ).first()

        if not session:
            logger.warning(f"[删除会话] 会话不存在: session_id={session_id}, user_id={current_user.id}")
            raise HTTPException(status_code=404, detail="会话不存在")

        logger.info(f"[删除会话] 开始删除会话: session_id={session_id}, id={session.id}")

        # 级联删除风险项（使用 session.id，因为 RiskItem.session_id 外键指向 RiskAnalysisSession.id）
        risk_items_deleted = db.query(RiskItem).filter(
            RiskItem.session_id == session.id
        ).delete()
        logger.info(f"[删除会话] 删除风险项: {risk_items_deleted} 条")

        # 删除预整理结果（使用 session_id 字符串，因为 RiskAnalysisPreorganization.session_id 外键指向 RiskAnalysisSession.session_id）
        preorg_deleted = db.query(RiskAnalysisPreorganization).filter(
            RiskAnalysisPreorganization.session_id == session_id
        ).delete()
        logger.info(f"[删除会话] 删除预整理结果: {preorg_deleted} 条")

        # 删除会话
        db.delete(session)
        db.commit()
        logger.info(f"[删除会话] 会话删除成功: session_id={session_id}")

        return {"message": "会话已删除"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[删除会话] 删除失败: session_id={session_id}, error={str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.delete("/sessions/cleanup")
async def cleanup_old_sessions(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    清理过期会话

    策略：
    - 未完成任务：30天
    - 已完成任务：90天
    """
    from datetime import timedelta

    now = datetime.utcnow()

    # 清理未完成的旧任务（30天）
    incomplete_cutoff = now - timedelta(days=30)
    incomplete_deleted = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.user_id == current_user.id,
        RiskAnalysisSession.status.in_([
            RiskAnalysisStatus.PENDING.value,
            RiskAnalysisStatus.PARSING.value,
            RiskAnalysisStatus.ANALYZING.value
        ]),
        RiskAnalysisSession.created_at < incomplete_cutoff
    ).delete(synchronize_session=False)

    # 清理已完成的旧任务（90天）
    completed_cutoff = now - timedelta(days=90)
    completed_deleted = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.user_id == current_user.id,
        RiskAnalysisSession.status.in_([
            RiskAnalysisStatus.COMPLETED.value,
            RiskAnalysisStatus.FAILED.value
        ]),
        RiskAnalysisSession.created_at < completed_cutoff
    ).delete(synchronize_session=False)

    db.commit()

    return {
        "message": f"已清理 {incomplete_deleted + completed_deleted} 个过期会话",
        "incomplete_deleted": incomplete_deleted,
        "completed_deleted": completed_deleted
    }


@router.post("/{session_id}/heartbeat")
async def session_heartbeat(
    session_id: str,
    ws_connected: bool = Body(True, embed=True),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    前端心跳，告诉后端用户是否在线

    用于：
    - 前端定期通知后端用户仍在查看任务
    - 用户退出时通知后端进入后台模式
    - 后端根据此标志决定是否推送 WebSocket 消息
    """
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 更新后台标志
    session.is_background = not ws_connected
    db.commit()

    logger.debug(f"[心跳] 会话 {session_id} ws_connected={ws_connected}, is_background={session.is_background}")

    return {"status": "ok"}


@router.get("/{session_id}/restore-state")
async def get_restore_state(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取会话完整状态用于恢复

    返回会话的当前阶段和可用数据，供前端恢复状态使用
    """
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id,
        RiskAnalysisSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    result = {
        "session_info": {
            "session_id": session.session_id,
            "status": session.status,
            "scene_type": session.scene_type,
            "user_description": session.user_description,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None
        },
        "current_stage": "unknown",
        "can_continue": False,
        "data": {}
    }

    # 确定当前阶段
    if session.status == RiskAnalysisStatus.PENDING.value:
        result["current_stage"] = "input"
    elif session.status == RiskAnalysisStatus.PARSING.value:
        result["current_stage"] = "preorganization_in_progress"
    elif session.status == RiskAnalysisStatus.ANALYZING.value:
        result["current_stage"] = "analysis_in_progress"
    elif session.status == RiskAnalysisStatus.COMPLETED.value:
        result["current_stage"] = "analysis_completed"
        result["can_continue"] = False

    # 检查预整理结果
    preorg = db.query(RiskAnalysisPreorganization).filter(
        RiskAnalysisPreorganization.session_id == session_id
    ).first()

    if preorg:
        result["current_stage"] = "preorganization_completed"
        result["can_continue"] = not preorg.is_confirmed

        # 解析 enhanced_analysis_json（如果存在）
        import json
        enhanced_analysis = None
        if preorg.enhanced_analysis_json:
            try:
                enhanced_analysis = json.loads(preorg.enhanced_analysis_json)
            except:
                enhanced_analysis = None

        result["data"]["preorganization"] = {
            "user_requirement_summary": preorg.user_requirement_summary,
            "documents_info": preorg.documents_info,
            "fact_summary": preorg.fact_summary,
            "contract_legal_features": preorg.contract_legal_features,
            "contract_relationships": preorg.contract_relationships,
            "architecture_diagram": preorg.architecture_diagram,
            "is_confirmed": preorg.is_confirmed,
            "analysis_mode": preorg.analysis_mode,
            "selected_model": preorg.selected_model,
            "enhanced_analysis": enhanced_analysis  # 新增：增强分析数据
        }

    return result


# ==================== WebSocket 实时进度 ====================

@router.websocket("/ws/{session_id}")
async def risk_analysis_websocket(
    websocket: WebSocket,
    session_id: str,
    db: Session = Depends(deps.get_db)
):
    """
    WebSocket 端点：实时推送分析进度

    消息格式：
    {
        "type": "node_progress",
        "node": "documentPreorganization|multiModelAnalysis|reportGeneration",
        "status": "pending|processing|completed|failed",
        "message": "进度描述",
        "progress": 0.5  // 0-1
    }

    架构说明：
    - 使用 asyncio.Queue 实现生产者-消费者模式
    - send_progress (生产者) 将消息放入队列
    - 此端点 (消费者) 从队列取出消息并发送到客户端
    - 解决了 Starlette WebSocket 不支持并发 send/receive 的问题
    """
    from app.api.websocket import manager

    # 接受连接（参数顺序：websocket, session_id）
    await manager.connect(websocket, session_id)
    logger.info(f"[WebSocket Endpoint] 连接已建立: {session_id}")

    try:
        # 验证会话是否存在
        session = db.query(RiskAnalysisSession).filter(
            RiskAnalysisSession.session_id == session_id
        ).first()

        if not session:
            logger.error(f"[WebSocket Endpoint] 会话不存在: {session_id}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": "会话不存在"
                })
            except Exception:
                pass
            await manager.disconnect(session_id)
            return

        logger.info(f"[WebSocket Endpoint] 会话验证成功: {session_id}")

        # 使用队列模式处理消息发送
        import asyncio

        async def receive_messages():
            """接收客户端消息（心跳）的协程"""
            logger.info(f"[WS Endpoint] 🔵 receive_messages 协程已启动: {session_id}")
            try:
                while True:
                    data = await websocket.receive_text()
                    if data == "ping":
                        logger.debug(f"[WS Endpoint] 收到ping，回复pong: {session_id}")
                        await websocket.send_json({"type": "pong"})
                    else:
                        logger.debug(f"[WS Endpoint] 收到其他消息: {data}")
            except WebSocketDisconnect as e:
                # 1005 = 正常关闭（前端完成任务后主动断开，或用户关闭浏览器）
                # 1006 = 异常断开（网络问题等）
                if e.code == 1005:
                    logger.info(f"[WS Endpoint] 接收协程：客户端正常关闭连接 ({session_id})")
                    # 正常关闭，不重新抛出异常，让协程正常结束
                    return
                else:
                    logger.warning(f"[WS Endpoint] 接收协程：连接异常断开 code={e.code} ({session_id})")
                    # 异常断开，也不重新抛出，让协程正常结束
                    return
            except Exception as e:
                logger.error(f"[WS Endpoint] 接收协程错误: {e}", exc_info=True)
                raise

        async def send_messages():
            """从队列取出消息并发送的协程"""
            logger.info(f"[WS Endpoint] 🟢🟢🟢 send_messages 协程 ENTRY: {session_id}")
            try:
                logger.info(f"[WS Endpoint] 🟢 send_messages 协程已启动: {session_id}")
                loop_count = 0
                logger.info(f"[WS Endpoint] 🟢 准备进入 while 循环: {session_id}")
                while True:
                    loop_count += 1
                    # 从队列获取消息（1秒超时）
                    message = await manager.get_message(session_id, timeout=1.0)

                    if message is not None:
                        logger.info(f"[WS Endpoint] 📨 从队列获取消息 (循环{loop_count}次): {message.get('type')}")
                        logger.debug(f"[WS Endpoint] 消息完整内容: {message}")
                        logger.debug(f"[WS Endpoint] 准备发送到 WebSocket，readyState: {websocket.client_state}")
                        # 发送消息到客户端
                        try:
                            await websocket.send_json(message)
                            logger.info(f"[WS Endpoint] ✅ 消息已成功发送 (循环{loop_count}次): {message.get('type')}")
                        except Exception as send_error:
                            logger.error(f"[WS Endpoint] ❌ 发送失败 (循环{loop_count}次): {send_error}", exc_info=True)
                            raise
                    else:
                        # 超时，继续等待
                        if loop_count % 10 == 0:  # 每10秒打印一次
                            logger.debug(f"[WS Endpoint] ⏳ 队列为空，继续等待... (循环{loop_count}次)")
            except WebSocketDisconnect:
                logger.info(f"[WS Endpoint] 发送协程检测到断开: {session_id}")
                raise
            except Exception as e:
                logger.error(f"[WS Endpoint] 发送协程错误: {e}", exc_info=True)
                raise

        # 同时运行接收和发送协程
        logger.info(f"[WS Endpoint] 🚀 准备启动协程: {session_id}")
        receive_task = asyncio.create_task(receive_messages())
        send_task = asyncio.create_task(send_messages())
        logger.info(f"[WS Endpoint] ✅ 协程已创建: {session_id}")

        # 等待任一协程完成
        logger.info(f"[WS Endpoint] ⏳ 等待协程完成: {session_id}")
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        logger.info(f"[WS Endpoint] 🏁 有协程完成了: {session_id}, done: {len(done)}, pending: {len(pending)}")
        for task in done:
            task_name = task.get_name()
            try:
                if task.cancelled():
                    logger.info(f"[WS Endpoint] ✅ 已完成的任务: {task_name}, 状态: cancelled")
                else:
                    result = task.result()
                    logger.info(f"[WS Endpoint] ✅ 已完成的任务: {task_name}, 结果: {result}")
            except asyncio.CancelledError:
                logger.info(f"[WS Endpoint] ✅ 已完成的任务: {task_name}, 状态: cancelled")
            except Exception as e:
                # 访问结果时可能抛出异常（如 WebSocketDisconnect）
                logger.info(f"[WS Endpoint] ✅ 已完成的任务: {task_name}, 异常: {type(e).__name__}")

        # 取消未完成的协程
        if pending:
            logger.info(f"[WS Endpoint] ⚠️ 准备取消 {len(pending)} 个未完成的协程: {session_id}")
            for task in pending:
                logger.info(f"[WS Endpoint] ❌ 取消任务: {task.get_name()}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"[WS Endpoint] ✅ 任务已取消: {task.get_name()}")
                    pass

        logger.info(f"[WS Endpoint] 连接结束: {session_id}")

    except Exception as e:
        logger.error(f"[WS Endpoint] 连接错误: {e}", exc_info=True)
    finally:
        logger.info(f"[WS Endpoint] 清理连接: {session_id}")
        await manager.disconnect(session_id)


# ==================== 预整理结果管理 ====================

class PreorganizationResultRequest(BaseModel):
    """保存预整理结果请求"""
    user_requirement_summary: Optional[str] = None
    documents_info: Optional[list] = None
    fact_summary: Optional[dict] = None
    contract_legal_features: Optional[dict] = None
    contract_relationships: Optional[list] = None
    architecture_diagram: Optional[dict] = None


@router.post("/{session_id}/preorganization-result")
async def save_preorganization_result(
    session_id: str,
    request: PreorganizationResultRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    保存预整理结果

    保存文档预整理的完整结果到数据库，供前端查询和用户确认
    """
    logger.info(f"保存预整理结果: session_id={session_id}")

    # 验证会话是否存在
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证权限
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 检查是否已存在预整理结果
    existing_result = db.query(RiskAnalysisPreorganization).filter(
        RiskAnalysisPreorganization.session_id == session_id
    ).first()

    if existing_result:
        # 更新现有记录
        existing_result.user_requirement_summary = request.user_requirement_summary
        existing_result.documents_info = request.documents_info
        existing_result.fact_summary = request.fact_summary
        existing_result.contract_legal_features = request.contract_legal_features
        existing_result.contract_relationships = request.contract_relationships
        existing_result.architecture_diagram = request.architecture_diagram
        existing_result.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(existing_result)

        logger.info(f"更新预整理结果: id={existing_result.id}")
        return {
            "message": "预整理结果已更新",
            "preorganization_id": existing_result.id
        }
    else:
        # 创建新记录
        preorganization = RiskAnalysisPreorganization(
            session_id=session_id,
            user_requirement_summary=request.user_requirement_summary,
            documents_info=request.documents_info,
            fact_summary=request.fact_summary,
            contract_legal_features=request.contract_legal_features,
            contract_relationships=request.contract_relationships,
            architecture_diagram=request.architecture_diagram,
            is_confirmed=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(preorganization)
        db.commit()
        db.refresh(preorganization)

        logger.info(f"创建预整理结果: id={preorganization.id}")
        return {
            "message": "预整理结果已保存",
            "preorganization_id": preorganization.id
        }


@router.get("/{session_id}/preorganization-result")
async def get_preorganization_result(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取预整理结果

    返回指定会话的预整理结果，供前端展示和用户确认
    """
    logger.info(f"获取预整理结果: session_id={session_id}")

    # 验证会话是否存在
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证权限
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 获取预整理结果
    preorganization = db.query(RiskAnalysisPreorganization).filter(
        RiskAnalysisPreorganization.session_id == session_id
    ).first()

    if not preorganization:
        raise HTTPException(status_code=404, detail="预整理结果不存在，请先完成文档预整理")

    return {
        "preorganization_id": preorganization.id,
        "session_id": preorganization.session_id,
        "user_requirement_summary": preorganization.user_requirement_summary,
        "documents_info": preorganization.documents_info,
        "fact_summary": preorganization.fact_summary,
        "contract_legal_features": preorganization.contract_legal_features,
        "contract_relationships": preorganization.contract_relationships,
        "architecture_diagram": preorganization.architecture_diagram,
        "is_confirmed": preorganization.is_confirmed,
        "user_modifications": preorganization.user_modifications,
        "analysis_mode": preorganization.analysis_mode,
        "selected_model": preorganization.selected_model,
        "created_at": preorganization.created_at.isoformat() if preorganization.created_at else None,
        "updated_at": preorganization.updated_at.isoformat() if preorganization.updated_at else None,
        "confirmed_at": preorganization.confirmed_at.isoformat() if preorganization.confirmed_at else None
    }


@router.post("/{session_id}/confirm-preorganization")
async def confirm_preorganization(
    session_id: str,
    request: ConfirmPreorganizationRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    确认预整理结果

    用户确认预整理结果，可选择修改部分内容
    """
    logger.info(f"确认预整理结果: session_id={session_id}")

    # 验证会话是否存在
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证权限
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 获取预整理结果
    preorganization = db.query(RiskAnalysisPreorganization).filter(
        RiskAnalysisPreorganization.session_id == session_id
    ).first()

    if not preorganization:
        raise HTTPException(status_code=404, detail="预整理结果不存在")

    # 记录用户修改
    if request.user_modifications:
        # 添加修改记录
        for field, modification in request.user_modifications.items():
            preorganization.add_modification(
                field=field,
                original_value=modification.get("original_value"),
                modified_value=modification.get("modified_value")
            )

        # 更新字段值
        if "user_requirement_summary" in request.user_modifications:
            preorganization.user_requirement_summary = request.user_modifications["user_requirement_summary"].get("modified_value")
        if "documents_info" in request.user_modifications:
            preorganization.documents_info = request.user_modifications["documents_info"].get("modified_value")
        if "fact_summary" in request.user_modifications:
            preorganization.fact_summary = request.user_modifications["fact_summary"].get("modified_value")

    preorganization.is_confirmed = True
    preorganization.confirmed_at = datetime.utcnow()
    preorganization.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(preorganization)

    logger.info(f"预整理结果已确认: id={preorganization.id}")

    return {
        "message": "预整理结果已确认",
        "preorganization_id": preorganization.id,
        "is_confirmed": True,
        "confirmed_at": preorganization.confirmed_at.isoformat() if preorganization.confirmed_at else None
    }


@router.post("/{session_id}/select-analysis-mode")
async def select_analysis_mode(
    session_id: str,
    request: SelectAnalysisModeRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    选择分析模式

    用户选择单模型或多模型分析模式
    """
    logger.info(f"选择分析模式: session_id={session_id}, mode={request.analysis_mode}")

    # 验证分析模式
    if request.analysis_mode not in ["single", "multi"]:
        raise HTTPException(status_code=400, detail="无效的分析模式，必须是 'single' 或 'multi'")

    # 单模型模式下必须指定模型
    if request.analysis_mode == "single" and not request.selected_model:
        raise HTTPException(status_code=400, detail="单模型模式下必须指定模型名称")

    # 验证会话是否存在
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证权限
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 获取预整理结果
    preorganization = db.query(RiskAnalysisPreorganization).filter(
        RiskAnalysisPreorganization.session_id == session_id
    ).first()

    if not preorganization:
        raise HTTPException(status_code=404, detail="预整理结果不存在，请先完成文档预整理")

    # 更新分析模式
    preorganization.analysis_mode = request.analysis_mode
    preorganization.selected_model = request.selected_model
    preorganization.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(preorganization)

    logger.info(f"分析模式已选择: mode={request.analysis_mode}, model={request.selected_model}")

    return {
        "message": "分析模式已选择",
        "analysis_mode": preorganization.analysis_mode,
        "selected_model": preorganization.selected_model
    }


# ==================== 预整理报告下载 ====================

@router.get("/preorganization-report/{session_id}")
async def download_preorganization_report(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    下载预整理报告（Word格式）

    生成并下载包含以下内容的Word报告：
    - 用户需求摘要
    - 文档信息（分类、摘要、质量评估）
    - 事实摘要（关键事实、时间线、涉及主体）
    - 合同法律特征（合同类型、法律条款、风险点）
    - 合同关系
    - 架构图
    """
    logger.info(f"生成预整理报告请求: session_id={session_id}")

    # 验证会话是否存在
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id
    ).first()

    if not session:
        logger.warning(f"预整理报告下载失败: 会话不存在, session_id={session_id}")
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证权限
    if session.user_id != current_user.id:
        logger.warning(f"预整理报告下载失败: 无权访问, session_id={session_id}, user_id={current_user.id}")
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 获取预整理结果
    preorganization = db.query(RiskAnalysisPreorganization).filter(
        RiskAnalysisPreorganization.session_id == session_id
    ).first()

    if not preorganization:
        logger.warning(f"预整理报告下载失败: 预整理结果不存在, session_id={session_id}")
        raise HTTPException(
            status_code=404,
            detail="预整理结果不存在，请先完成文档预整理"
        )

    # ✅ 新增：验证数据完整性
    missing_fields = []
    if not preorganization.user_requirement_summary:
        missing_fields.append("用户需求摘要")
    if not preorganization.documents_info:
        missing_fields.append("文档信息")
    if not preorganization.fact_summary:
        missing_fields.append("事实摘要")

    if missing_fields:
        logger.error(
            f"预整理报告下载失败: 数据不完整, session_id={session_id}, "
            f"缺失字段={', '.join(missing_fields)}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"预整理数据不完整，缺失：{', '.join(missing_fields)}。请重新进行文档预整理。"
        )

    try:
        logger.info(f"开始生成预整理报告, session_id={session_id}")

        # ✅ 新增：记录数据结构
        logger.debug(
            f"预整理数据结构: "
            f"user_requirement_summary_len={len(preorganization.user_requirement_summary or '')}, "
            f"documents_info_type={type(preorganization.documents_info).__name__}, "
            f"fact_summary_type={type(preorganization.fact_summary).__name__}"
        )

        # 构建预整理数据
        preorganization_data = {
            "user_requirement_summary": preorganization.user_requirement_summary,
            "documents_info": preorganization.documents_info,
            "fact_summary": preorganization.fact_summary,
            "contract_legal_features": preorganization.contract_legal_features,
            "contract_relationships": preorganization.contract_relationships,
            "architecture_diagram": preorganization.architecture_diagram
        }

        logger.info(f"预整理数据构建完成, session_id={session_id}")

        # 生成报告
        generator = get_preorganization_report_generator()
        logger.info(f"调用报告生成器, session_id={session_id}")

        report_path = generator.generate(session_id, preorganization_data)

        logger.info(f"报告文件生成成功: {report_path}")

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"预整理报告_{session_id}_{timestamp}.docx"

        logger.info(f"预整理报告生成成功, session_id={session_id}, path={report_path}")

        # 返回文件
        return FileResponse(
            report_path,
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except HTTPException:
        # 重新抛出 HTTP 异常（不记录重复日志）
        raise
    except Exception as e:
        # ✅ 新增：详细错误日志
        logger.error(
            f"生成预整理报告失败: session_id={session_id}, error={str(e)}",
            exc_info=True
        )

        # ✅ 新增：区分不同类型的错误
        error_msg = str(e)
        if "JSON" in error_msg or "parsing" in error_msg.lower():
            detail = "数据格式错误，无法生成报告。请联系管理员检查数据格式。"
        elif "file" in error_msg.lower() or "path" in error_msg.lower():
            detail = "文件操作失败，请稍后重试。"
        elif "permission" in error_msg.lower():
            detail = "权限不足，无法生成报告文件。"
        else:
            detail = f"生成报告失败: {error_msg}"

        raise HTTPException(status_code=500, detail=detail)


# ==================== 风险分析报告下载 ====================

@router.get("/report/{session_id}")
async def download_risk_analysis_report(
    session_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    下载风险分析报告（Word格式）

    生成并下载包含以下内容的Word报告：
    - 总体摘要
    - 风险分布（按等级和类别）
    - 风险项详情（标题、等级、置信度、描述、原因、建议）
    - 总体评估
    """
    logger.info(f"生成风险分析报告请求: session_id={session_id}")

    # 验证会话是否存在
    session = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证权限
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 验证会话状态
    if session.status != RiskAnalysisStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="分析尚未完成，无法生成报告")

    try:
        # 获取风险项
        from app.models.risk_analysis import RiskItem
        risk_items = db.query(RiskItem).filter(
            RiskItem.session_id == session.id
        ).all()

        # 构建分析结果数据
        analysis_result = {
            "summary": session.summary,
            "risk_distribution": session.risk_distribution,
            "total_confidence": session.total_confidence,
            "risk_items": [
                {
                    "title": item.title,
                    "description": item.description,
                    "risk_level": item.risk_level,
                    "confidence": item.confidence,
                    "reasons": item.reasons,
                    "suggestions": item.suggestions
                }
                for item in risk_items
            ]
        }

        # 生成报告
        generator = get_risk_analysis_report_generator()
        report_path = generator.generate(session_id, analysis_result)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"风险分析报告_{session_id}_{timestamp}.docx"

        logger.info(f"风险分析报告生成成功: {report_path}")

        # 返回文件
        return FileResponse(
            report_path,
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        logger.error(f"生成风险分析报告失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")
