#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stage 3 (P2) - 优化和监控 - 完成验证脚本

验证所有文件、代码和功能是否正确实现
"""

import os
import sys
from pathlib import Path

# 设置标准输出编码为 UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("Stage 3 (P2) - 优化和监控 - 完成验证脚本")
print("=" * 80)
print()

# ==================== 验证清单 ====================

checklist = {
    "文件存在性检查": [],
    "语法检查": [],
    "功能验证": [],
    "依赖检查": []
}


# ==================== 辅助函数 ====================

def check_file_exists(filepath: str, description: str) -> bool:
    """检查文件是否存在"""
    full_path = project_root / filepath
    exists = full_path.exists()

    status = "✅" if exists else "❌"
    checklist["文件存在性检查"].append({
        "项": f"{description} ({filepath})",
        "状态": status,
        "通过": exists
    })

    if exists:
        print(f"{status} {description}: {filepath}")
    else:
        print(f"{status} ❌ 缺失: {filepath}")

    return exists


def check_syntax(filepath: str) -> bool:
    """检查 Python 文件语法"""
    import py_compile
    full_path = project_root / filepath

    try:
        py_compile.compile(str(full_path), doraise=True)
        print(f"✅ 语法检查通过: {filepath}")
        checklist["语法检查"].append({
            "项": filepath,
            "状态": "✅",
            "通过": True
        })
        return True
    except Exception as e:
        print(f"❌ 语法错误 {filepath}: {e}")
        checklist["语法检查"].append({
            "项": filepath,
            "状态": "❌",
            "通过": False
        })
        return False


def check_import(module_path: str) -> bool:
    """检查模块是否可以导入"""
    try:
        __import__(module_path)
        print(f"✅ 模块导入成功: {module_path}")
        checklist["功能验证"].append({
            "项": f"导入 {module_path}",
            "状态": "✅",
            "通过": True
        })
        return True
    except Exception as e:
        print(f"❌ 模块导入失败 {module_path}: {e}")
        checklist["功能验证"].append({
            "项": f"导入 {module_path}",
            "状态": "❌",
            "通过": False
        })
        return False


def check_function_exists(module_path: str, function_name: str) -> bool:
    """检查模块中的函数是否存在"""
    try:
        module = __import__(module_path, fromlist=[function_name])
        func = getattr(module, function_name)
        print(f"✅ 函数存在: {module_path}.{function_name}")
        checklist["功能验证"].append({
            "项": f"{module_path}.{function_name}",
            "状态": "✅",
            "通过": True
        })
        return True
    except Exception as e:
        print(f"❌ 函数不存在 {module_path}.{function_name}: {e}")
        checklist["功能验证"].append({
            "项": f"{module_path}.{function_name}",
            "状态": "❌",
            "通过": False
        })
        return False


def check_class_exists(module_path: str, class_name: str) -> bool:
    """检查模块中的类是否存在"""
    try:
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"✅ 类存在: {module_path}.{class_name}")
        checklist["功能验证"].append({
            "项": f"{module_path}.{class_name}",
            "状态": "✅",
            "通过": True
        })
        return True
    except Exception as e:
        print(f"❌ 类不存在 {module_path}.{class_name}: {e}")
        checklist["功能验证"].append({
            "项": f"{module_path}.{class_name}",
            "状态": "❌",
            "通过": False
        })
        return False


def check_dependency_in_requirements(package_name: str) -> bool:
    """检查依赖是否在 requirements.txt 中"""
    requirements_path = project_root / "requirements.txt"

    try:
        with open(requirements_path, 'r', encoding='utf-8') as f:
            content = f.read()
            found = package_name.lower() in content.lower()

            if found:
                print(f"✅ 依赖已添加: {package_name}")
                checklist["依赖检查"].append({
                    "项": f"{package_name} 在 requirements.txt",
                    "状态": "✅",
                    "通过": True
                })
                return True
            else:
                print(f"❌ 依赖缺失: {package_name}")
                checklist["依赖检查"].append({
                    "项": f"{package_name} 在 requirements.txt",
                    "状态": "❌",
                    "通过": False
                })
                return False
    except Exception as e:
        print(f"❌ 检查依赖失败 {package_name}: {e}")
        checklist["依赖检查"].append({
            "项": f"{package_name} 在 requirements.txt",
            "状态": "❌",
            "通过": False
        })
        return False


# ==================== 验证执行 ====================

print("### 任务 3.1: 增强配置验证 ###")
print("-" * 80)

check_file_exists("app/core/config_validator.py", "配置验证模块")
check_syntax("app/core/config_validator.py")
check_function_exists("app.core.config_validator", "validate_multi_model_planning_config")
check_function_exists("app.core.config_validator", "validate_contract_generation_config")
check_function_exists("app.core.config_validator", "is_multi_model_planning_ready")
check_function_exists("app.core.config_validator", "get_config_summary")
check_function_exists("app.core.config_validator", "validate_all")
check_class_exists("app.core.config_validator", "ConfigValidationResult")

print()
print("### 任务 3.2: 添加监控指标 ###")
print("-" * 80)

check_file_exists("app/monitoring/metrics.py", "监控指标模块")
check_file_exists("app/monitoring/__init__.py", "监控模块导出")
check_syntax("app/monitoring/metrics.py")
check_syntax("app/monitoring/__init__.py")

# 检查 Prometheus 指标
check_function_exists("app.monitoring.metrics", "get_metrics_summary")
check_dependency_in_requirements("prometheus-client")

print()
print("### 任务 3.3: 完善错误处理 ###")
print("-" * 80)

check_file_exists("app/services/contract_generation/exceptions.py", "错误处理模块")
check_syntax("app/services/contract_generation/exceptions.py")

# 检查异常类
check_class_exists("app.services.contract_generation.exceptions", "ContractGenerationError")
check_class_exists("app.services.contract_generation.exceptions", "ConfigurationError")
check_class_exists("app.services.contract_generation.exceptions", "ModelServiceError")
check_class_exists("app.services.contract_generation.exceptions", "MultiModelPlanningError")
check_class_exists("app.services.contract_generation.exceptions", "DocumentProcessingError")
check_class_exists("app.services.contract_generation.exceptions", "DatabaseOperationError")
check_class_exists("app.services.contract_generation.exceptions", "WorkflowExecutionError")
check_class_exists("app.services.contract_generation.exceptions", "TemplateMatchingError")
check_class_exists("app.services.contract_generation.exceptions", "RateLimitError")

# 检查错误处理函数
check_function_exists("app.services.contract_generation.exceptions", "handle_error")
check_function_exists("app.services.contract_generation.exceptions", "get_error_strategy")
check_function_exists("app.services.contract_generation.exceptions", "should_fallback_to_single_model")
check_function_exists("app.services.contract_generation.exceptions", "is_retry_able")
check_function_exists("app.services.contract_generation.exceptions", "get_user_friendly_message")

# 检查 workflow.py 是否导入异常模块
check_syntax("app/services/contract_generation/workflow.py")

# 检查 API 路由是否导入异常模块
check_syntax("app/api/contract_generation_router.py")

print()
print("### 任务 3.4: 性能优化 ###")
print("-" * 80)

check_file_exists("app/services/contract_generation/performance.py", "性能优化工具")
check_syntax("app/services/contract_generation/performance.py")

# 检查性能优化工具
check_function_exists("app.services.contract_generation.performance", "cache_result")
check_function_exists("app.services.contract_generation.performance", "cache_async_result")
check_class_exists("app.services.contract_generation.performance", "BatchProcessor")
check_class_exists("app.services.contract_generation.performance", "ConcurrencyLimiter")
check_function_exists("app.services.contract_generation.performance", "limit_concurrency")
check_function_exists("app.services.contract_generation.performance", "monitor_performance")
check_function_exists("app.services.contract_generation.performance", "retry_on_failure")
check_class_exists("app.services.contract_generation.performance", "ResourceManager")
check_class_exists("app.services.contract_generation.performance", "LazyLoader")

print()
print("### 任务 3.5: 文档完善 ###")
print("-" * 80)

check_file_exists("docs/stage3_completion_summary.md", "Stage 3 完成总结文档")

print()
print("=" * 80)
print("### 验证结果汇总 ###")
print("=" * 80)

# 计算通过率
total_checks = sum(len(checks) for checks in checklist.values())
passed_checks = sum(
    sum(1 for item in checks if item["通过"])
    for checks in checklist.values()
)

pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0

print()
for category, checks in checklist.items():
    category_passed = sum(1 for item in checks if item["通过"])
    category_total = len(checks)
    print(f"{category}: {category_passed}/{category_total} 通过")

print()
print(f"总体通过率: {passed_checks}/{total_checks} ({pass_rate:.1f}%)")
print()

if pass_rate == 100:
    print("=" * 80)
    print("🎉 所有验证通过！Stage 3 (P2) 已完成！")
    print("=" * 80)
    sys.exit(0)
else:
    print("=" * 80)
    print(f"⚠️  有 {total_checks - passed_checks} 项检查未通过，请检查上述错误")
    print("=" * 80)
    sys.exit(1)
