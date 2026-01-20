"""
合同生成模块 - 性能优化工具

提供缓存、批处理、并发等性能优化功能
"""

from typing import Optional, Dict, Any, List, Callable
from functools import wraps, lru_cache
from datetime import datetime, timedelta
import hashlib
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


# ==================== 缓存装饰器 ====================

def cache_result(
    ttl_seconds: int = 3600,
    key_prefix: str = "",
    include_args: bool = True,
    include_kwargs: bool = True
):
    """
    简单的内存缓存装饰器（带 TTL）

    Args:
        ttl_seconds: 缓存过期时间（秒）
        key_prefix: 缓存键前缀
        include_args: 是否包含位置参数到键
        include_kwargs: 是否包含关键字参数到键

    Example:
        @cache_result(ttl_seconds=1800, key_prefix="model_config")
        def get_model_config(model_name: str):
            ...
    """
    cache = {}

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = [key_prefix, func.__name__]

            if include_args and args:
                # 跳过 self 参数（如果是方法）
                args_to_hash = args[1:] if args and hasattr(args[0], '__class__') else args
                key_parts.extend(str(arg) for arg in args_to_hash)

            if include_kwargs:
                for k, v in sorted(kwargs.items()):
                    key_parts.append(f"{k}={v}")

            cache_key = ":".join(key_parts)

            # 检查缓存
            if cache_key in cache:
                cached_data, cached_time = cache[cache_key]
                if datetime.now() - cached_time < timedelta(seconds=ttl_seconds):
                    logger.debug(f"[Cache] 命中缓存: {cache_key}")
                    return cached_data
                else:
                    # 缓存过期，删除
                    del cache[cache_key]

            # 执行函数
            result = func(*args, **kwargs)

            # 存储到缓存
            cache[cache_key] = (result, datetime.now())
            logger.debug(f"[Cache] 存储缓存: {cache_key}")

            return result

        return wrapper
    return decorator


def cache_async_result(
    ttl_seconds: int = 3600,
    key_prefix: str = "",
    max_size: int = 128
):
    """
    异步函数的缓存装饰器

    Args:
        ttl_seconds: 缓存过期时间（秒）
        key_prefix: 缓存键前缀
        max_size: 最大缓存条目数

    Example:
        @cache_async_result(ttl_seconds=1800, key_prefix="knowledge_graph")
        async def query_knowledge_graph(query: str):
            ...
    """
    cache = {}
    cache_order = []  # 用于 LRU 淘汰

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = [key_prefix, func.__name__]

            # 序列化参数
            params = []
            if args:
                # 跳过 self 参数
                args_to_hash = args[1:] if args and hasattr(args[0], '__class__') else args
                params.extend(str(arg) for arg in args_to_hash)
            if kwargs:
                for k, v in sorted(kwargs.items()):
                    params.append(f"{k}={v}")

            key_parts.extend(params)
            cache_key = ":".join(key_parts)

            # 检查缓存
            if cache_key in cache:
                cached_data, cached_time = cache[cache_key]
                if datetime.now() - cached_time < timedelta(seconds=ttl_seconds):
                    logger.debug(f"[Cache] 命中缓存: {cache_key}")
                    return cached_data
                else:
                    # 缓存过期，删除
                    del cache[cache_key]
                    cache_order.remove(cache_key)

            # 执行函数
            result = await func(*args, **kwargs)

            # LRU 淘汰
            if len(cache) >= max_size and cache_key not in cache:
                oldest_key = cache_order.pop(0)
                del cache[oldest_key]

            # 存储到缓存
            cache[cache_key] = (result, datetime.now())
            cache_order.append(cache_key)
            logger.debug(f"[Cache] 存储缓存: {cache_key}")

            return result

        return wrapper
    return decorator


# ==================== 批处理工具 ====================

class BatchProcessor:
    """批处理工具类"""

    def __init__(
        self,
        batch_size: int = 10,
        timeout_seconds: float = 1.0,
        max_concurrency: int = 5
    ):
        """
        Args:
            batch_size: 每批处理的最大数量
            timeout_seconds: 等待批次填满的超时时间
            max_concurrency: 最大并发批次数
        """
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.max_concurrency = max_concurrency
        self._queue = []
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def add(self, item: Any) -> Any:
        """
        添加项目到批处理队列

        Args:
            item: 要处理的项目

        Returns:
            处理结果
        """
        future = asyncio.Future()
        self._queue.append((item, future))

        if len(self._queue) >= self.batch_size:
            # 达到批大小，立即处理
            asyncio.create_task(self._process_batch())

        return await future

    async def _process_batch(self):
        """处理当前批次"""
        if not self._queue:
            return

        # 取出当前批次
        batch = self._queue[:self.batch_size]
        self._queue = self._queue[self.batch_size:]

        items = [item for item, _ in batch]
        futures = [future for _, future in batch]

        async with self._semaphore:
            try:
                # 子类实现具体的批处理逻辑
                results = await self.process_items(items)

                # 设置结果
                for future, result in zip(futures, results):
                    future.set_result(result)

            except Exception as e:
                # 设置异常
                for future in futures:
                    future.set_exception(e)

    async def process_items(self, items: List[Any]) -> List[Any]:
        """
        处理一批项目（子类实现）

        Args:
            items: 项目列表

        Returns:
            结果列表
        """
        raise NotImplementedError("子类必须实现 process_items 方法")

    async def flush(self):
        """处理剩余的所有项目"""
        while self._queue:
            await self._process_batch()


