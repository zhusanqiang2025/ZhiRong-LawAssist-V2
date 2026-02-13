# backend/app/api/v1/endpoints/knowledge_base.py
"""
知识库管理 API 端点

提供：
1. 知识源管理
2. 模块偏好设置
3. 知识库搜索
4. 健康检查
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
import uuid

from app.api.deps import get_current_user, get_db
from app.database import SessionLocal
from app.models.user import User
from app.models.knowledge_base import KnowledgeBaseConfig, UserModulePreference, KnowledgeDocument
from app.models.category import Category
from app.services.knowledge_base import (
    get_unified_kb_service,
    UnifiedKnowledgeService,
    create_feishu_kb_from_config,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class KnowledgeSourceInfo(BaseModel):
    """知识源信息"""
    id: str = Field(description="知识源 ID")
    name: str = Field(description="知识源名称")
    type: str = Field(description="知识源类型：local, feishu, confluence, notion")
    enabled: bool = Field(description="是否启用")
    priority: int = Field(description="优先级（数字越小优先级越高）")
    status: str = Field(description="状态：connected, disconnected, error")
    last_sync: Optional[str] = Field(default=None, description="最后同步时间")


class KnowledgeSourceListResponse(BaseModel):
    """知识源列表响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)


class ConfigureFeishuRequest(BaseModel):
    """配置飞书知识源请求"""
    app_id: str = Field(..., description="飞书应用 ID")
    app_secret: str = Field(..., description="飞书应用密钥")
    wiki_space_id: str = Field(..., description="Wiki 空间 ID")
    enabled: bool = Field(default=True, description="是否启用")


class UpdateSourceRequest(BaseModel):
    """更新知识源请求"""
    enabled: Optional[bool] = Field(default=None, description="是否启用")
    priority: Optional[int] = Field(default=None, description="优先级")


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索查询")
    domain: str = Field(default="", description="法律领域")
    limit: int = Field(default=5, description="返回结果数量")
    enabled_stores: Optional[List[str]] = Field(default=None, description="启用的知识库列表")


class SearchResponse(BaseModel):
    """搜索响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)


class ModulePreferencesRequest(BaseModel):
    """模块偏好设置请求"""
    module_name: str = Field(..., description="模块名称：consultation, contract_review, risk_analysis")
    knowledge_base_enabled: bool = Field(default=False, description="是否启用知识库")
    enabled_stores: Optional[List[str]] = Field(default=None, description="启用的知识库列表")


class ModulePreferencesResponse(BaseModel):
    """模块偏好设置响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)


# ==================== 知识源管理 ====================

@router.get("/sources", response_model=KnowledgeSourceListResponse)
async def get_knowledge_sources(
    current_user: User = Depends(get_current_user)
):
    """
    获取知识源列表

    返回所有可用的知识源及其状态
    """
    service = get_unified_kb_service()

    # 获取健康检查信息
    health = await service.health_check()

    # 构建知识源列表
    sources = []
    for store_health in health["stores"]:
        source = KnowledgeSourceInfo(
            id=store_health["name"],
            name=store_health["name"],
            type="local" if "本地" in store_health["name"] else "feishu",
            enabled=store_health["available"],
            priority=store_health["priority"],
            status="connected" if store_health["available"] else "disconnected",
        )
        sources.append(source)

    return KnowledgeSourceListResponse(
        success=True,
        data={
            "sources": [s.dict() for s in sources],
            "total": len(sources),
            "available": health["available_stores"]
        }
    )


