# backend/app/crud/task.py (最终决定版)
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
# <<< 核心修正点: 直接、精确地导入所需的模型和Schema >>>
from app.models.task import Task
from app.schemas import TaskCreate, TaskUpdate
from app.crud.base import CRUDBase

class CRUDTask(CRUDBase[Task, TaskCreate, TaskUpdate]):
    def get_tasks_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Task]:
        return (
            db.query(self.model)
            .filter(Task.owner_id == owner_id)
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ==================== 合同生成专用方法 ====================

    def create_contract_generation_task(
        self,
        db: Session,
        owner_id: int,
        user_input: str,
        planning_mode: str = "single_model",
        uploaded_files: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> Task:
        """
        创建合同生成任务

        Args:
            db: 数据库会话
            owner_id: 用户ID
            user_input: 用户需求
            planning_mode: 规划模式
            uploaded_files: 上传文件列表
            session_id: 会话ID
            **kwargs: 其他参数

        Returns:
            Task: 创建的任务对象
        """
        db_obj = Task(
            owner_id=owner_id,
            task_type="contract_generation",
            status="pending",
            task_params={
                "user_input": user_input,
                "uploaded_files": uploaded_files or [],
                "planning_mode": planning_mode,
                "session_id": session_id,
            },
            **kwargs
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_contract_generation_tasks(
        self,
        db: Session,
        owner_id: int,
        planning_mode: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Task]:
        """
        获取用户的合同生成任务列表

        Args:
            db: 数据库会话
            owner_id: 用户ID
            planning_mode: 筛选规划模式
            status: 筛选状态
            skip: 跳过数量
            limit: 限制数量

        Returns:
            List[Task]: 任务列表
        """
        query = db.query(Task).filter(
            Task.owner_id == owner_id,
            Task.task_type == "contract_generation"
        )

        # 可选筛选
        if planning_mode:
            query = query.filter(
                Task.task_params["planning_mode"].astext == planning_mode
            )
        if status:
            query = query.filter(Task.status == status)

        return query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

    def update_contract_generation_progress(
        self,
        db: Session,
        task_id: str,
        progress: float,
        status: Optional[str] = None,
        result_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Task]:
        """
        更新合同生成任务进度

        Args:
            db: 数据库会话
            task_id: 任务ID
            progress: 进度（0-100）
            status: 新状态
            result_data: 结果数据

        Returns:
            Optional[Task]: 更新后的任务对象
        """
        task = self.get(db, task_id)
        if not task or task.task_type != "contract_generation":
            return None

        task.progress = progress
        if status:
            task.status = status
        if result_data:
            # 合并现有结果数据
            existing_data = task.result_data or {}
            existing_data.update(result_data)
            task.result_data = existing_data

        db.commit()
        db.refresh(task)
        return task

    def save_synthesis_report(
        self,
        db: Session,
        task_id: str,
        synthesis_report: Dict[str, Any]
    ) -> Optional[Task]:
        """
        保存多模型融合报告

        Args:
            db: 数据库会话
            task_id: 任务ID
            synthesis_report: 融合报告

        Returns:
            Optional[Task]: 更新后的任务对象
        """
        task = self.get(db, task_id)
        if not task or task.task_type != "contract_generation":
            return None

        # 获取或初始化 result_data
        result_data = task.result_data or {}
        result_data["multi_model_synthesis_report"] = synthesis_report

        task.result_data = result_data
        db.commit()
        db.refresh(task)
        return task


task = CRUDTask(Task)