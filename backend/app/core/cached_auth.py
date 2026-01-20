# backend/app/core/cached_auth.py
"""
带缓存的认证模块 - 优化用户查询性能
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from .security import oauth2_scheme, SECRET_KEY, ALGORITHM
from ..database import get_db
from .. import schemas
from ..services.cache_service import cache_service

# 用户缓存过期时间（秒）
USER_CACHE_TTL = 300  # 5分钟


def get_current_user_cached(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> schemas.User:
    """
    获取当前用户（带缓存优化）

    Args:
        token: JWT token
        db: 数据库会话

    Returns:
        用户信息

    Raises:
        HTTPException: 认证失败时抛出401错误
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 解码JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenPayload(sub=username)
    except JWTError:
        raise credentials_exception

    # 构建缓存键
    cache_key = f"user:{username}:token:{token[-10:]}"

    # 尝试从缓存获取用户信息
    cached_user = cache_service.get(cache_key)
    if cached_user is not None:
        # 反序列化用户对象
        try:
            return schemas.User.model_validate(cached_user)
        except Exception as e:
            # 缓存数据损坏，重新查询
            import logging
            logging.getLogger(__name__).warning(f"Failed to deserialize cached user: {e}")

    # 缓存未命中，从数据库查询
    from ..models.user import User
    db_user = db.query(User).filter(User.email == (token_data.sub or "")).first()

    if db_user is None:
        raise credentials_exception

    # 转换为Schema
    user_schema = schemas.User.model_validate(db_user)

    # 存入缓存
    try:
        cache_service.set(cache_key, user_schema.model_dump(), expire=USER_CACHE_TTL)
    except Exception as e:
        # 缓存失败不影响正常流程
        import logging
        logging.getLogger(__name__).warning(f"Failed to cache user data: {e}")

    return user_schema


async def get_current_user_websocket_cached(token: str) -> Optional[schemas.User]:
    """
    WebSocket认证（带缓存优化）

    Args:
        token: JWT token字符串

    Returns:
        用户对象或None
    """
    try:
        # 解析token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None

        # 构建缓存键
        cache_key = f"user:{username}:token:{token[-10:]}"

        # 尝试从缓存获取
        cached_user = cache_service.get(cache_key)
        if cached_user is not None:
            try:
                return schemas.User.model_validate(cached_user)
            except Exception:
                pass  # 继续从数据库查询

        # 从数据库查询（需要单独的session）
        from ..database import SessionLocal
        from ..models.user import User

        db = SessionLocal()
        try:
            db_user = db.query(User).filter(User.email == username).first()
            if db_user:
                user_schema = schemas.User.model_validate(db_user)
                # 存入缓存
                try:
                    cache_service.set(cache_key, user_schema.model_dump(), expire=USER_CACHE_TTL)
                except Exception:
                    pass
                return user_schema
        finally:
            db.close()

    except JWTError:
        return None

    return None


def invalidate_user_cache(user_email: str) -> None:
    """
    使用户缓存失效（当用户信息更新时调用）

    Args:
        user_email: 用户邮箱
    """
    try:
        # 由于缓存键包含token后缀，我们无法精确删除
        # 这里使用简单的通配符删除（如果Redis支持）
        # 或者设置一个较短的TTL让缓存自然过期
        cache_key = f"user:{user_email}:"
        # 注意：这需要Redis支持键模式匹配删除
        # 实际实现可能需要根据Redis版本调整
        import logging
        logging.getLogger(__name__).info(f"User cache should be invalidated for: {user_email}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to invalidate user cache: {e}")
