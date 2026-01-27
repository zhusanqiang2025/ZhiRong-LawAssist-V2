# backend/app/api/contract_router.py
import os
import uuid
import shutil
import asyncio
import json  # ⭐ 新增：用于解析JSON字符串
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.contract import ContractDoc, ContractReviewItem, ContractStatus
from app.models.user import User
from app.schemas import ContractDocOut, ContractMetadataSchema
from app.services.contract_review_service import ContractReviewService
from app.services.langgraph_review_service import run_langgraph_review, run_langgraph_review_async
from app.services.document_preprocessor import get_preprocessor, ConversionResult
from app.services.converter import convert_to_pdf_via_onlyoffice
from fastapi import BackgroundTasks
from app.utils.office_utils import OfficeTokenManager
from app.utils.onlyoffice_config import get_onlyoffice_config_with_plugins, get_review_mode_config
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Contract Review System"]
)

UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
    """
    后台任务：处理上传的文件

    流程：
    1. 格式转换 (.doc → .docx)
    2. PDF 预览生成
    3. 元数据提取（如果启用）
    4. 飞书回调（如果提供 callback_url）

    Args:
        contract_id: 合同ID
        original_file_path: 原始文件路径
        file_ext: 文件扩展名
        auto_extract_metadata: 是否自动提取元数据
        callback_url: 飞书回调URL（可选）
        feishu_record_id: 飞书多维表记录ID（可选）
        feishu_file_key: 飞书文件标识（可选）
        reviewer_open_id: 审查人 OPEN_ID（可选，用于发送立场选择卡片）
    """
    from app.database import SessionLocal
    import logging
    import traceback
    import time

    logger = logging.getLogger(__name__)
    db = SessionLocal()

    start_time = time.time()

    try:
        logger.info(f"[后台处理] 开始处理合同 {contract_id} 的文件: {original_file_path}")

        # 获取合同记录
        contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
        if not contract:
            logger.error(f"[后台处理] 合同 {contract_id} 不存在")
            return

        # 使用预处理中心进行格式转换
        from app.services.document_preprocessor import get_preprocessor, ConversionResult
        preprocessor = get_preprocessor()

        # ========== 步骤1: 格式转换 (.doc → .docx) ==========
        logger.info(f"[后台处理] 步骤1: 开始格式转换...")
        step1_start = time.time()

        conversion_result, working_file_path, metadata = preprocessor.convert_to_docx(
            file_path=original_file_path
        )

        step1_elapsed = time.time() - step1_start
        logger.info(f"[后台处理] 格式转换完成 (耗时 {step1_elapsed:.2f}s): result={conversion_result}")

        # 转换成功后删除原始文件
        if conversion_result == ConversionResult.SUCCESS and working_file_path != original_file_path:
            try:
                os.remove(original_file_path)
                logger.info(f"[后台处理] 已删除原始文件: {original_file_path}")
            except Exception as e:
                logger.warning(f"[后台处理] 删除原始文件失败: {e}")

        if conversion_result == ConversionResult.FAILED:
            # 转换失败，更新状态为 error
            contract.status = ContractStatus.DRAFT.value  # 保持draft，但在metadata_info中标记错误
            contract.metadata_info = {"error": f"文件格式转换失败: {working_file_path}", "processing_status": "conversion_failed"}
            db.commit()
            logger.error(f"[后台处理] 格式转换失败: {working_file_path}")
            return

        # 更新文件路径（格式转换完成，立即更新数据库）
        contract.original_file_path = working_file_path
        contract.status = ContractStatus.DRAFT.value  # ⭐ 格式转换完成即可改为 draft
        db.commit()

        logger.info(f"[后台处理] 文件路径已更新，前端可以获取编辑器配置")

        # ========== 步骤2: PDF 预览生成 ==========
        logger.info(f"[后台处理] 步骤2: 生成PDF预览...")
        step2_start = time.time()

        pdf_path = working_file_path
        pdf_name = os.path.basename(working_file_path).rsplit(".", 1)[0] + ".pdf"
        pdf_full_path = os.path.join(UPLOAD_DIR, pdf_name)

        success, pdf_result = convert_to_pdf_via_onlyoffice(os.path.basename(working_file_path))
        if success:
            with open(pdf_full_path, "wb") as f:
                f.write(pdf_result)
            pdf_path = pdf_full_path
            logger.info(f"[后台处理] PDF生成成功: {pdf_path}")
        else:
            logger.warning(f"[后台处理] PDF生成失败，将使用docx作为预览")

        step2_elapsed = time.time() - step2_start
        logger.info(f"[后台处理] PDF生成完成 (耗时 {step2_elapsed:.2f}s)")

        # 更新PDF路径
        contract.pdf_converted_path = pdf_path
        contract.status = ContractStatus.DRAFT.value  # 处理完成，状态改为draft
        db.commit()

        # ========== 步骤3: 元数据提取（如果启用）==========
        if auto_extract_metadata:
            logger.info(f"[后台处理] 步骤3: 开始元数据提取...")
            step3_start = time.time()

            try:
                service = ContractReviewService(db)
                meta = service.extract_metadata(contract_id)

                step3_elapsed = time.time() - step3_start
                logger.info(f"[后台处理] 元数据提取完成 (耗时 {step3_elapsed:.2f}s)")

                if meta:
                    logger.info(f"[后台处理] 元数据提取成功: contract_name={meta.contract_name}, parties={meta.parties}, contract_type={meta.contract_type}")
                else:
                    logger.warning(f"[后台处理] 元数据提取失败（返回None）")
            except Exception as e:
                logger.error(f"[后台处理] 元数据提取出错: {str(e)}")
                logger.error(f"[后台处理] 错误堆栈: {traceback.format_exc()}")

        # ========== 步骤4: 飞书回调（如果提供 callback_url）==========
        if callback_url and feishu_record_id:
            logger.info(f"[后台处理] 步骤4: 执行飞书回调...")
            step4_start = time.time()

            try:
                # 准备回调数据
                callback_data = {
                    "contract_id": contract_id,
                    "feishu_record_id": feishu_record_id,
                    "feishu_file_key": feishu_file_key,
                    "metadata": contract.metadata_info if contract and contract.metadata_info else {},
                    "reviewer_open_id": reviewer_open_id or ""  # 添加审查人 OPEN_ID
                }

                # 发送回调请求（使用 requests，非阻塞模式）
                import requests
                response = requests.post(
                    callback_url,
                    json=callback_data,
                    timeout=10
                )

                if response.status_code == 200:
                    logger.info(f"[后台处理] ✅ 飞书回调成功 | URL: {callback_url}")
                else:
                    logger.warning(f"[后台处理] ⚠️  飞书回调失败 | 状态码: {response.status_code} | 响应: {response.text[:200]}")

                step4_elapsed = time.time() - step4_start
                logger.info(f"[后台处理] 飞书回调完成 (耗时 {step4_elapsed:.2f}s)")

            except Exception as e:
                # 回调失败不影响主流程
                logger.error(f"[后台处理] ⚠️  飞书回调异常: {str(e)}")
                logger.error(f"[后台处理] ⚠️  回调URL: {callback_url}")
        elif callback_url:
            logger.warning(f"[后台处理] ⚠️  提供了 callback_url 但缺少 feishu_record_id，跳过回调")
        else:
            logger.debug(f"[后台处理] 无 callback_url，跳过飞书回调")

        # 总耗时
        total_elapsed = time.time() - start_time
        logger.info(f"[后台处理] 合同 {contract_id} 处理完成 (总耗时 {total_elapsed:.2f}s)")

    except Exception as e:
        logger.error(f"[后台处理] 合同 {contract_id} 处理出错: {str(e)}")
        logger.error(f"[后台处理] 错误堆栈: {traceback.format_exc()}")
    finally:
        db.close()
        logger.info(f"[后台处理] 合同 {contract_id} 数据库会话已关闭")


