# backend/app/core/security.py (清洁版 v1.3 - 统一Schemas修复)
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import schemas # <-- 核心修改：导入统一的schemas模块
from app.database import SessionLocal
from app.core.config import settings
# 移除了 app.crud.user 的导入以避免循环导入

logger = logging.getLogger(__name__)

# SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login/token")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> schemas.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        # <-- 核心修改：使用 schemas.TokenPayload
        token_data = schemas.TokenPayload(sub=username)
    except JWTError:
        raise credentials_exception
    
    # 将用户查询逻辑移到这里以避免循环导入
    from app.models.user import User
    db_user = db.query(User).filter(User.email == (token_data.sub or "")).first()
    if db_user is None:
        raise credentials_exception
    
    # <-- 核心修改：使用 schemas.User
    return schemas.User.model_validate(db_user)


async def get_current_user_websocket(token: str) -> Optional[schemas.User]:
    """
    WebSocket认证：验证JWT token并返回用户信息

    Args:
        token: JWT token字符串

    Returns:
        用户对象或None
    """
    try:
        # 记录 token 信息（前 20 位）
        token_preview = token[:20] + "..." if len(token) > 20 else token
        logger.info(f"[WS Auth] 开始验证 token: '{token_preview}', 长度: {len(token)}")

        # 解析token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")

        if username is None:
            logger.error(f"[WS Auth] Token payload 中没有 'sub' 字段, payload keys: {list(payload.keys())}")
            return None

        logger.info(f"[WS Auth] Token 解析成功, 用户: {username}")
        token_data = schemas.TokenPayload(sub=username)

    except JWTError as e:
        logger.error(f"[WS Auth] JWT 解码失败: {type(e).__name__}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"[WS Auth] Token 解析异常: {type(e).__name__}: {str(e)}", exc_info=True)
        return None

    # 查询用户
    try:
        from app.models.user import User
        from app.database import SessionLocal

        # 使用上下文管理器确保数据库连接正确关闭
        db = SessionLocal()
        try:
            logger.info(f"[WS Auth] 查询数据库用户: {token_data.sub}")
            db_user = db.query(User).filter(User.email == (token_data.sub or "")).first()
            if db_user is None:
                logger.error(f"[WS Auth] 用户不存在: {token_data.sub}")
                return None
            logger.info(f"[WS Auth] 用户验证成功: {db_user.email}")
            return schemas.User.model_validate(db_user)
        finally:
            db.close()

    except Exception as e:
        logger.error(f"[WS Auth] 数据库查询错误: {type(e).__name__}: {str(e)}", exc_info=True)
        return None