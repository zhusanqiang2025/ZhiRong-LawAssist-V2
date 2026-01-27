# -*- coding: utf-8 -*-
"""
backend/app/utils/token_manager.py - 飞书集成本地开发
飞书集成专用系统服务账号的 JWT Token 全自动化管理工具

主要功能：
1. 初始化获取 Token：调用登录接口获取系统服务账号的 access_token
2. Token 有效性校验：结合获取时间和有效期判断 Token 是否有效
3. 自动刷新 Token：Token 即将过期时自动刷新
4. 全局获取 Token：提供统一的 Token 获取接口
5. Token 存储：Redis 优先，内存兜底

使用方式：
    from app.utils.token_manager import get_valid_token

    # 获取有效的 JWT Token
    token = get_valid_token()
"""

import os
import time
import logging
from typing import Optional
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

# 加载环境变量（优先从 .env 读取）
load_dotenv()

# ==================== 配置读取 ====================
# 系统服务账号配置
SYSTEM_SERVICE_EMAIL = os.getenv("SYSTEM_SERVICE_EMAIL", "zhusanqiang@az028.cn")
SYSTEM_SERVICE_PASSWORD = os.getenv("SYSTEM_SERVICE_PASSWORD", "")

# Token 管理配置
JWT_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_TOKEN_EXPIRE_HOURS", "24"))
JWT_TOKEN_REFRESH_INTERVAL_HOURS = float(os.getenv("JWT_TOKEN_REFRESH_INTERVAL_HOURS", "1.5"))
REDIS_TOKEN_KEY = os.getenv("REDIS_TOKEN_KEY", "feishu_integration:access_token")

# Redis 配置
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "123myredissecret")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# 后端 API 配置
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

