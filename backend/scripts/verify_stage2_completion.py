"""
Stage 2 (P1): 数据持久化集成 - 完成检查清单

验证所有文件和代码修改是否正确完成。
"""

import os
from pathlib import Path
import sys

def check_file_exists(file_path, description):
    """检查文件是否存在"""
    if os.path.exists(file_path):
        print(f"[OK] {description}")
        print(f"   路径: {file_path}")
        return True
    else:
        print(f"[FAIL] {description}")
        print(f"   路径: {file_path}")
        return False

def check_file_contains(file_path, search_strings, description):
    """检查文件是否包含特定内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        all_found = True
        for search_str in search_strings:
            if search_str in content:
                print(f"   [OK] 包含: {search_str[:50]}...")
            else:
                print(f"   [FAIL] 缺失: {search_str[:50]}...")
                all_found = False

        if all_found:
            print(f"[OK] {description}")
        else:
            print(f"[FAIL] {description}")

        return all_found
    except Exception as e:
        print(f"[FAIL] {description}")
        print(f"   错误: {e}")
        return False

def main():
    print("="*60)
    print("Stage 2 (P1): 数据持久化集成 - 完成检查")
    print("="*60)

    backend_dir = Path(__file__).parent.parent
    results = []

    # 任务 2.1: 分析现有 Task 模型
    print("\n任务 2.1: 分析现有 Task 模型")
    print("-" * 60)
    results.append(check_file_exists(
        backend_dir / "app" / "models" / "task.py",
        "Task 模型文件"
    ))

    # 任务 2.2: 创建数据库迁移文件
    print("\n任务 2.2: 创建数据库迁移文件")
    print("-" * 60)
    migration_file = backend_dir / "alembic" / "versions" / "20260117_add_contract_generation_indexes.py"
    results.append(check_file_exists(
        migration_file,
        "数据库迁移文件"
    ))

    if os.path.exists(migration_file):
        results.append(check_file_contains(
            migration_file,
            ["ix_tasks_owner_type_created", "ix_tasks_params_planning_mode", "ix_tasks_contract_gen_status"],
            "迁移文件包含所需索引"
        ))

    # 任务 2.3: 扩展 Task CRUD 操作
    print("\n任务 2.3: 扩展 Task CRUD 操作")
    print("-" * 60)
    crud_file = backend_dir / "app" / "crud" / "task.py"
    results.append(check_file_exists(
        crud_file,
        "CRUD 扩展文件"
    ))

    if os.path.exists(crud_file):
        results.append(check_file_contains(
            crud_file,
            [
                "create_contract_generation_task",
                "get_contract_generation_tasks",
                "update_contract_generation_progress",
                "save_synthesis_report"
            ],
            "CRUD 包含合同生成专用方法"
        ))

    # 任务 2.4: 修改 Celery 任务集成
    print("\n任务 2.4: 修改 Celery 任务集成")
    print("-" * 60)
    celery_file = backend_dir / "tasks" / "contract_generation_tasks.py"
    results.append(check_file_exists(
        celery_file,
        "Celery 任务文件"
    ))

    if os.path.exists(celery_file):
        results.append(check_file_contains(
            celery_file,
            [
                "from app.db.session import SessionLocal",
                "from app.crud.task import task as crud_task",
                "owner_id: Optional[int] = None",
                "db = SessionLocal()",
                "crud_task.create_contract_generation_task",
                "crud_task.update_contract_generation_progress",
                "crud_task.save_synthesis_report"
            ],
            "Celery 任务包含数据库集成"
        ))

    # 任务 2.5: 修改 API 路由集成
    print("\n任务 2.5: 修改 API 路由集成")
    print("-" * 60)
    router_file = backend_dir / "app" / "api" / "contract_generation_router.py"
    results.append(check_file_exists(
        router_file,
        "API 路由文件"
    ))

    if os.path.exists(router_file):
        results.append(check_file_contains(
            router_file,
            [
                "current_user: Optional[Any] = None",
                "owner_id = getattr(current_user, 'id', None)",
                "@router.get(\"/tasks\")",
                "@router.get(\"/tasks/{task_id}\")"
            ],
            "API 路由包含认证支持和历史端点"
        ))

    # 任务 2.6: 新增历史任务端点
    print("\n任务 2.6: 新增历史任务端点")
    print("-" * 60)
    if os.path.exists(router_file):
        results.append(check_file_contains(
            router_file,
            [
                "get_contract_generation_tasks",
                "get_contract_generation_task_detail",
                "planning_mode: Optional[str] = None",
                "status: Optional[str] = None"
            ],
            "历史任务端点实现"
        ))

    # 测试文件
    print("\n测试和文档")
    print("-" * 60)
    results.append(check_file_exists(
        backend_dir / "tests" / "test_contract_generation_db_integration.py",
        "数据库集成测试脚本"
    ))

    results.append(check_file_exists(
        backend_dir / "docs" / "database_migration_guide.md",
        "数据库迁移指南"
    ))

    # 汇总结果
    print("\n" + "="*60)
    print("检查结果汇总")
    print("="*60)
    passed = sum(results)
    total = len(results)

    print(f"通过: {passed}/{total}")

    if passed == total:
        print("\n[SUCCESS] 所有检查通过！Stage 2 (P1) 已完成。")
        print("\n下一步:")
        print("1. 执行数据库迁移: alembic upgrade head")
        print("2. 运行集成测试: python tests/test_contract_generation_db_integration.py")
        print("3. 参考 docs/database_migration_guide.md 进行详细验证")
        return 0
    else:
        print(f"\n[FAIL] 有 {total - passed} 项检查失败，请检查上述错误。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
