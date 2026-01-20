# backend/app/api/v1/endpoints/contract_templates.py
# [PART 1 START]
"""
合同模板管理 API (V3.4 - 最终生产版)

设计逻辑：
1. 深度集成 ContractKnowledgeType：上传时必须选择已存在的合同类型。
2. 自动化特征继承：自动从知识图谱表读取法律特征，填入模板。
3. 向量增强：生成的 Embedding 包含知识图谱的语义特征。
4. 前端友好：提供 options 接口，支持按一级分类分组显示下拉框。
"""
import os
import uuid
import shutil
import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy import desc, text

from app.database import get_db
from app.models.contract_template import ContractTemplate
from app.models.user import User
# 引入知识图谱模型，用于校验和数据获取
from app.models.contract_knowledge import ContractKnowledgeType
from app.api.deps import get_current_user

# 引入文档处理和向量服务
from app.services.unified_document_service import get_unified_document_service
from app.services.embedding_service import get_text_embedding
from fastapi import Body # 记得在文件头部导入 Body

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 文件存储路径配置
TEMPLATE_STORAGE_DIR = "storage/templates"
os.makedirs(TEMPLATE_STORAGE_DIR, exist_ok=True)


# ==================== 1. 响应模型定义 ====================

class TemplateResponse(BaseModel):
    """API 返回的模板数据结构"""
    id: str
    name: str
    category: str         # 具体的合同类型名称 (如: 房屋租赁合同)
    subcategory: Optional[str] = None # 一级分类 (如: 租赁合同)
    description: Optional[str] = None
    
    file_url: str
    file_name: str
    file_size: int
    file_type: str
    
    is_public: bool
    owner_id: Optional[int] = None
    status: str
    download_count: int
    rating: float
    is_recommended: bool
    
    # 核心元数据 (包含知识图谱关联信息)
    metadata_info: Optional[Dict[str, Any]] = None
    
    # 兼容性字段 (前端展示用)
    transaction_nature: Optional[str] = None
    contract_object: Optional[str] = None
    stance: Optional[str] = None
    risk_level: Optional[str] = None
    
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

