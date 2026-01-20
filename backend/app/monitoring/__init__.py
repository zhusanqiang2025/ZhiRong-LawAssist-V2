# backend/app/monitoring/__init__.py
"""
监控模块

提供合同生成模块的监控和指标收集功能。
"""

from .metrics import (
    # 合同生成指标
    contract_generation_total,
    contract_generation_duration,
    contract_planning_duration,
    contract_generation_in_progress,

    # 多模型规划指标
    multi_model_planning_total,
    multi_model_solution_score,
    multi_model_synthesis_total,

    # Celery 任务指标
    celery_task_duration,
    celery_task_retries,

    # 数据库操作指标
    db_query_duration,
    db_operation_errors,

    # API 端点指标
    api_request_duration,
    api_request_total,

    # 装饰器
    track_contract_generation,
    track_api_request,
    track_db_query,

    # 工具函数
    get_metrics_summary
)

__all__ = [
    # 合同生成指标
    "contract_generation_total",
    "contract_generation_duration",
    "contract_planning_duration",
    "contract_generation_in_progress",

    # 多模型规划指标
    "multi_model_planning_total",
    "multi_model_solution_score",
    "multi_model_synthesis_total",

    # Celery 任务指标
    "celery_task_duration",
    "celery_task_retries",

    # 数据库操作指标
    "db_query_duration",
    "db_operation_errors",

    # API 端点指标
    "api_request_duration",
    "api_request_total",

    # 装饰器
    "track_contract_generation",
    "track_api_request",
    "track_db_query",

    # 工具函数
    "get_metrics_summary"
]
