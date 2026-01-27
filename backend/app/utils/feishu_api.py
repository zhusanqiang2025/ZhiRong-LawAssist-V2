# -*- coding: utf-8 -*-
"""
backend/app/utils/feishu_api.py - 飞书集成本地开发
飞书开放平台 API 基础调用工具类

主要功能：
1. 飞书 tenant_access_token 自动获取与缓存
2. 飞书 API 通用请求方法（支持 GET/POST/PUT/DELETE）
3. 飞书多维表操作（获取数据、更新数据）
4. 飞书消息发送（文本消息、卡片消息）
5. 飞书卡片回调解析

使用方式：
    from app.utils.feishu_api import (
        get_tenant_access_token,
        get_base_table_data,
        send_feishu_text_msg
    )

    # 获取多维表数据
    data = get_base_table_data(app_token, table_id)
"""

import os
import json
import time
import logging
import hashlib
import hmac
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==================== 配置读取 ====================
# 飞书开放平台配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
# 飞书 API 基础 URL（注意：所有 API 路径都需要包含 /open-apis 前缀）
FEISHU_BASE_API_URL = os.getenv("FEISHU_BASE_API_URL", "https://open.feishu.cn/open-apis")

# 飞书多维表配置（用于查询记录获取真实 file_token）
FEISHU_BITABLE_APP_TOKEN = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
FEISHU_BITABLE_TABLE_ID = os.getenv("FEISHU_BITABLE_TABLE_ID", "")

# tenant_access_token 缓存配置
FEISHU_TENANT_TOKEN_CACHE_KEY = os.getenv(
    "FEISHU_TENANT_TOKEN_CACHE_KEY",
    "feishu_integration:tenant_token"
)
FEISHU_TENANT_TOKEN_EXPIRE_SECONDS = int(
    os.getenv("FEISHU_TENANT_TOKEN_EXPIRE_SECONDS", "7200")
)

