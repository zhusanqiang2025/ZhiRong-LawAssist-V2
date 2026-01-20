# backend/app/tasks/celery_app.py
"""
Celery 应用配置

配置Celery任务队列系统，包括Broker、Result Backend、任务路由等
"""

from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Redis配置
REDIS_URL = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("REDIS_URL", "redis://localhost:6379/0")
)

# 创建Celery应用
celery_app = Celery(
    "legal_assistant",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.litigation_analysis_tasks",
        "app.tasks.contract_generation_tasks", # ✨ 新增：合同生成任务模块
        "app.tasks.contract_review_tasks", # ✨ 新增：合同审查任务模块
        # 后续添加其他任务模块
        # "app.tasks.risk_analysis_tasks",
        # "app.tasks.document_drafting_tasks",
    ]
)

# 配置选项
celery_app.conf.update(
    # ==================== 任务路由 ====================
    task_routes={
        # 高优先级队列：合同生成、文书起草
        "tasks.generate": {"queue": "high_priority"},  # 合同生成任务

        # 高优先级队列：文书起草
        "app.tasks.document_drafting_tasks.*": {"queue": "high_priority"},

        # 中优先级队列：案件分析、风险评估
        "tasks.litigation_analysis": {"queue": "medium_priority"},  # 案件分析任务
        "app.tasks.risk_analysis_tasks.*": {"queue": "medium_priority"},

        # 低优先级队列：合同审查、批量处理
        "tasks.perform_contract_review": {"queue": "low_priority"},  # 合同审查任务
        "tasks.resume_contract_review": {"queue": "low_priority"},  # 恢复审查任务
        "tasks.cleanup_old_tasks": {"queue": "low_priority"},  # 清理旧任务
    },

    # ==================== 任务超时配置 ====================
    task_time_limit=3600,  # 硬超时（1小时）
    task_soft_time_limit=3300,  # 软超时（55分钟）

    # ==================== 重试配置 ====================
    task_acks_late=True,  # 任务执行后确认（防止任务丢失）
    task_reject_on_worker_lost=True,  # Worker丢失时拒绝任务
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # ==================== 结果配置 ====================
    result_expires=86400,  # 结果保留24小时
    result_extended=True,  # 扩展结果信息（包含进度等）

    # ==================== Worker配置 ====================
    worker_prefetch_multiplier=1,  # 预取倍数（1=不预取，按需获取）
    worker_max_tasks_per_child=100,  # 每个Worker处理100个任务后重启（防止内存泄漏）
    worker_concurrency=2,  # 默认并发数

    # ==================== 任务配置 ====================
    task_track_started=True,  # 追踪任务开始时间
    task_send_sent_event=True,  # 发送任务发送事件

    # ==================== 时区配置 ====================
    timezone="Asia/Shanghai",
    enable_utc=True,

    # ==================== 进度配置 ====================
    task_progress=True,  # 启用进度追踪

    # ==================== 安全配置 ====================
    worker_hijack_root_logger=False,  # 不劫持根日志记录器
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',

    # ==================== 性能优化 ====================
    broker_connection_retry_on_startup=True,  # 启动时重试Broker连接
    broker_connection_max_retries=10,  # Broker连接最大重试次数
    broker_connection_retry=True,  # 启用Broker连接重试
)

# 定时任务配置（可选）
celery_app.conf.beat_schedule = {
    # 示例：每天凌晨清理过期任务结果
    'cleanup-expired-results': {
        'task': 'app.tasks.cleanup_tasks',
        'schedule': crontab(hour=2, minute=0),
    },
}


# 健康检查任务
@celery_app.task(bind=True, name='tasks.health_check')
def health_check(self):
    """健康检查任务"""
    return {"status": "healthy", "worker": self.request.hostname}


if __name__ == '__main__':
    celery_app.start()