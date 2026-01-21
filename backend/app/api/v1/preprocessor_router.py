# backend/app/api/v1/preprocessor_router.py
"""
合同文件预处理中心 API 路由
提供文件格式转换、批量处理等功能
"""
import os
import uuid
import shutil
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.document_preprocessor import (
    DocumentPreprocessor,
    get_preprocessor,
    ConversionResult,
    DocumentFormat
)

router = APIRouter(
    tags=["Document Preprocessor"]
)


class PreprocessRequest(BaseModel):
    """预处理请求"""
    delete_original: bool = False
    force_conversion: bool = False


class BatchPreprocessRequest(BaseModel):
    """批量预处理请求"""
    file_ids: List[int]
    delete_originals: bool = False


class ConversionStatus(BaseModel):
    """转换状态响应"""
    original_format: str
    target_format: str = "docx"
    status: str
    output_path: Optional[str] = None
    metadata: Optional[dict] = None
    message: str


@router.post("/convert")
async def convert_document(
    file: UploadFile = File(...),
    delete_original: bool = Query(False, description="是否删除原始文件"),
    force: bool = Query(False, description="是否强制转换"),
    db: Session = Depends(get_db)
):
    """
    单文件格式转换

    支持的输入格式：.doc, .docx, .pdf, .txt, .rtf, .odt
    输出格式：.docx
    """
    UPLOAD_DIR = "storage/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 保存上传文件
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 使用预处理中心转换
    preprocessor = get_preprocessor()

    result, output_path, metadata = preprocessor.preprocess(
        file_path=file_path,
        delete_original=delete_original
    )

    if result == ConversionResult.SUCCESS:
        # 返回转换后的文件信息
        return {
            "success": True,
            "status": "converted",
            "original_format": file_ext,
            "output_format": "docx",
            "original_filename": file.filename,
            "output_filename": os.path.basename(output_path) if output_path else None,
            "output_path": output_path,
            "metadata": metadata,
            "download_url": f"/api/preprocessor/download/{os.path.basename(output_path)}" if output_path else None
        }

    elif result == ConversionResult.ALREADY_CONVERTED:
        return {
            "success": True,
            "status": "already_converted",
            "message": "文件已经是 .docx 格式，无需转换",
            "original_format": file_ext,
            "output_path": output_path,
            "metadata": metadata
        }

    else:
        # 转换失败
        return {
            "success": False,
            "status": "failed",
            "message": output_path,  # output_path 在这里是错误消息
            "original_format": file_ext
        }


@router.post("/batch-convert")
async def batch_convert_documents(
    files: List[UploadFile] = File(...),
    delete_originals: bool = Query(False, description="是否删除原始文件"),
    db: Session = Depends(get_db)
):
    """
    批量文件格式转换

    支持同时上传多个文件进行批量转换
    """
    UPLOAD_DIR = "storage/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    preprocessor = get_preprocessor()
    file_paths = []
    original_filenames = []

    # 保存所有上传文件
    for file in files:
        file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4().hex}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_paths.append(file_path)
        original_filenames.append(file.filename)

    # 批量处理
    results = preprocessor.batch_preprocess(
        file_paths=file_paths,
        delete_originals=delete_originals
    )

    # 格式化返回结果
    formatted_results = []
    for i, result in enumerate(results):
        formatted_results.append({
            "original_filename": original_filenames[i],
            "status": result["result"],
            "output_path": result["output_path"],
            "metadata": result["metadata"],
            "download_url": f"/api/preprocessor/download/{os.path.basename(result['output_path'])}"
            if result["output_path"] else None
        })

    return {
        "success": True,
        "total": len(files),
        "results": formatted_results
    }


@router.get("/detect-format")
async def detect_file_format(
    file_path: str = Query(..., description="文件路径")
):
    """
    检测文件格式

    返回文件的格式类型和是否需要转换
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    preprocessor = get_preprocessor()
    file_format = preprocessor.detect_format(file_path)
    needs_conversion = preprocessor.needs_conversion(file_path)
    is_valid, error_msg = preprocessor.validate_file(file_path)

    return {
        "file_path": file_path,
        "format": file_format.value,
        "needs_conversion": needs_conversion,
        "is_valid": is_valid,
        "error_message": error_msg if not is_valid else None
    }


@router.get("/metadata")
async def get_document_metadata(
    file_path: str = Query(..., description="文件路径")
):
    """
    获取文档元数据

    返回文件的详细信息：页数、字数、段落数等
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    preprocessor = get_preprocessor()
    metadata = preprocessor._extract_metadata(file_path)

    return {
        "file_path": file_path,
        "metadata": metadata
    }


