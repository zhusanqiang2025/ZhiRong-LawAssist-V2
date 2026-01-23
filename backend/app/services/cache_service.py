# backend/app/services/cache_service.py
"""
内存缓存服务（替代 Redis）
"""
import json
import time
import threading
from typing import Any, Optional, Union, List, Dict
from datetime import timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class _CacheItem:
    """缓存项，存储值和过期时间"""
    def __init__(self, value: Any, expire_at: Optional[float] = None):
        self.value = value
        self.expire_at = expire_at  # Unix 时间戳

    def is_expired(self) -> bool:
        """检查是否已过期"""
        if self.expire_at is None:
            return False
        return time.time() > self.expire_at


class CacheService:
    """内存缓存服务类（线程安全）"""

    def __init__(self):
        """初始化内存缓存"""
        self._cache: Dict[str, _CacheItem] = {}
        self._lock = threading.RLock()
        logger.info("Memory cache service initialized")

    def is_available(self) -> bool:
        """检查缓存是否可用（内存缓存始终可用）"""
        return True

    def _cleanup_expired(self):
        """清理过期的缓存项"""
        current_time = time.time()
        expired_keys = [
            key for key, item in self._cache.items()
            if item.expire_at is not None and current_time > item.expire_at
        ]
        for key in expired_keys:
            del self._cache[key]

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
        try:
            if isinstance(expire, timedelta):
                expire = int(expire.total_seconds())

            expire_at = time.time() + expire if expire else None

            with self._lock:
                self._cache[key] = _CacheItem(value, expire_at)
                # 定期清理过期项
                if len(self._cache) > 1000:
                    self._cleanup_expired()

            return True

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
        try:
            with self._lock:
                item = self._cache.get(key)

                if item is None:
                    return default

                if item.is_expired():
                    del self._cache[key]
                    return default

                return item.value

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
        try:
            with self._lock:
                if key in self._cache:
                    del self._cache[key]
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to delete cache key '{key}': {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        批量删除缓存（支持通配符 *）

        Args:
            pattern: 匹配模式（支持通配符 *）

        Returns:
            删除的键数量
        """
        try:
            import fnmatch
            with self._lock:
                keys_to_delete = [
                    key for key in self._cache.keys()
                    if fnmatch.fnmatch(key, pattern)
                ]
                for key in keys_to_delete:
                    del self._cache[key]
                return len(keys_to_delete)

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
        try:
            with self._lock:
                item = self._cache.get(key)
                if item is None:
                    return False
                if item.is_expired():
                    del self._cache[key]
                    return False
                return True

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
        try:
            with self._lock:
                item = self._cache.get(key)
                if item is None:
                    return False
                item.expire_at = time.time() + seconds
                return True

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
        try:
            with self._lock:
                item = self._cache.get(key)
                if item is None or item.is_expired():
                    new_value = amount
                    self._cache[key] = _CacheItem(new_value)
                else:
                    if not isinstance(item.value, int):
                        return None
                    item.value += amount
                    new_value = item.value
                return new_value

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
        try:
            import fnmatch
            with self._lock:
                # 先清理过期项
                self._cleanup_expired()
                # 返回匹配的键
                return [
                    key for key in self._cache.keys()
                    if fnmatch.fnmatch(key, pattern)
                ]

        except Exception as e:
            logger.error(f"Failed to get cache keys with pattern '{pattern}': {e}")
            return []

    def clear_all(self) -> bool:
        """
        清空所有缓存（谨慎使用）

        Returns:
            是否清空成功
        """
        try:
            with self._lock:
                self._cache.clear()
            return True

        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息
        """
        with self._lock:
            self._cleanup_expired()
            return {
                "type": "memory",
                "total_keys": len(self._cache),
                "keys": list(self._cache.keys())
            }


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
