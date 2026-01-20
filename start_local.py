#!/usr/bin/env python3
"""
Legal Document Assistant - Local Startup Script
启动脚本 - 本地Python模式
"""

import os
import sys
import subprocess
import platform
import time
from pathlib import Path

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    print(f"Python版本: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ 错误: 需要Python 3.10或更高版本")
        print(f"请从 https://python.org 下载并安装Python 3.10+")
        return False

    print("✅ Python版本检查通过")
    return True

def check_dependencies():
    """检查依赖管理工具"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"],
                      check=True, capture_output=True)
        print("✅ pip检查通过")
        return True
    except subprocess.CalledProcessError:
        print("❌ pip未找到")
        return False

def install_backend_deps():
    """安装后端依赖"""
    backend_dir = Path(__file__).parent / "backend"
    requirements_file = backend_dir / "requirements.txt"

    if not requirements_file.exists():
        print(f"❌ 未找到requirements.txt文件: {requirements_file}")
        return False

    print("📦 正在安装后端依赖...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ], cwd=backend_dir, check=True, capture_output=True, text=True)
        print("✅ 后端依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 后端依赖安装失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def install_frontend_deps():
    """安装前端依赖"""
    frontend_dir = Path(__file__).parent / "frontend"

    # 检查npm
    try:
        subprocess.run(["npm", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ 未找到npm，请安装Node.js: https://nodejs.org")
        return False

    print("📦 正在安装前端依赖...")
    try:
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
        print("✅ 前端依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 前端依赖安装失败: {e}")
        return False

def start_backend():
    """启动后端服务"""
    backend_dir = Path(__file__).parent / "backend"
    print("🚀 正在启动后端服务...")

    if platform.system() == "Windows":
        cmd = ["start", "cmd", "/k",
               f"cd /d {backend_dir} && {sys.executable} -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
        subprocess.Popen(cmd, shell=True)
    else:
        cmd = [sys.executable, "-m", "uvicorn", "app.main:app",
               "--host", "0.0.0.0", "--port", "8000", "--reload"]
        subprocess.Popen(cmd, cwd=backend_dir)

    print("✅ 后端服务已启动 (http://localhost:8000)")
    return True

def start_frontend():
    """启动前端服务"""
    frontend_dir = Path(__file__).parent / "frontend"
    print("🚀 正在启动前端服务...")

    if platform.system() == "Windows":
        cmd = ["start", "cmd", "/k", f"cd /d {frontend_dir} && npm run dev"]
        subprocess.Popen(cmd, shell=True)
    else:
        cmd = ["npm", "run", "dev"]
        subprocess.Popen(cmd, cwd=frontend_dir)

    print("✅ 前端服务已启动 (通常是 http://localhost:5173)")
    return True

def main():
    """主函数"""
    print("=" * 60)
    print("🎯 Legal Document Assistant - 本地启动模式")
    print("=" * 60)
    print()

    # 检查环境
    if not check_python_version():
        input("按回车键退出...")
        return 1

    if not check_dependencies():
        input("按回车键退出...")
        return 1

    # 安装依赖
    print("\n📋 第1步: 安装依赖")
    print("-" * 30)

    if not install_backend_deps():
        input("按回车键退出...")
        return 1

    if not install_frontend_deps():
        input("按回车键退出...")
        return 1

    # 启动服务
    print("\n🚀 第2步: 启动服务")
    print("-" * 30)

    start_backend()
    time.sleep(3)  # 等待后端启动

    start_frontend()
    time.sleep(3)  # 等待前端启动

    # 显示访问信息
    print("\n" + "=" * 60)
    print("🎉 Legal Document Assistant 已启动!")
    print("=" * 60)
    print("📱 前端地址: http://localhost:5173 (或类似端口)")
    print("🔧 后端API: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("=" * 60)
    print()
    print("💡 提示:")
    print("   - 服务启动可能需要1-2分钟")
    print("   - 如遇到端口冲突，请检查是否有其他服务占用8000或5173端口")
    print("   - 按Ctrl+C可停止服务")
    print()
    input("按回车键退出此启动器...")

    return 0

if __name__ == "__main__":
    sys.exit(main())