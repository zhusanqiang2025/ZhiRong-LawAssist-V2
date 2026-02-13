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

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.consultation_history import ConsultationHistory
from app.services.consultation.history_service import consultation_history_service

logger = logging.getLogger(__name__)


class ConsultationSessionService:
    """智能咨询会话管理服务"""

    def __init__(self, db: Optional[Session] = None):
        """
        初始化服务
        Args:
            db: 数据库会话，如果未提供则创建新的
        """
        self.db = db or SessionLocal()

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        从数据库获取会话信息
        """
        if not session_id:
            return None

        try:
            # 查询数据库
            history = self.db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id
            ).first()

            if history:
                # 【增强修复】优先使用 session_state 中的数据，但补充缺失的数据库字段
                if history.session_state:
                    # 合并数据库字段到 session_state 中，确保所有关键字段都存在
                    session_state = history.session_state.copy()

                    # 强制从数据库列回填到session_state，确保数据一致性
                    session_state['current_phase'] = history.current_phase
                    session_state['user_decision'] = history.user_decision
                    session_state['status'] = history.status
                    session_state['session_id'] = history.session_id

                    # 【修复】确保 specialist_output 字段存在
                    if 'specialist_output' not in session_state:
                        session_state['specialist_output'] = None

                    # 只有当classification不存在于session_state中时才从数据库获取
                    if 'classification' not in session_state:
                        session_state['classification'] = history.classification

                    logger.info(f"[会话管理] 从数据库加载会话状态: {session_id}")
                    return session_state

                # 兼容旧数据：如果 session_state 为空，从数据库字段构建完整状态
                logger.info(f"[会话管理] 发现旧版会话，构建临时状态: {session_id}")
                return {
                    "session_id": history.session_id,
                    "is_in_specialist_mode": bool(history.specialist_type),
                    "specialist_output": None, # 无法从旧结构完全恢复
                    "classification": history.classification,
                    "last_question": None,
                    "updated_at": history.updated_at.isoformat() if history.updated_at else None,
                    # 【增强修复】强制包含所有关键字段
                    "current_phase": history.current_phase,
                    "user_decision": history.user_decision,
                    "status": history.status
                }
            else:
                logger.info(f"[会话管理] 会话不存在: {session_id}")
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
        question: Optional[str] = None,
        user_id: int = 1,  # 默认用户ID
        current_phase: Optional[str] = None,  # 【新增】当前阶段
        user_decision: Optional[str] = None,  # 【新增】用户决策
        current_task_id: Optional[str] = None  # 【新增】当前任务ID
    ) -> bool:
        """保存会话信息到数据库"""
        if not session_id:
            return False

        try:
            # 构建会话状态对象
            session_data = {
                "session_id": session_id,
                "is_in_specialist_mode": is_in_specialist_mode,
                "specialist_output": specialist_output,
                "classification": classification,
                "last_question": question,
                "updated_at": datetime.now().isoformat()
            }

            # 查找现有记录
            history = self.db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id
            ).first()

            # 构造新消息对（如果提供了问题和输出）
            new_messages = []
            if question and specialist_output:
                # 构造 AI 回复内容
                analysis = specialist_output.get("legal_analysis", "")
                advice = specialist_output.get("legal_advice", "")
                risk = specialist_output.get("risk_warning", "")

                parts = []
                if analysis: parts.append(f"【分析】\n{analysis}")
                if advice: parts.append(f"【建议】\n{advice}")
                if risk: parts.append(f"【风险提醒】\n{risk}")
                answer_content = "\n\n".join(parts)

                new_messages = [
                    {
                        "role": "user",
                        "content": question,
                        "created_at": datetime.now().isoformat()
                    },
                    {
                        "role": "assistant",
                        "content": answer_content,
                        "specialist_output": specialist_output,
                        "created_at": datetime.now().isoformat()
                    }
                ]

            if history:
                # 更新现有记录
                history.updated_at = datetime.now()

                # 【新增】更新新字段
                if current_phase is not None:
                    history.current_phase = current_phase
                if user_decision is not None:
                    history.user_decision = user_decision
                if current_task_id is not None:
                    history.current_task_id = current_task_id

                # 【修复】同时更新 specialist_type 字段，保持查询一致性
                # 优先从 specialist_output 中提取，其次从 classification 中提取
                if specialist_output and 'specialist_type' in specialist_output:
                    history.specialist_type = specialist_output.get('specialist_type')
                elif classification and classification.get('specialist_role'):
                    # 【新增】从 classification 中提取 specialist_role 作为 specialist_type
                    history.specialist_type = classification.get('specialist_type') or classification.get('specialist_role')
                elif is_in_specialist_mode:
                    # 【新增】如果明确标记为专家模式，使用默认值
                    history.specialist_type = '专业律师'

                # 追加消息
                if new_messages:
                    # 注意：SQLAlchemy JSON 类型追加需要重新赋值
                    current_messages = list(history.messages) if history.messages else []
                    current_messages.extend(new_messages)
                    history.messages = current_messages
                    history.message_count = len(current_messages)

                # 【增强修复】确保关键字段同步到 session_state
                # 在更新数据库列后，立即将这些值同步到session_state
                session_data['current_phase'] = history.current_phase
                session_data['user_decision'] = history.user_decision
                session_data['status'] = history.status
                session_data['session_id'] = history.session_id
                history.session_state = session_data

                logger.info(f"[会话管理] 会话已更新: {session_id} (phase={history.current_phase}, decision={history.user_decision}, status={history.status})")
            else:
                # 创建新记录
                logger.warning(f"[会话管理] 会话记录不存在，正在创建新记录: {session_id}")
                
                # 【增强修复】在创建新记录时确保关键字段存在于session_state中
                session_data['current_phase'] = current_phase or 'initial'
                session_data['user_decision'] = user_decision or 'pending'
                session_data['status'] = 'active'
                session_data['session_id'] = session_id
                
                history = ConsultationHistory(
                    session_id=session_id,
                    user_id=user_id,
                    title=question[:50] if question else "新咨询",
                    messages=new_messages,
                    message_count=len(new_messages),
                    session_state=session_data,
                    classification=classification,
                    # 【新增】设置新字段
                    current_phase=current_phase or 'initial',
                    user_decision=user_decision or 'pending',
                    current_task_id=current_task_id,
                    status='active'  # 确保新记录有正确的状态
                )
                self.db.add(history)
                logger.info(f"[会话管理] 会话已创建: {session_id} (phase={history.current_phase}, decision={history.user_decision}, status={history.status})")

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"[会话管理] 保存会话失败: {e}")
            self.db.rollback()
            return False

    async def update_session(self, session_id: str, **kwargs) -> bool:
        """
        更新会话状态中的特定字段

        Args:
            session_id: 会话ID
            **kwargs: 要更新的字段，支持：
                - is_in_specialist_mode: bool
                - specialist_output: dict
                - classification: dict
                - status: str
                - current_phase: str (assistant/waiting_confirmation/specialist/completed)
                - user_decision: str (confirmed/cancelled/pending)
                - current_task_id: str

        Returns:
            更新成功返回 True，否则返回 False
        """
        try:
            # 获取现有会话
            history = self.db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id
            ).first()

            if not history:
                logger.warning(f"[会话管理] 会话不存在，无法更新: {session_id}")
                return False

            # 获取当前会话状态，如果没有则初始化为空字典
            session_state = history.session_state.copy() if history.session_state else {}
            
            # 首先更新数据库字段（如果存在对应的数据库列）
            fields_to_update_db = {'current_phase', 'user_decision', 'status'}
            for key, value in kwargs.items():
                if hasattr(history, key) and key in fields_to_update_db:
                    setattr(history, key, value)
                    logger.info(f"[会话管理] 更新数据库字段: {key} = {value}")

            # 更新非数据库字段到session_state
            for key, value in kwargs.items():
                if not hasattr(history, key) or key not in fields_to_update_db:
                    session_state[key] = value
                    logger.info(f"[会话管理] 更新会话状态: {key} = {value}")

            # 【增强修复】强制将数据库列的当前值同步到session_state
            # 确保session_state中包含最新的数据库列值，解决数据一致性问题
            session_state['current_phase'] = history.current_phase
            session_state['user_decision'] = history.user_decision
            session_state['status'] = history.status
            session_state['session_id'] = history.session_id

            # 更新更新时间
            session_state["updated_at"] = datetime.now().isoformat()

            history.session_state = session_state
            history.updated_at = datetime.now()

            self.db.commit()
            logger.info(f"[会话管理] 会话状态已更新: {session_id} (phase={history.current_phase}, decision={history.user_decision}, status={history.status})")
            return True

        except Exception as e:
            logger.error(f"[会话管理] 更新会话失败: {e}")
            self.db.rollback()
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
        这里对应的是软删除或重置状态，或者物理删除记录。
        为了保留历史记录，建议只清空 session_state 或设置为 archived
        """
        if not session_id:
            return False

        try:
            # 查找并更新
            history = self.db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id
            ).first()

            if history:
                # 方式1：物理删除 (类似于 Redis delete)
                # self.db.delete(history)
                
                # 方式2：重置状态 (保留记录但清空会话上下文)
                history.session_state = None
                history.status = 'archived' # 标记为归档
                history.updated_at = datetime.now()
                self.db.commit()
                
                logger.info(f"[会话管理] 会话已归档/重置: {session_id}")
                return True
            else:
                logger.warning(f"[会话管理] 删除失败，会话不存在: {session_id}")
                return False

        except Exception as e:
            logger.error(f"[会话管理] 删除会话失败: {e}")
            self.db.rollback()
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
        reset_session: bool = False,
        user_id: int = 1
    ) -> tuple[str, bool, Optional[Dict[str, Any]]]:
        """
        获取或创建会话

        Args:
            session_id: 会话ID
            question: 用户问题
            reset_session: 是否重置
            user_id: 用户ID
        """
        # 如果请求重置会话，删除旧会话
        if reset_session and session_id:
            logger.info(f"[会话管理] 重置会话请求: {session_id}")
            await self.delete_session(session_id)
            return await self.get_or_create_session(None, question, False, user_id)

        # 如果没有 session_id，创建新会话
        if not session_id:
            import uuid
            new_session_id = f"session-{uuid.uuid4().hex[:16]}"
            logger.info(f"[会话管理] 创建新会话: {new_session_id}")
            return new_session_id, False, None

        # 【新增】验证会话是否仍然有效
        is_valid = await self.validate_session(session_id)
        if not is_valid:
            logger.info(f"[会话管理] 会话无效，作为新问题: {session_id}")
            return session_id, False, None

        # 会话有效，检查状态
        session = await self.get_session(session_id)
        is_in_specialist_mode = session.get("is_in_specialist_mode", False)
        current_phase = session.get("current_phase", "initial")
        status = session.get("status", "active")

        # 【重构】智能判断是否为后续问题
        # 条件1：检查是否为专家模式
        if not is_in_specialist_mode:
            logger.info(f"[会话管理] 新问题（未进入专家模式）: {session_id}")
            return session_id, False, None

        # 条件2：检查会话状态
        if status not in ["active", "running"]:
            logger.info(f"[会话管理] 新问题（会话非活跃）: {session_id}, status={status}")
            return session_id, False, None

        # 条件3：检查是否已完成（防止重启后误判）
        if current_phase == "completed":
            # 检查时间窗口
            updated_at = session.get("updated_at")
            if updated_at:
                from datetime import datetime, timedelta
                try:
                    updated_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    # 如果超过30分钟，视为新问题
                    if datetime.now() - updated_time > timedelta(minutes=30):
                        logger.info(f"[会话管理] 新问题（完成时间超过30分钟）: {session_id}")
                        return session_id, False, None
                except Exception as e:
                    logger.warning(f"[会话管理] 时间解析失败，视为新问题: {session_id}, error={e}")
                    return session_id, False, None

        # 所有条件满足，视为真正的追问
        previous_output = await self.get_specialist_output(session_id)
        logger.info(f"[会话管理] 追问模式: {session_id}, previous_output_exists={bool(previous_output)}")
        return session_id, True, previous_output

    async def initialize_session(
        self,
        session_id: str,
        question: str,
        user_id: int = 1
    ) -> bool:
        """
        立即初始化并保存新会话（不等待完整结果）

        用于任务启动时立即持久化用户输入
        """
        if not session_id or not question:
            return False

        try:
            existing = self.db.query(ConsultationHistory).filter(
                ConsultationHistory.session_id == session_id
            ).first()

            # 【修复】initialize_session 只用于新会话的初始化
            # 对于已存在的会话，不应该修改 current_phase
            # current_phase 的更新由 update_session 独立控制
            if existing:
                existing.updated_at = datetime.now()
                existing.status = 'active'

                # 仅更新时间，不修改 phase
                # current_phase 的正确值由后续的 update_session 调用控制

                self.db.commit()
                return True
            else:
                # 创建新会话记录
                history = ConsultationHistory(
                    session_id=session_id,
                    user_id=user_id,
                    title=question[:50] if question else "新咨询",
                    messages=[{
                        "role": "user",
                        "content": question,
                        "created_at": datetime.now().isoformat()
                    }],
                    message_count=1,
                    session_state={
                        "session_id": session_id,
                        "is_in_specialist_mode": False,
                        "specialist_output": None,
                        "classification": None,
                        "last_question": question,
                        "status": "running",
                        "created_at": datetime.now().isoformat()
                    },
                    status='active'
                )
                self.db.add(history)
                self.db.commit()
                logger.info(f"[会话管理] 新会话已初始化: {session_id}")
                return True
        except Exception as e:
            logger.error(f"[会话管理] 初始化会话失败: {e}")
            self.db.rollback()
            return False

    async def validate_session(self, session_id: str) -> bool:
        """
        验证会话是否仍然有效

        Args:
            session_id: 会话ID

        Returns:
            有效返回 True，否则返回 False
        """
        if not session_id:
            return False

        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            current_phase = session.get("current_phase", "initial")
            status = session.get("status", "active")

            # 如果会话已完成，检查时间窗口
            if current_phase == "completed":
                updated_at = session.get("updated_at")
                if updated_at:
                    from datetime import datetime, timedelta
                    try:
                        updated_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        # 超过30分钟，视为会话过期
                        if datetime.now() - updated_time > timedelta(minutes=30):
                            logger.info(f"[会话管理] 会话已超过30分钟，标记为无效: {session_id}")
                            return False
                    except Exception as e:
                        logger.warning(f"[会话管理] 时间解析失败，视为新问题: {session_id}, error={e}")
                        return False

            return True
        except Exception as e:
            logger.error(f"[会话管理] 验证会话失败: {e}")
            return False


# 创建全局实例
consultation_session_service = ConsultationSessionService()