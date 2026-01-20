# backend/app/services/consultation_history_service.py
"""
对话历史管理服务
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.consultation_history import ConsultationHistory

logger = logging.getLogger(__name__)


class ConsultationHistoryService:
    """对话历史管理服务"""

    async def save_conversation(
        self,
        user_id: int,
        session_id: str,
        messages: List[Dict],
        title: str,
        specialist_type: Optional[str] = None,
        classification: Optional[Dict] = None
    ) -> bool:
        """
        保存对话到历史记录

        Args:
            user_id: 用户ID
            session_id: 会话ID
            messages: 消息列表
            title: 会话标题
            specialist_type: 专业律师类型
            classification: 分类结果

        Returns:
            是否保存成功
        """
        try:
            db: Session = SessionLocal()

            # 检查是否已存在
            existing = db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id
            ).first()

            if existing:
                # 更新现有记录
                existing.messages = messages
                existing.message_count = len(messages)
                existing.updated_at = datetime.now()
                if specialist_type:
                    existing.specialist_type = specialist_type
                if classification:
                    existing.classification = classification
                logger.info(f"[历史服务] 更新会话: {session_id}")
            else:
                # 创建新记录
                history = ConsultationHistory(
                    user_id=user_id,
                    session_id=session_id,
                    title=title,
                    messages=messages,
                    message_count=len(messages),
                    specialist_type=specialist_type,
                    classification=classification,
                    status='archived'  # 保存到历史即为归档
                )
                db.add(history)
                logger.info(f"[历史服务] 创建会话: {session_id}")

            db.commit()
            db.close()
            return True

        except Exception as e:
            logger.error(f"[历史服务] 保存会话失败: {e}")
            if 'db' in locals():
                db.close()
            return False

    async def get_user_history(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        获取用户历史记录列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            {sessions: [...], total: 10}
        """
        try:
            db: Session = SessionLocal()

            # 查询总数
            total = db.query(ConsultationHistory).filter(
                ConsultationHistory.user_id == user_id
            ).count()

            # 查询历史记录（按创建时间倒序）
            histories = db.query(ConsultationHistory).filter(
                ConsultationHistory.user_id == user_id
            ).order_by(
                ConsultationHistory.created_at.desc()
            ).offset(offset).limit(limit).all()

            sessions = [history.to_dict() for history in histories]

            db.close()

            logger.info(f"[历史服务] 获取用户历史: user_id={user_id}, count={len(sessions)}")

            return {
                "sessions": sessions,
                "total": total
            }

        except Exception as e:
            logger.error(f"[历史服务] 获取历史失败: {e}")
            if 'db' in locals():
                db.close()
            return {"sessions": [], "total": 0}

    async def get_conversation(
        self,
        user_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取单个会话详情

        Args:
            user_id: 用户ID
            session_id: 会话ID

        Returns:
            会话详情，如果不存在返回None
        """
        try:
            db: Session = SessionLocal()

            history = db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id,
                ConsultationHistory.user_id == user_id
            ).first()

            db.close()

            if not history:
                logger.warning(f"[历史服务] 会话不存在: {session_id}")
                return None

            logger.info(f"[历史服务] 获取会话详情: {session_id}")

            return history.to_dict()

        except Exception as e:
            logger.error(f"[历史服务] 获取会话失败: {e}")
            if 'db' in locals():
                db.close()
            return None

    async def delete_conversation(
        self,
        user_id: int,
        session_id: str
    ) -> bool:
        """
        删除会话

        Args:
            user_id: 用户ID
            session_id: 会话ID

        Returns:
            是否删除成功
        """
        try:
            db: Session = SessionLocal()

            history = db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id,
                ConsultationHistory.user_id == user_id
            ).first()

            if not history:
                logger.warning(f"[历史服务] 删除失败，会话不存在: {session_id}")
                db.close()
                return False

            db.delete(history)
            db.commit()
            db.close()

            logger.info(f"[历史服务] 删除会话成功: {session_id}")

            return True

        except Exception as e:
            logger.error(f"[历史服务] 删除会话失败: {e}")
            if 'db' in locals():
                db.close()
            return False

    async def continue_conversation(
        self,
        user_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        继续历史会话

        Args:
            user_id: 用户ID
            session_id: 会话ID

        Returns:
            会话详情，如果不存在返回None
        """
        try:
            db: Session = SessionLocal()

            history = db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id,
                ConsultationHistory.user_id == user_id
            ).first()

            if not history:
                logger.warning(f"[历史服务] 继续失败，会话不存在: {session_id}")
                db.close()
                return None

            # 更新状态为active
            history.status = 'active'
            history.updated_at = datetime.now()

            db.commit()
            db.close()

            logger.info(f"[历史服务] 继续会话: {session_id}")

            return history.to_dict()

        except Exception as e:
            logger.error(f"[历史服务] 继续会话失败: {e}")
            if 'db' in locals():
                db.close()
            return None


# 创建全局实例
consultation_history_service = ConsultationHistoryService()