# 日志配置
LOG_LEVEL = os.getenv("FEISHU_LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("FEISHU_LOG_FILE", "logs/feishu_integration.log")

# ==================== 日志配置 ====================
logger = logging.getLogger("feishu_integration.token_manager")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
console_formatter = logging.Formatter(
    '[%(asctime)s: %(levelname)s][%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# 文件处理器（可选）
if LOG_FILE:
    try:
        import os
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        file_formatter = logging.Formatter(
            '[%(asctime)s: %(levelname)s][%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"无法创建日志文件处理器: {e}")

# ==================== 自定义异常 ====================
class TokenRetrieveError(Exception):
    """Token 获取失败异常"""
    pass


class TokenRefreshError(Exception):
    """Token 刷新失败异常"""
    pass


# ==================== 内存存储（兜底方案） ====================
_memory_token_store: Optional[dict] = None


# ==================== Redis 工具函数 ====================
def _get_redis_connection():
    """
    获取 Redis 连接

    Returns:
        redis.Redis: Redis 连接对象，失败时返回 None
    """
    try:
        import redis
        return redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
    except Exception as e:
        logger.warning(f"Redis 连接失败，将使用内存存储: {e}")
        return None


def _save_token_to_redis(token: str, timestamp: float) -> bool:
    """
    保存 Token 到 Redis

    Args:
        token: JWT Token
        timestamp: 获取时间戳

    Returns:
        bool: 是否保存成功
    """
    try:
        redis_client = _get_redis_connection()
        if redis_client is None:
            return False

        redis_client.hset(
            REDIS_TOKEN_KEY,
            mapping={
                "token": token,
                "timestamp": str(timestamp)
            }
        )
        # 设置过期时间（比 Token 有效期多 1 小时）
        redis_client.expire(REDIS_TOKEN_KEY, int(JWT_TOKEN_EXPIRE_HOURS * 3600) + 3600)
        logger.info(f"Token 已保存到 Redis，Key: {REDIS_TOKEN_KEY}")
        return True
    except Exception as e:
        logger.warning(f"保存 Token 到 Redis 失败: {e}")
        return False


def _load_token_from_redis() -> Optional[tuple[str, float]]:
    """
    从 Redis 加载 Token

    Returns:
        Optional[tuple[str, float]]: (token, timestamp) 元组，失败时返回 None
    """
    try:
        redis_client = _get_redis_connection()
        if redis_client is None:
            return None

        data = redis_client.hgetall(REDIS_TOKEN_KEY)
        if not data or "token" not in data or "timestamp" not in data:
            return None

        token = data["token"]
        timestamp = float(data["timestamp"])
        logger.info(f"从 Redis 加载 Token 成功，Key: {REDIS_TOKEN_KEY}")
        return (token, timestamp)
    except Exception as e:
        logger.warning(f"从 Redis 加载 Token 失败: {e}")
        return None


def _delete_token_from_redis() -> bool:
    """
    从 Redis 删除 Token

    Returns:
        bool: 是否删除成功
    """
    try:
        redis_client = _get_redis_connection()
        if redis_client is None:
            return False

        redis_client.delete(REDIS_TOKEN_KEY)
        logger.info(f"已从 Redis 删除 Token，Key: {REDIS_TOKEN_KEY}")
        return True
    except Exception as e:
        logger.warning(f"从 Redis 删除 Token 失败: {e}")
        return False


# ==================== Token 有效性校验 ====================
def _is_token_valid(token: str, timestamp: float) -> bool:
    """
    校验 Token 是否有效

    Args:
        token: JWT Token
        timestamp: Token 获取时间戳

    Returns:
        bool: Token 是否有效
    """
    if not token or not timestamp:
        return False

    # 计算 Token 的有效期（提前刷新间隔）
    current_time = time.time()
    token_age_hours = (current_time - timestamp) / 3600

    # 判断是否需要刷新（剩余有效期小于刷新间隔）
    if token_age_hours >= (JWT_TOKEN_EXPIRE_HOURS - JWT_TOKEN_REFRESH_INTERVAL_HOURS):
        logger.info(f"Token 即将过期（已使用 {token_age_hours:.2f} 小时），需要刷新")
        return False

    logger.debug(f"Token 有效（已使用 {token_age_hours:.2f} 小时）")
    return True


# ==================== Token 获取与刷新 ====================
def _fetch_access_token() -> str:
    """
    调用登录接口获取新的 access_token

    Returns:
        str: access_token

    Raises:
        TokenRetrieveError: 获取 Token 失败
    """
    if not SYSTEM_SERVICE_PASSWORD:
        raise TokenRetrieveError("系统服务账号密码未配置（SYSTEM_SERVICE_PASSWORD）")

    login_url = f"{BACKEND_API_URL}/api/v1/auth/login"
    payload = {
        "username": SYSTEM_SERVICE_EMAIL,
        "password": SYSTEM_SERVICE_PASSWORD
    }

    logger.info(f"正在调用登录接口获取 Token: {login_url}")

    try:
        response = requests.post(
            login_url,
            data=payload,  # x-www-form-urlencoded 格式
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                logger.info("成功获取 access_token")
                return token
            else:
                raise TokenRetrieveError(f"登录响应中无 access_token: {data}")
        else:
            raise TokenRetrieveError(
                f"登录接口返回错误状态码: {response.status_code}, "
                f"响应: {response.text}"
            )
    except requests.exceptions.RequestException as e:
        raise TokenRetrieveError(f"登录接口请求失败: {e}")


def refresh_access_token() -> str:
    """
    刷新 access_token（核心方法）

    该方法会调用登录接口获取新的 Token，并保存到 Redis 和内存中

    Returns:
        str: 新的 access_token

    Raises:
        TokenRefreshError: 刷新 Token 失败
    """
    global _memory_token_store

    max_retries = 2
    last_error = None

    for attempt in range(max_retries):
        try:
            logger.info(f"开始刷新 access_token（尝试 {attempt + 1}/{max_retries}）")

            # 获取新 Token
            token = _fetch_access_token()
            timestamp = time.time()

            # 保存到 Redis
            _save_token_to_redis(token, timestamp)

            # 保存到内存（兜底）
            _memory_token_store = {
                "token": token,
                "timestamp": timestamp
            }

            logger.info("access_token 刷新成功")
            return token

        except TokenRetrieveError as e:
            last_error = e
            logger.warning(f"刷新 Token 失败（尝试 {attempt + 1}/{max_retries}）: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 重试前等待 2 秒

    # 所有重试均失败
    error_msg = f"刷新 access_token 失败（已重试 {max_retries} 次）: {last_error}"
    logger.error(error_msg)
    raise TokenRefreshError(error_msg)


def get_valid_token() -> str:
    """
    获取有效的 access_token（对外统一接口）

    该方法会自动处理 Token 的有效性校验和刷新，调用方无需关心刷新逻辑

    Returns:
        str: 有效的 access_token

    Raises:
        TokenRetrieveError: 获取 Token 失败

    使用示例：
        >>> from app.utils.token_manager import get_valid_token
        >>> token = get_valid_token()
    """
    global _memory_token_store

    # 1. 尝试从 Redis 加载 Token
    token_data = _load_token_from_redis()

    # 2. Redis 无数据时，尝试从内存加载
    if token_data is None and _memory_token_store is not None:
        token_data = (_memory_token_store["token"], _memory_token_store["timestamp"])
        logger.info("从内存加载 Token")

    # 3. 校验 Token 是否有效
    if token_data is not None:
        token, timestamp = token_data
        if _is_token_valid(token, timestamp):
            logger.debug("使用现有有效 Token")
            return token
        else:
            # Token 即将过期，需要刷新
            logger.info("现有 Token 即将过期，开始刷新")

    # 4. 无有效 Token，需要重新获取
    logger.info("无有效 Token，开始获取新 Token")
    return refresh_access_token()


def clear_token_cache() -> bool:
    """
    清除 Token 缓存（Redis + 内存）

    主要用于测试或强制重新获取 Token

    Returns:
        bool: 是否清除成功
    """
    global _memory_token_store

    # 清除 Redis 缓存
    redis_success = _delete_token_from_redis()

    # 清除内存缓存
    _memory_token_store = None
    logger.info("已清除内存 Token 缓存")

    return redis_success


# ==================== 模块测试 ====================
if __name__ == "__main__":
    # 测试 Token 管理
    print("=" * 60)
    print("飞书集成 Token 管理工具测试")
    print("=" * 60)

    try:
        # 测试获取有效 Token
        print("\n[测试] 获取有效 Token...")
        token = get_valid_token()
        print(f"✓ 成功获取 Token（长度: {len(token)} 字符）")
        print(f"  Token 前 50 字符: {token[:50]}...")

        # 测试重复调用（应使用缓存）
        print("\n[测试] 重复获取 Token（应使用缓存）...")
        token2 = get_valid_token()
        if token == token2:
            print("✓ 复用缓存 Token")
        else:
            print("✗ 获取了新 Token（可能缓存已过期）")

        # 测试清除缓存
        print("\n[测试] 清除缓存...")
        clear_token_cache()
        print("✓ 缓存已清除")

        # 测试重新获取
        print("\n[测试] 重新获取 Token...")
        token3 = get_valid_token()
        print(f"✓ 成功重新获取 Token（长度: {len(token3)} 字符）")

        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
