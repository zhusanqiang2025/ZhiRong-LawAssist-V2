"""
修复管理员权限脚本

用法:
    python backend/fix_admin_permission.py

此脚本会将 DEFAULT_ADMIN_EMAIL 指定的用户设置为管理员
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.core.config import settings


def fix_admin_permission():
    """修复管理员权限"""
    db: Session = SessionLocal()
    try:
        # 从环境变量读取管理员邮箱
        admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "zhusanqiang@az028.cn")

        # 查找用户
        user = db.query(User).filter(User.email == admin_email).first()

        if not user:
            print(f"错误: 找不到用户 {admin_email}")
            print(f"请确保用户已存在或检查 DEFAULT_ADMIN_EMAIL 环境变量")
            return False

        # 检查当前权限
        print(f"用户邮箱: {user.email}")
        print(f"当前 is_admin: {user.is_admin}")
        print(f"当前 is_superuser: {user.is_superuser}")
        print(f"当前 is_active: {user.is_active}")

        # 更新权限
        user.is_admin = True
        user.is_superuser = True
        user.is_active = True

        db.commit()
        db.refresh(user)

        print("\n✓ 管理员权限已更新:")
        print(f"  is_admin: {user.is_admin}")
        print(f"  is_superuser: {user.is_superuser}")
        print(f"  is_active: {user.is_active}")
        print(f"\n现在可以使用 {admin_email} 登录了")

        return True

    except Exception as e:
        print(f"错误: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("管理员权限修复脚本")
    print("=" * 60)
    fix_admin_permission()
