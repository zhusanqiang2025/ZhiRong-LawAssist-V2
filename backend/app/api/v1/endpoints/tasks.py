# backend/app/api/v1/endpoints/tasks.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.api.deps import get_current_user, get_db
from app.crud import task as crud_task
from app.models.user import User
from app.models.task import Task
from app.models.task_view import TaskViewRecord

# 尝试导入 celery_app,如果模块不存在则设为 None
try:
    from app.tasks.celery_app import celery_app
except ImportError:
    celery_app = None

router = APIRouter()


@router.post("/create")
async def create_task(
    task_type: str,
    params: Dict[str, Any],
    priority: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    创建Celery任务

    Args:
        task_type: 任务类型（litigation_analysis, risk_analysis等）
        params: 任务参数
        priority: 优先级（1-10，数字越小优先级越高）
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        任务信息（task_id, celery_task_id, status）
    """
    # 任务注册表
    task_registry = {
        "litigation_analysis": "app.tasks.litigation_analysis_tasks:litigation_analysis_task",
        # 后续添加其他任务类型
        # "risk_analysis": "app.tasks.risk_analysis_tasks:risk_analysis_task",
        # "contract_review": "app.tasks.contract_review_tasks:contract_review_task",
    }

    # 验证任务类型
    if task_type not in task_registry:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task type: {task_type}. Available types: {list(task_registry.keys())}"
        )

    # 创建任务记录
    task = Task(
        task_type=task_type,
        status="pending",
        priority=priority,
        owner_id=current_user.id,
        created_at=datetime.utcnow(),
        task_params=params
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 提交Celery任务
    try:
        # 根据任务类型获取任务函数
        if task_type == "litigation_analysis":
            from app.tasks.litigation_analysis_tasks import litigation_analysis_task

            celery_task = litigation_analysis_task.apply_async(
                args=[
                    params.get("session_id"),
                    params.get("user_input", ""),
                    params.get("document_paths", []),
                    params.get("case_package_id"),
                    params.get("case_type"),
                    params.get("case_position")
                ],
                priority=priority,
                queue="medium_priority"
            )
        # else if task_type == "risk_analysis":
        #     from app.tasks.risk_analysis_tasks import risk_analysis_task
        #     celery_task = risk_analysis_task.apply_async(...)
        else:
            raise HTTPException(status_code=400, detail=f"Task type {task_type} not implemented")

        # 更新Celery任务ID
        task.celery_task_id = celery_task.id
        task.queue_name = celery_task.queue  # type: ignore
        db.commit()

        return {
            "task_id": task.id,
            "celery_task_id": celery_task.id,
            "status": "pending",
            "message": "任务已创建"
        }

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get("/{task_id}/status")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取任务状态

    Args:
        task_id: 任务ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        任务状态信息
    """
    # 验证任务存在且属于当前用户
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 从Celery获取最新状态
    celery_status = None
    if task.celery_task_id:
        try:
            result = celery_app.AsyncResult(task.celery_task_id)
            celery_status = result.state

            # 更新状态（如果Celery状态更新）
            if result.successful():
                task.status = "completed"
                task.progress = 100.0
            elif result.failed():
                task.status = "failed"
                task.error_message = str(result.info)
            elif result.state == "PENDING":
                if task.status != "pending":
                    task.status = "pending"
            elif result.state == "STARTED":
                if task.status != "processing":
                    task.status = "processing"

            db.commit()
        except Exception as e:
            # Celery连接失败，使用数据库中的状态
            pass

    return {
        "task_id": task.id,
        "celery_task_id": task.celery_task_id,
        "status": task.status,
        "celery_status": celery_status,
        "progress": task.progress or 0,
        "current_node": task.current_node,
        "node_progress": task.node_progress,
        "estimated_time_remaining": task.estimated_time_remaining,
        "error_message": task.error_message,
        "retry_count": task.retry_count,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    取消任务

    Args:
        task_id: 任务ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        操作结果
    """
    # 验证任务存在且属于当前用户
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 检查任务状态
    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task with status: {task.status}"
        )

    # 撤销Celery任务
    if task.celery_task_id:
        try:
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        except Exception as e:
            # 即使撤销失败也继续更新状态
            pass

    # 更新状态
    task.status = "cancelled"
    task.completed_at = datetime.utcnow()
    db.commit()

    return {
        "task_id": task_id,
        "status": "cancelled",
        "message": "任务已取消"
    }


@router.get("/{task_id}/result")
async def get_task_result(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取任务结果

    Args:
        task_id: 任务ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        任务结果
    """
    # 验证任务存在且属于当前用户
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 检查任务状态
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task.status}"
        )

    # 获取Celery结果
    celery_result = None
    if task.celery_task_id:
        try:
            result = celery_app.AsyncResult(task.celery_task_id)
            if result.successful():
                celery_result = result.result
        except Exception as e:
            pass

    return {
        "task_id": task.id,
        "status": task.status,
        "result": task.result_data or celery_result,
        "analysis_report": task.analysis_report,
        "final_document": task.final_document
    }


