#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
费用测算模块测试脚本
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.cost_calculation import run_cost_calculation, calculate_litigation_fee, calculate_preservation_fee, calculate_execution_fee, calculate_appraisal_fee, calculate_lawyer_fee

def test_cost_calculation():
    """测试费用测算功能"""
    print("="*60)
    print("费用测算模块测试")
    print("="*60)
    
    # 测试用例1：合同纠纷，标的额100万元
    print("\n测试用例1：合同纠纷，标的额100万元")
    print("-"*40)
    case_type = "合同纠纷"
    case_description = "买卖合同纠纷，对方未按时交付货物，造成损失约100万元"
    case_amount = 1000000  # 100万元
    
    result = run_cost_calculation(case_type, case_description, case_amount)
    
    print(f"案件类型: {case_type}")
    print(f"案件描述: {case_description}")
    print(f"标的额: {case_amount:,}元")
    print(f"总费用估算: {result.total_cost:,.2f}元")
    print("\n费用明细:")
    for item in result.cost_breakdown:
        print(f"  - {item.name}: {item.amount:,.2f}元 ({item.description})")
    print(f"计算依据: {result.calculation_basis}")
    print(f"免责声明: {result.disclaimer}")
    
    # 测试用例2：劳动争议，无明确标的额
    print("\n\n测试用例2：劳动争议，无明确标的额")
    print("-"*40)
    case_type = "劳动争议"
    case_description = "劳动争议案件，涉及工资、经济补偿金等争议"
    case_amount = None
    
    result = run_cost_calculation(case_type, case_description, case_amount)
    
    print(f"案件类型: {case_type}")
    print(f"案件描述: {case_description}")
    print(f"标的额: {case_amount}")
    print(f"总费用估算: {result.total_cost:,.2f}元")
    print("\n费用明细:")
    for item in result.cost_breakdown:
        print(f"  - {item.name}: {item.amount:,.2f}元 ({item.description})")
    print(f"计算依据: {result.calculation_basis}")
    print(f"免责声明: {result.disclaimer}")
    
    # 测试用例3：建设工程纠纷，标的额500万元，包含鉴定
    print("\n\n测试用例3：建设工程纠纷，标的额500万元，包含鉴定")
    print("-"*40)
    case_type = "建设工程"
    case_description = "建设工程施工合同纠纷，涉及工程造价鉴定，标的额约500万元"
    case_amount = 5000000  # 500万元
    
    result = run_cost_calculation(case_type, case_description, case_amount)
    
    print(f"案件类型: {case_type}")
    print(f"案件描述: {case_description}")
    print(f"标的额: {case_amount:,}元")
    print(f"总费用估算: {result.total_cost:,.2f}元")
    print("\n费用明细:")
    for item in result.cost_breakdown:
        print(f"  - {item.name}: {item.amount:,.2f}元 ({item.description})")
    print(f"计算依据: {result.calculation_basis}")
    print(f"免责声明: {result.disclaimer}")
    
    print("\n" + "="*60)
    print("费用测算模块测试完成")
    print("="*60)


def test_individual_calculation_functions():
    """测试各个费用计算函数"""
    print("="*60)
    print("各项费用计算函数测试")
    print("="*60)
    
    # 测试诉讼费计算
    print("\n诉讼费计算测试:")
    test_amounts = [5000, 50000, 250000, 1000000, 2500000, 5000000]
    for amount in test_amounts:
        fee, desc = calculate_litigation_fee(amount)
        print(f"  标的额 {amount:,}元 -> 诉讼费 {fee:,.2f}元 ({desc})")
    
    # 测试保全费计算
    print("\n保全费计算测试:")
    for amount in test_amounts:
        fee, desc = calculate_preservation_fee(amount)
        print(f"  保全额 {amount:,}元 -> 保全费 {fee:,.2f}元 ({desc})")
    
    # 测试执行费计算
    print("\n执行费计算测试:")
    for amount in test_amounts:
        fee, desc = calculate_execution_fee(amount)
        print(f"  执行额 {amount:,}元 -> 执行费 {fee:,.2f}元 ({desc})")
    
    # 测试鉴定费计算
    print("\n鉴定费计算测试:")
    for amount in test_amounts:
        fee, desc = calculate_appraisal_fee(amount)
        print(f"  鉴定额 {amount:,}元 -> 鉴定费 {fee:,.2f}元 ({desc})")
    
    # 测试律师费计算
    print("\n律师费计算测试:")
    case_types = ["合同纠纷", "劳动争议", "知识产权"]
    for case_type in case_types:
        for amount in [None, 100000, 1000000]:
            fee, desc = calculate_lawyer_fee(amount, case_type)
            amount_str = f"{amount:,}" if amount else "无"
            print(f"  {case_type}, 标的额 {amount_str}元 -> 律师费 {fee:,.2f}元 ({desc})")


if __name__ == "__main__":
    test_individual_calculation_functions()
    test_cost_calculation()