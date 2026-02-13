from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

from app.api.deps import get_current_user_optional
from app.services.consultation.content_extractor import consultation_content_extractor, ExtractedContext

router = APIRouter()
logger = logging.getLogger(__name__)

class ContextExtractionRequest(BaseModel):
    session_id: str
    target_module: str

@router.post("/extract", response_model=ExtractedContext)
async def extract_consultation_context(
    request: ContextExtractionRequest,
    current_user = Depends(get_current_user_optional)
):
    """
    提取咨询上下文用于跨模块复用
    """
    user_id = current_user.id if current_user else 1
    
    logger.info(f"[Context API] 收到提取请求: session_id={request.session_id}, target={request.target_module}")
    
    result = await consultation_content_extractor.extract_context_for_module(
        session_id=request.session_id,
        target_module=request.target_module,
        user_id=user_id
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="无法提取上下文或会话不存在")
        
    return result