def extract_metadata_background(contract_id: int, db: Session = None):
    """
    后台任务：自动提取合同元数据

    ⚠️ 已弃用：请使用 process_uploaded_file_background
    保留此函数以兼容旧代码
    """
    process_uploaded_file_background(contract_id, "", "", False)


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
    """
    上传合同文件（优化版本 - 快速响应）

    支持格式：.doc, .docx, .pdf, .txt, .rtf, .odt
    统一转换为 .docx 格式进行处理

    ⭐ 优化：先返回基本信息，后台异步处理耗时操作
    - 格式转换 (.doc → .docx): 后台处理
    - PDF 预览生成: 后台处理
    - 元数据提取: 后台处理

    ⭐ 飞书集成：支持元数据提取完成后的回调
    - callback_url: 飞书回调URL（可选）
    - feishu_record_id: 飞书多维表记录ID（可选）
    - feishu_file_key: 飞书文件标识（可选）
    - reviewer_open_id: 审查人 OPEN_ID（可选，用于发送立场选择卡片）

    响应时间：1-2秒（原20-45秒）
    """
    import time
    start_time = time.time()

    # ========== 步骤1: 快速保存原始文件 (约1秒) ==========
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{file_ext}"
    original_file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(original_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    logger.info(f"[快速上传] 原始文件保存完成: {original_file_path} (耗时 {time.time() - start_time:.2f}s)")

    # ========== 步骤2: 基础验证 (约0.5秒) ==========
    preprocessor = get_preprocessor()
    is_valid, error_msg = preprocessor.validate_file(original_file_path)

    if not is_valid:
        try:
            os.remove(original_file_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"文件验证失败: {error_msg}")

    # 检测格式
    file_format = preprocessor.detect_format(original_file_path)

    logger.info(f"[快速上传] 文件验证完成: 格式={file_format.value} (耗时 {time.time() - start_time:.2f}s)")

    # ========== 步骤3: 立即创建数据库记录 (约0.5秒) ==========
    db_contract = ContractDoc(
        title=file.filename,
        status=ContractStatus.PARSING.value,  # ⭐ 设置为解析中状态
        original_file_path=original_file_path,  # 临时路径，后台会更新
        pdf_converted_path=None,  # 后台生成
        owner_id=1  # 临时，后面接用户系统
    )
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)

    logger.info(f"[快速上传] 数据库记录创建完成: contract_id={db_contract.id} (耗时 {time.time() - start_time:.2f}s)")

    # ========== 步骤4: 提交后台任务处理 ==========
    logger.info(f"[快速上传] 提交后台处理任务: contract_id={db_contract.id}")

    # 记录飞书集成参数（如果有）
    if callback_url:
        logger.info(f"[快速上传] 📌 飞书集成模式 | callback_url: {callback_url} | feishu_record_id: {feishu_record_id} | reviewer_open_id: {reviewer_open_id[:20] if reviewer_open_id else '(空)'}...")

    background_tasks.add_task(
        process_uploaded_file_background,
        db_contract.id,
        original_file_path,
        file_ext,
        auto_extract_metadata,
        callback_url,
        feishu_record_id,
        feishu_file_key,
        reviewer_open_id  # 添加审查人 OPEN_ID
    )

    # ========== 步骤5: 立即返回基本信息 ==========
    total_elapsed = time.time() - start_time
    logger.info(f"[快速上传] 响应返回，总耗时: {total_elapsed:.2f}s")

    response = {
        "contract_id": db_contract.id,
        "id": db_contract.id,
        "title": db_contract.title,
        "status": db_contract.status,  # "parsing" - 表示正在后台处理
        "message": "文件上传成功，正在后台处理...",
        "original_file_path": db_contract.original_file_path,
        "pdf_converted_path": None,  # 后台生成
        "final_docx_path": None,
        "metadata_info": None,
        "stance": None,
        "review_items": [],
        "created_at": db_contract.created_at,
        "updated_at": db_contract.updated_at,
        "config": None,  # 暂不提供，等处理完成
        "token": None,
        "filename": db_contract.title,
        "preprocess_info": {
            "original_format": file_format.value,
            "processing_status": "background",
            "estimated_time": "20-45秒"
        },
        "ai_processing": {
            "auto_extract_metadata": auto_extract_metadata,
            "metadata_status": "pending",
            "message": "文件正在后台处理中（格式转换 + PDF生成 + 元数据提取）"
        }
    }

    return response