# Redis 配置
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "123myredissecret")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# 日志配置
LOG_LEVEL = os.getenv("FEISHU_LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("FEISHU_LOG_FILE", "logs/feishu_integration.log")

# ==================== 日志配置 ====================
logger = logging.getLogger("feishu_integration.api")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# 控制台处理器
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    console_formatter = logging.Formatter(
        '[%(asctime)s: %(levelname)s][%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

# 文件处理器
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
class FeishuApiError(Exception):
    """飞书 API 调用异常"""
    pass


class FeishuAuthError(FeishuApiError):
    """飞书认证异常"""
    pass


class FeishuRateLimitError(FeishuApiError):
    """飞书限流异常"""
    pass


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
        logger.warning(f"Redis 连接失败: {e}")
        return None


def _clear_tenant_token_cache() -> bool:
    """
    清除 tenant_access_token 缓存（Redis + 内存）

    Returns:
        bool: 是否清除成功
    """
    global _memory_tenant_token_store

    # 清除内存缓存
    _memory_tenant_token_store = None

    # 清除 Redis 缓存
    try:
        redis_client = _get_redis_connection()
        if redis_client:
            redis_client.delete(FEISHU_TENANT_TOKEN_CACHE_KEY)
            logger.info("已清除 Redis 中的 tenant_access_token 缓存")
    except Exception as e:
        logger.warning(f"清除 Redis 缓存失败: {e}")

    logger.info("tenant_access_token 缓存已清除（内存+Redis）")
    return True


# ==================== tenant_access_token 管理 ====================
_memory_tenant_token_store: Optional[dict] = None


def _save_tenant_token_to_cache(token: str, expire_time: float) -> bool:
    """
    保存 tenant_access_token 到缓存

    Args:
        token: tenant_access_token
        expire_time: 过期时间戳

    Returns:
        bool: 是否保存成功
    """
    global _memory_tenant_token_store

    # 保存到内存
    _memory_tenant_token_store = {
        "token": token,
        "expire_time": expire_time
    }

    # 保存到 Redis
    try:
        redis_client = _get_redis_connection()
        if redis_client:
            redis_client.setex(
                FEISHU_TENANT_TOKEN_CACHE_KEY,
                int(expire_time - time.time()),
                token
            )
            logger.debug(f"tenant_access_token 已保存到 Redis")
            return True
    except Exception as e:
        logger.warning(f"保存 tenant_access_token 到 Redis 失败: {e}")

    return False


def _load_tenant_token_from_cache() -> Optional[str]:
    """
    从缓存加载 tenant_access_token

    Returns:
        Optional[str]: tenant_access_token，无缓存时返回 None
    """
    global _memory_tenant_token_store

    # 先从 Redis 加载
    try:
        redis_client = _get_redis_connection()
        if redis_client:
            token = redis_client.get(FEISHU_TENANT_TOKEN_CACHE_KEY)
            if token:
                logger.info(f"✅ 从 Redis 加载 tenant_access_token | 长度: {len(token)} 字符")
                # 同步到内存
                _memory_tenant_token_store = {
                    "token": token,
                    "expire_time": time.time() + FEISHU_TENANT_TOKEN_EXPIRE_SECONDS
                }
                return token
            else:
                logger.info(f"⚠️  Redis 中无 tenant_access_token 缓存")
    except Exception as e:
        logger.warning(f"从 Redis 加载 tenant_access_token 失败: {e}")

    # Redis 无数据时，从内存加载
    if _memory_tenant_token_store:
        token = _memory_tenant_token_store["token"]
        expire_time = _memory_tenant_token_store["expire_time"]
        if time.time() < expire_time:
            logger.info(f"✅ 从内存加载 tenant_access_token | 长度: {len(token)} 字符")
            return token
        else:
            logger.info(f"⚠️  内存中的 tenant_access_token 已过期")

    return None


def _fetch_tenant_access_token() -> str:
    """
    调用飞书 API 获取新的 tenant_access_token

    Returns:
        str: tenant_access_token

    Raises:
        FeishuAuthError: 获取 token 失败
    """
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        raise FeishuAuthError("飞书 APP_ID 或 APP_SECRET 未配置")

    url = f"{FEISHU_BASE_API_URL}/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }

    logger.info(f"正在调用飞书 API 获取 tenant_access_token: {url}")
    logger.info(f"📌 请求参数: app_id={FEISHU_APP_ID[:8]}...")

    try:
        response = requests.post(url, json=payload, timeout=30)

        # 记录响应状态码和内容类型
        logger.info(f"📌 响应状态码: {response.status_code}")
        logger.info(f"📌 响应头: {response.headers.get('Content-Type', 'unknown')}")

        # 先检查响应是否成功
        if response.status_code != 200:
            logger.error(f"❌ HTTP 请求失败 | 状态码: {response.status_code}")
            logger.error(f"❌ 响应内容: {response.text[:500]}")
            raise FeishuAuthError(f"HTTP 请求失败，状态码: {response.status_code}")

        # 记录响应文本（前200字符）
        logger.info(f"📌 响应内容（前200字符）: {response.text[:200]}")

        # 尝试解析 JSON
        try:
            data = response.json()
        except ValueError as je:
            logger.error(f"❌ JSON 解析失败: {je}")
            logger.error(f"❌ 原始响应: {response.text[:500]}")
            raise FeishuAuthError(f"响应不是有效的 JSON 格式: {je}")

        # 检查业务错误码
        if data.get("code") == 0:
            token = data.get("tenant_access_token")
            expire = data.get("expire", FEISHU_TENANT_TOKEN_EXPIRE_SECONDS)
            logger.info(f"✅ 成功获取 tenant_access_token | 长度: {len(token)} 字符 | 有效期: {expire} 秒")
            return token
        else:
            error_msg = data.get("msg", "未知错误")
            error_code = data.get("code")
            logger.error(f"❌ 飞书 API 返回业务错误 | 错误码: {error_code} | 错误信息: {error_msg}")
            raise FeishuAuthError(
                f"飞书 API 返回错误: {error_msg}, "
                f"错误码: {error_code}"
            )
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 飞书 API 请求异常: {e}", exc_info=True)
        raise FeishuAuthError(f"飞书 API 请求失败: {e}")


def get_tenant_access_token() -> str:
    """
    获取有效的 tenant_access_token（对外统一接口）

    该方法会自动处理 token 的获取和缓存，调用方无需关心刷新逻辑

    Returns:
        str: 有效的 tenant_access_token

    Raises:
        FeishuAuthError: 获取 token 失败

    使用示例：
        >>> from app.utils.feishu_api import get_tenant_access_token
        >>> token = get_tenant_access_token()
    """
    logger.info(f"🔑 获取 tenant_access_token...")
    # 先尝试从缓存加载
    token = _load_tenant_token_from_cache()

    if token:
        logger.info(f"✅ 使用缓存的 tenant_access_token | 长度: {len(token)} 字符")
        return token

    # 缓存无数据，重新获取
    logger.info("⚠️  缓存无 tenant_access_token，开始获取新 token")
    token = _fetch_tenant_access_token()

    # 保存到缓存
    expire_time = time.time() + FEISHU_TENANT_TOKEN_EXPIRE_SECONDS
    _save_tenant_token_to_cache(token, expire_time)

    logger.info(f"✅ 获取新 tenant_access_token 成功 | 长度: {len(token)} 字符")
    return token


# ==================== 飞书 API 通用请求方法 ====================
def feishu_api_request(
    method: str,
    api_path: str,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    _retry_count: int = 0  # 内部重试计数器（防止无限递归）
) -> Dict[str, Any]:
    """
    飞书 API 通用请求方法

    Args:
        method: HTTP 方法（GET/POST/PUT/DELETE）
        api_path: API 路径（如 /bitable/v1/apps/{app_token}/tables/{table_id}/records）
        payload: POST/PUT 请求的请求体
        params: GET 请求的查询参数
        headers: 额外的请求头

    Returns:
        Dict[str, Any]: API 响应数据

    Raises:
        FeishuApiError: API 调用失败
        FeishuAuthError: 认证失败（包括 token 过期重试失败）

    Note:
        当遇到错误码 99991663 (tenant_access_token 过期) 时，会自动：
        1. 清除 Redis 和内存缓存
        2. 重新获取 token
        3. 重试原始请求（最多 1 次）

    使用示例：
        >>> # 获取多维表数据
        >>> data = feishu_api_request(
        ...     "GET",
        ...     f"/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        ... )
    """
    # 获取 tenant_access_token
    tenant_token = get_tenant_access_token()

    # 构建请求 URL
    url = f"{FEISHU_BASE_API_URL}{api_path}"

    # 构建请求头
    request_headers = {
        "Authorization": f"Bearer {tenant_token}",
        "Content-Type": "application/json"
    }
    if headers:
        request_headers.update(headers)

    # 记录请求信息
    logger.info(f"飞书 API 请求: {method} {url}")
    if payload:
        logger.debug(f"请求体: {json.dumps(payload, ensure_ascii=False)[:500]}")
    if params:
        logger.debug(f"查询参数: {params}")

    start_time = time.time()

    try:
        # 发送请求
        if method.upper() == "GET":
            response = requests.get(url, params=params, headers=request_headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=payload, headers=request_headers, timeout=30)
        elif method.upper() == "PUT":
            response = requests.put(url, json=payload, headers=request_headers, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, json=payload, headers=request_headers, timeout=30)
        else:
            raise FeishuApiError(f"不支持的 HTTP 方法: {method}")

        # 计算耗时
        elapsed = time.time() - start_time
        logger.info(f"飞书 API 响应: 状态码 {response.status_code}, 耗时 {elapsed:.2f}s")

        # 解析响应
        data = response.json()

        # 检查业务错误码
        code = data.get("code")
        if code != 0:
            error_msg = data.get("msg", "未知错误")
            error_code = data.get("code")

            # 处理常见错误
            if error_code == 99991663:
                # tenant_access_token 过期，清除缓存并重试
                # 防止无限递归：最多重试 1 次
                if _retry_count >= 1:
                    logger.error(f"tenant_access_token 重试后仍过期: {error_msg}")
                    raise FeishuAuthError(f"tenant_access_token 重试后仍过期: {error_msg}")

                logger.warning(f"检测到 tenant_access_token 过期 (错误码: {error_code}), 开始重试")

                # 1. 清除缓存（Redis + 内存）
                _clear_tenant_token_cache()

                # 2. 递归重试（重试计数器 +1）
                logger.info(f"🔄 开始重试 API 请求 | 方法: {method} | 路径: {api_path}")
                return feishu_api_request(
                    method=method,
                    api_path=api_path,
                    payload=payload,
                    params=params,
                    headers=headers,
                    _retry_count=_retry_count + 1
                )
            elif error_code == 99991401:
                raise FeishuRateLimitError(f"飞书 API 限流: {error_msg}")
            else:
                raise FeishuApiError(f"飞书 API 返回错误: {error_msg} (错误码: {error_code})")

        logger.debug(f"响应数据: {json.dumps(data, ensure_ascii=False)[:500]}")
        return data

    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        logger.error(f"飞书 API 请求失败，耗时 {elapsed:.2f}s: {e}")
        raise FeishuApiError(f"飞书 API 请求失败: {e}")


# ==================== 飞书多维表操作 ====================
def get_base_table_data(
    app_token: str,
    table_id: str,
    page_size: int = 100,
    page_token: Optional[str] = None,
    view_id: Optional[str] = None,
    field_names: Optional[List[str]] = None,
    sort: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    获取飞书多维表数据

    Args:
        app_token: 多维表格应用的 app_token
        table_id: 数据表的 table_id
        page_size: 每页数量（默认 100，最大 100）
        page_token: 分页 token（用于获取下一页）
        view_id: 视图 ID（可选，用于获取特定视图的数据）
        field_names: 指定返回的字段（可选）
        sort: 排序配置（可选）

    Returns:
        Dict[str, Any]: 包含 records 和 page_token 的响应数据

    使用示例：
        >>> data = get_base_table_data("app_xxx", "table_xxx")
        >>> records = data.get("data", {}).get("items", [])
    """
    api_path = f"/bitable/v1/apps/{app_token}/tables/{table_id}/records"

    params = {
        "page_size": min(page_size, 100)
    }

    if page_token:
        params["page_token"] = page_token
    if view_id:
        params["view_id"] = view_id
    if field_names:
        params["field_names"] = json.dumps(field_names)
    if sort:
        params["sort"] = json.dumps(sort)

    return feishu_api_request("GET", api_path, params=params)


def update_base_table_data(
    app_token: str,
    table_id: str,
    record_id: str,
    fields: Dict[str, Any]
) -> Dict[str, Any]:
    """
    更新飞书多维表数据

    Args:
        app_token: 多维表格应用的 app_token
        table_id: 数据表的 table_id
        record_id: 记录的 record_id
        fields: 要更新的字段数据

    Returns:
        Dict[str, Any]: 更新后的记录数据

    使用示例：
        >>> result = update_base_table_data(
        ...     "app_xxx", "table_xxx", "record_xxx",
        ...     {"fields": {"审核状态": "已通过"}}
        ... )
    """
    api_path = f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"

    payload = {
        "fields": fields
    }

    return feishu_api_request("PUT", api_path, payload=payload)


def create_base_table_record(
    app_token: str,
    table_id: str,
    fields: Dict[str, Any]
) -> Dict[str, Any]:
    """
    创建飞书多维表记录

    Args:
        app_token: 多维表格应用的 app_token
        table_id: 数据表的 table_id
        fields: 记录的字段数据

    Returns:
        Dict[str, Any]: 创建的记录数据

    使用示例：
        >>> result = create_base_table_record(
        ...     "app_xxx", "table_xxx",
        ...     {"fields": {"任务名称": "新任务", "状态": "待处理"}}
        ... )
    """
    api_path = f"/bitable/v1/apps/{app_token}/tables/{table_id}/records"

    payload = {
        "fields": fields
    }

    return feishu_api_request("POST", api_path, payload=payload)


def get_bitable_record(
    app_token: str,
    table_id: str,
    record_id: str
) -> Optional[Dict[str, Any]]:
    """
    查询单条飞书多维表记录（用于获取附件的真实 file_token）

    Args:
        app_token: 多维表格应用的 app_token
        table_id: 数据表的 table_id
        record_id: 记录的 record_id

    Returns:
        Dict[str, Any]: 记录数据，如果失败返回 None

    使用示例：
        >>> result = get_bitable_record(
        ...     "app_xxx", "table_xxx", "record_xxx"
        ... )
    """
    try:
        api_path = f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"

        response = feishu_api_request("GET", api_path)

        if response and response.get("code") == 0:
            data = response.get("data", {})
            record = data.get("record", {})
            logger.info(f"✅ 成功查询记录 | record_id: {record_id}")
            return record
        else:
            error_msg = response.get("msg", "未知错误") if response else "无响应"
            error_code = response.get("code") if response else None
            logger.error(f"❌ 查询记录失败 | 错误码: {error_code} | 错误: {error_msg}")
            return None

    except Exception as e:
        logger.error(f"❌ 查询记录异常: {e}", exc_info=True)
        return None


def get_bitable_record_simple(record_id: str) -> Optional[Dict[str, Any]]:
    """
    查询单条飞书多维表记录（使用全局配置）

    Args:
        record_id: 记录的 record_id

    Returns:
        Dict[str, Any]: 记录数据，如果失败返回 None
    """
    if not FEISHU_BITABLE_APP_TOKEN or not FEISHU_BITABLE_TABLE_ID:
        logger.error("❌ 未配置 FEISHU_BITABLE_APP_TOKEN 或 FEISHU_BITABLE_TABLE_ID")
        return None

    return get_bitable_record(FEISHU_BITABLE_APP_TOKEN, FEISHU_BITABLE_TABLE_ID, record_id)


# ==================== 飞书消息发送 ====================
def send_feishu_text_msg(
    receive_id: str,
    msg_type: str = "text",
    content: Optional[str] = None,
    receive_id_type: str = "user_id"
) -> Dict[str, Any]:
    """
    发送飞书文本消息

    Args:
        receive_id: 接收者 ID（用户 ID、部门 ID 等）
        msg_type: 消息类型（默认 text）
        content: 消息内容（文本格式）
        receive_id_type: 接收者 ID 类型（user_id、union_id、open_id、email、chat_id）

    Returns:
        Dict[str, Any]: 发送结果

    使用示例：
        >>> result = send_feishu_text_msg(
        ...     "ou_xxx",
        ...     content="您好，这是测试消息"
        ... )
    """
    api_path = "/im/v1/messages"

    # 构建消息内容
    if content is None:
        content = "空消息"

    text_content = json.dumps({"text": content}, ensure_ascii=False)

    payload = {
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": text_content,
        "receive_id_type": receive_id_type
    }

    return feishu_api_request("POST", api_path, payload=payload)


def send_feishu_card_msg(
    receive_id: str,
    card_content: Dict[str, Any],
    receive_id_type: str = "user_id"
) -> Dict[str, Any]:
    """
    发送飞书卡片消息

    Args:
        receive_id: 接收者 ID
        card_content: 卡片内容（JSON 格式）
        receive_id_type: 接收者 ID 类型

    Returns:
        Dict[str, Any]: 发送结果

    使用示例：
        >>> card = {
        ...     "config": {"wide_screen_mode": True},
        ...     "header": {"title": {"content": "审核通知", "tag": "plain_text"}},
        ...     "elements": [{"tag": "div", "text": {"tag": "plain_text", "content": "请审核"}}]
        ... }
        >>> result = send_feishu_card_msg("ou_xxx", card)
    """
    api_path = "/im/v1/messages"

    payload = {
        "receive_id": receive_id,
        "msg_type": "interactive",
        "content": json.dumps(card_content, ensure_ascii=False),
        "receive_id_type": receive_id_type
    }

    return feishu_api_request("POST", api_path, payload=payload)


# ==================== 飞书卡片回调解析 ====================
def parse_feishu_card_callback(callback_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析飞书卡片点击事件回调
    支持两种格式：
    1. 标准格式: {"schema": "2.0", "event": {"action": ..., "operator": ..., "token": ...}}
    2. 简化格式: {"action": ..., "user_id": ..., "token": ..., "tag": "button"}

    Args:
        callback_data: 飞书回调的原始数据

    Returns:
        Dict[str, Any]: 解析后的回调数据

    使用示例：
        >>> # 在飞书回调接口中使用
        >>> callback_data = await request.json()
        >>> parsed = parse_feishu_card_callback(callback_data)
        >>> action = parsed.get("action")  # 用户点击的操作
        >>> user_id = parsed.get("user_id")  # 用户 ID
    """
    try:
        # 判断数据格式类型
        has_schema = "schema" in callback_data
        has_event = "event" in callback_data
        has_top_level_action = "action" in callback_data

        if has_schema and has_event:
            # 标准格式：从 event 对象获取数据
            event = callback_data.get("event", {})
            action = event.get("action", {})
            operator = event.get("operator", {})
            user_id = operator.get("user_id") or callback_data.get("user_id")
            token = event.get("token", "")
            logger.info(f"[标准格式] 解析飞书卡片回调 | event_type={callback_data.get('event_type')}")
        elif has_top_level_action:
            # 简化格式：从顶层获取数据
            action = callback_data.get("action", {})
            operator = callback_data.get("operator", {})
            user_id = callback_data.get("user_id") or operator.get("user_id")
            token = callback_data.get("token", "")
            logger.info(f"[简化格式] 解析飞书卡片回调 | tag={callback_data.get('tag')}")
        else:
            logger.warning(f"[未知格式] 无法识别回调数据格式 | keys={list(callback_data.keys())}")
            action = {}
            user_id = None
            token = ""

        timestamp = callback_data.get("timestamp", "")

        result = {
            "action": action,
            "user_id": user_id,
            "token": token,
            "timestamp": timestamp,
            "raw_data": callback_data
        }

        logger.info(f"解析飞书卡片回调: 用户 {user_id}, 操作 {action}")
        return result

    except Exception as e:
        logger.error(f"解析飞书卡片回调失败: {e}")
        raise FeishuApiError(f"解析飞书卡片回调失败: {e}")


# ==================== 飞书文件下载 ====================
def _make_feishu_download_request(download_url: str, max_retries: int = 1) -> requests.Response:
    """
    飞书文件下载请求（带 token 过期自动重试）

    Args:
        download_url: 下载 URL
        max_retries: 最大重试次数（默认 1 次）

    Returns:
        requests.Response: HTTP 响应对象

    Raises:
        FeishuApiError: 下载失败
        FeishuAuthError: 认证失败（包括重试后仍失败）
    """
    for attempt in range(max_retries + 1):
        # 获取 tenant_access_token
        token = get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}"
        }

        logger.info(f"📌 下载请求 (尝试 {attempt + 1}/{max_retries + 1}): {download_url}")

        # 发送请求
        download_response = requests.get(download_url, headers=headers, timeout=60)

        # 检查是否为 token 过期错误
        if download_response.status_code == 400:
            try:
                data = download_response.json()
                if data.get("code") == 99991663:
                    if attempt < max_retries:
                        logger.warning(f"检测到 token 过期，清除缓存并重试...")
                        _clear_tenant_token_cache()
                        continue  # 重试
                    else:
                        logger.error(f"token 过期，重试 {max_retries} 次后仍失败")
            except:
                pass  # 非 JSON 响应，继续处理

        # 成功或其他错误，直接返回
        return download_response

    # 理论上不会到达这里
    return download_response


def download_feishu_file(file_key: str, save_path: str, record_id: Optional[str] = None) -> bool:
    """
    下载飞书文件到本地（支持附件、云文档、多维表文件）

    参数:
        file_key: 飞书文件标识
        save_path: 本地保存路径
        record_id: 多维表记录ID（可选，用于查询记录获取真实 file_token）

    返回:
        是否下载成功

    文档:
    - 查询文件: https://open.feishu.cn/document/server-docs/docs/drive/v1/file/Query_file
    - 附件: https://open.feishu.cn/document/server-docs/docs/drive-v1/attachment/Download_attachment
    - 云文档: https://open.feishu.cn/document/server-docs/docs/drive/v1/file/Download_file
    """
    try:
        logger.info(f"正在下载飞书文件: {file_key}")

        # ========== 步骤 0: 如果提供了 record_id，先查询多维表记录获取真实 file_token ==========
        actual_file_token = file_key  # 默认使用传入的 file_key

        # 只有当 record_id 是有效的 Feishu 记录 ID（以 rec 开头）时才查询记录
        # 飞书记录 ID 格式：recXXXXXX，字段 ID 以 fld 开头，文件 token 以 v0/fld 开头
        if record_id and record_id.startswith("rec") and FEISHU_BITABLE_APP_TOKEN and FEISHU_BITABLE_TABLE_ID:
            logger.info(f"📌 查询多维表记录获取真实 file_token | record_id: {record_id}")
            record = get_bitable_record(FEISHU_BITABLE_APP_TOKEN, FEISHU_BITABLE_TABLE_ID, record_id)

            if record:
                fields = record.get("fields", {})
                logger.info(f"📄 记录字段: {json.dumps(fields, ensure_ascii=False)[:200]}")

                # 查找附件字段（可能的字段名）
                attachment_field = None
                for field_name in ["待审查合同文件", "合同文件", "附件"]:
                    if field_name in fields:
                        attachment_field = fields[field_name]
                        logger.info(f"✅ 找到附件字段: {field_name}")
                        break

                if attachment_field and isinstance(attachment_field, list) and len(attachment_field) > 0:
                    # 附件字段格式：[{"file_token": "xxx", "file_name": "xxx", ...}]
                    first_attachment = attachment_field[0]
                    actual_file_token = first_attachment.get("file_token", file_key)
                    file_name = first_attachment.get("file_name", "unknown")
                    logger.info(f"✅ 获取真实 file_token: {actual_file_token} | 文件名: {file_name}")
                else:
                    logger.warning(f"⚠️  未找到附件字段或附件为空")
            else:
                logger.warning(f"⚠️  查询记录失败，使用原始 file_key")
        elif record_id:
            # record_id 存在但不是有效的记录 ID（可能是字段ID或其他标识）
            logger.info(f"📌 record_id ({record_id}) 不是有效的飞书记录ID（应以 rec 开头），直接使用传入的 file_key")

        # ========== 步骤 1: 判断是否为多维表附件（优先使用多维表附件 API） ==========
        # 如果配置了多维表信息，优先使用多维表附件下载 API
        if FEISHU_BITABLE_APP_TOKEN and FEISHU_BITABLE_TABLE_ID:
            # 飞书多维表附件专属下载 API（官方唯一支持）
            # 文档：https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-row/attachment/download
            download_url = f"{FEISHU_BASE_API_URL}/bitable/v1/apps/{FEISHU_BITABLE_APP_TOKEN}/tables/{FEISHU_BITABLE_TABLE_ID}/attachments/{actual_file_token}/download"
            logger.info(f"📌 使用多维表附件下载 API")

            download_response = _make_feishu_download_request(download_url)

            if download_response.status_code == 200:
                # 确保目录存在
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                # 写入文件
                with open(save_path, 'wb') as f:
                    f.write(download_response.content)
                file_size = len(download_response.content)
                logger.info(f"✅ 成功下载飞书多维表附件 | 大小: {file_size} 字节 | 路径: {save_path}")
                return True
            else:
                logger.error(f"❌ 多维表附件下载失败 | 状态码: {download_response.status_code} | 响应: {download_response.text[:200]}")

        # ========== 步骤 2: 兜底方案 - 使用云文档 API（兼容普通文件） ==========
        logger.info(f"⚠️  尝试兜底方案：云文档下载 API")
        download_url = f"{FEISHU_BASE_API_URL}/drive/v1/medias/{actual_file_token}/download"
        logger.info(f"📌 下载 URL: {download_url}")

        download_response = _make_feishu_download_request(download_url)

        if download_response.status_code == 200:
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            # 写入文件
            with open(save_path, 'wb') as f:
                f.write(download_response.content)
            file_size = len(download_response.content)
            logger.info(f"✅ 成功下载飞书文件（云文档） | 大小: {file_size} 字节 | 路径: {save_path}")
            return True
        else:
            logger.error(f"❌ 下载失败 | 状态码: {download_response.status_code} | 响应: {download_response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"❌ 下载飞书文件异常: {e}", exc_info=True)
        return False


# ==================== 飞书多维表查询函数 ====================
def find_record_by_file_token(file_token: str) -> Optional[str]:
    """
    通过 file_token 查找飞书多维表中包含该文件的记录ID

    参数:
        file_token: 飞书文件标识

    返回:
        记录ID（recxxxxx）或 None
    """
    try:
        # 获取 tenant_access_token
        tenant_token = get_tenant_access_token()
        if not tenant_token:
            logger.error("❌ 获取 tenant_access_token 失败")
            return None

        # 获取多维表配置
        app_token = os.getenv("FEISHU_BITABLE_APP_TOKEN")
        table_id = os.getenv("FEISHU_BITABLE_TABLE_ID")

        if not app_token or not table_id:
            logger.error("❌ 缺少多维表配置")
            return None

        # 调用飞书API搜索记录
        url = f"{FEISHU_BASE_API_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"

        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }

        # 构造搜索条件（在所有字段中查找包含该 file_token 的记录）
        request_body = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": "待审查合同文件",  # 假设文件存储在这个字段
                        "operator": "isNotEmpty",
                        "value": []
                    }
                ]
            },
            "page_size": 100
        }

        logger.info(f"📌 通过 file_token 查找记录 | file_token: {file_token}")
        response = requests.post(url, headers=headers, json=request_body, timeout=30)

        if response.status_code != 200:
            logger.error(f"❌ 搜索记录失败 | 状态码: {response.status_code} | 响应: {response.text[:300]}")
            return None

        data = response.json()

        # 检查API返回码
        if data.get("code") != 0:
            logger.error(f"❌ API返回错误 | code: {data.get('code')} | msg: {data.get('msg')}")
            return None

        # 解析搜索结果
        records = data.get("data", {}).get("items", [])

        if not records:
            logger.warning(f"⚠️  未找到包含该文件的记录")
            return None

        # 在搜索结果中查找包含目标 file_token 的记录
        for record in records:
            record_id = record.get("record_id", "")
            fields = record.get("fields", {})

            # 检查附件字段
            attachment_field = fields.get("待审查合同文件", [])
            if attachment_field and isinstance(attachment_field, list):
                for attachment in attachment_field:
                    if attachment.get("file_token") == file_token:
                        logger.info(f"✅ 找到匹配记录 | record_id: {record_id}")
                        return record_id

        logger.warning(f"⚠️  未找到包含 file_token {file_token} 的记录")
        return None

    except Exception as e:
        logger.error(f"❌ 查找记录异常: {e}", exc_info=True)
        return None


