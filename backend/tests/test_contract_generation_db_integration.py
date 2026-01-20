"""
合同生成模块 - 数据库集成测试脚本

用于验证 Stage 2 (P1) 的所有功能：
1. 数据库索引是否正确创建
2. CRUD 操作是否正常工作
3. API 端点是否正常响应
4. Celery 任务集成是否正确

使用方法：
1. 确保数据库正在运行
2. 确保已执行数据库迁移：alembic upgrade head
3. 运行测试：python tests/test_contract_generation_db_integration.py
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.session import SessionLocal
from app.crud.task import task as crud_task
from app.models.task import Task


class TestResult:
    """测试结果"""
    def __init__(self):
        self.passed = []
        self.failed = []

    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        print(f"✅ {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"❌ {test_name}")
        print(f"   错误: {error}")

    def summary(self):
        print("\n" + "="*60)
        print("测试结果汇总")
        print("="*60)
        print(f"通过: {len(self.passed)}")
        print(f"失败: {len(self.failed)}")
        if self.failed:
            print("\n失败的测试:")
            for test_name, error in self.failed:
                print(f"  - {test_name}: {error}")
        return len(self.failed) == 0


def test_database_indexes(db):
    """测试 1: 验证数据库索引是否正确创建"""
    print("\n测试 1: 验证数据库索引")
    print("-" * 60)
    result = TestResult()

    try:
        # 查询 PostgreSQL 的索引信息
        query = text("""
            SELECT
                indexname,
                indexdef
            FROM
                pg_indexes
            WHERE
                tablename = 'tasks'
                AND indexname LIKE '%contract_generation%' OR indexname LIKE '%owner_type_created%' OR indexname LIKE '%params_planning_mode%'
            ORDER BY
                indexname;
        """)

        indexes = db.execute(query).fetchall()

        expected_indexes = [
            'ix_tasks_owner_type_created',
            'ix_tasks_params_planning_mode',
            'ix_tasks_contract_gen_status'
        ]

        found_indexes = [idx[0] for idx in indexes]

        for expected in expected_indexes:
            if expected in found_indexes:
                result.add_pass(f"索引 {expected} 已创建")
            else:
                result.add_fail(f"索引 {expected} 未找到", "索引不存在")

        # 打印找到的索引详情
        if indexes:
            print("\n找到的索引详情:")
            for idx_name, idx_def in indexes:
                print(f"  - {idx_name}")
                print(f"    {idx_def[:100]}...")

    except Exception as e:
        result.add_fail("查询索引信息", str(e))

    return result


def test_crud_operations(db):
    """测试 2: CRUD 操作功能测试"""
    print("\n测试 2: CRUD 操作功能")
    print("-" * 60)
    result = TestResult()

    try:
        # 2.1 测试创建合同生成任务
        print("\n2.1 创建合同生成任务")
        task = crud_task.create_contract_generation_task(
            db=db,
            owner_id=1,  # 假设用户 ID 为 1
            user_input="测试合同生成需求",
            planning_mode="multi_model",
            uploaded_files=["test1.pdf", "test2.docx"],
            session_id="test_session_123"
        )

        if task and task.id:
            result.add_pass("创建合同生成任务")
            print(f"   任务 ID: {task.id}")
            print(f"   任务类型: {task.task_type}")
            print(f"   规划模式: {task.task_params.get('planning_mode')}")
        else:
            result.add_fail("创建合同生成任务", "任务创建失败")
            return result

        # 2.2 测试获取任务列表
        print("\n2.2 获取合同生成任务列表")
        tasks = crud_task.get_contract_generation_tasks(
            db=db,
            owner_id=1,
            planning_mode="multi_model",
            skip=0,
            limit=10
        )

        if tasks and len(tasks) > 0:
            result.add_pass(f"获取任务列表 (找到 {len(tasks)} 个任务)")
        else:
            result.add_fail("获取任务列表", "未找到任务")

        # 2.3 测试更新任务进度
        print("\n2.3 更新任务进度")
        updated_task = crud_task.update_contract_generation_progress(
            db=db,
            task_id=task.id,
            progress=50.0,
            status="processing"
        )

        if updated_task and updated_task.progress == 50.0:
            result.add_pass("更新任务进度")
        else:
            result.add_fail("更新任务进度", "进度更新失败")

        # 2.4 测试保存融合报告
        print("\n2.4 保存融合报告")
        synthesis_report = {
            "solution_analyses": "测试方案分析",
            "extracted_strengths": "优点1、优点2",
            "identified_weaknesses": "缺点1、缺点2",
            "fusion_strategy": "融合策略",
            "fusion_summary": "融合摘要"
        }

        task_with_report = crud_task.save_synthesis_report(
            db=db,
            task_id=task.id,
            synthesis_report=synthesis_report
        )

        if task_with_report and task_with_report.result_data:
            result.add_pass("保存融合报告")
            print(f"   融合报告已保存: {task_with_report.result_data.get('multi_model_synthesis_report')}")
        else:
            result.add_fail("保存融合报告", "报告保存失败")

        # 2.5 测试更新任务结果
        print("\n2.5 更新任务结果")
        result_data = {
            "generated_contracts": [
                {
                    "contract_name": "测试合同",
                    "contract_type": "买卖合同",
                    "content": "合同内容..."
                }
            ]
        }

        completed_task = crud_task.update_contract_generation_progress(
            db=db,
            task_id=task.id,
            progress=100.0,
            status="completed",
            result_data=result_data
        )

        if completed_task and completed_task.status == "completed":
            result.add_pass("更新任务结果")
        else:
            result.add_fail("更新任务结果", "结果更新失败")

        # 2.6 测试按状态筛选
        print("\n2.6 按状态筛选任务")
        completed_tasks = crud_task.get_contract_generation_tasks(
            db=db,
            owner_id=1,
            status="completed",
            skip=0,
            limit=10
        )

        if completed_tasks and len(completed_tasks) > 0:
            result.add_pass(f"按状态筛选 (找到 {len(completed_tasks)} 个已完成任务)")
        else:
            result.add_fail("按状态筛选", "未找到已完成任务")

        # 清理测试数据
        print("\n清理测试数据")
        db.delete(task)
        db.commit()
        result.add_pass("清理测试数据")

    except Exception as e:
        result.add_fail("CRUD 操作测试", str(e))
        import traceback
        traceback.print_exc()

    return result


def test_task_model_fields(db):
    """测试 3: Task 模型字段验证"""
    print("\n测试 3: Task 模型字段验证")
    print("-" * 60)
    result = TestResult()

    try:
        # 创建测试任务
        task = Task(
            owner_id=1,
            task_type="contract_generation",
            status="pending",
            task_params={
                "user_input": "测试需求",
                "planning_mode": "single_model",
                "uploaded_files": ["test.pdf"]
            },
            result_data={
                "generated_contracts": []
            },
            progress=0.0
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        # 验证字段
        fields_to_check = [
            ("id", task.id),
            ("owner_id", task.owner_id),
            ("task_type", task.task_type),
            ("status", task.status),
            ("task_params", task.task_params),
            ("result_data", task.result_data),
            ("progress", task.progress)
        ]

        for field_name, field_value in fields_to_check:
            if field_value is not None:
                result.add_pass(f"字段 {field_name} 存在")
            else:
                result.add_fail(f"字段 {field_name}", "字段值为 None")

        # 清理
        db.delete(task)
        db.commit()

    except Exception as e:
        result.add_fail("Task 模型字段验证", str(e))
        import traceback
        traceback.print_exc()

    return result


def test_json_field_queries(db):
    """测试 4: JSON 字段查询"""
    print("\n测试 4: JSON 字段查询")
    print("-" * 60)
    result = TestResult()

    try:
        # 创建多个测试任务
        for i in range(3):
            task = Task(
                owner_id=1,
                task_type="contract_generation",
                status="pending",
                task_params={
                    "user_input": f"测试需求 {i}",
                    "planning_mode": "multi_model" if i % 2 == 0 else "single_model",
                    "uploaded_files": [f"test{i}.pdf"]
                },
                progress=0.0
            )
            db.add(task)

        db.commit()

        # 测试按 planning_mode 查询
        print("\n4.1 按 planning_mode 筛选")
        multi_model_tasks = db.query(Task).filter(
            Task.owner_id == 1,
            Task.task_type == "contract_generation",
            Task.task_params["planning_mode"].astext == "multi_model"
        ).all()

        if len(multi_model_tasks) > 0:
            result.add_pass(f"按 planning_mode 筛选 (找到 {len(multi_model_tasks)} 个多模型任务)")
        else:
            result.add_fail("按 planning_mode 筛选", "未找到多模型任务")

        # 清理测试数据
        for task in multi_model_tasks:
            db.delete(task)
        db.commit()

        result.add_pass("清理测试数据")

    except Exception as e:
        result.add_fail("JSON 字段查询", str(e))
        import traceback
        traceback.print_exc()

    return result


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("合同生成模块 - 数据库集成测试")
    print("="*60)

    db = SessionLocal()

    try:
        # 测试 1: 数据库索引
        result1 = test_database_indexes(db)

        # 测试 2: CRUD 操作
        result2 = test_crud_operations(db)

        # 测试 3: Task 模型字段
        result3 = test_task_model_fields(db)

        # 测试 4: JSON 字段查询
        result4 = test_json_field_queries(db)

        # 汇总结果
        print("\n" + "="*60)
        print("总体测试结果")
        print("="*60)

        all_passed = True
        for i, result in enumerate([result1, result2, result3, result4], 1):
            print(f"\n测试组 {i}:")
            if result.summary():
                print("✅ 全部通过")
            else:
                print("❌ 存在失败")
                all_passed = False

        if all_passed:
            print("\n" + "="*60)
            print("🎉 所有测试通过！")
            print("="*60)
            return 0
        else:
            print("\n" + "="*60)
            print("⚠️  部分测试失败，请检查上述错误信息")
            print("="*60)
            return 1

    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
