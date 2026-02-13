# backend/app/services/document_cache_service.py
"""
文档处理缓存服务

提供文档处理结果的缓存功能，避免重复处理相同文档。
支持 Redis 和内存缓存两种模式。
"""

import json
import logging
import os
from typing import Optional, Dict, Any
from dataclasses import asdict

logger = logging.getLogger(__name__)


class DocumentCacheService:
    """
    文档处理缓存服务

    支持基于文件哈希的结果缓存，提高重复文档的处理效率。
    """

    def __init__(self, use_redis: bool = False, redis_url: str = None):
        """
        初始化缓存服务

        Args:
            use_redis: 是否使用 Redis 缓存（否则使用内存缓存）
            redis_url: Redis 连接 URL
        """
        self.use_redis = use_redis
        self._memory_cache: Dict[str, Any] = {}
        self._redis_client = None

        if use_redis and redis_url:
            try:
                import redis
                self._redis_client = redis.from_url(redis_url, decode_responses=True)
                # 测试连接
                self._redis_client.ping()
                logger.info("[DocumentCacheService] Redis 缓存已启用")
            except Exception as e:
                logger.warning(f"[DocumentCacheService] Redis 连接失败，使用内存缓存: {str(e)}")
                self.use_redis = False
        else:
            logger.info("[DocumentCacheService] 使用内存缓存")

    def get_cached_result(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的处理结果

        Args:
            file_hash: 文件哈希值

        Returns:
            缓存的处理结果，如果不存在则返回 None
        """
        try:
            if self.use_redis and self._redis_client:
                cached = self._redis_client.get(f"doc_cache:{file_hash}")
                if cached:
                    logger.debug(f"[DocumentCacheService] Redis 缓存命中: {file_hash}")
                    return json.loads(cached)
            else:
                if file_hash in self._memory_cache:
                    logger.debug(f"[DocumentCacheService] 内存缓存命中: {file_hash}")
                    return self._memory_cache[file_hash]

            return None

        except Exception as e:
            logger.error(f"[DocumentCacheService] 获取缓存失败: {str(e)}")
            return None

    def cache_result(self, file_hash: str, result: Any, ttl: int = 3600) -> bool:
        """
        缓存处理结果

        Args:
            file_hash: 文件哈希值
            result: 处理结果
            ttl: 缓存过期时间（秒），默认 1 小时

        Returns:
            是否缓存成功
        """
        try:
            # 将结果序列化为字典
            if hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
            else:
                result_dict = asdict(result)

            if self.use_redis and self._redis_client:
                # Redis 缓存
                self._redis_client.setex(
                    f"doc_cache:{file_hash}",
                    ttl,
                    json.dumps(result_dict, ensure_ascii=False)
                )
                logger.info(f"[DocumentCacheService] 结果已缓存到 Redis: {file_hash}")
            else:
                # 内存缓存
                self._memory_cache[file_hash] = result_dict
                logger.info(f"[DocumentCacheService] 结果已缓存到内存: {file_hash}")

            return True

        except Exception as e:
            logger.error(f"[DocumentCacheService] 缓存失败: {str(e)}")
            return False

    def invalidate_cache(self, file_hash: str) -> bool:
        """
        使缓存失效

        Args:
            file_hash: 文件哈希值

        Returns:
           是否成功失效
        """
        try:
            if self.use_redis and self._redis_client:
                self._redis_client.delete(f"doc_cache:{file_hash}")
            else:
                if file_hash in self._memory_cache:
                    del self._memory_cache[file_hash]

            logger.info(f"[DocumentCacheService] 缓存已失效: {file_hash}")
            return True

        except Exception as e:
            logger.error(f"[DocumentCacheService] 失效缓存失败: {str(e)}")
            return False

    def clear_all_cache(self) -> bool:
        """
        清空所有缓存

        Returns:
           是否成功清空
        """
        try:
            if self.use_redis and self._redis_client:
                # 清空所有 doc_cache:* 的键
                keys = self._redis_client.keys("doc_cache:*")
                if keys:
                    self._redis_client.delete(*keys)
            else:
                self._memory_cache.clear()

            logger.info("[DocumentCacheService] 所有缓存已清空")
            return True

        except Exception as e:
            logger.error(f"[DocumentCacheService] 清空缓存失败: {str(e)}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息
        """
        stats = {
            "cache_type": "redis" if self.use_redis else "memory",
            "enabled": True
        }

        try:
            if self.use_redis and self._redis_client:
                keys = self._redis_client.keys("doc_cache:*")
                stats["cached_count"] = len(keys)
                stats["memory_usage"] = self._redis_client.dbsize()
            else:
                stats["cached_count"] = len(self._memory_cache)
                stats["memory_usage"] = len(self._memory_cache)

        except Exception as e:
            logger.error(f"[DocumentCacheService] 获取统计信息失败: {str(e)}")
            stats["error"] = str(e)

        return stats

    def is_available(self) -> bool:
        """
        检查缓存服务是否可用

        Returns:
            是否可用
        """
        if self.use_redis and self._redis_client:
            try:
                self._redis_client.ping()
                return True
            except Exception:
                return False
        return True


# ==================== 单例模式 ====================

_cache_service_instance: Optional[DocumentCacheService] = None


def get_document_cache_service() -> DocumentCacheService:
    """
    获取文档缓存服务单例

    Returns:
        DocumentCacheService 实例
    """
    global _cache_service_instance

    if _cache_service_instance is None:
        # 从环境变量读取配置
        use_redis = os.getenv("DOCUMENT_CACHE_ENABLED", "false").lower() == "true"
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        _cache_service_instance = DocumentCacheService(
            use_redis=use_redis,
            redis_url=redis_url
        )
        logger.info("[DocumentCacheService] 文档缓存服务初始化完成")

    return _cache_service_instance