@router.get("/{contract_id}/processing-status")
def get_processing_status(contract_id: int, db: Session = Depends(get_db)):
    """
    查询文件处理状态

    返回后台文件处理任务的进度和状态：
    - status: draft (处理完成) | parsing (处理中)
    - has_pdf: PDF是否生成
    - has_metadata: 元数据是否提取
    - processing_status: 详细处理状态
    """
    # 强制刷新会话，确保看到最新的数据库更改
    db.expire_all()
    db.commit()

    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    logger.info(f"[处理状态查询] contract_id={contract_id}, status={contract.status}")

    # 判断处理状态
    is_processing = contract.status == ContractStatus.PARSING.value
    has_docx = bool(contract.original_file_path and contract.original_file_path.endswith('.docx'))
    has_pdf = bool(contract.pdf_converted_path)
    has_metadata = bool(contract.metadata_info)

    # 检查是否有错误
    processing_status = "processing"
    error_message = None
    can_load_editor = False  # ⭐ 新增：是否可以加载编辑器

    if contract.metadata_info and isinstance(contract.metadata_info, dict):
        if contract.metadata_info.get("processing_status") == "conversion_failed":
            processing_status = "error"
            error_message = contract.metadata_info.get("error", "文件格式转换失败")
        elif has_metadata:
            processing_status = "completed"
            can_load_editor = True
        elif has_pdf and not has_metadata:
            processing_status = "metadata_extraction"
            can_load_editor = True  # ⭐ PDF生成后就可以加载编辑器
        elif has_docx and not has_pdf:
            processing_status = "pdf_generation"
            can_load_editor = True  # ⭐ docx格式转换后就可以加载编辑器（优先级）
        else:
            processing_status = "format_conversion"
    elif has_metadata:
        processing_status = "completed"
        can_load_editor = True
    elif has_docx:
        # 有 docx 文件就可以加载编辑器
        can_load_editor = True
        if not has_pdf:
            processing_status = "pdf_generation"
        elif not has_metadata:
            processing_status = "metadata_extraction"

    return {
        "contract_id": contract_id,
        "status": contract.status,  # draft | parsing
        "is_processing": is_processing,
        "has_docx": has_docx,  # ⭐ 新增
        "has_pdf": has_pdf,
        "pdf_path": contract.pdf_converted_path,
        "has_metadata": has_metadata,
        "metadata": contract.metadata_info,
        "processing_status": processing_status,
        "can_load_editor": can_load_editor,  # ⭐ 新增：是否可以加载编辑器
        "error_message": error_message,
        "message": {
            "processing": "文件正在后台处理中（格式转换 + PDF生成 + 元数据提取）",
            "format_conversion": "正在转换文件格式...",
            "pdf_generation": "正在生成PDF预览...",
            "metadata_extraction": "正在提取合同元数据...",
            "completed": "文件处理完成",
            "error": f"处理失败: {error_message}" if error_message else "处理失败"
        }.get(processing_status, "未知状态")
    }


@router.get("/{contract_id}/metadata-status")
def get_metadata_status(contract_id: int, db: Session = Depends(get_db)):
    """
    查询元数据提取状态

    返回元数据是否存在，以及处理状态
    """
    # ⭐ 修复：强制刷新会话，确保看到最新的数据库更改
    db.expire_all()
    db.commit()

    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # ⭐ 添加调试日志
    logger = logging.getLogger(__name__)
    logger.info(f"[元数据状态查询] contract_id={contract_id}, metadata_info存在: {bool(contract.metadata_info)}")
    if contract.metadata_info:
        logger.info(f"[元数据状态查询] metadata_info内容: {list(contract.metadata_info.keys()) if isinstance(contract.metadata_info, dict) else type(contract.metadata_info)}")

    return {
        "contract_id": contract_id,
        "has_metadata": bool(contract.metadata_info),
        "metadata": contract.metadata_info,
        "status": "completed" if contract.metadata_info else "pending"
    }

