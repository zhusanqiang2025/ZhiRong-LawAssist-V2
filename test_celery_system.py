#!/usr/bin/env python3
"""
Celery 系统测试脚本

用于测试 Celery 任务队列系统与旧系统 (BackgroundTasks) 的差异

使用方法:
1. 确保后端服务正在运行 (http://localhost:8000)
2. 获取访问令牌 (登录或使用默认管理员账户)
3. 运行: python test_celery_system.py --token YOUR_TOKEN
"""

import requests
import time
import json
import sys
from typing import Dict, Any

API_BASE = "http://localhost:8000/api/v1"


def test_litigation_analysis(token: str, use_celery: bool = True) -> Dict[str, Any]:
    """
    测试案件分析功能

    Args:
        token: 访问令牌
        use_celery: 是否使用 Celery (True) 或 BackgroundTasks (False)
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "package_id": "contract_dispute_default",
        "case_type": "contract_performance",
        "case_position": "plaintiff",
        "user_input": "测试案件分析 - Celery系统" if use_celery else "测试案件分析 - 旧系统",
        "document_ids": []
    }

    print(f"\n{'='*60}")
    print(f"测试案件分析 - {'Celery 系统' if use_celery else '旧系统 (BackgroundTasks)'}")
    print(f"{'='*60}\n")

    # 1. 启动任务
    print("1. 启动案件分析任务...")
    start_time = time.time()

    response = requests.post(
        f"{API_BASE}/litigation-analysis/start",
        headers=headers,
        json=payload
    )

    elapsed = time.time() - start_time

    if response.status_code != 200:
        print(f"   ❌ 失败: {response.status_code}")
        print(f"   {response.text}")
        return {"success": False, "error": response.text}

    data = response.json()
    print(f"   ✅ 成功! 响应时间: {elapsed:.2f}秒")
    print(f"   Session ID: {data.get('session_id')}")
    print(f"   任务系统: {data.get('task_system', 'unknown')}")
    print(f"   Celery 任务 ID: {data.get('celery_task_id', 'N/A')}")

    session_id = data.get("session_id")
    task_system = data.get("task_system")

    # 2. 监控任务进度
    print("\n2. 监控任务进度...")

    max_wait = 300  # 最多等待5分钟
    check_interval = 2  # 每2秒检查一次
    start_check_time = time.time()

    progress_history = []

    while time.time() - start_check_time < max_wait:
        response = requests.get(
            f"{API_BASE}/litigation-analysis/{session_id}/status",
            headers=headers
        )

        if response.status_code == 200:
            status_data = response.json()
            status = status_data.get("status")
            progress = status_data.get("progress", 0)
            current_node = status_data.get("current_node", "")
            message = status_data.get("message", "")

            progress_record = {
                "time": time.time() - start_check_time,
                "progress": progress,
                "node": current_node,
                "message": message
            }
            progress_history.append(progress_record)

            print(f"   进度: {progress:5.1f}% | 状态: {status:12} | 节点: {current_node:30} | {message}")

            if status in ["completed", "failed", "cancelled"]:
                total_time = time.time() - start_check_time
                print(f"\n   任务 {status}! 总耗时: {total_time:.2f}秒")
                break

        time.sleep(check_interval)
    else:
        print(f"\n   ⚠️  超时: 等待超过 {max_wait} 秒")

    # 3. 获取任务结果
    print("\n3. 获取任务结果...")
    response = requests.get(
        f"{API_BASE}/litigation-analysis/{session_id}/result",
        headers=headers
    )

    if response.status_code == 200:
        result = response.json()
        print("   ✅ 成功获取结果!")

        # 显示结果摘要
        if "analysis_report" in result:
            report = result["analysis_report"]
            print(f"   分析报告: {len(str(report))} 字符")

        return {
            "success": True,
            "task_system": task_system,
            "session_id": session_id,
            "progress_history": progress_history,
            "result": result
        }
    else:
        print(f"   ❌ 获取结果失败: {response.status_code}")
        return {"success": False, "error": "Failed to get result"}


def compare_systems(token: str):
    """
    对比测试两个系统
    """
    print("\n" + "="*60)
    print("Celery vs BackgroundTasks 系统对比测试")
    print("="*60)

    # 测试旧系统
    print("\n### 测试旧系统 (BackgroundTasks) ###")
    old_result = test_litigation_analysis(token, use_celery=False)

    time.sleep(5)  # 等待5秒

    # 测试新系统
    print("\n### 测试新系统 (Celery) ###")
    new_result = test_litigation_analysis(token, use_celery=True)

    # 对比结果
    print("\n" + "="*60)
    print("对比结果")
    print("="*60)

    if old_result.get("success") and new_result.get("success"):
        print("\n✅ 两个系统都成功完成任务!")

        old_history = old_result.get("progress_history", [])
        new_history = new_result.get("progress_history", [])

        if old_history and new_history:
            old_time = old_history[-1]["time"]
            new_time = new_history[-1]["time"]

            print(f"\n旧系统总耗时: {old_time:.2f}秒")
            print(f"新系统总耗时: {new_time:.2f}秒")
            print(f"时间差异: {new_time - old_time:+.2f}秒")

            print(f"\n旧系统进度更新次数: {len(old_history)}")
            print(f"新系统进度更新次数: {len(new_history)}")

    else:
        print("\n❌ 测试失败，请检查日志")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="测试 Celery 任务队列系统")
    parser.add_argument("--token", required=True, help="访问令牌")
    parser.add_argument("--old", action="store_true", help="只测试旧系统")
    parser.add_argument("--new", action="store_true", help="只测试新系统")
    parser.add_argument("--compare", action="store_true", help="对比测试两个系统")

    args = parser.parse_args()

    if args.compare:
        compare_systems(args.token)
    elif args.old:
        test_litigation_analysis(args.token, use_celery=False)
    elif args.new:
        test_litigation_analysis(args.token, use_celery=True)
    else:
        print("请指定测试选项: --old, --new, 或 --compare")
        sys.exit(1)


if __name__ == "__main__":
    main()