@router.get("/")
def get_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: Optional[str] = Query(None, description="过滤状态：pending, processing, completed, failed"),
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0)
) -> List[Dict[str, Any]]:
    """
    获取当前用户的任务列表（统一视图）

    聚合所有模块的任务数据：
    - tasks 表（新任务系统）
    - litigation_analysis_sessions（案件分析）
    - risk_analysis_sessions（风险评估）

    Args:
        db: 数据库会话
        current_user: 当前登录用户
        status: 可选的状态过滤（pending,processing 或 completed）
        limit: 返回数量限制
        skip: 跳过数量（分页）

    Returns:
        任务列表，每个任务包含 id, title, status, progress, time, created_at
    """
    all_tasks = []

    # 1. 获取新任务系统中的任务
    tasks_from_db = crud_task.task.get_tasks_by_owner(
        db,
        owner_id=current_user.id,
        skip=0,
        limit=1000
    )

    # 状态过滤（支持逗号分隔的多状态）
    if status:
        status_list = [s.strip() for s in status.split(',')]
        tasks_from_db = [t for t in tasks_from_db if t.status in status_list]

    # 转换新系统任务
    for task in tasks_from_db:
        all_tasks.append({
            **_task_to_response(task),
            'source': 'celery'
        })

    # 2. 获取案件分析任务
    from app.models.litigation_analysis import LitigationAnalysisSession
    litigation_sessions = db.query(LitigationAnalysisSession).filter(
        LitigationAnalysisSession.user_id == current_user.id
    ).order_by(LitigationAnalysisSession.created_at.desc()).limit(20).all()

    for session in litigation_sessions:
        # 映射状态
        session_status = _map_session_status(session.status)
        # 根据过滤条件决定是否添加
        if status:
            status_list = [s.strip() for s in status.split(',')]
            # 映射前端状态到后端状态
            if 'pending' in status_list or 'processing' in status_list:
                if session.status not in ['pending', 'processing', 'started']:
                    continue
            elif 'completed' in status_list:
                if session.status != 'completed':
                    continue

        all_tasks.append({
            'id': session.session_id,
            'title': f"{_get_case_type_name(session.case_type)} - {session.user_input[:20]}..." if session.user_input else f"{_get_case_type_name(session.case_type)}",
            'status': session_status,
            'progress': _extract_session_progress(session),
            'time': _format_relative_time(session.created_at.isoformat() if session.created_at else None),
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'source': 'litigation_analysis'
        })

    # 3. 获取风险评估任务
    from app.models.risk_analysis import RiskAnalysisSession
    risk_sessions = db.query(RiskAnalysisSession).filter(
        RiskAnalysisSession.user_id == current_user.id
    ).order_by(RiskAnalysisSession.created_at.desc()).limit(20).all()

    for session in risk_sessions:
        # 映射状态
        session_status = _map_session_status(session.status)
        # 根据过滤条件决定是否添加
        if status:
            status_list = [s.strip() for s in status.split(',')]
            if 'pending' in status_list or 'processing' in status_list:
                if session.status not in ['pending', 'processing', 'started']:
                    continue
            elif 'completed' in status_list:
                if session.status != 'completed':
                    continue

        all_tasks.append({
            'id': session.session_id,
            'title': f"风险评估 - {session.user_description[:20]}..." if session.user_description else "风险评估",
            'status': session_status,
            'progress': _extract_session_progress(session),
            'time': _format_relative_time(session.created_at.isoformat() if session.created_at else None),
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'source': 'risk_analysis'
        })

    # 按创建时间排序
    all_tasks.sort(key=lambda x: x['created_at'] or '', reverse=True)

    # 分页
    return all_tasks[skip:skip + limit]


@router.get("/stats")
def get_task_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, int]:
    """
    获取任务统计信息

    Args:
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        包含 in_progress, completed, total 的统计字典
    """
    tasks = crud_task.task.get_tasks_by_owner(
        db,
        owner_id=current_user.id,
        skip=0,
        limit=1000  # 统计时获取更多数据
    )

    in_progress = len([t for t in tasks if t.status in ['pending', 'processing']])
    completed = len([t for t in tasks if t.status == 'completed'])

    return {
        "in_progress": in_progress,
        "completed": completed,
        "total": len(tasks)
    }


def _task_to_response(task: Task) -> Dict[str, Any]:
    """
    将Task模型转换为前端响应格式

    Args:
        task: 数据库Task模型实例

    Returns:
        前端可用的任务字典
    """
    # 生成标题：优先使用 doc_type，其次 user_demand，最后默认值
    title = task.doc_type or task.user_demand or "未命名任务"

    # 如果标题过长，截断
    if len(title) > 30:
        title = title[:27] + "..."

    # 格式化时间
    time_str = _format_relative_time(task.created_at) if task.created_at else ""

    return {
        "id": str(task.id),
        "title": title,
        "status": _map_status(task.status),
        "progress": task.progress or 0,
        "time": time_str,
        "created_at": task.created_at.isoformat() if task.created_at else None
    }


