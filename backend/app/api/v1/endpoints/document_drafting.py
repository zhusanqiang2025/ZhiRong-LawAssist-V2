# backend/app/api/v1/endpoints/document_drafting.py
"""
文书起草 API 端点

提供文书起草相关的 API 接口：
1. /templates - 获取可用的文书类型列表
2. /analyze - 分析用户需求，识别文书类型和要素
3. /generate - 生成文书（支持文件上传）
4. /upload - 上传相关资料文件
"""
import logging
import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.document_drafting.config import list_document_types, get_document_config
from app.services.document_drafting.workflow import get_document_drafting_workflow

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class AnalyzeRequest(BaseModel):
    """需求分析请求"""
    user_input: str
    uploaded_files: Optional[List[str]] = []
    reference_content: Optional[str] = ""


class AnalyzeResponse(BaseModel):
    """需求分析响应"""
    document_type: str
    document_name: str
    extracted_info: Dict[str, Any]
    clarification_questions: List[str]


class GenerateRequest(BaseModel):
    """文书生成请求"""
    user_input: str
    uploaded_files: Optional[List[str]] = []
    document_type: Optional[str] = None  # 可指定文书类型
    clarification_answers: Optional[Dict[str, Any]] = {}


class GenerateResponse(BaseModel):
    """文书生成响应"""
    session_id: str
    generated_documents: List[Dict[str, Any]]
    status: str
    message: str


class TemplateInfo(BaseModel):
    """文书模板信息"""
    id: str
    name: str
    description: str
    category: str


# ==================== API 端点 ====================

