# backend/app/services/cache_service.py
"""
Redis 缓存服务
"""
import json
import pickle
from typing import Any, Optional, Union, List, Dict
from datetime import timedelta
import redis
from redis.connection import ConnectionPool
import logging
from functools import wraps
import os

from ..core.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis 缓存服务类"""

    def __init__(self):
        """初始化 Redis 连接池"""
        self._redis_client = None
        self._connection_pool = None
        self._connect()

    def _connect(self):
        """使用连接池连接到 Redis"""
        try:
            # 从环境变量读取连接池配置
            redis_max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
            redis_socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
            redis_socket_connect_timeout = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))

            # 创建连接池
            self._connection_pool = ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                max_connections=redis_max_connections,  # 最大连接数
                decode_responses=False,  # 使用 bytes 以支持 pickle
                socket_connect_timeout=redis_socket_connect_timeout,
                socket_timeout=redis_socket_timeout,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # 使用连接池创建 Redis 客户端
            self._redis_client = redis.Redis(
                connection_pool=self._connection_pool
            )

            # 测试连接
            self._redis_client.ping()
            logger.info(f"Redis connection pool established successfully (max_connections={redis_max_connections})")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._redis_client = None
            self._connection_pool = None

    def _serialize_value(self, value: Any) -> bytes:
        """序列化值"""
        try:
            return pickle.dumps(value)
        except Exception as e:
            logger.error(f"Failed to serialize value: {e}")
            # 如果序列化失败，尝试转为字符串
            return str(value).encode('utf-8')

    def _deserialize_value(self, value: bytes) -> Any:
        """反序列化值"""
        try:
            return pickle.loads(value)
        except Exception as e:
            logger.error(f"Failed to deserialize value: {e}")
            # 如果反序列化失败，尝试解码为字符串
            return value.decode('utf-8')

    def is_available(self) -> bool:
        """检查 Redis 是否可用"""
        if not self._redis_client:
            return False

        try:
            self._redis_client.ping()
            return True
        except Exception:
            return False

    def set(self, key: str, value: Any, expire: Optional[Union[int, timedelta]] = None) -> bool:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间（秒或 timedelta）

        Returns:
            是否设置成功
        """
        if not self.is_available():
            return False

        try:
            serialized_value = self._serialize_value(value)

            if isinstance(expire, timedelta):
                expire = int(expire.total_seconds())

            if expire:
                return self._redis_client.setex(key, expire, serialized_value)
            else:
                return self._redis_client.set(key, serialized_value)

        except Exception as e:
            logger.error(f"Failed to set cache key '{key}': {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存值或默认值
        """
        if not self.is_available():
            return default

        try:
            value = self._redis_client.get(key)
            if value is None:
                return default

            return self._deserialize_value(value)

        except Exception as e:
            logger.error(f"Failed to get cache key '{key}': {e}")
            return default

    def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        if not self.is_available():
            return False

        try:
            return bool(self._redis_client.delete(key))
        except Exception as e:
            logger.error(f"Failed to delete cache key '{key}': {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        批量删除缓存

        Args:
            pattern: 匹配模式（支持通配符 *）

        Returns:
            删除的键数量
        """
        if not self.is_available():
            return 0

        try:
            keys = self._redis_client.keys(pattern)
            if keys:
                return self._redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Failed to delete cache pattern '{pattern}': {e}")
            return 0

    def exists(self, key: str) -> bool:
        """
        检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        if not self.is_available():
            return False

        try:
            return bool(self._redis_client.exists(key))
        except Exception as e:
            logger.error(f"Failed to check cache key '{key}': {e}")
            return False

    def expire(self, key: str, seconds: int) -> bool:
        """
        设置缓存过期时间

        Args:
            key: 缓存键
            seconds: 过期时间（秒）

        Returns:
            是否设置成功
        """
        if not self.is_available():
            return False

        try:
            return bool(self._redis_client.expire(key, seconds))
        except Exception as e:
            logger.error(f"Failed to set expire for cache key '{key}': {e}")
            return False

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        递增缓存值

        Args:
            key: 缓存键
            amount: 递增量

        Returns:
            递增后的值
        """
        if not self.is_available():
            return None

        try:
            return self._redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Failed to increment cache key '{key}': {e}")
            return None

    def get_all_keys(self, pattern: str = "*") -> List[str]:
        """
        获取所有匹配的键

        Args:
            pattern: 匹配模式

        Returns:
            键列表
        """
        if not self.is_available():
            return []

        try:
            keys = self._redis_client.keys(pattern)
            return [key.decode('utf-8') if isinstance(key, bytes) else key for key in keys]
        except Exception as e:
            logger.error(f"Failed to get cache keys with pattern '{pattern}': {e}")
            return []

    def clear_all(self) -> bool:
        """
        清空所有缓存（谨慎使用）

        Returns:
            是否清空成功
        """
        if not self.is_available():
            return False

        try:
            return self._redis_client.flushdb()
        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return False


# 全局缓存服务实例
cache_service = CacheService()

def cache(expire: Union[int, timedelta] = 3600, key_prefix: str = ""):
    """
    缓存装饰器

    Args:
        expire: 过期时间（秒）
        key_prefix: 键前缀
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"

            # 尝试从缓存获取
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            cache_service.set(cache_key, result, expire)
            logger.debug(f"Cache set for key: {cache_key}")

            return result

        return wrapper
    return decorator

def clear_cache_pattern(pattern: str):
    """
    清除匹配模式的缓存

    Args:
        pattern: 匹配模式
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 执行函数
            result = await func(*args, **kwargs)

            # 清除匹配的缓存
            deleted_count = cache_service.delete_pattern(pattern)
            logger.info(f"Cleared {deleted_count} cache entries with pattern: {pattern}")

            return result

        return wrapper
    return decorator