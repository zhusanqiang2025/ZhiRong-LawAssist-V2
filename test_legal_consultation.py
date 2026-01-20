#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试法律咨询模块的功能
"""

import sys
import os

# 添加backend目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.legal_consultation_graph import run_legal_consultation

def test_legal_consultation():
    """测试法律咨询功能"""
    print("🧪 开始测试法律咨询功能...")
    
    # 测试问题
    test_question = "劳动合同到期后，公司不续签，需要支付经济补偿金吗？"
    
    # 测试上下文
    test_context = {
        "user_type": "劳动者",
        "region": "北京",
        "work_years": "3年"
    }
    
    print(f"❓ 测试问题: {test_question}")
    print(f"📋 测试上下文: {test_context}")
    
    try:
        # 运行法律咨询
        result, report = run_legal_consultation(test_question, test_context)
        
        if result:
            print("\n✅ 法律咨询成功!")
            print("="*50)
            print(f"问题: {result.advice.question}")
            print(f"法律依据: {result.advice.legal_basis}")
            print(f"分析: {result.advice.analysis}")
            print(f"建议: {result.advice.advice}")
            print(f"风险提醒: {result.advice.risk_warning}")
            print(f"行动步骤: {', '.join(result.advice.action_steps)}")
            print("="*50)
        else:
            print("❌ 法律咨询失败")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_legal_consultation()