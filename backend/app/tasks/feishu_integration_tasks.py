# -*- coding: utf-8 -*-
"""
backend/app/tasks/feishu_integration_tasks.py - 飞书集成本地开发
飞书集成专用的 Celery 定时任务模块

主要功能：
1. Token 定时刷新任务：自动刷新系统服务账号的 JWT Token
2. 支持通过环境变量配置刷新间隔

使用方式：
    # 通过 Celery Beat 定时执行
    # 或手动调用：
    from app.tasks.feishu_integration_tasks import refresh_feishu_integration_token

    task = refresh_feishu_integration_token.delay()
"""

import os
import logging
from datetime import timedelta
from celery.schedules import crontab
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入 Celery 应用
from app.tasks.celery_app import celery_app

# 导入 Token 管理工具
from app.utils.token_manager import (
    refresh_access_token,
    TokenRefreshError,
    REDIS_TOKEN_KEY,
    JWT_TOKEN_REFRESH_INTERVAL_HOURS,
)

# ==================== 日志配置 ====================
logger = logging.getLogger("feishu_integration.tasks")
logger.setLevel(os.getenv("FEISHU_LOG_LEVEL", "INFO"))

# 控制台处理器
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(os.getenv("FEISHU_LOG_LEVEL", "INFO"))
    console_formatter = logging.Formatter(
        '[%(asctime)s: %(levelname)s][%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

# ==================== 定时任务定义 ====================
@celery_app.task(
    bind=True,
    name='app.tasks.feishu_integration_tasks.refresh_feishu_integration_token',
    max_retries=3,
    default_retry_delay=60,  # 重试延迟 60 秒
)
def refresh_feishu_integration_token(self):
    """
    飞书集成 Token 定时刷新任务

    该任务会调用 token_manager 的 refresh_access_token() 方法，
    自动刷新系统服务账号的 JWT Token，确保 Token 始终有效。

    执行间隔：由环境变量 JWT_TOKEN_REFRESH_INTERVAL_HOURS 控制（默认 1.5 小时）

    Returns:
        dict: 任务执行结果

    Raises:
        TokenRefreshError: Token 刷新失败（已包含重试逻辑）

    使用示例：
        >>> from app.tasks.feishu_integration_tasks import refresh_feishu_integration_token
        >>> # 手动触发任务
        >>> task = refresh_feishu_integration_token.delay()
        >>> task_id = task.id
    """
    logger.info("=" * 60)
    logger.info("开始执行飞书集成 Token 刷新任务")
    logger.info("=" * 60)

    try:
        # 调用 Token 刷新方法
        token = refresh_access_token()

        logger.info(f"Token 刷新成功，Token 长度: {len(token)} 字符")
        logger.info(f"Token 前 50 字符: {token[:50]}...")
        logger.info("=" * 60)
        logger.info("飞书集成 Token 刷新任务执行成功")
        logger.info("=" * 60)

        return {
            "status": "success",
            "token_length": len(token),
            "message": "飞书集成 Token 刷新成功"
        }

    except TokenRefreshError as e:
        logger.error(f"Token 刷新失败: {e}")
        logger.error("=" * 60)
        logger.error("飞书集成 Token 刷新任务执行失败")

        # 检查是否需要重试
        if self.request.retries < self.max_retries:
            logger.info(f"将在 60 秒后重试（第 {self.request.retries + 1}/{self.max_retries} 次）")
            raise self.retry(exc=e)

        # 重试次数用尽，返回失败结果
        return {
            "status": "failed",
            "error": str(e),
            "message": "飞书集成 Token 刷新失败（已重试 3 次）"
        }

    except Exception as e:
        logger.error(f"任务执行过程中发生未知错误: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "message": "飞书集成 Token 刷新任务执行异常"
        }


# ==================== 任务注册到 Celery Beat ====================
# 获取刷新间隔（小时）
refresh_interval_hours = float(JWT_TOKEN_REFRESH_INTERVAL_HOURS)

# 将小时转换为分钟
refresh_interval_minutes = int(refresh_interval_hours * 60)

# 更新 Celery Beat 配置
# 注意：这里需要在 celery_app.py 中导入本模块才能生效
# 或者直接在 celery_app.py 的 beat_schedule 中添加本任务
celery_app.conf.beat_schedule.update({
    'feishu-integration-token-refresh': {
        'task': 'app.tasks.feishu_integration_tasks.refresh_feishu_integration_token',
        'schedule': crontab(minute=f'*/{refresh_interval_minutes}'),  # 每 N 分钟执行一次
        'options': {
            'expires': 300,  # 任务过期时间 5 分钟
        }
    },
})

logger.info(f"飞书集成 Token 刷新任务已注册到 Celery Beat，执行间隔: {refresh_interval_minutes} 分钟")


# ==================== 模块测试 ====================
if __name__ == "__main__":
    # 测试定时任务
    print("=" * 60)
    print("飞书集成定时任务测试")
    print("=" * 60)

    # 同步执行测试
    print("\n[测试] 同步执行 Token 刷新任务...")
    result = refresh_feishu_integration_token()
    print(f"✓ 任务执行结果: {result}")

    # 异步执行测试（需要 Celery Worker 运行）
    print("\n[测试] 异步执行 Token 刷新任务...")
    print("提示：请确保 Celery Worker 正在运行（docker-compose logs -f celery）")
    async_result = refresh_feishu_integration_token.delay()
    print(f"✓ 任务已提交，Task ID: {async_result.id}")
    print(f"  可通过以下命令查看任务状态:")
    print(f"  docker-compose exec backend python -c \"from app.tasks.feishu_integration_tasks import refresh_feishu_integration_token; result = refresh_feishu_integration_task.AsyncResult('{async_result.id}'); print(result.state, result.result)\"")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
