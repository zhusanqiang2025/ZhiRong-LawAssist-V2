#!/usr/bin/env python3
# backend/scripts/dev_tools.py
"""
开发和代码质量工具脚本
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd: str, description: str) -> bool:
    """运行命令并显示结果"""
    print(f"\n{'='*50}")
    print(f"执行: {description}")
    print(f"命令: {cmd}")
    print(f"{'='*50}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=False,
            cwd=Path(__file__).parent.parent
        )
        print(f"✅ {description} - 成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - 失败 (退出码: {e.returncode})")
        return False

def format_code():
    """格式化代码"""
    commands = [
        ("black app/ tests/", "使用 Black 格式化代码"),
        ("isort app/ tests/", "使用 isort 整理导入"),
    ]

    success_count = 0
    for cmd, desc in commands:
        if run_command(cmd, desc):
            success_count += 1

    print(f"\n代码格式化完成: {success_count}/{len(commands)} 成功")

def check_types():
    """类型检查"""
    return run_command("mypy app/", "MyPy 类型检查")

def lint_code():
    """代码风格检查"""
    commands = [
        ("flake8 app/", "Flake8 代码风格检查"),
        ("pylint app/", "Pylint 代码质量检查"),
    ]

    success_count = 0
    for cmd, desc in commands:
        if run_command(cmd, desc):
            success_count += 1

    print(f"\n代码风格检查完成: {success_count}/{len(commands)} 成功")

def security_check():
    """安全检查"""
    return run_command("bandit -r app/", "Bandit 安全检查")

def run_tests():
    """运行测试"""
    return run_command("pytest -v --cov=app --cov-report=html", "运行测试套件")

def install_dev_dependencies():
    """安装开发依赖"""
    return run_command(
        "pip install -r requirements.txt && pip install -r requirements-dev.txt",
        "安装开发依赖"
    )

def create_database_indexes():
    """创建数据库索引"""
    cmd = "python -c 'from app.database.indexes import create_database_indexes; create_database_indexes()'"
    return run_command(cmd, "创建数据库索引")

def analyze_database():
    """分析数据库性能"""
    cmd = "python -c 'from app.database.indexes import analyze_database; print(analyze_database())'"
    return run_command(cmd, "分析数据库性能")

def optimize_database():
    """优化数据库"""
    cmd = "python -c 'from app.database.indexes import optimize_database; optimize_database()'"
    return run_command(cmd, "优化数据库")

def check_environment():
    """检查开发环境"""
    print("检查开发环境...")

    checks = [
        ("Python 版本", "python --version"),
        ("pip 版本", "pip --version"),
        ("Black", "black --version"),
        ("isort", "isort --version"),
        ("MyPy", "mypy --version"),
        ("Flake8", "flake8 --version"),
        ("Bandit", "bandit --version"),
        ("Pytest", "pytest --version"),
    ]

    for name, cmd in checks:
        print(f"\n检查 {name}:")
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ {result.stdout.strip()}")
            else:
                print(f"  ❌ 未安装或不可用")
        except Exception as e:
            print(f"  ❌ 错误: {e}")

def setup_git_hooks():
    """设置 Git hooks"""
    hooks_dir = Path(".git/hooks")
    if not hooks_dir.exists():
        print("❌ 这不是一个 Git 仓库")
        return False

    # pre-commit hook
    pre_commit_content = """#!/bin/sh
# Pre-commit hook
echo "运行预提交检查..."

# 格式化代码
echo "格式化代码..."
black app/ tests/ || exit 1
isort app/ tests/ || exit 1

# 类型检查
echo "类型检查..."
mypy app/ || exit 1

# 代码风格检查
echo "代码风格检查..."
flake8 app/ || exit 1

# 安全检查
echo "安全检查..."
bandit -r app/ || exit 1

echo "✅ 所有检查通过！"
"""

    pre_commit_file = hooks_dir / "pre-commit"
    with open(pre_commit_file, 'w') as f:
        f.write(pre_commit_content)

    # 设置执行权限
    os.chmod(pre_commit_file, 0o755)

    print("✅ Git pre-commit hook 设置完成")
    return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="开发和代码质量工具")
    parser.add_argument(
        "command",
        choices=[
            "format", "check-types", "lint", "security", "test",
            "install", "db-indexes", "db-analyze", "db-optimize",
            "check-env", "setup-hooks", "all-checks", "ci"
        ],
        help="要执行的命令"
    )

    args = parser.parse_args()

    if args.command == "format":
        format_code()
    elif args.command == "check-types":
        check_types()
    elif args.command == "lint":
        lint_code()
    elif args.command == "security":
        security_check()
    elif args.command == "test":
        run_tests()
    elif args.command == "install":
        install_dev_dependencies()
    elif args.command == "db-indexes":
        create_database_indexes()
    elif args.command == "db-analyze":
        analyze_database()
    elif args.command == "db-optimize":
        optimize_database()
    elif args.command == "check-env":
        check_environment()
    elif args.command == "setup-hooks":
        setup_git_hooks()
    elif args.command == "all-checks":
        # 运行所有检查
        checks = [
            ("代码格式化", format_code),
            ("类型检查", check_types),
            ("代码风格检查", lint_code),
            ("安全检查", security_check),
            ("测试", run_tests),
        ]

        results = []
        for name, func in checks:
            print(f"\n开始 {name}...")
            result = func()
            results.append((name, result))

        print(f"\n{'='*50}")
        print("检查结果汇总:")
        for name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"  {name}: {status}")

    elif args.command == "ci":
        # CI 环境检查
        print("运行 CI 检查...")
        format_code()
        check_types()
        lint_code()
        security_check()
        run_tests()
        print("✅ CI 检查完成")

if __name__ == "__main__":
    main()