def _map_status(status: str) -> str:
    """
    映射后端状态到前端显示状态

    Args:
        status: 后端状态值

    Returns:
        前端显示的中文状态
    """
    status_map = {
        'pending': '进行中',
        'processing': '进行中',
        'completed': '已完成',
        'failed': '失败',
        'cancelled': '已取消'
    }
    return status_map.get(status, '未知')


def _format_relative_time(date_str: Optional[str]) -> str:
    """
    格式化相对时间（如：10分钟前）

    Args:
        date_str: ISO格式日期字符串

    Returns:
        相对时间字符串
    """
    if not date_str:
        return ""

    try:
        # 处理带时区的日期字符串
        if date_str.endswith('Z'):
            date_str = date_str.replace('Z', '+00:00')

        date = datetime.fromisoformat(date_str)
        # 使用UTC时间进行比较
        now = datetime.utcnow()

        # 如果date是带时区的naive datetime，先转换为UTC
        if date.tzinfo is not None:
            date = date.astimezone(None).replace(tzinfo=None)

        diff = int((now - date).total_seconds() / 60)  # 分钟

        if diff < 1:
            return "刚刚"
        elif diff < 60:
            return f"{diff}分钟前"
        elif diff < 1440:  # 24小时
            return f"{diff // 60}小时前"
        elif diff < 43200:  # 30天
            return f"{diff // 1440}天前"
        else:
            return date.strftime("%Y-%m-%d")
    except Exception as e:
        # 如果格式化失败，返回空字符串
        return ""


@router.get("/unviewed")
def get_unviewed_completed_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    获取已完成但未查看的任务

    返回用户已完成但尚未查看结果的任务列表，用于任务保持功能

    Args:
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        未查看的已完成任务列表
    """
    # 获取用户所有已完成的任务
    all_tasks = crud_task.task.get_tasks_by_owner(
        db,
        owner_id=current_user.id,
        skip=0,
        limit=1000
    )

    # 筛选已完成的任务
    completed_tasks = [t for t in all_tasks if t.status == 'completed']

    if not completed_tasks:
        return []

    # 获取该用户已查看的任务ID列表
    viewed_task_ids = db.query(TaskViewRecord.task_id).filter(
        TaskViewRecord.user_id == current_user.id,
        TaskViewRecord.has_viewed_result == True
    ).all()
    viewed_ids = {t[0] for t in viewed_task_ids}

    # 过滤出未查看的任务
    unviewed_tasks = [t for t in completed_tasks if str(t.id) not in viewed_ids]

    return [_task_to_response(t) for t in unviewed_tasks]


@router.post("/{task_id}/mark-viewed")
def mark_task_as_viewed(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    标记任务为已查看

    当用户点击查看任务结果时调用，记录查看时间和次数

    Args:
        task_id: 任务ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        操作结果
    """
    # 验证任务存在且属于当前用户
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 查找或创建查看记录
    record = db.query(TaskViewRecord).filter(
        TaskViewRecord.task_id == task_id,
        TaskViewRecord.user_id == current_user.id
    ).first()

    if not record:
        # 创建新记录
        record = TaskViewRecord(
            task_id=task_id,
            user_id=current_user.id,
            has_viewed_result=True,
            first_viewed_at=datetime.utcnow(),
            view_count=1
        )
        db.add(record)
    else:
        # 更新现有记录
        if not record.has_viewed_result:
            record.has_viewed_result = True
            record.first_viewed_at = datetime.utcnow()
        record.view_count += 1
        record.last_viewed_at = datetime.utcnow()

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"标记失败: {str(e)}")

    return {
        "success": True,
        "message": "任务已标记为已查看",
        "task_id": task_id,
        "view_count": record.view_count
    }


# ==================== 辅助函数 ====================

def _map_session_status(status: str) -> str:
    """
    映射会话状态到前端显示状态

    Args:
        status: 会话状态值

    Returns:
        前端显示的状态字符串
    """
    status_map = {
        'pending': '进行中',
        'processing': '进行中',
        'started': '进行中',
        'completed': '已完成',
        'failed': '失败',
        'cancelled': '已取消'
    }
    return status_map.get(status, '进行中')


def _get_case_type_name(case_type: str) -> str:
    """
    获取案件类型中文名称

    Args:
        case_type: 案件类型代码

    Returns:
        中文名称
    """
    case_type_map = {
        'civil': '民事诉讼',
        'criminal': '刑事诉讼',
        'administrative': '行政诉讼',
        'execution': '执行案件'
    }
    return case_type_map.get(case_type, '案件分析')


def _extract_session_progress(session) -> int:
    """
    从会话对象中提取进度

    Args:
        session: 会话对象（LitigationAnalysisSession 或 RiskAnalysisSession）

    Returns:
        进度值 0-100
    """
    # 尝试从不同来源获取进度
    if hasattr(session, 'progress') and session.progress:
        return session.progress

    # 根据状态推断进度
    status = session.status if hasattr(session, 'status') else ''
    if status == 'completed':
        return 100
    elif status in ['started', 'processing']:
        return 50
    elif status == 'pending':
        return 0
    else:
        return 0
