# backend/app/api/v1/endpoints/consultation_history.py
"""
对话历史管理API端点
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from app.services.consultation.history_service import consultation_history_service
from app.api.deps import get_current_user

router = APIRouter(prefix="/consultation/history", tags=["对话历史"])
logger = logging.getLogger(__name__)


# ==================== 请求/响应模型 ====================

class SaveHistoryRequest(BaseModel):
    """保存历史请求"""
    session_id: str
    messages: List[Dict]
    title: str
    specialist_type: Optional[str] = None
    classification: Optional[Dict] = None


class SaveHistoryResponse(BaseModel):
    """保存历史响应"""
    success: bool
    message: str


class HistoryListResponse(BaseModel):
    """历史列表响应"""
    sessions: List[Dict]
    total: int


class HistoryDetailResponse(BaseModel):
    """历史详情响应"""
    session_id: str
    title: str
    messages: List[Dict]
    message_count: int
    created_at: str
    updated_at: str
    specialist_type: Optional[str]
    classification: Optional[Dict]


class ContinueSessionResponse(BaseModel):
    """继续会话响应"""
    success: bool
    session: Optional[Dict] = None
    message: str


# ==================== API端点 ====================

@router.post("", response_model=SaveHistoryResponse)
async def save_conversation_history(
    request: SaveHistoryRequest,
    current_user = Depends(get_current_user)
):
    """
    保存对话到历史记录

    Args:
        request: 保存历史请求
        current_user: 当前用户

    Returns:
        保存结果
    """
    try:
        success = await consultation_history_service.save_conversation(
            user_id=current_user.id,
            session_id=request.session_id,
            messages=request.messages,
            title=request.title,
            specialist_type=request.specialist_type,
            classification=request.classification
        )

        if success:
            logger.info(f"[API] 保存会话历史成功: {request.session_id}")
            return SaveHistoryResponse(
                success=True,
                message="会话已保存到历史"
            )
        else:
            logger.error(f"[API] 保存会话历史失败: {request.session_id}")
            return SaveHistoryResponse(
                success=False,
                message="保存失败，请稍后重试"
            )

    except Exception as e:
        logger.error(f"[API] 保存历史异常: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("", response_model=HistoryListResponse)
async def get_conversation_history(
    limit: int = 50,
    offset: int = 0,
    current_user = Depends(get_current_user)
):
    """
    获取用户历史记录列表

    Args:
        limit: 返回数量限制
        offset: 偏移量
        current_user: 当前用户

    Returns:
        历史记录列表
    """
    try:
        result = await consultation_history_service.get_user_history(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )

        logger.info(f"[API] 获取历史列表: user_id={current_user.id}, count={result['total']}")

        return HistoryListResponse(
            sessions=result["sessions"],
            total=result["total"]
        )

    except Exception as e:
        logger.error(f"[API] 获取历史列表异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/{session_id}", response_model=HistoryDetailResponse)
async def get_conversation_detail(
    session_id: str,
    current_user = Depends(get_current_user)
):
    """
    获取单个会话详情

    Args:
        session_id: 会话ID
        current_user: 当前用户

    Returns:
        会话详情
    """
    try:
        session = await consultation_history_service.get_conversation(
            user_id=current_user.id,
            session_id=session_id
        )

        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        logger.info(f"[API] 获取会话详情: {session_id}")

        return HistoryDetailResponse(**session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 获取会话详情异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.delete("/{session_id}")
async def delete_conversation(
    session_id: str,
    current_user = Depends(get_current_user)
):
    """
    删除会话

    Args:
        session_id: 会话ID
        current_user: 当前用户

    Returns:
        删除结果
    """
    try:
        success = await consultation_history_service.delete_conversation(
            user_id=current_user.id,
            session_id=session_id
        )

        if success:
            logger.info(f"[API] 删除会话成功: {session_id}")
            return {"success": True, "message": "会话已删除"}
        else:
            raise HTTPException(status_code=404, detail="会话不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 删除会话异常: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.post("/{session_id}/continue", response_model=ContinueSessionResponse)
async def continue_conversation(
    session_id: str,
    current_user = Depends(get_current_user)
):
    """
    继续历史会话

    Args:
        session_id: 会话ID
        current_user: 当前用户

    Returns:
        继续结果
    """
    try:
        session = await consultation_history_service.continue_conversation(
            user_id=current_user.id,
            session_id=session_id
        )

        if session:
            logger.info(f"[API] 继续会话成功: {session_id}")
            return ContinueSessionResponse(
                success=True,
                session=session,
                message="已加载历史会话"
            )
        else:
            raise HTTPException(status_code=404, detail="会话不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 继续会话异常: {e}")
        raise HTTPException(status_code=500, detail=f"继续失败: {str(e)}")
