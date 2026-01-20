# backend/app/monitoring/metrics.py
"""
监控指标模块

使用 Prometheus 监控合同生成模块的关键指标。
"""

from prometheus_client import Counter, Histogram, Gauge, Info
import logging
from functools import wraps
from typing import Callable, Any
import time

logger = logging.getLogger(__name__)

# ==================== 合同生成指标 ====================

# 合同生成总数（按模式和状态分类）
contract_generation_total = Counter(
    "contract_generation_total",
    "合同生成请求总数",
    ["planning_mode", "status"]  # planning_mode: single_model/multi_model, status: success/failed
)

# 合同生成耗时（按模式分类）
contract_generation_duration = Histogram(
    "contract_generation_duration_seconds",
    "合同生成耗时（秒）",
    ["planning_mode"],
    buckets=[10, 30, 60, 120, 300, 600, 1800]  # 10秒到30分钟
)

# 合同规划耗时（单模型 vs 多模型）
contract_planning_duration = Histogram(
    "contract_planning_duration_seconds",
    "合同规划耗时（秒）",
    ["planning_mode"],
    buckets=[5, 10, 20, 30, 60, 120, 300]
)

# 当前正在处理的合同生成任务数
contract_generation_in_progress = Gauge(
    "contract_generation_in_progress",
    "当前正在处理的合同生成任务数",
    ["planning_mode"]
)

# ==================== 多模型规划专用指标 ====================

# 多模型规划调用次数
multi_model_planning_total = Counter(
    "multi_model_planning_total",
    "多模型规划调用总数",
    ["model", "status"]  # model: Qwen3/DeepSeek/GPT-OSS, status: success/failed
)

# 多模型方案评估得分
multi_model_solution_score = Histogram(
    "multi_model_solution_score",
    "多模型方案评估得分",
    ["model"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# 多模型融合报告生成次数
multi_model_synthesis_total = Counter(
    "multi_model_synthesis_total",
    "多模型融合报告生成次数",
    ["status"]  # status: success/failed
)

# ==================== 任务队列指标 ====================

# Celery 任务处理耗时
celery_task_duration = Histogram(
    "celery_task_duration_seconds",
    "Celery 任务处理耗时（秒）",
    ["task_type", "status"],  # task_type: contract_generation, status: success/failed
    buckets=[5, 10, 30, 60, 120, 300, 600, 1800]
)

# Celery 任务重试次数
celery_task_retries = Counter(
    "celery_task_retries_total",
    "Celery 任务重试次数",
    ["task_type"]
)

# ==================== 数据库操作指标 ====================

# 数据库查询耗时
db_query_duration = Histogram(
    "db_query_duration_seconds",
    "数据库查询耗时（秒）",
    ["operation"],  # operation: create_task/get_tasks/update_progress
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

# 数据库操作失败次数
db_operation_errors = Counter(
    "db_operation_errors_total",
    "数据库操作失败次数",
    ["operation", "error_type"]
)

# ==================== API 端点指标 ====================

# API 请求耗时
api_request_duration = Histogram(
    "api_request_duration_seconds",
    "API 请求耗时（秒）",
    ["endpoint", "method"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
)

# API 请求总数
api_request_total = Counter(
    "api_request_total",
    "API 请求总数",
    ["endpoint", "method", "status"]  # status: success/client_error/server_error
)

# ==================== 模块信息 ====================

# 合同生成模块信息
contract_generation_info = Info(
    "contract_generation_info",
    "合同生成模块信息"
)
# 设置静态信息
contract_generation_info.info({
    "version": "2.0",
    "features": "single_model,multi_model,async_tasks,task_history"
})


# ==================== 装饰器 ====================

def track_contract_generation(planning_mode: str = "single_model"):
    """
    跟踪合同生成的装饰器

    Args:
        planning_mode: 规划模式
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            status = "success"

            # 增加进行中的计数
            contract_generation_in_progress.labels(
                planning_mode=planning_mode
            ).inc()

            try:
                result = await func(*args, **kwargs)

                # 检查结果状态
                if not result.get("success") and result.get("error"):
                    status = "failed"

                return result

            except Exception as e:
                status = "failed"
                logger.error(f"[Metrics] 合同生成失败: {e}")
                raise

            finally:
                # 记录耗时
                duration = time.time() - start_time
                contract_generation_duration.labels(
                    planning_mode=planning_mode
                ).observe(duration)

                # 记录总数
                contract_generation_total.labels(
                    planning_mode=planning_mode,
                    status=status
                ).inc()

                # 减少进行中的计数
                contract_generation_in_progress.labels(
                    planning_mode=planning_mode
                ).dec()

        return wrapper
    return decorator


def track_api_request(endpoint: str, method: str = "POST"):
    """
    跟踪 API 请求的装饰器

    Args:
        endpoint: 端点名称
        method: HTTP 方法
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result

            except Exception as e:
                # 判断错误类型
                if hasattr(e, "status_code"):
                    if 400 <= e.status_code < 500:
                        status = "client_error"
                    else:
                        status = "server_error"
                else:
                    status = "server_error"

                raise

            finally:
                # 记录耗时
                duration = time.time() - start_time
                api_request_duration.labels(
                    endpoint=endpoint,
                    method=method
                ).observe(duration)

                # 记录总数
                api_request_total.labels(
                    endpoint=endpoint,
                    method=method,
                    status=status
                ).inc()

        return wrapper
    return decorator


def track_db_query(operation: str):
    """
    跟踪数据库查询的装饰器

    Args:
        operation: 操作名称
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            error_type = None

            try:
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                error_type = type(e).__name__
                db_operation_errors.labels(
                    operation=operation,
                    error_type=error_type
                ).inc()
                raise

            finally:
                # 记录耗时
                duration = time.time() - start_time
                db_query_duration.labels(
                    operation=operation
                ).observe(duration)

        return wrapper
    return decorator


# ==================== 指标导出 ====================

def get_metrics_summary() -> dict:
    """
    获取指标摘要（用于调试和展示）

    Returns:
        dict: 指标摘要
    """
    summary = {
        "contract_generation": {
            "total": str(contract_generation_total),
            "duration": str(contract_generation_duration),
            "in_progress": str(contract_generation_in_progress)
        },
        "contract_planning": {
            "duration": str(contract_planning_duration)
        },
        "multi_model_planning": {
            "total": str(multi_model_planning_total),
            "solution_score": str(multi_model_solution_score),
            "synthesis_total": str(multi_model_synthesis_total)
        },
        "celery_tasks": {
            "duration": str(celery_task_duration),
            "retries": str(celery_task_retries)
        },
        "db_operations": {
            "duration": str(db_query_duration),
            "errors": str(db_operation_errors)
        },
        "api_requests": {
            "total": str(api_request_total),
            "duration": str(api_request_duration)
        }
    }
    return summary


if __name__ == "__main__":
    # 测试代码
    print("监控指标模块已加载")
    print("可用的指标:")
    print("- contract_generation_total")
    print("- contract_generation_duration")
    print("- contract_planning_duration")
    print("- multi_model_planning_total")
    print("- multi_model_solution_score")
    print("- celery_task_duration")
    print("- api_request_total")
    print("- api_request_duration")
