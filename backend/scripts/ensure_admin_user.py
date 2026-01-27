#!/usr/bin/env python3
# backend/scripts/ensure_admin_user.py
"""
确保管理员用户具有正确权限

独立脚本，可以直接运行以确保管理员用户具有正确的权限。
此脚本可以在 K8s init container 中执行，或通过 SSH 登录服务器后手动执行。

使用方法：
    # 方法 1: 直接运行（从项目根目录）
    python backend/scripts/ensure_admin_user.py

    # 方法 2: 作为模块运行
    python -m backend.scripts.ensure_admin_user

    # 方法 3: 在 Docker 容器中运行
    docker exec <container_name> python backend/scripts/ensure_admin_user.py

环境变量（需要设置以下之一）：
    DEFAULT_ADMIN_EMAIL - 默认管理员邮箱
    DEFAULT_ADMIN_PASSWORD - 默认管理员密码（可选，仅用于创建新用户时）
    SEED_ADMIN_EMAIL - 种子数据管理员邮箱
    SEED_ADMIN_PASSWORD - 种子数据管理员密码（可选）

幂等性：
    此脚本可以安全地重复执行。如果用户已经是管理员，则不会做任何更改。
"""
import os
import sys
import logging

# 添加项目根目录到 Python 路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from app.models.user import User
from app.core.database import SessionLocal

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_admin_credentials():
    """
    从环境变量中获取管理员凭证

    Returns:
        tuple: (email, password) 或 (None, None)
    """
    email = os.getenv("DEFAULT_ADMIN_EMAIL") or os.getenv("SEED_ADMIN_EMAIL")
    password = os.getenv("DEFAULT_ADMIN_PASSWORD") or os.getenv("SEED_ADMIN_PASSWORD")

    if not email:
        logger.error("未找到环境变量 DEFAULT_ADMIN_EMAIL 或 SEED_ADMIN_EMAIL")
        return None, None

    return email, password


def check_admin_status(db: Session, email: str) -> dict:
    """
    检查管理员用户状态

    Args:
        db: 数据库会话
        email: 管理员邮箱

    Returns:
        dict: 包含用户状态信息的字典
    """
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return {
            "exists": False,
            "is_admin": False,
            "is_superuser": False,
            "is_correct": False
        }

    return {
        "exists": True,
        "is_admin": user.is_admin,
        "is_superuser": user.is_superuser,
        "is_correct": user.is_admin and user.is_superuser
    }


def ensure_admin_user(db: Session = None) -> dict:
    """
    确保管理员用户具有正确权限

    Args:
        db: 数据库会话（可选，如果不提供则创建新的）

    Returns:
        dict: 操作结果
    """
    should_close_db = db is None
    if db is None:
        db = SessionLocal()

    try:
        # 获取管理员凭证
        admin_email, admin_password = get_admin_credentials()

        if not admin_email:
            return {
                "success": False,
                "status": "no_credentials",
                "message": "未配置管理员邮箱环境变量"
            }

        # 检查用户状态
        status = check_admin_status(db, admin_email)

        if not status["exists"]:
            logger.warning(f"管理员用户不存在: {admin_email}")
            return {
                "success": False,
                "status": "user_not_found",
                "email": admin_email,
                "message": f"用户 {admin_email} 不存在于数据库中"
            }

        if status["is_correct"]:
            logger.info(f"✓ 管理员用户权限正确: {admin_email}")
            return {
                "success": True,
                "status": "already_correct",
                "email": admin_email,
                "message": f"用户 {admin_email} 已经具有正确的管理员权限"
            }

        # 提升为管理员
        user = db.query(User).filter(User.email == admin_email).first()
        was_admin = user.is_admin
        was_superuser = user.is_superuser

        user.is_admin = True
        user.is_superuser = True
        db.commit()
        db.refresh(user)

        logger.info(
            f"✓ 成功提升用户为管理员: {admin_email} "
            f"(is_admin: {was_admin} -> True, is_superuser: {was_superuser} -> True)"
        )

        return {
            "success": True,
            "status": "promoted",
            "email": admin_email,
            "message": f"成功将用户 {admin_email} 提升为管理员",
            "previous_is_admin": was_admin,
            "previous_is_superuser": was_superuser,
            "current_is_admin": user.is_admin,
            "current_is_superuser": user.is_superuser
        }

    except Exception as e:
        db.rollback()
        logger.error(f"提升管理员权限失败: {e}", exc_info=True)
        return {
            "success": False,
            "status": "error",
            "message": f"操作失败: {str(e)}"
        }
    finally:
        if should_close_db:
            db.close()


def main():
    """
    主函数：执行管理员权限确保操作并打印结果
    """
    print("=" * 60)
    print("管理员权限确保脚本")
    print("=" * 60)

    # 显示当前配置
    admin_email, _ = get_admin_credentials()
    if admin_email:
        print(f"目标管理员邮箱: {admin_email}")
    else:
        print("⚠️  未配置管理员邮箱环境变量")
        print("请设置 DEFAULT_ADMIN_EMAIL 或 SEED_ADMIN_EMAIL")
        return 1

    print()

    # 执行操作
    result = ensure_admin_user()

    # 显示结果
    print("-" * 60)
    print(f"状态: {result.get('status', 'unknown')}")
    print(f"消息: {result.get('message', 'N/A')}")

    if result.get('status') == 'promoted':
        print(f"之前权限: is_admin={result.get('previous_is_admin')}, is_superuser={result.get('previous_is_superuser')}")
        print(f"当前权限: is_admin={result.get('current_is_admin')}, is_superuser={result.get('current_is_superuser')}")

    print("=" * 60)

    return 0 if result.get('success') else 1


if __name__ == "__main__":
    sys.exit(main())