# ==================== 多维表字段ID动态获取 ====================
# 字段ID缓存（字段名 -> field_id）
_field_id_cache = {}
_field_id_cache_time = None
_field_id_cache_ttl = 3600  # 缓存1小时


def get_bitable_fields(force_refresh: bool = False) -> Dict[str, str]:
    """
    获取多维表所有字段列表（从飞书API动态获取）

    参数:
        force_refresh: 是否强制刷新缓存

    返回:
        字典 {字段名: field_id}
    """
    global _field_id_cache, _field_id_cache_time

    # 检查缓存
    current_time = time.time()
    if not force_refresh and _field_id_cache is not None:
        if _field_id_cache_time and (current_time - _field_id_cache_time) < _field_id_cache_ttl:
            logger.info(f"📌 使用字段ID缓存 | 共 {len(_field_id_cache)} 个字段")
            return _field_id_cache

    try:
        # 获取 tenant_access_token
        tenant_token = get_tenant_access_token()
        if not tenant_token:
            logger.error("❌ 获取 tenant_access_token 失败")
            return {}

        # 获取多维表配置
        app_token = os.getenv("FEISHU_BITABLE_APP_TOKEN")
        table_id = os.getenv("FEISHU_BITABLE_TABLE_ID")

        if not app_token or not table_id:
            logger.error("❌ 缺少多维表配置（FEISHU_BITABLE_APP_TOKEN 或 FEISHU_BITABLE_TABLE_ID）")
            return {}

        # 调用飞书API列出所有字段
        url = f"{FEISHU_BASE_API_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields"

        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }

        logger.info(f"📌 调用飞书API获取字段列表 | URL: {url}")
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            logger.error(f"❌ 获取字段列表失败 | 状态码: {response.status_code} | 响应: {response.text[:300]}")
            return _field_id_cache or {}  # 返回缓存（如果有）

        data = response.json()

        # 检查API返回码
        if data.get("code") != 0:
            error_msg = data.get("msg", "未知错误")
            logger.error(f"❌ API返回错误 | code: {data.get('code')} | msg: {error_msg}")
            return _field_id_cache or {}

        # 解析字段列表
        field_items = data.get("data", {}).get("items", [])

        if not field_items:
            logger.warning(f"⚠️  字段列表为空")
            return {}

        # 构建字段名 -> field_id 映射
        field_map = {}
        for field in field_items:
            field_name = field.get("field_name", "")
            field_id = field.get("field_id", "")
            if field_name and field_id:
                field_map[field_name] = field_id

        # 更新缓存
        _field_id_cache = field_map
        _field_id_cache_time = current_time

        logger.info(f"✅ 获取字段列表成功 | 共 {len(field_map)} 个字段")
        logger.info(f"📌 字段映射: {json.dumps(field_map, ensure_ascii=False)}")

        return field_map

    except Exception as e:
        logger.error(f"❌ 获取字段列表异常: {e}", exc_info=True)
        # 返回缓存（如果有）
        return _field_id_cache or {}