@router.post("/sources/feishu/config")
async def configure_feishu_source(
    config: ConfigureFeishuRequest,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    配置飞书知识源

    保存飞书应用配置并测试连接
    """
    # 检查用户权限（仅管理员可配置全局知识源）
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以配置全局知识源"
        )

    # 保存配置到数据库
    kb_config = db.query(KnowledgeBaseConfig).filter_by(
        config_key="feishu_kb",
        user_id=None  # NULL 表示全局配置
    ).first()

    if not kb_config:
        kb_config = KnowledgeBaseConfig(
            config_key="feishu_kb",
            user_id=None,
            config_value={},
            is_active=True
        )
        db.add(kb_config)

    # 更新配置
    kb_config.config_value = {
        "app_id": config.app_id,
        "app_secret": config.app_secret,
        "wiki_space_id": config.wiki_space_id,
        "enabled": config.enabled,
    }
    db.commit()

    # 测试连接
    try:
        feishu_kb = create_feishu_kb_from_config(kb_config.config_value)
        is_available = feishu_kb.is_available()

        if is_available:
            # 注册到统一服务
            service = get_unified_kb_service()
            service.register_store(feishu_kb)

            return {"success": True, "message": "飞书知识源配置成功"}
        else:
            return {"success": False, "message": "飞书知识源配置失败，请检查凭证"}

    except Exception as e:
        logger.error(f"[知识库API] 配置飞书知识源失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"配置失败: {str(e)}"
        )


@router.post("/sources/{source_id}/toggle")
async def toggle_knowledge_source(
    source_id: str,
    enabled: bool,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    切换知识源启用状态

    Args:
        source_id: 知识源 ID
        enabled: 是否启用
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以修改知识源配置"
        )

    # 更新配置
    kb_config = db.query(KnowledgeBaseConfig).filter_by(
        config_key=source_id,
        user_id=None
    ).first()

    if not kb_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识源 '{source_id}' 不存在"
        )

    kb_config.config_value["enabled"] = enabled
    kb_config.is_active = enabled
    db.commit()

    return {
        "success": True,
        "message": f"知识源 '{source_id}' 已{'启用' if enabled else '禁用'}"
    }


# ==================== 知识库搜索 ====================

@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(
    request: SearchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    搜索知识库

    多源并发搜索，返回最相关的结果
    """
    service = get_unified_kb_service()

    try:
        result = await service.search(
            query=request.query,
            domain=request.domain,
            limit=request.limit,
            enabled_stores=request.enabled_stores
        )

        return SearchResponse(
            success=True,
            data=result.to_dict()
        )

    except Exception as e:
        logger.error(f"[知识库API] 搜索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )


# ==================== 模块偏好设置 ====================

@router.get("/modules/{module_name}/preferences", response_model=ModulePreferencesResponse)
async def get_module_preferences(
    module_name: str,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    获取模块知识库偏好设置

    Args:
        module_name: 模块名称（consultation, contract_review, risk_analysis）
    """
    # 验证模块名称
    valid_modules = ["consultation", "contract_review", "risk_analysis", "litigation_analysis"]
    if module_name not in valid_modules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的模块名称: {module_name}"
        )

    # 获取用户偏好设置
    pref = db.query(UserModulePreference).filter_by(
        user_id=current_user.id,
        module_name=module_name
    ).first()

    if not pref:
        # 返回默认设置
        return ModulePreferencesResponse(
            success=True,
            data={
                "module_name": module_name,
                "knowledge_base_enabled": False,
                "enabled_stores": []
            }
        )

    return ModulePreferencesResponse(
        success=True,
        data={
            "module_name": pref.module_name,
            "knowledge_base_enabled": pref.knowledge_base_enabled,
            "enabled_stores": pref.enabled_stores or [],
            "updated_at": pref.updated_at.isoformat() if pref.updated_at else None
        }
    )


@router.post("/modules/{module_name}/preferences", response_model=ModulePreferencesResponse)
async def save_module_preferences(
    module_name: str,
    request: ModulePreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    保存模块知识库偏好设置

    Args:
        module_name: 模块名称（consultation, contract_review, risk_analysis）
    """
    # 验证模块名称
    valid_modules = ["consultation", "contract_review", "risk_analysis", "litigation_analysis"]
    if module_name not in valid_modules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的模块名称: {module_name}"
        )

    # 获取或创建偏好设置
    pref = db.query(UserModulePreference).filter_by(
        user_id=current_user.id,
        module_name=module_name
    ).first()

    if not pref:
        pref = UserModulePreference(
            user_id=current_user.id,
            module_name=module_name
        )
        db.add(pref)

    # 更新设置
    pref.knowledge_base_enabled = request.knowledge_base_enabled
    pref.enabled_stores = request.enabled_stores
    db.commit()
    db.refresh(pref)

    return ModulePreferencesResponse(
        success=True,
        data={
            "module_name": pref.module_name,
            "knowledge_base_enabled": pref.knowledge_base_enabled,
            "enabled_stores": pref.enabled_stores,
            "updated_at": pref.updated_at.isoformat() if pref.updated_at else None
        }
    )


# ==================== 健康检查 ====================

@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    current_user: User = Depends(get_current_user)
):
    """
    知识库健康检查

    返回所有知识源的状态信息
    """
    service = get_unified_kb_service()
    health = await service.health_check()

    return HealthCheckResponse(
        success=True,
        data=health
    )


# ==================== 重复检测 ====================

class CheckDuplicateRequest(BaseModel):
    """重复检测请求"""
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    category: Optional[str] = Field(default=None, description="分类（可选）")


class CheckDuplicateResponse(BaseModel):
    """重复检测响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)


@router.post("/check-duplicate", response_model=CheckDuplicateResponse)
async def check_duplicate(
    request: CheckDuplicateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    检测上传内容是否与系统知识库重复

    在用户上传文档前调用，检测是否与系统知识库重复
    """
    from app.services.knowledge_base import get_deduplicator

    deduplicator = get_deduplicator()
    duplicate_info = deduplicator.check_duplicate_on_upload(
        title=request.title,
        content=request.content,
        category=request.category
    )

    # 构建响应数据
    data = {
        "is_duplicate": duplicate_info.is_duplicate,
        "similarity": round(duplicate_info.similarity * 100, 2),  # 转为百分比
        "recommendation": duplicate_info.recommendation,
    }

    # 如果发现重复，返回系统版本信息
    if duplicate_info.original_item:
        data["system_item"] = {
            "title": duplicate_info.original_item.title,
            "content": duplicate_info.original_item.content[:200] + "..." if len(duplicate_info.original_item.content) > 200 else duplicate_info.original_item.content,
            "source": duplicate_info.original_item.source,
        }

    # 根据相似度给出建议操作
    if duplicate_info.similarity >= 0.85:
        data["action"] = "block"  # 阻止上传
        data["message"] = "该内容与系统知识库高度重复，不建议上传"
    elif duplicate_info.similarity >= 0.70:
        data["action"] = "warn"  # 警告用户
        data["message"] = "该内容与系统知识库较为相似，请确认是否需要上传"
    else:
        data["action"] = "allow"  # 允许上传
        data["message"] = "该内容为独立内容，可以正常上传"

    return CheckDuplicateResponse(
        success=True,
        data=data
    )


# ==================== 用户知识库文档管理 ====================

class UserDocumentListResponse(BaseModel):
    """用户文档列表响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)


class UserDocumentResponse(BaseModel):
    """用户文档响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)


