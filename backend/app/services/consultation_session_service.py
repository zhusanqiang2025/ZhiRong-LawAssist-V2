# backend/app/services/consultation_session_service.py
"""
智能咨询会话管理服务

使用 Redis 存储会话状态，实现：
1. 会话持久化
2. 后端自动判断是否为后续问题
3. 不依赖前端状态管理
"""
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .cache_service import cache_service

logger = logging.getLogger(__name__)


class ConsultationSessionService:
    """智能咨询会话管理服务"""

    def __init__(self):
        """初始化服务"""
        self.cache = cache_service
        self.session_prefix = "consultation_session:"
        self.session_expire = 3600  # 1小时过期

    def _make_key(self, session_id: str) -> str:
        """生成缓存键"""
        return f"{self.session_prefix}{session_id}"

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话信息

        Args:
            session_id: 会话ID

        Returns:
            会话信息，如果不存在返回 None
        """
        if not session_id:
            return None

        try:
            key = self._make_key(session_id)
            session_data = self.cache.get(key)

            if session_data:
                logger.info(f"[会话管理] 找到会话: {session_id}")
                return session_data
            else:
                logger.info(f"[会话管理] 会话不存在或已过期: {session_id}")
                return None

        except Exception as e:
            logger.error(f"[会话管理] 获取会话失败: {e}")
            return None

    async def save_session(
        self,
        session_id: str,
        is_in_specialist_mode: bool = False,
        specialist_output: Optional[Dict[str, Any]] = None,
        classification: Optional[Dict[str, Any]] = None,
        question: Optional[str] = None
    ) -> bool:
        """
        保存会话信息

        Args:
            session_id: 会话ID
            is_in_specialist_mode: 是否已进入专业律师模式
            specialist_output: 专业律师输出
            classification: 分类结果
            question: 用户问题

        Returns:
            是否保存成功
        """
        if not session_id:
            return False

        try:
            key = self._make_key(session_id)

            session_data = {
                "session_id": session_id,
                "is_in_specialist_mode": is_in_specialist_mode,
                "specialist_output": specialist_output,
                "classification": classification,
                "last_question": question,
                "updated_at": datetime.now().isoformat()
            }

            # 保存到 Redis，1小时过期
            success = self.cache.set(key, session_data, expire=self.session_expire)

            if success:
                logger.info(f"[会话管理] 会话已保存: {session_id} (specialist_mode={is_in_specialist_mode})")
            else:
                logger.warning(f"[会话管理] 会话保存失败: {session_id}")

            return success

        except Exception as e:
            logger.error(f"[会话管理] 保存会话失败: {e}")
            return False

    async def is_follow_up_question(self, session_id: str) -> bool:
        """
        判断是否为后续问题

        Args:
            session_id: 会话ID

        Returns:
            True 表示后续问题，False 表示新问题
        """
        session = await self.get_session(session_id)

        if not session:
            return False

        # 如果会话存在且已进入专业律师模式，则为后续问题
        is_in_specialist_mode = session.get("is_in_specialist_mode", False)
        logger.info(f"[会话管理] 判断是否为后续问题: {session_id} -> {is_in_specialist_mode}")

        return is_in_specialist_mode

    async def get_specialist_output(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取上一轮专业律师输出

        Args:
            session_id: 会话ID

        Returns:
            专业律师输出，如果不存在返回 None
        """
        session = await self.get_session(session_id)

        if not session:
            return None

        return session.get("specialist_output")

    async def get_classification(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取第一阶段的分类结果

        Args:
            session_id: 会话ID

        Returns:
            分类结果，如果不存在返回 None
        """
        session = await self.get_session(session_id)

        if not session:
            return None

        return session.get("classification")

    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话（用户主动开启新对话）

        Args:
            session_id: 会话ID

        Returns:
            是否删除成功
        """
        if not session_id:
            return False

        try:
            key = self._make_key(session_id)
            success = self.cache.delete(key)

            if success:
                logger.info(f"[会话管理] 会话已删除: {session_id}")
            else:
                logger.warning(f"[会话管理] 会话删除失败: {session_id}")

            return success

        except Exception as e:
            logger.error(f"[会话管理] 删除会话失败: {e}")
            return False

    def _calculate_question_similarity(self, question1: str, question2: str) -> float:
        """
        计算两个问题的相似度（简单实现）

        Args:
            question1: 问题1
            question2: 问题2

        Returns:
            相似度（0-1）
        """
        # 简单实现：比较前N个字符的匹配度
        n = min(20, len(question1), len(question2))
        if n == 0:
            return 0.0

        matches = sum(1 for i in range(n) if question1[i] == question2[i])
        return matches / n

    async def get_or_create_session(
        self,
        session_id: Optional[str],
        question: Optional[str] = None,
        reset_session: bool = False
    ) -> tuple[str, bool, Optional[Dict[str, Any]]]:
        """
        获取或创建会话

        Args:
            session_id: 会话ID（可为None）
            question: 用户问题
            reset_session: 是否重置会话状态（强制作为新问题处理）

        Returns:
            (session_id, is_follow_up, previous_output)
        """
        # 如果请求重置会话，删除旧会话
        if reset_session and session_id:
            logger.info(f"[会话管理] 重置会话请求: {session_id}")
            await self.delete_session(session_id)
            return await self.get_or_create_session(None, question, False)

        # 如果没有 session_id，创建新会话
        if not session_id:
            import uuid
            new_session_id = f"session-{uuid.uuid4().hex[:16]}"
            logger.info(f"[会话管理] 创建新会话: {new_session_id}")
            return new_session_id, False, None

        # 检查会话是否存在
        session = await self.get_session(session_id)

        if not session:
            # 会话不存在或已过期，作为新问题处理
            logger.info(f"[会话管理] 会话不存在，作为新问题: {session_id}")
            return session_id, False, None

        # 会话存在，判断是否为后续问题
        is_in_specialist_mode = session.get("is_in_specialist_mode", False)

        # 【关键修改】检查是否为真正的新问题
        # 如果问题内容差异很大，可能是用户在咨询新的法律问题
        if is_in_specialist_mode and question:
            last_question = session.get("last_question", "")
            # 简单的启发式判断：如果新问题与上一轮问题差异很大
            # TODO: 可以使用嵌入向量相似度来判断
            if last_question and len(question) > 0:
                # 如果新问题的前20个字符与上一轮问题差异较大
                similarity = self._calculate_question_similarity(question, last_question)
                if similarity < 0.3:  # 相似度低于30%，认为是新问题
                    logger.info(f"[会话管理] 检测到新问题（相似度={similarity:.2f}）: {session_id}")
                    # 重置会话状态
                    await self.save_session(
                        session_id=session_id,
                        is_in_specialist_mode=False,
                        specialist_output=None,
                        classification=None,
                        question=question
                    )
                    return session_id, False, None

        # 后续问题：获取上一轮输出
        if is_in_specialist_mode:
            previous_output = await self.get_specialist_output(session_id)
            logger.info(f"[会话管理] 后续问题: {session_id}")
            return session_id, True, previous_output

        # 新问题：使用现有 session_id
        logger.info(f"[会话管理] 新问题（重用会话ID）: {session_id}")
        return session_id, False, None


# 创建全局实例
consultation_session_service = ConsultationSessionService()
