# backend/app/api/v1/endpoints/smart_chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from pydantic import BaseModel

from app.api import deps
from app.services.deepseek_service import deepseek_service

router = APIRouter()


# ==================== 请求/响应模型 ====================

class GuidanceRequest(BaseModel):
    """智能引导请求模型"""
    message: str
    conversation_history: List[Dict[str, str]] = []


class ConsultationRequest(BaseModel):
    """智能咨询请求模型"""
    message: str
    conversation_history: List[Dict[str, str]] = []


class GuidanceResponse(BaseModel):
    """智能引导响应模型"""
    response: str
    suggestions: List[str] = []
    action_buttons: List[Dict[str, Any]] = []
    confidence: float = 0.0


class ConsultationResponse(BaseModel):
    """智能咨询响应模型"""
    response: str
    suggestions: List[str] = []
    action_buttons: List[Dict[str, Any]] = []
    confidence: float = 0.0


# ==================== 智能引导接口 ====================

@router.post("/guidance", response_model=GuidanceResponse)
async def intelligent_guidance_endpoint(
    request: GuidanceRequest,
    current_user = Depends(deps.get_current_user_optional)
) -> GuidanceResponse:
    """
    智能引导接口 - 帮助用户明确需求,推荐最匹配的工作流

    Args:
        request: 包含用户消息和对话历史的请求
        current_user: 当前用户(可选)

    Returns:
        GuidanceResponse: 包含AI回复、建议和操作按钮的响应

    Example:
        POST /api/v1/smart-chat/guidance
        {
            "message": "我需要法律咨询服务",
            "conversation_history": []
        }
    """
    try:
        # 调用Deepseek服务进行智能引导
        result = await deepseek_service.intelligent_guidance(
            user_message=request.message,
            conversation_history=request.conversation_history
        )

        return GuidanceResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"智能引导失败: {str(e)}"
        )


# ==================== 智能咨询接口 ====================

@router.post("/expert-consultation", response_model=ConsultationResponse)
async def legal_expert_consultation_endpoint(
    request: ConsultationRequest,
    current_user = Depends(deps.get_current_user_optional)
) -> ConsultationResponse:
    """
    智能咨询接口 - 资深律师角色,提供专业法律咨询服务

    Args:
        request: 包含用户消息和对话历史的请求
        current_user: 当前用户(可选)

    Returns:
        ConsultationResponse: 包含AI回复、建议和操作按钮的响应

    Example:
        POST /api/v1/smart-chat/expert-consultation
        {
            "message": "我遇到了劳动合同纠纷,请问我该怎么办?",
            "conversation_history": []
        }
    """
    try:
        # 调用Deepseek服务进行专业咨询
        result = await deepseek_service.legal_expert_consultation(
            user_message=request.message,
            conversation_history=request.conversation_history
        )

        return ConsultationResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"智能咨询失败: {str(e)}"
        )


# ==================== 健康检查接口 ====================

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    智能对话服务健康检查

    Returns:
        服务状态信息
    """
    return {
        "status": "healthy",
        "service": "smart-chat",
        "features": {
            "intelligent_guidance": True,
            "legal_expert_consultation": True
        }
    }