@router.get("/user/documents", response_model=UserDocumentListResponse)
async def get_user_documents(
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    获取用户知识库文档列表

    Args:
        page: 页码（从1开始）
        size: 每页数量
        search: 搜索关键词（搜索标题和内容）
        status: 状态筛选（active, archived, deleted）
    """
    # 构建查询
    query = db.query(KnowledgeDocument).filter_by(
        user_id=current_user.id,
        kb_type="user"  # 只获取用户私有知识库
    )

    # 状态筛选
    if status:
        query = query.filter_by(status=status)
    else:
        # 默认不显示已删除的文档
        query = query.filter(KnowledgeDocument.status != "deleted")

    # 搜索
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (KnowledgeDocument.title.ilike(search_pattern)) |
            (KnowledgeDocument.content.ilike(search_pattern))
        )

    # 排序：最新更新优先
    query = query.order_by(KnowledgeDocument.updated_at.desc())

    # 分页
    total = query.count()
    documents = query.offset((page - 1) * size).limit(size).all()

    # 转换为字典格式
    items = []
    for doc in documents:
        items.append({
            "id": doc.id,
            "doc_id": doc.doc_id,
            "title": doc.title,
            "content": doc.content,
            "category": doc.category,
            "category_id": doc.category_id,
            "category_name_cache": doc.category_name_cache,
            "tags": doc.tags,
            "source_type": doc.source_type,
            "status": doc.status,
            "is_public": doc.is_public,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "extra_data": doc.extra_data,
        })

    return UserDocumentListResponse(
        success=True,
        data={
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        }
    )


@router.post("/user/documents", response_model=UserDocumentResponse)
async def upload_user_document(
    file: UploadFile = File(None),
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    is_public: Optional[bool] = Form(False),
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    上传文档到用户知识库

    支持两种方式：
    1. 直接上传文本内容（提供 title 和 content）
    2. 上传文件（自动使用 DocumentPreprocessor 处理）

    支持的文件格式：
    - 文档类：PDF, DOCX, DOC, TXT, RTF, ODT
    - 图片类：JPG, PNG, BMP, TIFF, GIF（自动OCR识别）
    """
    import json
    import os
    import tempfile

    file_text = content or ""
    metadata = {}

    # 如果上传了文件，使用 DocumentPreprocessor 处理
    if file:
        try:
            # 保存上传文件到临时目录
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, f"kb_upload_{current_user.id}_{uuid.uuid4().hex[:8]}_{file.filename}")

            # 写入临时文件
            file_bytes = await file.read()
            with open(temp_file_path, 'wb') as f:
                f.write(file_bytes)

            logger.info(f"[知识库API] 文件已保存到临时路径: {temp_file_path}, 大小: {len(file_bytes)} bytes")

            # 使用 DocumentPreprocessor 提取文本
            from app.services.common.document_preprocessor import get_preprocessor

            preprocessor = get_preprocessor()

            # 检测文件格式
            file_format = preprocessor.detect_format(temp_file_path)
            logger.info(f"[知识库API] 检测到文件格式: {file_format.value}")

            # 提取文本内容
            try:
                file_text = preprocessor.extract_text(temp_file_path)
                logger.info(f"[知识库API] 文本提取成功，长度: {len(file_text)} chars")

                # 收集元数据
                file_metadata = preprocessor._extract_metadata(temp_file_path)
                metadata.update(file_metadata)
                metadata["original_filename"] = file.filename
                metadata["file_format"] = file_format.value

                # 清理 NUL 字符和控制字符
                file_text = file_text.replace('\x00', '')
                file_text = ''.join(char for char in file_text if char == '\n' or char == '\t' or char == '\r' or char >= ' ')

            except Exception as extract_error:
                logger.error(f"[知识库API] 文本提取失败: {extract_error}")
                # 回退到简单解码
                try:
                    file_text = file_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    file_text = file_bytes.decode('gbk', errors='ignore')
                file_text = file_text.replace('\x00', '')

            # 清理临时文件
            try:
                os.remove(temp_file_path)
                logger.info(f"[知识库API] 临时文件已删除: {temp_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"[知识库API] 清理临时文件失败: {cleanup_error}")

        except Exception as e:
            logger.error(f"[知识库API] 文件处理失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件处理失败: {str(e)}"
            )

    # 如果没有提供标题，使用文件名
    doc_title = title or (file.filename if file else None) or "未命名文档"

    # 处理标签
    doc_tags = []
    if tags:
        try:
            doc_tags = json.loads(tags)
        except:
            # 如果解析失败，按逗号分割
            doc_tags = [t.strip() for t in tags.split(',') if t.strip()]

    # 生成唯一文档 ID
    doc_id = f"user_{current_user.id}_{uuid.uuid4().hex[:12]}"

    # 处理分类关联
    category_name_cache = None
    if category_id:
        # 根据 category_id 查找分类名称
        category_obj = db.query(Category).filter(Category.id == category_id).first()
        if category_obj:
            category_name_cache = category_obj.name
        else:
            # 如果分类不存在，忽略 category_id
            category_id = None

    # 准备 extra_data，包含处理元数据
    extra_data = {
        "original_filename": file.filename if file else None,
        "file_size": len(file_text) if file_text else 0,
    }
    # 添加从 DocumentPreprocessor 获取的元数据
    if metadata:
        extra_data.update(metadata)

    # 创建文档记录
    document = KnowledgeDocument(
        doc_id=doc_id,
        title=doc_title,
        content=file_text,
        category=category,
        category_id=category_id,
        category_name_cache=category_name_cache,
        tags=doc_tags,
        source_type="upload",
        source_id=file.filename if file else None,
        kb_type="user",
        is_public=is_public or False,
        user_id=current_user.id,
        status="active",
        extra_data=extra_data
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    logger.info(f"[知识库API] 文档上传成功: doc_id={doc_id}, title={doc_title}, content_length={len(file_text)}")

    return UserDocumentResponse(
        success=True,
        data={
            "id": document.id,
            "doc_id": document.doc_id,
            "title": document.title,
            "message": "文档上传成功",
            "metadata": metadata if metadata else {}
        }
    )


@router.put("/user/documents/{doc_id}", response_model=UserDocumentResponse)
async def update_user_document(
    doc_id: str,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    更新用户知识库文档

    Args:
        doc_id: 文档 ID
        request: 包含更新字段的请求体
    """
    # 查找文档
    document = db.query(KnowledgeDocument).filter_by(
        id=int(doc_id),
        user_id=current_user.id,
        kb_type="user"
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 更新字段
    if "title" in request:
        document.title = request["title"]
    if "content" in request:
        document.content = request["content"]
    if "category" in request:
        document.category = request["category"]
    if "category_id" in request:
        # 更新 category_id 和 category_name_cache
        category_id = request["category_id"]
        if category_id is not None:
            category_obj = db.query(Category).filter(Category.id == category_id).first()
            if category_obj:
                document.category_id = category_id
                document.category_name_cache = category_obj.name
            else:
                # 如果分类不存在，清除关联
                document.category_id = None
                document.category_name_cache = None
        else:
            document.category_id = None
            document.category_name_cache = None
    if "tags" in request:
        document.tags = request["tags"]
    if "is_public" in request:
        document.is_public = request["is_public"]
    if "status" in request:
        document.status = request["status"]

    db.commit()
    db.refresh(document)

    return UserDocumentResponse(
        success=True,
        data={
            "id": document.id,
            "doc_id": document.doc_id,
            "title": document.title,
            "message": "文档更新成功"
        }
    )


@router.delete("/user/documents/{doc_id}", response_model=UserDocumentResponse)
async def delete_user_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    删除用户知识库文档

    Args:
        doc_id: 文档 ID

    注意：这是软删除，将文档状态设为 deleted
    """
    # 查找文档
    document = db.query(KnowledgeDocument).filter_by(
        id=int(doc_id),
        user_id=current_user.id,
        kb_type="user"
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 软删除
    document.status = "deleted"
    db.commit()

    return UserDocumentResponse(
        success=True,
        data={
            "id": document.id,
            "message": "文档删除成功"
        }
    )


@router.get("/user/documents/{doc_id}", response_model=UserDocumentResponse)
async def get_user_document_detail(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """
    获取用户知识库文档详情

    Args:
        doc_id: 文档 ID
    """
    # 查找文档
    document = db.query(KnowledgeDocument).filter_by(
        id=int(doc_id),
        user_id=current_user.id,
        kb_type="user"
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    return UserDocumentResponse(
        success=True,
        data={
            "id": document.id,
            "doc_id": document.doc_id,
            "title": document.title,
            "content": document.content,
            "category": document.category,
            "category_id": document.category_id,
            "category_name_cache": document.category_name_cache,
            "tags": document.tags,
            "source_type": document.source_type,
            "status": document.status,
            "is_public": document.is_public,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
            "extra_data": document.extra_data,
        }
    )
