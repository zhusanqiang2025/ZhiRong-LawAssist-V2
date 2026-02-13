# backend/app/api/contract_router.py
import os
import uuid
import shutil
import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.contract import ContractDoc, ContractReviewItem, ContractStatus
from app.models.user import User
from app.models.category import Category  # ✅ 核心增强：引入分类模型
from app.schemas import ContractDocOut, ContractMetadataSchema
from app.services.contract_review.contract_review_service import ContractReviewService
from app.services.contract_review.langgraph_review_service import run_langgraph_review, run_langgraph_review_async
from app.services.common.document_preprocessor import get_preprocessor, ConversionResult
from app.services.common.converter import convert_to_pdf_via_onlyoffice
from app.utils.office_utils import OfficeTokenManager
from app.utils.onlyoffice_config import get_review_mode_config
from app.api.deps import get_current_user
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Contract Review System"])
UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== 核心增强：自动关联分类 ====================

def _resolve_and_update_category(db: Session, contract: ContractDoc, contract_type_name: str):
    """
    根据合同类型名称自动关联分类ID（RuleAssembler 依赖此字段加载规则）
    匹配策略：精确匹配 > 模糊匹配（去除"合同"/"协议"后缀）
    """
    if not contract_type_name or contract.category_id:  # 已有关联则跳过
        return

    # 1. 精确匹配
    category = db.query(Category).filter(Category.name == contract_type_name).first()
    
    # 2. 模糊匹配（简单策略：去除常见后缀）
    if not category:
        short_name = contract_type_name.replace("合同", "").replace("协议", "").strip()
        if short_name:
            category = db.query(Category).filter(Category.name.like(f"%{short_name}%")).first()

    if category:
        contract.category_id = category.id
        logger.info(f"[CategoryLink] contract_id={contract.id} type='{contract_type_name}' → category_id={category.id} ({category.name})")
    else:
        logger.warning(f"[CategoryLink] 未找到合同类型 '{contract_type_name}' 的匹配分类，将使用通用规则")


# ==================== 文件处理逻辑 ====================