@router.post("/{contract_id}/extract-metadata")
def extract_metadata(contract_id: int, db: Session = Depends(get_db)):
    service = ContractReviewService(db)
    meta = service.extract_metadata(contract_id)
    if meta is None:
        raise HTTPException(status_code=500, detail="元数据提取失败")
    return {"metadata": meta}

@router.post("/{contract_id}/deep-review")
async def start_deep_review(
    contract_id: int,
    stance: str = Form("甲方"),
    updated_metadata: Optional[str] = Form(None),  # ⭐ 修改：接收JSON字符串
    enable_custom_rules: bool = Form(False),
    use_langgraph: bool = Form(True),
    use_celery: bool = Form(True),  # ⭐ 新增: 异步模式开关
    transaction_structures: Optional[str] = Form(None),  # ⭐ 修改：接收JSON字符串
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    启动深度合同审查 (支持任务历史管理)

    参数:
    - use_langgraph: 是否使用新的 LangGraph 三阶段审查系统（默认 True）
    - use_celery: 是否使用异步模式 (默认 True)
                    - True: 提交Celery任务,立即返回task_id (适用于长文本)
                    - False: 同步执行,等待完成后返回结果 (适用于短文本)
    - transaction_structures: 用户选择的交易结构列表 (新增)

    新系统特性:
    - 三阶段审查: Profile → Relation → Review
    - 动态规则加载: 管理员修改数据库规则后立即生效
    - 知识图谱集成: 支持基于合同类型的动态推演
    - 交易结构规则: 支持基于用户选择的交易结构加载对应规则 ⭐ 新增
    - 任务历史管理: 记录每次审查任务,支持暂停/恢复 ⭐ 新增
    """
    # ⭐ 添加调试日志
    logger = logging.getLogger(__name__)
    logger.info(f"[API] 收到深度审查请求: contract_id={contract_id}, stance={stance}")
    logger.info(f"[API] updated_metadata类型: {type(updated_metadata)}, 长度: {len(updated_metadata) if updated_metadata else 0}")
    logger.info(f"[API] updated_metadata内容（前200字符）: {updated_metadata[:200] if updated_metadata else 'None'}")

    from app.models.contract_review_task import ContractReviewTask

    # ========== ⭐ 解析交易结构JSON字符串 ==========
    parsed_transaction_structures = None
    if transaction_structures:
        try:
            parsed_transaction_structures = json.loads(transaction_structures)
            if not isinstance(parsed_transaction_structures, list):
                raise ValueError("transaction_structures must be a list")
            logger.info(f"[API] ✅ 解析交易结构成功: {parsed_transaction_structures}")
        except json.JSONDecodeError as e:
            logger.error(f"[API] ❌ 解析交易结构JSON失败: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"transaction_structures格式错误: 期望JSON数组字符串，收到: {transaction_structures[:100]}"
            )
        except ValueError as e:
            logger.error(f"[API] ❌ 交易结构类型错误: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"transaction_structures必须是数组格式"
            )
    else:
        logger.info(f"[API] 交易结构为空，使用默认规则")

    # ========== ⭐ 解析元数据JSON字符串 ==========
    parsed_metadata = None
    if updated_metadata:
        try:
            parsed_metadata = json.loads(updated_metadata)
            logger.info(f"[API] ✅ 解析元数据成功: contract_type={parsed_metadata.get('contract_type')}, parties={parsed_metadata.get('parties')}")
        except json.JSONDecodeError as e:
            logger.error(f"[API] ❌ 解析元数据JSON失败: {e}")
            logger.error(f"[API] 收到的updated_metadata: {updated_metadata[:500]}")
            raise HTTPException(
                status_code=422,
                detail=f"updated_metadata格式错误: 期望JSON对象字符串。错误: {str(e)}"
            )
    else:
        logger.info(f"[API] 元数据为空，使用数据库中的元数据")

    # ========== 保存交易结构到 ContractDoc ==========
    if parsed_transaction_structures:
        contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
        if contract:
            contract.transaction_structures = parsed_transaction_structures
            db.commit()
            logger.info(f"[API] 保存交易结构到合同 {contract_id}: {parsed_transaction_structures}")

    # ========== 创建任务记录 ==========
    task = ContractReviewTask(
        contract_id=contract_id,
        user_id=current_user.id,
        task_type="review",
        stance=stance,
        use_custom_rules=enable_custom_rules,
        use_langgraph=use_langgraph,
        transaction_structures=parsed_transaction_structures,
        metadata_info=parsed_metadata,  # ⭐ 使用解析后的元数据
        status="pending"
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    logger.info(f"[API] 创建审查任务: task_id={task.id}, contract_id={contract_id}")

    # ========== 模式选择: 同步 vs 异步 ==========
    if use_celery:
        # ========== 异步模式: 提交Celery任务 ==========
        logger.info(f"[API] 启动异步审查任务: task_id={task.id}")

        # 提交Celery任务
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

        # 更新Celery任务ID
        task.celery_task_id = celery_task.id

        # ⭐ 立即更新合同状态为 REVIEWING，避免前端轮询时收到 draft 状态
        contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
        if contract:
            contract.status = ContractStatus.REVIEWING.value
            logger.info(f"[API] 合同 {contract_id} 状态已更新为 REVIEWING")

        db.commit()

        # 立即返回任务信息
        return {
            "success": True,
            "message": "审查任务已创建",
            "task_id": task.id,
            "celery_task_id": celery_task.id,
            "status": "pending",
            "execution_mode": "async"
        }

    else:
        # ========== 同步模式: 直接执行审查 ==========
        logger.info(f"[API] 启动同步审查任务: task_id={task.id}")

        try:
            # 更新任务状态为running
            task.status = "running"
            task.started_at = datetime.utcnow()
            db.commit()

            # 选择审查系统
            if use_langgraph:
                # V2: LangGraph系统
                result = await run_langgraph_review(
                    contract_id=contract_id,
                    stance=stance,
                    updated_metadata=parsed_metadata,  # 修复：传递解析后的字典而不是JSON字符串
                    enable_custom_rules=enable_custom_rules,
                    user_id=current_user.id,
                    transaction_structures=parsed_transaction_structures
                )
            else:
                # V1: 传统系统
                service = ContractReviewService(db)
                success = service.run_deep_review(
                    contract_id=contract_id,
                    stance=stance,
                    updated_metadata=parsed_metadata,  # 修复：传递解析后的字典而不是JSON字符串
                    enable_custom_rules=enable_custom_rules,
                    user_id=current_user.id,
                    transaction_structures=parsed_transaction_structures
                )
                result = {"success": success, "message": "审查完成" if success else "审查失败"}

            # 更新任务状态
            if result.get("success"):
                task.status = "completed"
                task.completed_at = datetime.utcnow()

                # 保存结果摘要
                contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
                if contract:
                    review_items_count = len(contract.review_items)
                    severity_counts = {
                        "Critical": len([i for i in contract.review_items if i.severity == "Critical"]),
                        "High": len([i for i in contract.review_items if i.severity == "High"]),
                        "Medium": len([i for i in contract.review_items if i.severity == "Medium"]),
                        "Low": len([i for i in contract.review_items if i.severity == "Low"]),
                    }
                    task.result_summary = {
                        "total_items": review_items_count,
                        "by_severity": severity_counts
                    }

                logger.info(f"[API] 同步审查任务完成: task_id={task.id}")
            else:
                task.status = "failed"
                task.error_message = result.get("message", "审查失败")
                logger.error(f"[API] 同步审查任务失败: task_id={task.id}")

            db.commit()

            # 返回审查结果
            return {
                "success": result.get("success", False),
                "message": result.get("message"),
                "task_id": task.id,
                "status": task.status,
                "execution_mode": "sync",
                "result_summary": task.result_summary if task.status == "completed" else None
            }

        except Exception as e:
            # 异常处理
            logger.exception(f"[API] 同步审查任务异常: task_id={task.id}, error={str(e)}")

            task.status = "failed"
            task.error_message = str(e)
            db.commit()

            raise HTTPException(status_code=500, detail=f"审查失败: {str(e)}")

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

    # OnlyOffice 服务器需要使用内部地址访问后端（Docker 网络内部）
    backend_internal_url = "http://backend:8000"
    file_url = f"{backend_internal_url}/storage/uploads/{os.path.basename(contract.original_file_path)}"
    callback_url = f"{backend_internal_url}/api/v1/contract-review/{contract.id}/callback"

    config = {
        "document": {
            "fileType": contract.original_file_path.rsplit(".", 1)[-1],
            "key": str(contract.id) + "_" + str(int(datetime.now().timestamp())),
            "title": contract.title,
            "url": file_url,
        },
        "editorConfig": {
            "mode": "edit",
            "user": {"id": "1", "name": "法务管理员"},
            "callbackUrl": callback_url,
            "customization": {
                "features": {
                    "spellcheck": False  # 禁用拼写检查，避免中文显示红色波浪线
                }
            }
        }
    }

    token = OfficeTokenManager.create_token(config)
    return {"config": config, "token": token}


@router.post("/{contract_id}/run-graph", status_code=202)
def run_graph(
    contract_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    运行 LangGraph 合同审查（后台任务）

    使用新的三阶段审查系统：
    - Profile: 合同法律画像
    - Relation: 法律关系与适用法
    - Review: 风险与责任审查（使用 RuleAssembler 动态加载规则）
    """
    background_tasks.add_task(
        run_langgraph_review_async,
        contract_id
    )
    return {
        "success": True,
        "message": "LangGraph 任务已调度",
        "contract_id": contract_id,
        "system": "langgraph"
    }


@router.post("/{contract_id}/run-graph/langchain", status_code=202)
def run_graph_langchain(contract_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """New LangGraph+LangChain runner route (background)."""
    raise HTTPException(status_code=501, detail="功能暂未实现")


# ==================== 审查意见编辑与文档修订 API ====================

from pydantic import BaseModel


class ReviewItemUpdate(BaseModel):
    """审查意见更新请求"""
    explanation: str
    suggestion: str


class ApplyRevisionRequest(BaseModel):
    """应用修订请求"""
    review_item_ids: list[int]  # 要应用的审查意见ID列表
    auto_apply: bool = False     # 是否自动应用所有建议


@router.put("/review-items/{item_id}")
def update_review_item(
    item_id: int,
    update_data: ReviewItemUpdate,
    db: Session = Depends(get_db)
):
    """更新单条审查意见"""
    item = db.query(ContractReviewItem).filter(ContractReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="审查意见不存在")

    item.explanation = update_data.explanation
    item.suggestion = update_data.suggestion
    db.commit()
    db.refresh(item)

    return {
        "success": True,
        "item": item.__dict__
    }


@router.post("/{contract_id}/apply-revisions")
def apply_revisions(
    contract_id: int,
    request_data: ApplyRevisionRequest,
    db: Session = Depends(get_db)
):
    """
    应用审查修订，生成修订版文档

    流程：
    1. 获取原始文档（Word 或 PDF）
    2. PDF 自动转换为 Word 格式
    3. 对每条审查意见，直接替换原文为建议文本
    4. 保存修订版文档
    5. 返回修订版文档配置
    """
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 获取要应用的审查意见
    if request_data.auto_apply:
        items = db.query(ContractReviewItem).filter(
            ContractReviewItem.contract_id == contract_id
        ).all()
    else:
        items = db.query(ContractReviewItem).filter(
            ContractReviewItem.id.in_(request_data.review_item_ids)
        ).all()

    if not items:
        raise HTTPException(status_code=400, detail="没有要应用的审查意见")

    logger.info(f"[应用修订] 合同 {contract_id}, 准备应用 {len(items)} 条审查意见")

    # 检查原始文件格式
    original_path = contract.original_file_path
    file_ext = original_path.rsplit('.', 1)[-1].lower() if '.' in original_path else ''
    is_pdf = file_ext == 'pdf'
    is_doc = file_ext == 'doc'

    logger.info(f"[应用修订] 原始文件: {original_path}, 格式: {file_ext}")

    # 处理 PDF 或 .doc 文件：先转换为 .docx
    working_path = original_path
    if is_pdf or is_doc:
        from app.services.docx_editor import DocxEditor

        if is_pdf:
            # PDF 转 docx
            logger.info(f"[应用修订] 检测到 PDF 文件，开始转换...")
            success, converted_path, msg = DocxEditor.convert_pdf_to_docx(original_path)
            if not success:
                logger.error(f"[应用修订] PDF 转换失败: {msg}")
                raise HTTPException(status_code=500, detail=f"PDF 转换失败: {msg}")
            working_path = converted_path
            logger.info(f"[应用修订] PDF 转换成功: {converted_path}")

        elif is_doc:
            # .doc 转 .docx（使用已有的 converter）
            from app.services.converter import convert_doc_to_docx
            filename = os.path.basename(original_path)
            logger.info(f"[应用修订] 检测到 .doc 文件，开始转换...")
            success, docx_filename, msg = convert_doc_to_docx(filename)
            if success and docx_filename:
                working_path = os.path.join(os.path.dirname(original_path), docx_filename)
                logger.info(f"[应用修订] .doc 转换成功: {working_path}")
            else:
                logger.error(f"[应用修订] .doc 转换失败: {msg}")
                raise HTTPException(status_code=500, detail=f".doc 转换失败: {msg}")

    # 生成修订版文档路径
    revision_path = working_path.replace('.docx', '.revised.docx')
    if '.converted.' in revision_path:
        revision_path = revision_path.replace('.converted.', '.')

    logger.info(f"[应用修订] 修订版将保存至: {revision_path}")

    # 使用新的编辑器应用修订
    try:
        from app.services.docx_editor import DocxEditor

        # 创建编辑器
        logger.info(f"[应用修订] 初始化 DocxEditor...")
        editor = DocxEditor(working_path)

        # 准备修订数据
        revisions = [
            {"quote": item.quote, "suggestion": item.suggestion}
            for item in items
        ]

        logger.info(f"[应用修订] 准备应用 {len(revisions)} 条修订")

        # 打印前3条修订内容用于调试
        for i, rev in enumerate(revisions[:3]):
            logger.info(f"[应用修订] 修订{i}: 原文='{rev['quote'][:50]}...', 建议='{rev['suggestion'][:50]}...'")

        # 应用所有修订
        results = editor.apply_revisions(revisions)

        # 记录详细结果
        logger.info(f"[应用修订] 应用结果: 总共{results['total']}条建议，成功应用{results['applied']}条，未找到{results['not_found']}条")

        # 打印未找到的修订
        if results['not_found'] > 0:
            logger.warning(f"[应用修订] 以下 {results['not_found']} 条修订未找到原文:")
            for detail in results['details']:
                if not detail['success']:
                    logger.warning(f"[应用修订]   - '{detail['quote'][:50]}...'")

        # 保存修订版文档
        logger.info(f"[应用修订] 保存修订版文档...")
        editor.save(revision_path)
        logger.info(f"[应用修订] 修订版文档保存成功: {revision_path}")

        # 更新合同记录
        contract.final_docx_path = revision_path
        contract.status = ContractStatus.APPROVED.value
        db.commit()

        # 生成 OnlyOffice 配置（用于修订版）
        file_url = f"http://backend:8000/storage/uploads/{os.path.basename(revision_path)}"

        config = {
            "document": {
                "fileType": "docx",
                "key": str(contract.id) + "_revised_" + str(int(datetime.now().timestamp())),
                "title": os.path.basename(revision_path),
                "url": file_url,
            },
            "editorConfig": {
                "mode": "edit",
                "user": {"id": "1", "name": "法务管理员"}
            }
        }

        token = OfficeTokenManager.create_token(config)

        return {
            "success": True,
            "message": f"已应用 {results['applied']} 条修订建议（{results['not_found']} 条未找到原文）",
            "revision_path": revision_path,
            "config": config,
            "token": token,
            "applied_count": results['applied'],
            "not_found_count": results['not_found'],
            "original_format": file_ext,
            "converted": is_pdf or is_doc
        }

    except Exception as e:
        import traceback
        logger.error(f"[应用修订] 发生异常: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"应用修订失败: {str(e)}")


@router.get("/{contract_id}/revision-config")
def get_revision_config(contract_id: int, db: Session = Depends(get_db)):
    """获取修订版文档的 OnlyOffice 配置（审查模式）"""
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    if not contract.final_docx_path or not os.path.exists(contract.final_docx_path):
        raise HTTPException(status_code=404, detail="修订版文档不存在，请先应用修订")

    backend_internal_url = "http://backend:8000"
    file_url = f"{backend_internal_url}/storage/uploads/{os.path.basename(contract.final_docx_path)}"
    callback_url = f"{backend_internal_url}/api/contract/{contract.id}/callback"

    # 使用新的审查模式配置（包含插件支持）
    config = get_review_mode_config(
        file_url=file_url,
        document_key=str(contract.id) + "_revised_" + str(int(datetime.now().timestamp())),
        title=os.path.basename(contract.final_docx_path),
        callback_url=callback_url,
        review_items=[]  # 可以传入审查意见
    )

    token = OfficeTokenManager.create_token(config)
    return {"config": config, "token": token}


@router.get("/{contract_id}/download")
def download_original_contract(contract_id: int, db: Session = Depends(get_db)):
    """下载原始合同文件"""
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    if not contract.original_file_path or not os.path.exists(contract.original_file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    from fastapi.responses import FileResponse
    return FileResponse(
        contract.original_file_path,
        filename=contract.title,
        media_type='application/octet-stream'
    )


@router.get("/{contract_id}/download-revised")
def download_revised_contract(contract_id: int, db: Session = Depends(get_db)):
    """下载修订版合同文件"""
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 如果没有修订版，返回原始文件
    file_path = contract.final_docx_path if contract.final_docx_path else contract.original_file_path

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在，请先应用修订")

    from fastapi.responses import FileResponse
    filename = os.path.basename(file_path)
    return FileResponse(
        file_path,
        filename=filename,
        media_type='application/octet-stream'
    )


# ==================== OnlyOffice Callback ====================

class CallbackRequest(BaseModel):
    """OnlyOffice 回调请求"""
    key: str
    status: int
    users: list[str] = []
    actions: list[dict] = []
    token: str


@router.post("/{contract_id}/callback")
def onlyoffice_callback(
    contract_id: int,
    callback_data: CallbackRequest,
    db: Session = Depends(get_db)
):
    """
    OnlyOffice 编辑器回调

    当用户在编辑器中保存或关闭文档时，OnlyOffice 会调用此端点通知后端

    状态码说明：
    - 0: 正在编辑中
    - 1: 文档已准备好保存
    - 2: 文档保存失败
    - 3: 强制保存（不考虑编辑时间）
    - 4: 文档已关闭，没有更改
    - 6: 文档正在编辑中，但当前保存状态不正确
    - 7: 强制保存，不考虑编辑时间
    """
    logger.info(f"[OnlyOffice Callback] 合同 {contract_id} 回调: status={callback_data.status}")

    # status=1 表示文档已准备好保存
    if callback_data.status == 1:
        logger.info(f"[OnlyOffice Callback] 合同 {contract_id} 文档已准备好保存")
        # 这里可以添加保存逻辑，例如下载 OnlyOffice 保存的版本
        # 目前我们使用修订系统，不需要在这里保存

    # status=4 表示文档已关闭，没有更改
    elif callback_data.status == 4:
        logger.info(f"[OnlyOffice Callback] 合同 {contract_id} 文档已关闭，无更改")

    return {"error": 0}  # 返回 0 表示成功处理回调


# ==================== Debug / Test Endpoints ====================

@router.post("/{contract_id}/test-revision")
def test_revision(
    contract_id: int,
    test_quote: str,
    test_suggestion: str,
    db: Session = Depends(get_db)
):
    """
    测试端点：验证 DocxEditor 修订功能

    用于调试修订应用是否正常工作
    """
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    if not contract.original_file_path or not os.path.exists(contract.original_file_path):
        raise HTTPException(status_code=404, detail="合同文件不存在")

    try:
        from app.services.docx_editor import DocxEditor

        logger.info(f"[测试修订] 合同 {contract_id}")
        logger.info(f"[测试修订] 原文: {test_quote}")
        logger.info(f"[测试修订] 建议: {test_suggestion}")

        # 创建编辑器
        editor = DocxEditor(contract.original_file_path)

        # 应用单条修订
        success = editor.apply_revision(test_quote, test_suggestion)

        if success:
            # 保存测试版本
            test_path = contract.original_file_path.replace('.docx', '.test.docx')
            editor.save(test_path)

            logger.info(f"[测试修订] 成功！测试版保存至: {test_path}")

            return {
                "success": True,
                "message": "测试修订成功",
                "test_file": test_path,
                "applied_count": editor.applied_count,
                "not_found_count": editor.not_found_count
            }
        else:
            logger.warning(f"[测试修订] 失败：未找到原文")
            return {
                "success": False,
                "message": "未找到原文，无法应用修订",
                "quote": test_quote
            }

    except Exception as e:
        import traceback
        logger.error(f"[测试修订] 异常: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


# ================= 任务历史管理 API =================

@router.get("/review-tasks", response_model=List[dict])
async def get_review_tasks(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的审查任务历史

    Query Parameters:
    - skip: 跳过数量 (分页)
    - limit: 每页数量 (分页)
    - status: 状态过滤 (pending/running/paused/completed/failed)
    """
    from app.models.contract_review_task import ContractReviewTask

    query = db.query(ContractReviewTask).filter(
        ContractReviewTask.user_id == current_user.id
    )

    if status:
        query = query.filter(ContractReviewTask.status == status)

    tasks = query.order_by(ContractReviewTask.created_at.desc()).offset(skip).limit(limit).all()

    # 转换为字典
    result = []
    for task in tasks:
        result.append({
            "id": task.id,
            "contract_id": task.contract_id,
            "user_id": task.user_id,
            "task_type": task.task_type,
            "status": task.status,
            "stance": task.stance,
            "use_langgraph": task.use_langgraph,
            "transaction_structures": task.transaction_structures,
            "result_summary": task.result_summary,
            "error_message": task.error_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "created_at": task.created_at.isoformat()
        })

    return result


@router.get("/review-tasks/{task_id}")
async def get_review_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个审查任务详情"""
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
        "user_id": task.user_id,
        "task_type": task.task_type,
        "status": task.status,
        "stance": task.stance,
        "use_custom_rules": task.use_custom_rules,
        "use_langgraph": task.use_langgraph,
        "transaction_structures": task.transaction_structures,
        "metadata_info": task.metadata_info,
        "result_summary": task.result_summary,
        "error_message": task.error_message,
        "celery_task_id": task.celery_task_id,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat()
    }


@router.put("/review-tasks/{task_id}/pause")
async def pause_review_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    暂停正在执行的任务

    注意: 此功能需要Celery任务支持revoke
    """
    from app.models.contract_review_task import ContractReviewTask

    task = db.query(ContractReviewTask).filter(
        ContractReviewTask.id == task_id,
        ContractReviewTask.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "running":
        raise HTTPException(status_code=400, detail="只能暂停正在运行的任务")

    # 撤销Celery任务
    if task.celery_task_id:
        try:
            from app.tasks.celery_app import celery_app
            celery_app.control.revoke(task.celery_task_id, terminate=True)
            logger.info(f"[API] 撤销Celery任务: celery_task_id={task.celery_task_id}")
        except Exception as e:
            logger.error(f"[API] 撤销Celery任务失败: {e}")
            # 即使撤销失败,也更新任务状态

    # 更新状态
    task.status = "paused"
    db.commit()

    return {"message": "任务已暂停", "task_id": task_id}


@router.put("/review-tasks/{task_id}/resume")
async def resume_review_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """恢复暂停的任务"""
    from app.models.contract_review_task import ContractReviewTask
    from app.tasks.contract_review_tasks import resume_contract_review

    task = db.query(ContractReviewTask).filter(
        ContractReviewTask.id == task_id,
        ContractReviewTask.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "paused":
        raise HTTPException(status_code=400, detail="只能恢复已暂停的任务")

    # 提交Celery任务
    celery_task = resume_contract_review.delay(task_id)

    return {
        "message": "任务已恢复",
        "task_id": task_id,
        "celery_task_id": celery_task.id
    }


@router.delete("/review-tasks/{task_id}")
async def delete_review_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除审查任务记录"""
    from app.models.contract_review_task import ContractReviewTask

    task = db.query(ContractReviewTask).filter(
        ContractReviewTask.id == task_id,
        ContractReviewTask.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 只能删除非运行中的任务
    if task.status == "running":
        raise HTTPException(status_code=400, detail="不能删除正在运行的任务")

    # 撤销Celery任务 (如果还在运行)
    if task.status == "pending" and task.celery_task_id:
        try:
            from app.tasks.celery_app import celery_app
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        except Exception as e:
            logger.error(f"[API] 撤销Celery任务失败: {e}")

    db.delete(task)
    db.commit()

    return {"message": "任务已删除", "task_id": task_id}


# ==================== 合同健康度评估 API ====================

@router.get("/{contract_id}/health-assessment")
def get_health_assessment(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取合同健康度综合评估

    基于审查结果计算合同整体健康度评分和总结

    返回:
    - score: 健康度评分 (0-100)
    - level: 风险等级 (健康/良好/中等风险/高风险/极高风险)
    - summary: 综合评语
    - risk_distribution: 风险分布 (按严重程度统计)
    - total_risks: 风险点总数
    - recommendations: 改进建议列表
    """
    from app.services.contract_review.health_assessment import contract_health_assessor

    # 查询合同
    contract = db.query(ContractDoc).filter(ContractDoc.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 获取审查结果
    review_items = contract.review_items

    if not review_items:
        logger.info(f"[HealthAssessment] 合同 {contract_id} 暂无审查结果")
    else:
        logger.info(f"[HealthAssessment] 合同 {contract_id} 有 {len(review_items)} 条审查结果")

    # 计算健康度
    health_assessment = contract_health_assessor.calculate_health_score(review_items)

    logger.info(
        f"[HealthAssessment] 合同 {contract_id} 健康度评估完成: "
        f"分数={health_assessment['score']}, 等级={health_assessment['level']}"
    )

    return health_assessment
