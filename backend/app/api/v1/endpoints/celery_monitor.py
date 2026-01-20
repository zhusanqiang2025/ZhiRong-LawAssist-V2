"""
Celery 监控 API

提供 Celery 任务队列状态的 REST API 接口
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.tasks.celery_app import celery_app

router = APIRouter()


@router.get("/stats")
async def get_celery_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取 Celery 统计数据

    返回:
    - workers: Worker 列表及其状态
    - tasks: 最近的任务列表
    - stats: 总体统计信息
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        # 获取 Worker 统计
        inspect = celery_app.control.inspect()
        stats = inspect.stats()

        workers = []
        active_workers = 0
        total_tasks = 0
        succeeded_tasks = 0
        failed_tasks = 0
        pending_tasks = 0

        if stats:
            for worker_name, worker_stats in stats.items():
                active_workers += 1
                total = worker_stats.get('total', {})
                workers.append({
                    'name': worker_name,
                    'status': 'online',
                    'concurrency': worker_stats.get('pool', {}).get('max-concurrency', 0),
                    'active_tasks': len(worker_stats.get('pool', {}).get('processes', [])),
                    'tasks': {
                        'received': total.get('tasks.received', 0),
                        'started': total.get('tasks.started', 0),
                        'succeeded': total.get('tasks.succeeded', 0),
                        'failed': total.get('tasks.failed', 0),
                        'retry': total.get('tasks.retry', 0),
                    }
                })
                succeeded_tasks += total.get('tasks.succeeded', 0)
                failed_tasks += total.get('tasks.failed', 0)

        # 获取活跃任务
        active = inspect.active()
        recent_tasks = []

        if active:
            for worker_name, tasks in active.items():
                for task in tasks:
                    total_tasks += 1
                    if task.get('state') in ['PENDING', 'STARTED']:
                        pending_tasks += 1
                    recent_tasks.append({
                        'id': task.get('id'),
                        'name': task.get('name'),
                        'state': task.get('state'),
                        'worker': worker_name,
                        'args': task.get('args', []),
                        'kwargs': task.get('kwargs', {}),
                        'received': task.get('time_start'),
                        'started': task.get('time_start'),
                        'runtime': 0,
                        'retries': task.get('request', {}).get('retries', 0),
                    })

        # 获取预定任务
        scheduled = inspect.scheduled()
        if scheduled:
            for worker_name, tasks in scheduled.items():
                for task in tasks:
                    total_tasks += 1
                    pending_tasks += 1
                    recent_tasks.append({
                        'id': task.get('id'),
                        'name': task.get('name'),
                        'state': 'PENDING',
                        'worker': worker_name,
                        'args': task.get('args', []),
                        'kwargs': task.get('kwargs', {}),
                        'received': task.get('eta'),
                        'started': 0,
                        'runtime': 0,
                        'retries': 0,
                    })

        return {
            'workers': workers,
            'tasks': recent_tasks[:50],  # 只返回最近 50 个任务
            'stats': {
                'activeWorkers': active_workers,
                'totalTasks': total_tasks,
                'succeededTasks': succeeded_tasks,
                'failedTasks': failed_tasks,
                'pendingTasks': pending_tasks,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Celery 状态失败: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_task_detail(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取任务详细信息
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        result = celery_app.AsyncResult(task_id)

        return {
            'id': task_id,
            'state': result.state,
            'result': result.result if result.successful() else None,
            'error': str(result.info) if result.failed() else None,
            'traceback': result.traceback if result.failed() else None,
            'args': result.args if result.args else [],
            'kwargs': result.kwargs if result.kwargs else {},
            'worker': result.info.get('worker') if result.info else None,
            'received': result.info.get('received') if result.info else None,
            'started': result.info.get('started') if result.info else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务详情失败: {str(e)}")


@router.post("/tasks/{task_id}/revoke")
async def revoke_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    撤销任务
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        celery_app.control.revoke(task_id, terminate=True)
        return {
            'success': True,
            'message': f'任务 {task_id} 已撤销'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"撤销任务失败: {str(e)}")


@router.post("/workers/{worker_name}/shutdown")
async def shutdown_worker(
    worker_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    关闭 Worker
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        celery_app.control.shutdown(worker_name)
        return {
            'success': True,
            'message': f'Worker {worker_name} 已关闭'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关闭 Worker 失败: {str(e)}")


@router.post("/purge")
async def purge_queue(
    queue: str = "default",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    清空队列
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        celery_app.control.purge()
        return {
            'success': True,
            'message': f'队列 {queue} 已清空'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空队列失败: {str(e)}")


@router.get("/configuration")
async def get_celery_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取 Celery 配置信息
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        from app.core.config import settings

        return {
            'broker_url': settings.CELERY_BROKER_URL,
            'result_backend': settings.CELERY_RESULT_BACKEND,
            'enabled': settings.CELERY_ENABLED,
            'task_track_started': settings.CELERY_TASK_TRACK_STARTED,
            'task_time_limit': settings.CELERY_TASK_TIME_LIMIT,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")