class PaginatedTemplateResponse(BaseModel):
    """分页列表响应结构"""
    templates: list[TemplateResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


# ==================== 2. 内部辅助函数 ====================

def convert_to_markdown(file_path: str) -> str:
    """调用文档服务将文件内容转换为 Markdown"""
    try:
        service = get_unified_document_service()
        content = service.convert_to_markdown(file_path)
        return content if content else ""
    except Exception as e:
        logger.error(f"文档转换失败: {e}", exc_info=True)
        return ""


# ==================== 3. 前端辅助接口 ====================

@router.get("/options/contract-types")
async def get_contract_type_options(db: Session = Depends(get_db)):
    """
    [前端专用] 获取系统中所有可用的合同类型
    
    用途：前端调用此接口生成"合同类型"下拉框。
    返回格式：
    [
        {
            "label": "房屋租赁合同",  (显示名)
            "value": "房屋租赁合同",  (提交值)
            "group": "租赁合同"      (一级分组名)
        },
        ...
    ]
    """
    # 直接查询 ContractKnowledgeType 表
    types = db.query(ContractKnowledgeType.name, ContractKnowledgeType.category)\
              .filter(ContractKnowledgeType.is_active == True)\
              .order_by(ContractKnowledgeType.category, ContractKnowledgeType.name)\
              .all()
    
    options = []
    for name, category in types:
        options.append({
            "label": name,
            "value": name,
            "group": category
        })
    return options


# ==================== 4. 核心上传接口 ====================

@router.post("/upload", response_model=TemplateResponse)
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(..., description="模板显示名称"),
    
    # 【核心逻辑】这里接收的是具体的"合同类型名称"，必须与知识图谱匹配
    category: str = Form(..., description="必须是系统中已存在的合同类型名称（如：房屋租赁合同）"),
    
    subcategory: Optional[str] = Form(None), # 可选，通常会自动从图谱填充
    description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    keywords: Optional[str] = Form(None),
    
    # 允许手动覆盖的字段
    risk_level: Optional[str] = Form(None),
    is_recommended: Optional[bool] = Form(False),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传合同模板 (V3流程)
    
    1. 【校验】检查 category 是否存在于知识图谱表 (ContractKnowledgeType)。
    2. 【处理】保存文件 -> 转 Markdown。
    3. 【向量】结合知识图谱特征和文档内容生成 Embedding。
    4. 【入库】保存模板，并自动填充法律特征。
    """
    # 0. 权限校验
    if is_public and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足：只有管理员可上传公开模板")

    # 1. === 校验并获取知识图谱数据 ===
    kg_item = db.query(ContractKnowledgeType).filter(
        ContractKnowledgeType.name == category
    ).first()

    if not kg_item:
        raise HTTPException(
            status_code=400, 
            detail=f"合同类型 '{category}' 不存在。请先在【合同类型管理】中创建该类型，或使用下拉框选择有效类型。"
        )
    
    logger.info(f"[Upload] 已关联知识图谱类型: {kg_item.name} (ID: {kg_item.id})")

    # 2. === 文件处理 ===
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in {".docx", ".doc", ".pdf", ".md", ".txt"}:
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    # 保存源文件
    source_filename = f"{uuid.uuid4().hex}{file_ext}"
    source_path = os.path.join(TEMPLATE_STORAGE_DIR, "source", source_filename)
    os.makedirs(os.path.dirname(source_path), exist_ok=True)
    
    try:
        with open(source_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        raise HTTPException(status_code=500, detail="文件保存失败")

    # 转换为 Markdown
    md_filename = f"{os.path.splitext(source_filename)[0]}.md"
    md_path = os.path.join(TEMPLATE_STORAGE_DIR, "markdown", md_filename)
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    
    markdown_content = convert_to_markdown(source_path)
    if markdown_content:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

    # 3. === 生成向量 (RAG) ===
    vector_embedding = None
    if markdown_content:
        # 构造 prompt：包含 合同类型 + 法律特征 + 文本内容
        # 这样搜索时，即使用户搜的是"不动产"，也能匹配到属于"不动产"特征的合同
        features_context = f"类型:{kg_item.name} 性质:{kg_item.transaction_nature} 标的:{kg_item.contract_object}"
        embed_text = f"标题:{name}\n特征:{features_context}\n内容:{markdown_content[:6000]}"
        
        try:
            vector_embedding = await get_text_embedding(embed_text)
            if vector_embedding:
                logger.info("[Upload] 向量生成成功")
        except Exception as e:
            logger.warning(f"[Upload] 向量生成失败 (将降级为普通搜索): {e}")

    # 4. === 数据入库 ===
    
    # 构造知识图谱关联数据 (存入 JSON 字段)
    kg_link_data = {
        "id": kg_item.id,
        "name": kg_item.name,
        "source": "strict_match",
        "features": {
            "transaction_nature": kg_item.transaction_nature,
            "contract_object": kg_item.contract_object,
            "stance": kg_item.stance,
            "usage_scenario": kg_item.usage_scenario,
            "risk_points": getattr(kg_item, 'risk_points', None) # 假设模型有此字段
        }
    }

    metadata_info = {
        "source_file_url": source_path,
        "original_filename": file.filename,
        "knowledge_graph_link": kg_link_data,
        "file_processing": {
            "converted": bool(markdown_content),
            "vectorized": bool(vector_embedding)
        }
    }

    keywords_list = [k.strip() for k in keywords.split(",")] if keywords else []

    try:
        template = ContractTemplate(
            name=name,
            # category 存储具体的类型名 (如: 房屋租赁合同)
            category=kg_item.name,
            # subcategory 存储一级分类 (如: 租赁合同)，方便统计
            subcategory=subcategory or kg_item.category,
            description=description,
            file_url=md_path,
            file_name=file.filename,
            file_size=os.path.getsize(source_path),
            file_type=file_ext[1:],
            is_public=is_public,
            owner_id=current_user.id,
            keywords=keywords_list,
            status="active",
            
            # V3 核心字段
            metadata_info=metadata_info,
            embedding=vector_embedding,
            is_recommended=is_recommended,
            
            # 自动填充兼容字段 (从 KG 获取)
            transaction_nature=kg_item.transaction_nature,
            contract_object=kg_item.contract_object,
            stance=kg_item.stance,
            risk_level=risk_level or "中", 
            primary_contract_type=kg_item.category
        )

        db.add(template)
        db.commit()
        db.refresh(template)
        
        return json.loads(json.dumps(template.to_dict(), default=str))

    except Exception as e:
        logger.error(f"入库失败: {e}")
        # 清理垃圾文件
        if os.path.exists(source_path): os.remove(source_path)
        if os.path.exists(md_path): os.remove(md_path)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"入库失败: {str(e)}")

# ==================== 5. 查询与管理 API ====================

@router.get("/", response_model=PaginatedTemplateResponse)
async def get_templates(
    scope: str = Query("public", description="查询范围: public/my/all"),
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取模板列表
    支持：向量语义搜索、分类筛选
    """
    query = db.query(ContractTemplate).filter(ContractTemplate.status == "active")

    # 1. 权限范围
    if scope == "public":
        query = query.filter(ContractTemplate.is_public == True)
    elif scope == "my":
        query = query.filter(ContractTemplate.owner_id == current_user.id)
    elif scope == "all" and current_user.is_admin:
        pass 
    
    # 2. 类别过滤
    if category:
        # 支持查 具体类型(房屋租赁合同) 或 一级大类(租赁合同)
        query = query.filter(
            (ContractTemplate.category == category) | 
            (ContractTemplate.subcategory == category) |
            (ContractTemplate.primary_contract_type == category)
        )

    # 3. 智能搜索 (向量优先)
    if keyword:
        search_vector = None
        try:
            search_vector = await get_text_embedding(keyword)
        except:
            pass

        if search_vector:
            # 语义搜索：按向量距离排序
            query = query.order_by(ContractTemplate.embedding.l2_distance(search_vector))
        else:
            # 降级搜索：关键词模糊匹配
            query = query.filter(
                (ContractTemplate.name.ilike(f"%{keyword}%")) |
                (ContractTemplate.description.ilike(f"%{keyword}%"))
            )
    else:
        # 默认按时间倒序
        query = query.order_by(ContractTemplate.created_at.desc())

    # 4. 分页
    total_count = query.count()
    templates = query.offset((page - 1) * page_size).limit(page_size).all()

    # 转换字典
    results = [t.to_dict() for t in templates]

    return {
        "templates": results,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size
    }


@router.get("/{template_id}/download")
async def download_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """下载文件 (优先下载原始 Source File)"""
    template = db.query(ContractTemplate).filter(ContractTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 权限检查
    if not template.is_public and template.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权下载")

    # 查找物理路径
    file_path = None
    if template.metadata_info and "source_file_url" in template.metadata_info:
        file_path = template.metadata_info["source_file_url"]
    
    if not file_path or not os.path.exists(file_path):
        # 兜底：找系统生成的 MD 文件
        file_path = template.file_url

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="物理文件已丢失")

    # 更新下载计数
    template.download_count += 1
    db.commit()

    filename = template.metadata_info.get("original_filename", template.file_name)
    return FileResponse(file_path, filename=filename, media_type='application/octet-stream')


@router.get("/{template_id}/content")
async def get_template_content(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Markdown 文本 (用于前端预览)"""
    template = db.query(ContractTemplate).filter(ContractTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    content = ""
    if template.file_url and os.path.exists(template.file_url):
        try:
            with open(template.file_url, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            pass
            
    return {"id": template.id, "content": content, "editable": True}


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新模板 (如果上传新文件，会重新向量化)"""
    template = db.query(ContractTemplate).filter(ContractTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if not current_user.is_admin and template.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="权限不足")
    
    if name:
        template.name = name
    
    if file:
        try:
            # 1. 保存新文件
            filename = f"{template_id}_{file.filename}"
            source_path = os.path.join(TEMPLATE_STORAGE_DIR, "source", filename)
            os.makedirs(os.path.dirname(source_path), exist_ok=True)
            
            with open(source_path, 'wb') as f:
                shutil.copyfileobj(file.file, f)
            
            # 2. 转 Markdown
            md_path = os.path.join(TEMPLATE_STORAGE_DIR, "markdown", f"{template_id}.md")
            md_content = convert_to_markdown(source_path)
            
            if md_content:
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                
                # 3. 更新向量
                # 重新构建 Prompt，包含原有的分类信息
                emb_text = f"标题:{template.name}\n分类:{template.category}\n内容:{md_content[:6000]}"
                vector_embedding = await get_text_embedding(emb_text)
                if vector_embedding:
                    template.embedding = vector_embedding
            
            # 4. 更新 DB 路径
            template.file_url = md_path
            if not template.metadata_info: template.metadata_info = {}
            template.metadata_info["source_file_url"] = source_path
            template.metadata_info["original_filename"] = file.filename

        except Exception as e:
            logger.error(f"更新失败: {e}")
            raise HTTPException(status_code=500, detail="文件更新失败")

    db.commit()
    return {"message": "更新成功", "id": template.id}

@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除模板"""
    template = db.query(ContractTemplate).filter(ContractTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404)

    if not current_user.is_admin and template.owner_id != current_user.id:
        raise HTTPException(status_code=403)

    # 清理文件
    if template.file_url and os.path.exists(template.file_url):
        try: os.remove(template.file_url)
        except: pass
    
    if template.metadata_info and "source_file_url" in template.metadata_info:
        try: os.remove(template.metadata_info["source_file_url"])
        except: pass

    db.delete(template)
    db.commit()
    return {"message": "删除成功"}
@router.put("/{template_id}/contract-features")
async def update_template_contract_features(
    template_id: str,
    contract_features_data: dict = Body(...), # 显式声明为 Body
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新合同法律特征及详细场景 (修复 404 及字段缺失问题)
    """
    # 1. 权限校验
    if not current_user.is_admin:
        # 如果不是管理员，检查是否是自己的模板
        template = db.query(ContractTemplate).filter(ContractTemplate.id == template_id).first()
        if template and template.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="权限不足")
    
    # 2. 查找模板
    template = db.query(ContractTemplate).filter(ContractTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 3. 允许更新的字段白名单 (加入了 detailed_usage_scenario)
    allowed_fields = [
        "primary_contract_type", "secondary_types", "transaction_nature", 
        "contract_object", "complexity", "stance", "risk_level", 
        "is_recommended", "metadata_info",
        "detailed_usage_scenario", "version_type", "stance_tendency" # ✨ 新增支持这些字段
    ]
    
    # 4. 执行更新
    updated_keys = []
    for field in allowed_fields:
        if field in contract_features_data:
            setattr(template, field, contract_features_data[field])
            updated_keys.append(field)

    db.commit()
    logger.info(f"[Update] 模板 {template_id} 特征更新成功，字段: {updated_keys}")
    
    return {"message": "更新成功", "id": template.id, "updated_fields": updated_keys}