def get_field_id(field_name: str) -> str:
    """
    获取多维表字段的 field_id（从飞书API动态获取）

    参数:
        field_name: 字段名称（如 "系统合同 ID"、"合同名称"）

    返回:
        field_id（如 "field_xxxxx"）或原字段名称（如果未找到）
    """
    # 获取所有字段映射
    field_map = get_bitable_fields()

    # 查找对应字段ID
    field_id = field_map.get(field_name)

    if field_id:
        return field_id
    else:
        # 未找到字段，记录警告并返回原字段名
        logger.warning(f"⚠️  未找到字段ID | 字段名: {field_name} | 可用字段: {list(field_map.keys())}")
        return field_name


# ==================== 多维表更新函数 ====================
def update_feishu_bitable_record(record_id: str, update_data: dict) -> bool:
    """
    更新飞书多维表记录

    参数:
        record_id: 飞书多维表记录ID
        update_data: 要更新的字段字典 {"字段名": "字段值"}

    返回:
        bool: 更新是否成功
    """
    try:
        # 获取 tenant_access_token
        tenant_token = get_tenant_access_token()
        if not tenant_token:
            logger.error("❌ 获取 tenant_access_token 失败")
            return False

        # 构造更新请求
        app_token = os.getenv("FEISHU_BITABLE_APP_TOKEN")
        table_id = os.getenv("FEISHU_BITABLE_TABLE_ID")

        if not app_token or not table_id:
            logger.error("❌ 缺少多维表配置（FEISHU_BITABLE_APP_TOKEN 或 FEISHU_BITABLE_TABLE_ID）")
            return False

        url = f"{FEISHU_BASE_API_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"

        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }

        # 构造请求体（直接使用字段名）
        # 注意：飞书API更新记录时使用字段名作为key，而不是字段ID
        fields = {}
        for field_name, field_value in update_data.items():
            # 验证字段名是否存在于多维表中
            field_map = get_bitable_fields()
            if field_name in field_map:
                fields[field_name] = field_value
                logger.info(f"📌 字段验证通过 | {field_name} -> 字段ID: {field_map[field_name]}")
            else:
                logger.warning(f"⚠️  字段名不存在于多维表 | 字段名: {field_name}")
                # 仍然尝试使用该字段名，让API返回具体错误
                fields[field_name] = field_value

        request_body = {
            "fields": fields
        }

        logger.info(f"📌 更新多维表记录 | record_id: {record_id}")
        logger.info(f"📌 更新字段: {list(fields.keys())}")
        logger.info(f"📌 请求数据: {json.dumps(request_body, ensure_ascii=False)[:800]}...")

        response = requests.put(url, headers=headers, json=request_body, timeout=30)

        # 详细的响应日志
        logger.info(f"📌 响应状态码: {response.status_code}")
        logger.info(f"📌 响应头: {dict(response.headers)}")
        logger.info(f"📌 响应内容: {response.text[:800]}...")

        if response.status_code == 200:
            try:
                response_data = response.json()
                logger.info(f"✅ 更新多维表记录成功 | record_id: {record_id}")
                logger.info(f"📌 完整响应: {json.dumps(response_data, ensure_ascii=False)}")

                # 检查是否有错误信息
                if response_data.get("code") != 0:
                    error_msg = response_data.get("msg", "未知错误")
                    logger.error(f"❌ API返回错误 | code: {response_data.get('code')} | msg: {error_msg}")
                    return False

                return True
            except Exception as e:
                logger.warning(f"⚠️  解析响应JSON失败: {e}")
                return True
        else:
            logger.error(f"❌ 更新多维表记录失败 | 状态码: {response.status_code} | 响应: {response.text[:500]}")
            return False

    except Exception as e:
        logger.error(f"❌ 更新多维表记录异常: {e}", exc_info=True)
        return False