@router.get("/download/{filename}")
async def download_converted_file(filename: str):
    """
    下载转换后的文件
    """
    UPLOAD_DIR = "storage/uploads"
    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    from fastapi.responses import FileResponse
    return FileResponse(
        file_path,
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


@router.get("/supported-formats")
async def get_supported_formats():
    """
    获取支持的文件格式列表
    """
    return {
        "input_formats": [f.value for f in DocumentPreprocessor.SUPPORTED_INPUT_FORMATS],
        "output_format": "docx",
        "no_conversion_needed": [f.value for f in DocumentPreprocessor.NO_CONVERSION_NEEDED],
        "description": "合同文件预处理中心统一将所有格式转换为 .docx (Word) 格式"
    }


@router.post("/validate")
async def validate_document(
    file: UploadFile = File(...)
):
    """
    验证文件有效性

    检查文件是否有效、格式是否支持、大小是否符合要求
    """
    UPLOAD_DIR = "storage/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 临时保存文件
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"temp_{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        preprocessor = get_preprocessor()
        is_valid, error_msg = preprocessor.validate_file(file_path)
        file_format = preprocessor.detect_format(file_path)

        return {
            "filename": file.filename,
            "is_valid": is_valid,
            "error_message": error_msg if not is_valid else None,
            "detected_format": file_format.value,
            "needs_conversion": preprocessor.needs_conversion(file_path),
            "file_size": os.path.getsize(file_path)
        }

    finally:
        # 清理临时文件
        if os.path.exists(file_path):
            os.remove(file_path)


@router.get("/stats")
async def get_preprocessor_stats():
    """
    获取预处理中心统计信息

    返回支持的功能、格式统计等
    """
    from app.services.document_preprocessor import get_preprocessor

    preprocessor = get_preprocessor()

    return {
        "name": "合同文件预处理中心",
        "version": "2.0.0",
        "description": "统一处理各种格式的合同文件，转换为标准的 .docx 格式",
        "supported_input_formats": {
            "doc": "Legacy Word 文档 (需要转换)",
            "docx": "Modern Word 文档 (无需转换)",
            "pdf": "PDF 文档 (需要转换，支持扫描版 OCR)",
            "txt": "纯文本文档 (需要转换)",
            "rtf": "富文本格式 (需要转换)",
            "odt": "OpenDocument Text (需要转换)",
            "jpg/jpeg/png/bmp/tiff/gif": "图片格式 (OCR 识别)",
        },
        "output_format": {
            "docx": "Microsoft Word 2007+ 格式"
        },
        "features": [
            "自动格式检测",
            "批量文件转换",
            "元数据提取（页数、字数、段落数）",
            "文件有效性验证",
            "编码自动检测（文本文件）",
            "转换质量检查",
            "智能后处理（规则引擎）",
            "AI 辅助页码识别",
            "AI 辅助段落边界判断",
        ],
        "ai_features": {
            "enabled": preprocessor.ENABLE_AI_POSTPROCESSING,
            "model": "qwen3-vl-32b",
            "capabilities": [
                "智能页码识别（区分页码与正文数字）",
                "段落边界智能判断（识别不正常换行）",
                "批量处理优化",
            ],
            "strategy": "混合模式：规则引擎优先 + AI 处理不确定情况"
        },
        "postprocessing": {
            "enabled": preprocessor.ENABLE_POSTPROCESSING,
            "remove_page_numbers": preprocessor.REMOVE_PAGE_NUMBERS,
            "clean_spaces": preprocessor.CLEAN_SPACES,
            "fix_line_breaks": preprocessor.FIX_LINE_BREAKS,
            "remove_empty_paragraphs": preprocessor.REMOVE_EMPTY_PARAGRAPHS,
        },
        "limitations": {
            "max_file_size": "50MB",
            "pdf_conversion": "基于 LibreOffice，复杂布局可能需要人工检查",
            "ocr_support": "支持 RapidOCR/pytesseract，需安装系统依赖",
            "ai_requirement": "需要配置 Qwen3-VL API"
        }
    }


@router.get("/ai-status")
async def get_ai_status():
    """
    获取 AI 辅助功能状态

    检查 AI 服务是否可用及配置情况
    """
    from app.services.document_preprocessor import get_preprocessor
    from app.services.ai_document_helper import get_ai_helper

    preprocessor = get_preprocessor()
    ai_helper = get_ai_helper()

    return {
        "ai_postprocessing_enabled": preprocessor.ENABLE_AI_POSTPROCESSING,
        "ai_service_available": ai_helper.is_available(),
        "ai_model": ai_helper.model if ai_helper.is_available() else None,
        "ai_api_url": ai_helper.api_url if ai_helper.is_available() else None,
        "confidence_threshold": preprocessor.AI_CONFIDENCE_THRESHOLD,
        "batch_size": preprocessor.AI_BATCH_SIZE,
        "only_ambiguous": preprocessor.AI_ONLY_AMBIGUOUS,
        "message": "AI 服务已启用，将自动处理规则引擎不确定的段落" if ai_helper.is_available()
                 else "AI 服务未配置，仅使用规则引擎进行后处理"
    }


@router.post("/toggle-ai")
async def toggle_ai_feature(enabled: bool = Query(..., description="是否启用 AI 功能")):
    """
    动态开关 AI 辅助功能

    无需重启服务即可切换 AI 功能
    """
    from app.services.document_preprocessor import get_preprocessor

    preprocessor = get_preprocessor()
    preprocessor.ENABLE_AI_POSTPROCESSING = enabled

    return {
        "success": True,
        "ai_enabled": preprocessor.ENABLE_AI_POSTPROCESSING,
        "message": f"AI 辅助功能已{'启用' if enabled else '禁用'}"
    }


# ==================== 新增：结构化文档处理和异步处理 API ====================

@router.post("/convert-async")
async def convert_document_async(
    file: UploadFile = File(...),
    extract_metadata: bool = Query(True, description="是否提取元数据")
):
    """
    异步文档转换

    使用异步处理模式，避免阻塞 API
    """
    from app.services.unified_document_service import get_unified_document_service

    UPLOAD_DIR = "storage/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 保存上传文件
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 异步处理
    service = get_unified_document_service()
    result = await service.process_document_async(
        file_path,
        extract_content=True,
        extract_metadata=extract_metadata
    )

    return {
        "success": result.status == "success",
        "status": result.status,
        "content": result.content,
        "metadata": result.metadata,
        "processing_method": result.processing_method,
        "from_cache": result.from_cache,
        "error": result.error,
        "warnings": result.warnings
    }


@router.post("/convert-structured")
async def convert_structured(
    file: UploadFile = File(...),
    extract_structure: bool = Query(True, description="是否提取结构化信息")
):
    """
    结构化文档转换

    返回包含段落、表格、标题、签名等结构化信息的处理结果
    """
    from app.services.unified_document_service import get_unified_document_service

    UPLOAD_DIR = "storage/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 保存上传文件
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 结构化处理
    service = get_unified_document_service()
    result = service.process_document_structured(
        file_path,
        extract_structure=extract_structure
    )

    return {
        "success": result.status == "success",
        "status": result.status,
        "content": result.content,
        "metadata": result.metadata,
        "processing_method": result.processing_method,
        "from_cache": result.from_cache,
        "error": result.error,
        "warnings": result.warnings,
        # 结构化信息
        "structure": {
            "paragraphs": result.paragraphs,
            "tables": result.tables,
            "headings": result.headings,
            "signatures": result.signatures,
            "parties": result.parties
        } if extract_structure else None
    }


@router.post("/batch-async")
async def batch_convert_async(
    files: List[UploadFile] = File(...),
    extract_metadata: bool = Query(False, description="是否提取元数据"),
    max_concurrent: int = Query(3, description="最大并发数")
):
    """
    异步批量转换文档

    使用异步并发处理多个文档，提高处理效率
    """
    from app.services.unified_document_service import get_unified_document_service

    UPLOAD_DIR = "storage/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    service = get_unified_document_service()
    file_paths = []
    original_filenames = []

    # 保存所有上传文件
    for file in files:
        file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4().hex}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_paths.append(file_path)
        original_filenames.append(file.filename)

    # 异步批量处理
    results = await service.batch_process_async(
        file_paths,
        extract_content=True,
        extract_metadata=extract_metadata,
        max_concurrent=max_concurrent
    )

    # 格式化返回结果
    formatted_results = []
    for i, result in enumerate(results):
        formatted_results.append({
            "original_filename": original_filenames[i],
            "status": result.status,
            "content": result.content,
            "metadata": result.metadata,
            "processing_method": result.processing_method,
            "from_cache": result.from_cache,
            "error": result.error,
            "warnings": result.warnings
        })

    return {
        "success": True,
        "total": len(files),
        "results": formatted_results
    }


@router.get("/file-hash/{filename:path}")
async def get_file_hash_info(filename: str):
    """
    获取文件哈希值

    用于缓存验证，返回文件的唯一哈希标识
    """
    from app.services.unified_document_service import get_unified_document_service

    UPLOAD_DIR = "storage/uploads"
    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    service = get_unified_document_service()
    file_hash = service.get_file_hash(file_path)

    return {
        "filename": filename,
        "file_hash": file_hash,
        "file_size": os.path.getsize(file_path),
        "file_path": file_path
    }