@router.get("/templates", response_model=List[TemplateInfo])
def get_templates(
    category: Optional[str] = None
) -> List[TemplateInfo]:
    """
    获取可用的文书类型列表

    Args:
        category: 可选的分类筛选（letter/judicial）

    Returns:
        文书类型列表
    """
    try:
        docs = list_document_types(category)

        templates = []
        for doc_id, doc_config in {
            "lawyer_letter": {
                "name": "律师函",
                "template_type": "letter",
                "description": "律师事务所函件，用于催告、通知等",
                "legal_features": {
                    "transaction_nature": "法律服务",
                    "contract_object": "法律服务函件"
                }
            },
            "demand_letter": {
                "name": "催告函",
                "template_type": "letter",
                "description": "催告履行义务的函件",
                "legal_features": {
                    "transaction_nature": "债务催收",
                    "contract_object": "债权催收"
                }
            },
            "notification_letter": {
                "name": "通知函",
                "template_type": "letter",
                "description": "各类通知告知函件",
                "legal_features": {
                    "transaction_nature": "通知告知",
                    "contract_object": "通知事项"
                }
            },
            "civil_complaint": {
                "name": "民事起诉状",
                "template_type": "judicial",
                "description": "民事诉讼起诉状",
                "legal_features": {
                    "transaction_nature": "民事诉讼",
                    "contract_object": "民事纠纷",
                    "stance": "原告立场"
                }
            },
            "defense_statement": {
                "name": "答辩状",
                "template_type": "judicial",
                "description": "被告答辩状",
                "legal_features": {
                    "transaction_nature": "民事诉讼",
                    "contract_object": "民事纠纷",
                    "stance": "被告立场"
                }
            },
            "evidence_list": {
                "name": "证据清单",
                "template_type": "judicial",
                "description": "诉讼证据清单",
                "legal_features": {
                    "transaction_nature": "民事诉讼",
                    "contract_object": "证据材料"
                }
            },
            "application": {
                "name": "申请书",
                "template_type": "judicial",
                "description": "各类申请书（财产保全、先予执行等）",
                "legal_features": {
                    "transaction_nature": "民事诉讼",
                    "contract_object": "程序申请"
                }
            },
            "power_of_attorney": {
                "name": "授权委托书",
                "template_type": "judicial",
                "description": "诉讼授权委托书",
                "legal_features": {
                    "transaction_nature": "法律服务",
                    "contract_object": "代理授权"
                }
            }
        }.items():
            # 如果指定了分类，进行过滤
            if category and doc_config["template_type"] != category:
                continue

            templates.append(TemplateInfo(
                id=doc_id,
                name=doc_config["name"],
                description=doc_config["description"],
                category=doc_config["template_type"]
            ))

        return templates

    except Exception as e:
        logger.error(f"[DocumentDraftingAPI] 获取模板列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取模板列表失败: {str(e)}")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_requirement(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_user)
) -> AnalyzeResponse:
    """
    分析用户需求，识别文书类型和要素

    Args:
        request: 分析请求
        current_user: 当前登录用户

    Returns:
        分析结果，包含文书类型、提取的信息和需要澄清的问题
    """
    try:
        user_input = request.user_input

        # 简单的文书类型识别（实际应该使用 LLM）
        document_type = None
        type_keywords = {
            "lawyer_letter": ["律师函", "律师通知", "律师事务所函"],
            "demand_letter": ["催告函", "催款函", "催告"],
            "notification_letter": ["通知函", "通知书", "通知"],
            "legal_opinion": ["法律意见书", "法律意见"],
            "civil_complaint": ["起诉状", "民事起诉状", "起诉"],
            "defense_statement": ["答辩状", "答辩"],
            "evidence_list": ["证据清单", "证据", "举证"],
            "application": ["申请书", "申请"],
            "power_of_attorney": ["授权委托书", "委托书", "授权"]
        }

        for doc_type, keywords in type_keywords.items():
            if any(keyword in user_input for keyword in keywords):
                document_type = doc_type
                break

        if not document_type:
            document_type = "lawyer_letter"

        doc_config = get_document_config(document_type)

        return AnalyzeResponse(
            document_type=document_type,
            document_name=doc_config["name"] if doc_config else document_type,
            extracted_info={
                "用户需求": user_input,
                "上传文件数": len(request.uploaded_files) if request.uploaded_files else 0
            },
            clarification_questions=[]
        )

    except Exception as e:
        logger.error(f"[DocumentDraftingAPI] 需求分析失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"需求分析失败: {str(e)}")


@router.post("/generate", response_model=GenerateResponse)
async def generate_document(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user)
) -> GenerateResponse:
    """
    生成文书

    Args:
        request: 生成请求
        current_user: 当前登录用户

    Returns:
        生成的文书内容
    """
    try:
        # 获取工作流
        workflow = get_document_drafting_workflow()

        # 构建初始状态
        initial_state = {
            "user_input": request.user_input,
            "uploaded_files": request.uploaded_files or [],
            "reference_content": None,
            "knowledge_graph_features": None,
            "document_type": request.document_type,
            "analysis_result": None,
            "template_match_result": None,
            "generation_strategy": None,
            "template_content": None,
            "drafted_content": None,
            "generated_documents": [],
            "error": None,
            "requires_user_input": False,
            "clarification_questions": []
        }

        # 执行工作流
        logger.info(f"[DocumentDraftingAPI] 开始文书生成流程，用户: {current_user.id}")
        result = await workflow.ainvoke(initial_state)

        # 检查错误
        if result.get("error"):
            logger.error(f"[DocumentDraftingAPI] 文书生成失败: {result['error']}")
            return GenerateResponse(
                session_id=str(current_user.id),
                generated_documents=[],
                status="failed",
                message=result["error"]
            )

        # 检查生成结果
        generated_documents = result.get("generated_documents", [])
        if not generated_documents:
            logger.error("[DocumentDraftingAPI] 未生成文书内容")
            return GenerateResponse(
                session_id=str(current_user.id),
                generated_documents=[],
                status="failed",
                message="未生成文书内容"
            )

        logger.info(f"[DocumentDraftingAPI] 文书生成成功，类型: {result.get('document_type')}")

        return GenerateResponse(
            session_id=str(current_user.id),
            generated_documents=generated_documents,
            status="success",
            message="文书生成成功"
        )

    except Exception as e:
        logger.error(f"[DocumentDraftingAPI] 文书生成异常: {str(e)}", exc_info=True)
        return GenerateResponse(
            session_id=str(current_user.id),
            generated_documents=[],
            status="failed",
            message=f"文书生成异常: {str(e)}"
        )


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    上传相关资料文件

    Args:
        file: 上传的文件
        current_user: 当前登录用户

    Returns:
        上传结果，包含文件路径
    """
    try:
        # 创建用户上传目录
        upload_dir = f"storage/uploads/{current_user.id}/document_drafting"
        os.makedirs(upload_dir, exist_ok=True)

        # 保存文件
        file_path = f"{upload_dir}/{file.filename}"
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"[DocumentDraftingAPI] 文件上传成功: {file.filename}, 用户: {current_user.id}")

        return {
            "file_path": file_path,
            "filename": file.filename,
            "message": "文件上传成功"
        }

    except Exception as e:
        logger.error(f"[DocumentDraftingAPI] 文件上传失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")
