#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试 Celery 系统

这个脚本会：
1. 登录获取令牌
2. 启动一个案件分析任务（使用 Celery）
3. 监控任务进度
4. 显示结果
"""

import requests
import time
import json
import sys
import io

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

API_BASE = "http://localhost:8000/api/v1"

# 1. 登录
print("=" * 60)
print("Celery 系统测试")
print("=" * 60)

print("\n1. 登录...")
login_response = requests.post(
    f"{API_BASE}/auth/login",
    data={"username": "test@example.com", "password": "Test123456"}  # 使用 data 而不是 json
)

if login_response.status_code != 200:
    print(f"   ❌ 登录失败: {login_response.status_code}")
    print(f"   {login_response.text}")
    exit(1)

token = login_response.json()["access_token"]
print(f"   ✅ 登录成功!")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 2. 启动案件分析任务
print("\n2. 启动案件分析任务...")
payload = {
    "package_id": "contract_dispute_default",
    "case_type": "contract_performance",
    "case_position": "plaintiff",
    "user_input": "测试 Celery 系统 - 这是一条测试案件",
    "document_ids": []
}

start_response = requests.post(
    f"{API_BASE}/litigation-analysis/start",
    headers=headers,
    json=payload
)

if start_response.status_code != 200:
    print(f"   ❌ 启动任务失败: {start_response.status_code}")
    print(f"   {start_response.text}")
    exit(1)

data = start_response.json()
session_id = data.get("session_id")
task_system = data.get("task_system", "unknown")
celery_task_id = data.get("celery_task_id", "N/A")

print(f"   ✅ 任务启动成功!")
print(f"   Session ID: {session_id}")
print(f"   任务系统: {task_system}")
print(f"   Celery 任务 ID: {celery_task_id}")

if task_system != "celery":
    print(f"\n   ⚠️  警告: 任务没有使用 Celery 系统!")
    print(f"   当前 CELERY_ENABLED 设置可能为 false")

# 3. 监控任务进度
print("\n3. 监控任务进度...")

max_wait = 180  # 最多等待 3 分钟
check_interval = 3  # 每 3 秒检查一次
start_time = time.time()

while time.time() - start_time < max_wait:
    status_response = requests.get(
        f"{API_BASE}/litigation-analysis/{session_id}/status",
        headers=headers
    )

    if status_response.status_code == 200:
        status_data = status_response.json()
        status = status_data.get("status")
        progress = status_data.get("progress", 0)
        current_node = status_data.get("current_node", "")
        message = status_data.get("message", "")

        print(f"   进度: {progress:5.1f}% | 状态: {status:12} | {message[:50]}")

        if status in ["completed", "failed", "cancelled"]:
            total_time = time.time() - start_time
            print(f"\n   任务 {status}! 总耗时: {total_time:.1f}秒")
            break
    else:
        print(f"   ❌ 获取状态失败: {status_response.status_code}")

    time.sleep(check_interval)
else:
    print(f"\n   ⚠️  超时: 等待超过 {max_wait} 秒")

# 4. 获取任务结果
print("\n4. 获取任务结果...")
result_response = requests.get(
    f"{API_BASE}/litigation-analysis/{session_id}/result",
    headers=headers
)

if result_response.status_code == 200:
    result = result_response.json()
    print("   ✅ 成功获取结果!")

    # 显示结果摘要
    if "analysis_report" in result:
        report = result["analysis_report"]
        if isinstance(report, dict):
            print(f"   分析报告包含 {len(report)} 个字段")
        elif isinstance(report, str):
            print(f"   分析报告: {len(report)} 字符")
else:
    print(f"   ❌ 获取结果失败: {result_response.status_code}")

# 5. 总结
print("\n" + "=" * 60)
print("测试总结")
print("=" * 60)
print(f"✅ 任务系统: {task_system}")
if task_system == "celery":
    print(f"✅ Celery 任务 ID: {celery_task_id}")
    print(f"\n✅ Celery 系统正常运行!")
    print(f"\n提示:")
    print(f"  - 如果 task_system 显示 'celery'，说明 Celery 系统已启用")
    print(f"  - 即使关闭浏览器，任务也会继续执行")
    print(f"  - 可以随时重新查询任务状态和结果")
else:
    print(f"\n⚠️  当前使用的是旧系统 (BackgroundTasks)")
    print(f"   如需启用 Celery，请设置 CELERY_ENABLED=true")