# ==================== 并发控制 ====================

class ConcurrencyLimiter:
    """并发限制器"""

    def __init__(self, max_concurrent: int = 10):
        """
        Args:
            max_concurrent: 最大并发数
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def __aenter__(self):
        await self.semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.semaphore.release()


def limit_concurrency(max_concurrent: int = 10):
    """
    并发限制装饰器

    Args:
        max_concurrent: 最大并发数

    Example:
        @limit_concurrency(max_concurrent=5)
        async def process_contract(data):
            ...
    """
    limiter = ConcurrencyLimiter(max_concurrent)

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with limiter:
                return await func(*args, **kwargs)
        return wrapper
    return decorator


# ==================== 性能监控装饰器 ====================

def monitor_performance(
    log_slow_calls: bool = True,
    slow_threshold_seconds: float = 5.0,
    log_all_calls: bool = False
):
    """
    性能监控装饰器

    Args:
        log_slow_calls: 是否记录慢调用
        slow_threshold_seconds: 慢调用阈值（秒）
        log_all_calls: 是否记录所有调用

    Example:
        @monitor_performance(slow_threshold_seconds=10.0)
        async def generate_contract(user_input: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            import time
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                func_name = func.__name__

                if log_all_calls or (log_slow_calls and elapsed > slow_threshold_seconds):
                    log_level = logger.warning if elapsed > slow_threshold_seconds else logger.info
                    log_level(
                        f"[Performance] {func_name} 耗时 {elapsed:.2f}s"
                        f"{' (慢调用)' if elapsed > slow_threshold_seconds else ''}"
                    )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                func_name = func.__name__

                if log_all_calls or (log_slow_calls and elapsed > slow_threshold_seconds):
                    log_level = logger.warning if elapsed > slow_threshold_seconds else logger.info
                    log_level(
                        f"[Performance] {func_name} 耗时 {elapsed:.2f}s"
                        f"{' (慢调用)' if elapsed > slow_threshold_seconds else ''}"
                    )

        # 根据函数类型返回适当的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ==================== 重试机制 ====================

def retry_on_failure(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    失败重试装饰器（带指数退避）

    Args:
        max_retries: 最大重试次数
        backoff_factor: 退避因子（秒）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数

    Example:
        @retry_on_failure(max_retries=3, backoff_factor=2.0, exceptions=(ConnectionError,))
        async def call_external_api(url: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            import asyncio

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"[Retry] {func.__name__} 失败 (尝试 {attempt + 1}/{max_retries + 1}), "
                            f"{wait_time}s 后重试: {str(e)}"
                        )

                        if on_retry:
                            on_retry(attempt, e)

                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} 在 {max_retries + 1} 次尝试后仍然失败"
                        )

            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"[Retry] {func.__name__} 失败 (尝试 {attempt + 1}/{max_retries + 1}), "
                            f"{wait_time}s 后重试: {str(e)}"
                        )

                        if on_retry:
                            on_retry(attempt, e)

                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} 在 {max_retries + 1} 次尝试后仍然失败"
                        )

            raise last_exception

        # 根据函数类型返回适当的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ==================== 资源清理工具 ====================

class ResourceManager:
    """资源管理器（确保资源正确释放）"""

    def __init__(self):
        self._resources = []

    def register(self, resource: Any, cleanup_func: Callable):
        """
        注册资源及其清理函数

        Args:
            resource: 资源对象
            cleanup_func: 清理函数
        """
        self._resources.append((resource, cleanup_func))

    async def cleanup_all(self):
        """清理所有注册的资源"""
        for resource, cleanup_func in reversed(self._resources):
            try:
                if asyncio.iscoroutinefunction(cleanup_func):
                    await cleanup_func(resource)
                else:
                    cleanup_func(resource)
            except Exception as e:
                logger.error(f"[ResourceManager] 清理资源失败: {e}")

        self._resources.clear()

    def __del__(self):
        """析构函数，确保资源被清理"""
        if self._resources:
            logger.warning("[ResourceManager] 还有未清理的资源，将在析构时清理")
            for resource, cleanup_func in reversed(self._resources):
                try:
                    if not asyncio.iscoroutinefunction(cleanup_func):
                        cleanup_func(resource)
                except Exception as e:
                    logger.error(f"[ResourceManager] 析构清理失败: {e}")


# ==================== 延迟加载工具 ====================

class LazyLoader:
    """延迟加载器"""

    def __init__(self, load_func: Callable):
        """
        Args:
            load_func: 加载资源的函数
        """
        self._load_func = load_func
        self._loaded = False
        self._value = None

    def get(self):
        """获取资源（首次调用时加载）"""
        if not self._loaded:
            logger.debug(f"[LazyLoader] 延迟加载: {self._load_func.__name__}")
            self._value = self._load_func()
            self._loaded = True
        return self._value

    def is_loaded(self) -> bool:
        """检查是否已加载"""
        return self._loaded

    def reset(self):
        """重置加载状态（强制重新加载）"""
        self._loaded = False
        self._value = None