def process_uploaded_file_background(
    contract_id: int,
    original_file_path: str,
    file_ext: str,
    auto_extract_metadata: bool = True,
    callback_url: Optional[str] = None,
    feishu_record_id: Optional[str] = None,
    feishu_file_key: Optional[str] = None,
    reviewer_open_id: Optional[str] = None
):
    """后台任务：格式转换 → PDF生成 → 元数据提取 → 飞书回调"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
        if not contract:
            logger.error(f"[后台处理] 合同 {contract_id} 不存在")
            return

        # 步骤1: 格式转换
        preprocessor = get_preprocessor()
        conversion_result, working_file_path, _ = preprocessor.convert_to_docx(file_path=original_file_path)
        
        if conversion_result == ConversionResult.SUCCESS and working_file_path != original_file_path:
            try:
                os.remove(original_file_path)
            except Exception:
                pass
        if conversion_result == ConversionResult.FAILED:
            contract.status = ContractStatus.DRAFT.value
            contract.metadata_info = {"error": "文件格式转换失败", "processing_status": "conversion_failed"}
            db.commit()
            return

        contract.original_file_path = working_file_path
        contract.status = ContractStatus.DRAFT.value
        db.commit()

        # 步骤2: PDF生成
        pdf_name = os.path.basename(working_file_path).rsplit(".", 1)[0] + ".pdf"
        pdf_full_path = os.path.join(UPLOAD_DIR, pdf_name)
        success, pdf_result = convert_to_pdf_via_onlyoffice(os.path.basename(working_file_path))
        if success:
            with open(pdf_full_path, "wb") as f:
                f.write(pdf_result)
            contract.pdf_converted_path = pdf_full_path
        db.commit()

        # 步骤3: 元数据提取 + 自动关联分类 ✅
        if auto_extract_metadata:
            try:
                meta = ContractReviewService(db).extract_metadata(contract_id)
                if meta and meta.contract_type:
                    _resolve_and_update_category(db, contract, meta.contract_type)
                    db.commit()
            except Exception as e:
                logger.error(f"[后台处理] 元数据提取失败: {e}", exc_info=True)

        # 步骤4: 飞书回调
        if callback_url and feishu_record_id:
            try:
                import requests
                requests.post(callback_url, json={
                    "contract_id": contract_id,
                    "feishu_record_id": feishu_record_id,
                    "feishu_file_key": feishu_file_key,
                    "metadata": contract.metadata_info or {},
                    "reviewer_open_id": reviewer_open_id or ""
                }, timeout=10)
            except Exception as e:
                logger.error(f"[后台处理] 飞书回调失败: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[后台处理] 合同 {contract_id} 处理异常: {e}", exc_info=True)
    finally:
        db.close()


@router.post("/upload")
async def upload_contract(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    auto_extract_metadata: bool = True,
    callback_url: Optional[str] = Form(None),
    feishu_record_id: Optional[str] = Form(None),
    feishu_file_key: Optional[str] = Form(None),
    reviewer_open_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """上传合同文件（快速响应模式）"""
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{file_ext}"
    original_file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(original_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if not get_preprocessor().validate_file(original_file_path)[0]:
        try:
            os.remove(original_file_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="文件验证失败")

    db_contract = ContractDoc(
        title=file.filename,
        status=ContractStatus.PARSING.value,
        original_file_path=original_file_path,
        owner_id=1  # TODO: 替换为真实用户ID
    )
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)

    background_tasks.add_task(
        process_uploaded_file_background,
        db_contract.id,
        original_file_path,
        file_ext,
        auto_extract_metadata,
        callback_url,
        feishu_record_id,
        feishu_file_key,
        reviewer_open_id
    )

    return {
        "contract_id": db_contract.id,
        "title": db_contract.title,
        "status": db_contract.status,
        "message": "文件上传成功，正在后台处理..."
    }


@router.get("/{contract_id}/processing-status")
def get_processing_status(contract_id: int, db: Session = Depends(get_db)):
    """查询处理状态（含分类关联信息）"""
    db.expire_all()
    db.commit()
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    has_docx = bool(contract.original_file_path and contract.original_file_path.endswith('.docx'))
    has_pdf = bool(contract.pdf_converted_path)
    has_metadata = bool(contract.metadata_info)

    processing_status = "completed" if has_metadata else (
        "metadata_extraction" if has_pdf else (
            "pdf_generation" if has_docx else "processing"
        )
    )

    return {
        "contract_id": contract_id,
        "status": contract.status,
        "processing_status": processing_status,
        "has_docx": has_docx,
        "has_pdf": has_pdf,
        "has_metadata": has_metadata,
        "can_load_editor": has_docx,  # docx生成后即可加载编辑器
        "category_id": contract.category_id,  # ✅ 返回分类ID，便于前端调试
        "error_message": contract.metadata_info.get("error") if isinstance(contract.metadata_info, dict) else None
    }


@router.post("/{contract_id}/extract-metadata")
def extract_metadata(contract_id: int, db: Session = Depends(get_db)):
    """手动触发元数据提取 + 自动关联分类"""
    meta = ContractReviewService(db).extract_metadata(contract_id)
    if not meta:
        raise HTTPException(status_code=500, detail="元数据提取失败")
    
    # ✅ 自动关联分类
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if meta.contract_type and contract:
        _resolve_and_update_category(db, contract, meta.contract_type)
        db.commit()
    
    return {"metadata": meta}


@router.post("/{contract_id}/deep-review")
async def start_deep_review(
    contract_id: int,
    stance: str = Form("甲方"),
    updated_metadata: Optional[str] = Form(None),
    enable_custom_rules: bool = Form(False),
    use_langgraph: bool = Form(True),
    use_celery: bool = Form(True),
    transaction_structures: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """启动深度审查（核心增强：更新元数据时自动关联分类）"""
    from app.models.contract_review_task import ContractReviewTask

    # 解析JSON参数
    parsed_transaction_structures = json.loads(transaction_structures) if transaction_structures else None
    parsed_metadata = json.loads(updated_metadata) if updated_metadata else None

    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 保存交易结构
    if parsed_transaction_structures:
        contract.transaction_structures = parsed_transaction_structures

    # ✅ 核心增强：更新元数据时自动关联分类
    if parsed_metadata:
        contract.metadata_info = parsed_metadata
        if "contract_type" in parsed_metadata:
            _resolve_and_update_category(db, contract, parsed_metadata["contract_type"])
    
    db.commit()

    # 创建任务
    task = ContractReviewTask(
        contract_id=contract_id,
        user_id=current_user.id,
        task_type="review",
        stance=stance,
        use_custom_rules=enable_custom_rules,
        use_langgraph=use_langgraph,
        transaction_structures=parsed_transaction_structures,
        metadata_info=parsed_metadata,
        status="pending"
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 异步执行
    if use_celery:
        from app.tasks.contract_review_tasks import perform_contract_review
        celery_task = perform_contract_review.delay(
            task_id=task.id,
            contract_id=contract_id,
            user_id=current_user.id,
            stance=stance,
            use_custom_rules=enable_custom_rules,
            use_langgraph=use_langgraph,
            transaction_structures=parsed_transaction_structures
        )
        task.celery_task_id = celery_task.id
        contract.status = ContractStatus.REVIEWING.value
        db.commit()
        return {
            "success": True,
            "task_id": task.id,
            "celery_task_id": celery_task.id,
            "execution_mode": "async"
        }
    
    # 同步执行（简化版，生产环境建议始终使用异步）
    task.status = "running"
    task.started_at = datetime.utcnow()
    db.commit()
    
    try:
        result = await run_langgraph_review(
            contract_id=contract_id,
            stance=stance,
            updated_metadata=parsed_metadata,
            enable_custom_rules=enable_custom_rules,
            user_id=current_user.id,
            transaction_structures=parsed_transaction_structures
        )
        task.status = "completed" if result.get("success") else "failed"
        task.completed_at = datetime.utcnow()
        db.commit()
        return {"success": result.get("success"), "task_id": task.id, "execution_mode": "sync"}
    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 其他接口（保持简洁） ====================

@router.get("/{contract_id}/review-results")
def get_review_results(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    return {
        "status": contract.status,
        "metadata": contract.metadata_info,
        "stance": contract.stance,
        "review_items": [item.__dict__ for item in contract.review_items]
    }


@router.get("/{contract_id}/onlyoffice-config")
def get_onlyoffice_config(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    backend_internal_url = "http://backend:8000"
    file_url = f"{backend_internal_url}/storage/uploads/{os.path.basename(contract.original_file_path)}"
    callback_url = f"{backend_internal_url}/api/contract/{contract.id}/callback"
    
    config = {
        "document": {
            "fileType": contract.original_file_path.rsplit(".", 1)[-1],
            "key": f"{contract.id}_{int(datetime.now().timestamp())}",
            "title": contract.title,
            "url": file_url,
        },
        "editorConfig": {
            "mode": "edit",
            "user": {"id": "1", "name": "法务管理员"},
            "callbackUrl": callback_url,
            "customization": {"features": {"spellcheck": False}}
        }
    }
    return {"config": config, "token": OfficeTokenManager.create_token(config)}


@router.post("/{contract_id}/run-graph", status_code=202)
def run_graph(contract_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_langgraph_review_async, contract_id)
    return {"success": True, "message": "LangGraph任务已调度", "contract_id": contract_id}


# ==================== 修订相关 API ====================

class ReviewItemUpdate(BaseModel):
    explanation: str
    suggestion: str

class ApplyRevisionRequest(BaseModel):
    review_item_ids: List[int]
    auto_apply: bool = False

@router.put("/review-items/{item_id}")
def update_review_item(item_id: int, update_data: ReviewItemUpdate, db: Session = Depends(get_db)):
    item = db.query(ContractReviewItem).filter(ContractReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="审查意见不存在")
    item.explanation = update_data.explanation
    item.suggestion = update_data.suggestion
    db.commit()
    return {"success": True}


@router.post("/{contract_id}/apply-revisions")
def apply_revisions(contract_id: int, request_data: ApplyRevisionRequest, db: Session = Depends(get_db)):
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    items = db.query(ContractReviewItem).filter(
        ContractReviewItem.id.in_(request_data.review_item_ids) if not request_data.auto_apply 
        else ContractReviewItem.contract_id == contract_id
    ).all()
    
    if not items:
        raise HTTPException(status_code=400, detail="无审查意见可应用")
    
    # 处理文件格式（PDF/DOC → DOCX）
    working_path = contract.original_file_path
    file_ext = working_path.rsplit('.', 1)[-1].lower()
    
    if file_ext in ('pdf', 'doc'):
        from app.services.common.docx_editor import DocxEditor
        if file_ext == 'pdf':
            success, path, _ = DocxEditor.convert_pdf_to_docx(working_path)
            if not success:
                raise HTTPException(status_code=500, detail="PDF转换失败")
            working_path = path
        else:  # .doc
            from app.services.common.converter import convert_doc_to_docx
            success, filename, _ = convert_doc_to_docx(os.path.basename(working_path))
            if not success:
                raise HTTPException(status_code=500, detail=".doc转换失败")
            working_path = os.path.join(os.path.dirname(working_path), filename)
    
    # 应用修订
    revision_path = working_path.replace('.docx', '.revised.docx').replace('.converted.', '.')
    from app.services.common.docx_editor import DocxEditor
    editor = DocxEditor(working_path)
    results = editor.apply_revisions([{"quote": i.quote, "suggestion": i.suggestion} for i in items])
    editor.save(revision_path)
    
    contract.final_docx_path = revision_path
    contract.status = ContractStatus.APPROVED.value
    db.commit()
    
    # 生成OnlyOffice配置
    file_url = f"http://backend:8000/storage/uploads/{os.path.basename(revision_path)}"
    config = {
        "document": {
            "fileType": "docx",
            "key": f"{contract.id}_revised_{int(datetime.now().timestamp())}",
            "title": os.path.basename(revision_path),
            "url": file_url,
        },
        "editorConfig": {"mode": "edit", "user": {"id": "1", "name": "法务管理员"}}
    }
    
    return {
        "success": True,
        "message": f"已应用 {results['applied']} 条修订（{results['not_found']} 条未匹配）",
        "revision_path": revision_path,
        "config": config,
        "token": OfficeTokenManager.create_token(config)
    }


@router.get("/{contract_id}/revision-config")
def get_revision_config(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract or not contract.final_docx_path:
        raise HTTPException(status_code=404, detail="修订版文档不存在")
    
    file_url = f"http://backend:8000/storage/uploads/{os.path.basename(contract.final_docx_path)}"
    config = get_review_mode_config(
        file_url=file_url,
        document_key=f"{contract.id}_revised_{int(datetime.now().timestamp())}",
        title=os.path.basename(contract.final_docx_path),
        callback_url=f"http://backend:8000/api/contract/{contract.id}/callback",
        review_items=[]
    )
    return {"config": config, "token": OfficeTokenManager.create_token(config)}


@router.get("/{contract_id}/download")
def download_original_contract(contract_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract or not contract.original_file_path:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(contract.original_file_path, filename=contract.title)


@router.get("/{contract_id}/download-revised")
def download_revised_contract(contract_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    path = contract.final_docx_path or contract.original_file_path
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=os.path.basename(path))


class CallbackRequest(BaseModel):
    key: str
    status: int
    users: List[str] = []
    actions: List[dict] = []
    token: str

@router.post("/{contract_id}/callback")
def onlyoffice_callback(contract_id: int, callback_data: CallbackRequest, db: Session = Depends(get_db)):
    logger.debug(f"[OnlyOffice Callback] contract_id={contract_id} status={callback_data.status}")
    return {"error": 0}


# ==================== 任务历史管理 ====================

@router.get("/review-tasks")
async def get_review_tasks(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.contract_review_task import ContractReviewTask
    query = db.query(ContractReviewTask).filter(ContractReviewTask.user_id == current_user.id)
    if status:
        query = query.filter(ContractReviewTask.status == status)
    tasks = query.order_by(ContractReviewTask.created_at.desc()).offset(skip).limit(limit).all()
    return [{
        "id": t.id,
        "contract_id": t.contract_id,
        "status": t.status,
        "task_type": t.task_type,
        "stance": t.stance,
        "transaction_structures": t.transaction_structures,
        "result_summary": t.result_summary,
        "created_at": t.created_at.isoformat()
    } for t in tasks]


@router.get("/review-tasks/{task_id}")
async def get_review_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.contract_review_task import ContractReviewTask
    task = db.query(ContractReviewTask).filter(
        ContractReviewTask.id == task_id,
        ContractReviewTask.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": task.id,
        "contract_id": task.contract_id,
        "status": task.status,
        "metadata_info": task.metadata_info,
        "result_summary": task.result_summary,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat()
    }


@router.put("/review-tasks/{task_id}/pause")
async def pause_review_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.contract_review_task import ContractReviewTask
    task = db.query(ContractReviewTask).filter(
        ContractReviewTask.id == task_id,
        ContractReviewTask.user_id == current_user.id
    ).first()
    if not task or task.status != "running":
        raise HTTPException(status_code=400, detail="无法暂停该任务")
    
    if task.celery_task_id:
        try:
            from app.tasks.celery_app import celery_app
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        except Exception as e:
            logger.warning(f"撤销Celery任务失败: {e}")
    
    task.status = "paused"
    db.commit()
    return {"message": "任务已暂停"}


@router.put("/review-tasks/{task_id}/resume")
async def resume_review_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.contract_review_task import ContractReviewTask
    from app.tasks.contract_review_tasks import resume_contract_review
    task = db.query(ContractReviewTask).filter(
        ContractReviewTask.id == task_id,
        ContractReviewTask.user_id == current_user.id
    ).first()
    if not task or task.status != "paused":
        raise HTTPException(status_code=400, detail="无法恢复该任务")
    
    celery_task = resume_contract_review.delay(task_id)
    return {"message": "任务已恢复", "celery_task_id": celery_task.id}


@router.delete("/review-tasks/{task_id}")
async def delete_review_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.contract_review_task import ContractReviewTask
    task = db.query(ContractReviewTask).filter(
        ContractReviewTask.id == task_id,
        ContractReviewTask.user_id == current_user.id
    ).first()
    if not task or task.status == "running":
        raise HTTPException(status_code=400, detail="无法删除该任务")
    
    if task.status == "pending" and task.celery_task_id:
        try:
            from app.tasks.celery_app import celery_app
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        except Exception as e:
            logger.warning(f"撤销Celery任务失败: {e}")
    
    db.delete(task)
    db.commit()
    return {"message": "任务已删除"}


@router.get("/{contract_id}/health-assessment")
def get_health_assessment(contract_id: int, db: Session = Depends(get_db)):
    from app.services.contract_review.health_assessment import contract_health_assessor
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    return contract_health_assessor.calculate_health_score(contract.review_items)