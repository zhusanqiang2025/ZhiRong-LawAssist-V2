# backend/app/api/v1/endpoints/system.py
"""
系统管理 API 端点

提供系统级别的管理功能，包括：
- 管理员用户状态检查
- 确保管理员用户权限
"""
import os
import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin-status")
def check_admin_status() -> Any:
    """
    检查管理员用户状态

    返回环境变量中配置的默认管理员用户的当前权限状态。
    此端点不需要认证，用于诊断管理员权限问题。

    Returns:
        {
            "admin_email": str,           # 管理员邮箱
            "user_exists": bool,          # 用户是否存在
            "is_admin": bool,             # 是否是管理员
            "is_superuser": bool,         # 是否是超级用户
            "is_correct": bool            # 权限是否正确
        }
    """
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL") or os.getenv("SEED_ADMIN_EMAIL")

    if not admin_email:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="管理员邮箱未配置（DEFAULT_ADMIN_EMAIL 或 SEED_ADMIN_EMAIL）"
        )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == admin_email).first()

        if not user:
            return {
                "admin_email": admin_email,
                "user_exists": False,
                "is_admin": False,
                "is_superuser": False,
                "is_correct": False,
                "message": f"用户 {admin_email} 不存在于数据库中"
            }

        is_correct = user.is_admin and user.is_superuser

        return {
            "admin_email": admin_email,
            "user_exists": True,
            "is_admin": user.is_admin,
            "is_superuser": user.is_superuser,
            "is_correct": is_correct,
            "message": (
                f"用户 {admin_email} {'权限正确' if is_correct else '权限不足，需要提升'}"
            )
        }
    finally:
        db.close()


@router.post("/ensure-admin")
def ensure_admin_user() -> Any:
    """
    确保管理员用户具有正确权限

    检查环境变量中配置的默认管理员用户，如果该用户存在但不是管理员，
    则将其提升为管理员（is_admin=True, is_superuser=True）。

    此操作是幂等的，可以安全地重复执行。

    Returns:
        {
            "status": str,              # "already_correct", "promoted", "user_not_found", "error"
            "admin_email": str,         # 管理员邮箱
            "message": str              # 详细信息
        }
    """
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL") or os.getenv("SEED_ADMIN_EMAIL")

    if not admin_email:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="管理员邮箱未配置（DEFAULT_ADMIN_EMAIL 或 SEED_ADMIN_EMAIL）"
        )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == admin_email).first()

        if not user:
            logger.warning(f"[System] Admin user not found: {admin_email}")
            return {
                "status": "user_not_found",
                "admin_email": admin_email,
                "message": f"用户 {admin_email} 不存在于数据库中，无法提升权限"
            }

        # 检查当前权限
        if user.is_admin and user.is_superuser:
            logger.info(f"[System] Admin user already has correct privileges: {admin_email}")
            return {
                "status": "already_correct",
                "admin_email": admin_email,
                "message": f"用户 {admin_email} 已经具有正确的管理员权限",
                "is_admin": True,
                "is_superuser": True
            }

        # 提升权限
        was_admin = user.is_admin
        was_superuser = user.is_superuser

        user.is_admin = True
        user.is_superuser = True
        db.commit()

        logger.info(
            f"[System] ✓ Promoted user to admin: {admin_email} "
            f"(is_admin: {was_admin} -> True, is_superuser: {was_superuser} -> True)"
        )

        return {
            "status": "promoted",
            "admin_email": admin_email,
            "message": f"成功将用户 {admin_email} 提升为管理员",
            "is_admin": True,
            "is_superuser": True,
            "previous_is_admin": was_admin,
            "previous_is_superuser": was_superuser
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[System] Failed to ensure admin user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提升管理员权限失败: {str(e)}"
        )
    finally:
        db.close()


@router.post("/auto-ensure-admin")
def auto_ensure_admin() -> Any:
    """
    自动确保管理员权限（由应用启动事件调用）

    此端点专为 FastAPI 启动事件调用设计，静默执行，不会抛出异常。
    如果操作失败，仅记录日志而不中断应用启动。

    Returns:
        {
            "executed": bool,           # 是否执行了权限提升
            "status": str,              # 执行结果状态
            "message": str              # 详细信息
        }
    """
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL") or os.getenv("SEED_ADMIN_EMAIL")

    if not admin_email:
        logger.warning("[System] Admin email not configured, skipping auto-ensure")
        return {
            "executed": False,
            "status": "skipped",
            "message": "管理员邮箱未配置"
        }

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == admin_email).first()

        if not user:
            logger.warning(f"[System] Admin user not found during startup: {admin_email}")
            return {
                "executed": False,
                "status": "user_not_found",
                "message": f"用户 {admin_email} 不存在"
            }

        if user.is_admin and user.is_superuser:
            logger.info(f"[System] Admin user privileges verified: {admin_email}")
            return {
                "executed": True,
                "status": "already_correct",
                "message": f"用户 {admin_email} 权限正确"
            }

        # 提升权限
        user.is_admin = True
        user.is_superuser = True
        db.commit()

        logger.info(f"[System] ✓ Auto-promoted user to admin: {admin_email}")
        return {
            "executed": True,
            "status": "promoted",
            "message": f"自动提升用户 {admin_email} 为管理员"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[System] Auto-ensure admin failed: {e}", exc_info=True)
        return {
            "executed": True,
            "status": "error",
            "message": f"自动提升失败: {str(e)}"
        }
    finally:
        db.close()