# ==================== 飞书文件上传 ====================
def upload_file_to_feishu(file_path: str) -> Optional[str]:
    """
    上传本地文件到飞书云空间（用于回写多维表附件）

    参数:
        file_path: 本地文件路径

    返回:
        file_token: 飞书文件标识（可直接用于多维表附件字段），失败返回 None

    文档:
        https://open.feishu.cn/document/server-docs/docs/drive/v1/media/upload_all
    """
    try:
        # 1. 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"❌ 上传文件不存在: {file_path}")
            return None

        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        # 2. 获取 token
        tenant_token = get_tenant_access_token()
        if not tenant_token:
            logger.error("❌ 获取 tenant_access_token 失败")
            return None

        # 3. 准备上传请求
        # 使用 drive/v1/files/upload_all 接口（上传到云空间根目录，不挂载父节点）
        # 注意：多维表附件需要的是云空间的文件 token
        url = f"{FEISHU_BASE_API_URL}/drive/v1/files/upload_all"
        
        headers = {
            "Authorization": f"Bearer {tenant_token}"
            # 注意：requests 处理 multipart/form-data 时不需要手动设置 Content-Type
        }
        
        # 构造 multipart/form-data
        data = {
            "file_name": file_name,
            "parent_type": "explorer", # 上传到云空间根目录
            "parent_node": "",         # 根目录为空
            "size": str(file_size)
        }
        
        logger.info(f"📤 开始上传文件到飞书 | 文件: {file_name} | 大小: {file_size} bytes")
        
        with open(file_path, "rb") as f:
            files = {
                "file": (file_name, f)
            }
            
            response = requests.post(url, headers=headers, data=data, files=files, timeout=120)

        # 4. 处理响应
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("code") == 0:
                file_token = res_json.get("data", {}).get("file_token")
                logger.info(f"✅ 文件上传成功 | file_token: {file_token}")
                return file_token
            else:
                logger.error(f"❌ 飞书上传接口业务错误: {res_json}")
                return None
        else:
            logger.error(f"❌ 飞书上传HTTP错误 | 状态码: {response.status_code} | 响应: {response.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"❌ 上传文件异常: {e}", exc_info=True)
        return None

# ==================== 飞书卡片消息函数 ====================
def get_user_open_id_by_name(user_name: str) -> Optional[str]:
    """
    根据用户姓名查找用户的 open_id

    参数:
        user_name: 用户姓名

    返回:
        用户的 open_id，如果未找到则返回 None
    """
    try:
        import requests

        # 获取 tenant_access_token
        tenant_token = get_tenant_access_token()
        if not tenant_token:
            logger.error("❌ 获取 tenant_access_token 失败")
            return None

        # 使用飞书 API 搜索用户
        url = f"{FEISHU_BASE_API_URL}/contact/v3/users/search"

        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }

        request_body = {
            "query": user_name,
            "page_size": 10
        }

        response = requests.post(url, json=request_body, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            user_list = data.get("data", {}).get("user_list", [])

            if user_list:
                # 查找完全匹配的用户
                for user in user_list:
                    if user.get("name") == user_name:
                        open_id = user.get("open_id")
                        logger.info(f"✅ 根据姓名找到用户 open_id | 姓名: {user_name} -> open_id: {open_id}")
                        return open_id

                logger.warning(f"⚠️  未找到完全匹配的用户 | 姓名搜索: {user_name}")
                return None
            else:
                logger.warning(f"⚠️  搜索用户结果为空 | 姓名搜索: {user_name}")
                return None
        else:
            logger.error(f"❌ 搜索用户失败 | 状态码: {response.status_code} | 响应: {response.text[:200]}")
            return None

    except Exception as e:
        logger.error(f"❌ 搜索用户异常: {e}")
        return None


def send_feishu_text_message(user_open_id: str, text_content: str) -> bool:
    """
    发送飞书文本消息

    参数:
        user_open_id: 用户 OPEN_ID 或 UNION_ID
        text_content: 文本内容（支持 Markdown 格式）

    返回:
        bool: 发送是否成功
    """
    try:
        # 获取 tenant_access_token
        tenant_token = get_tenant_access_token()
        if not tenant_token:
            logger.error("❌ 获取 tenant_access_token 失败")
            return False

        # 判断 ID 类型并设置对应的 receive_id_type
        if user_open_id.startswith("ou_"):
            receive_id_type = "open_id"
        elif user_open_id.startswith("on_"):
            receive_id_type = "union_id"
        else:
            logger.error(f"❌ 无效的用户 ID 格式: {user_open_id}（应以 ou_ 或 on_ 开头）")
            return False

        # 构造发送消息请求
        url = f"{FEISHU_BASE_API_URL}/im/v1/messages?receive_id_type={receive_id_type}"

        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }

        logger.info(f"📌 发送飞书文本消息 | user_open_id: {user_open_id[:20]}... | type: {receive_id_type}")

        # 构造文本消息（使用 text 类型，支持 lark_md）
        request_body = {
            "msg_type": "text",
            "receive_id": user_open_id,
            "content": json.dumps({"text": text_content}, ensure_ascii=False)
        }

        logger.info(f"📌 请求 URL: {url}")
        logger.debug(f"🔍 [DEBUG] 请求体 (前500字符): {json.dumps(request_body, ensure_ascii=False)[:500]}...")

        response = requests.post(url, headers=headers, json=request_body, timeout=30)

        logger.info(f"📌 响应状态码: {response.status_code}")
        logger.info(f"📌 响应内容: {response.text}")

        if response.status_code != 200:
            logger.error(f"❌ HTTP 状态码非 200 | 状态码: {response.status_code}")
            return False

        try:
            response_data = response.json()
            feishu_code = response_data.get("code", -1)

            if feishu_code == 0:
                logger.info(f"✅ 飞书文本消息发送成功 | user_open_id: {user_open_id[:20]}...")
                return True
            else:
                feishu_msg = response_data.get("msg", "未知错误")
                logger.error(f"❌ 飞书 API 返回错误 | code: {feishu_code} | msg: {feishu_msg}")
                return False

        except Exception as e:
            logger.error(f"❌ 解析响应 JSON 失败: {e} | 原始响应: {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"❌ 发送飞书文本消息异常: {e}", exc_info=True)
        return False


def send_feishu_quick_reply_message(
    user_open_id: str,
    text_content: str,
    quick_buttons: list
) -> bool:
    """
    发送飞书快捷回复消息（文本消息 + 快捷按钮）

    这种方式使用 post 类型的消息，配合 element 元素，可以通过事件订阅接收回调
    不需要配置"卡片能力"

    参数:
        user_open_id: 用户 OPEN_ID 或 UNION_ID
        text_content: 文本内容
        quick_buttons: 快捷按钮列表，每个按钮格式：
            {
                "text": "按钮文本",
                "value": {"key": "value"}  # 回调数据
            }

    返回:
        bool: 发送是否成功
    """
    try:
        # 获取 tenant_access_token
        tenant_token = get_tenant_access_token()
        if not tenant_token:
            logger.error("❌ 获取 tenant_access_token 失败")
            return False

        # 判断 ID 类型并设置对应的 receive_id_type
        if user_open_id.startswith("ou_"):
            receive_id_type = "open_id"
        elif user_open_id.startswith("on_"):
            receive_id_type = "union_id"
        else:
            logger.error(f"❌ 无效的用户 ID 格式: {user_open_id}（应以 ou_ 或 on_ 开头）")
            return False

        # 构造发送消息请求
        url = f"{FEISHU_BASE_API_URL}/im/v1/messages?receive_id_type={receive_id_type}"

        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }

        logger.info(f"📌 发送飞书快捷回复消息 | user_open_id: {user_open_id[:20]}... | type: {receive_id_type}")

        # 构造 post 类型消息（带 element 元素）
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": text_content
                }
            }
        ]

        # 添加快捷回复按钮
        if quick_buttons:
            quick_actions = []
            for btn in quick_buttons:
                quick_actions.append({
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": btn["text"]
                    },
                    "value": btn["value"],
                    "type": "primary" if quick_actions.index(btn) == 0 else "default"
                })

            elements.append({
                "tag": "action",
                "actions": quick_actions
            })

        request_body = {
            "msg_type": "interactive",
            "receive_id": user_open_id,
            "content": json.dumps({
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📋 合同审查 - 立场确认"
                    },
                    "template": "blue"
                },
                "elements": elements
            }, ensure_ascii=False)
        }

        logger.info(f"📌 请求 URL: {url}")
        logger.debug(f"🔍 [DEBUG] 请求体 (前500字符): {json.dumps(request_body, ensure_ascii=False)[:500]}...")

        response = requests.post(url, headers=headers, json=request_body, timeout=30)

        logger.info(f"📌 响应状态码: {response.status_code}")
        logger.info(f"📌 响应内容: {response.text}")

        if response.status_code != 200:
            logger.error(f"❌ HTTP 状态码非 200 | 状态码: {response.status_code}")
            return False

        try:
            response_data = response.json()
            feishu_code = response_data.get("code", -1)

            if feishu_code == 0:
                logger.info(f"✅ 飞书快捷回复消息发送成功 | user_open_id: {user_open_id[:20]}...")
                return True
            else:
                feishu_msg = response_data.get("msg", "未知错误")
                logger.error(f"❌ 飞书 API 返回错误 | code: {feishu_code} | msg: {feishu_msg}")
                return False

        except Exception as e:
            logger.error(f"❌ 解析响应 JSON 失败: {e} | 原始响应: {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"❌ 发送飞书快捷回复消息异常: {e}", exc_info=True)
        return False


def send_feishu_card_message(user_open_id: str, card_content: dict) -> bool:
    """
    发送飞书卡片消息

    参数:
        user_open_id: 接收用户的 open_id
        card_content: 卡片内容（飞书卡片JSON格式）

    返回:
        bool: 发送是否成功
    """
    try:
        # 获取 tenant_access_token
        tenant_token = get_tenant_access_token()
        if not tenant_token:
            logger.error("❌ 获取 tenant_access_token 失败")
            return False

        # 判断 ID 类型并设置对应的 receive_id_type
        if user_open_id.startswith("ou_"):
            receive_id_type = "open_id"
        elif user_open_id.startswith("on_"):
            receive_id_type = "union_id"
        else:
            logger.error(f"❌ 无效的用户 ID 格式: {user_open_id}（应以 ou_ 或 on_ 开头）")
            return False

        # 构造发送消息请求
        # 使用飞书官方文档的 API 路径：/im/v1/messages
        # receive_id_type 需要作为查询参数传递
        url = f"{FEISHU_BASE_API_URL}/im/v1/messages?receive_id_type={receive_id_type}"

        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }

        logger.info(f"📌 发送飞书卡片消息 | user_open_id: {user_open_id[:20]}... | type: {receive_id_type}")
        logger.info(f"📌 请求 URL: {url}")
        logger.info(f"📌 请求体结构: msg_type=interactive, receive_id={user_open_id[:20]}...")

        request_body = {
            "msg_type": "interactive",
            "receive_id": user_open_id,
            "content": json.dumps(card_content, ensure_ascii=False)  # 卡片内容需要是 JSON 字符串
        }

        # 🔍 调试日志：打印完整请求体（敏感信息脱敏）
        logger.debug(f"🔍 [DEBUG] 完整请求体字典: {json.dumps(request_body, ensure_ascii=False)[:1000]}...")

        # 使用 requests 的 json 参数（推荐方式）
        # requests 会自动处理 Content-Type 头和 JSON 序列化
        response = requests.post(url, headers=headers, json=request_body, timeout=30)

        # 🔍 调试日志：打印实际发送的 JSON（敏感信息脱敏）
        actual_sent = json.dumps(request_body, ensure_ascii=False)
        logger.debug(f"🔍 [DEBUG] 实际发送的 JSON 长度: {len(actual_sent)} 字符")
        logger.debug(f"🔍 [DEBUG] 实际发送的 JSON (前500字符): {actual_sent[:500]}...")

        logger.info(f"📌 响应状态码: {response.status_code}")
        logger.info(f"📌 响应内容: {response.text}")  # 记录完整响应内容

        # 检查 HTTP 状态码
        if response.status_code != 200:
            logger.error(f"❌ HTTP 状态码非 200 | 状态码: {response.status_code}")
            return False

        # 解析响应 JSON 并检查 Feishu API 的 code 字段
        try:
            response_data = response.json()
            feishu_code = response_data.get("code", -1)

            if feishu_code == 0:
                logger.info(f"✅ 飞书卡片消息发送成功 | user_open_id: {user_open_id[:20]}...")
                return True
            else:
                feishu_msg = response_data.get("msg", "未知错误")
                logger.error(f"❌ 飞书 API 返回错误 | code: {feishu_code} | msg: {feishu_msg}")
                return False

        except Exception as e:
            logger.error(f"❌ 解析响应 JSON 失败: {e} | 原始响应: {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"❌ 发送飞书卡片消息异常: {e}", exc_info=True)
        return False


# ==================== 模块测试 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("飞书 API 工具测试")
    print("=" * 60)

    try:
        # 测试获取 tenant_access_token
        print("\n[测试] 获取 tenant_access_token...")
        token = get_tenant_access_token()
        print(f"✓ 成功获取 token（长度: {len(token)} 字符）")

        # 测试重复调用（应使用缓存）
        print("\n[测试] 重复获取 token（应使用缓存）...")
        token2 = get_tenant_access_token()
        if token == token2:
            print("✓ 复用缓存 token")

        # 测试 API 请求（需要配置多维表信息）
        print("\n[测试] API 请求（需要配置多维表信息）")
        print("提示：请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 后测试")
        print("可测试接口：")
        print("  - get_base_table_data(app_token, table_id)")
        print("  - send_feishu_text_msg(user_id, content)")

        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
