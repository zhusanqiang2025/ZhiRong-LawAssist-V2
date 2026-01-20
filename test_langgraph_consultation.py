#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试重构后的 LangGraph 法律咨询工作流

测试用例：
1. 简单问题：公司设立法律要求
2. 复杂建工纠纷：两家公司之间的法律关系梳理
"""

import sys
import os
import asyncio

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from legal_consultation_graph import run_legal_consultation


async def test_simple_question():
    """测试简单问题"""
    print("=" * 80)
    print("测试1：简单问题 - 公司设立法律要求")
    print("=" * 80)

    test_question = "公司设立法律要求"

    result, report = await run_legal_consultation(test_question)

    if result:
        print("\n✅ 咨询成功！\n")
        print(f"分类结果：{result.classification_result}")
        print(f"\n分析（前300字）：\n{result.analysis[:300]}...")
        print(f"\n建议（前300字）：\n{result.advice[:300]}...")
        print(f"\n行动步骤：{result.action_steps}")
        print("\n" + "=" * 80)
        print("完整报告：")
        print("=" * 80)
        print(report)
    else:
        print(f"❌ 咨询失败：{report}")


async def test_complex_case():
    """测试复杂建工纠纷案例"""
    print("\n\n" + "=" * 80)
    print("测试2：复杂建工纠纷 - 梳理鑫绵兴与兴业之间的法律关系")
    print("=" * 80)

    test_question = """1.成都兴业建筑工程有限公司以四川鑫绵兴建筑工程有限公司名义取得了一个施工总承包项目，四川鑫绵兴建筑工程有限公司为合同约定的总承包单位，合同总金额1.9亿元，预估结算金额1.42亿。
2.四川鑫绵兴建筑工程有限公司对下签署了系列分包合同，合计总金额1.04亿元，预估结算8775万；成都兴业建筑工程有限公司也对下签署了系列分包合同，合计总金额2113万元，预估结算金额1597万，两家公司合计对下合同金额合计约1.25亿元。
3.资金流向，业主依据总承包合同向四川鑫绵兴建筑工程有限公司支付工程款后，四川鑫绵兴建筑工程有限公司即支付给了成都兴业建筑工程有限公司，由兴业建筑公司对下进行支付。导致四川鑫绵兴建筑工程有限公司与兴业建筑之间存在较大金额的往来。
4.四川鑫绵兴建筑工程有限公司已被其外部债权起诉（金额约1800万元），并保全了其应收业主方的工程款余额（约2600万元），为避免其他债权人继续保全这边应收工程款，四川鑫绵兴建筑工程有限公司与兴业建筑公司签署了一个金鸽5472万元的钢结构劳务分包合同，并以该合同为依据发起诉讼，形成调解书，确认四川鑫绵兴建筑工程有限公司与兴业建筑公司应付兴业建筑公司2500余万。

现在的任务，梳理明确鑫绵兴与兴业之间的法律关系。目前有两种思路：
1.成都兴业建筑工程有限公司为四川鑫绵兴建筑工程有限公司的合法分包商之一，合同依据为：《钢结构分包合同》，成都兴业建筑工程有限公司以合法分包人身份向鑫绵兴主张工程款，结果可能会出现：因外部债权人在先保全，未付工程款2600万元在分配给在先外部债权人外，兴业建筑实际可收到的工程款为2600万元-1800万元=800万元；
基于这种法律关系，四川鑫绵兴建筑工程有限公司与兴业建筑之间的大额往来以代付协议作为支撑，即兴业建筑代四川鑫绵兴建筑工程有限公司向其下游单位支付工程款。

2.成都兴业建筑是项目的实际权益人，带帽四川鑫绵兴建筑工程有限公司取得项目，项目的实际权益人和工程款归属与兴业建筑，除已签署的《钢结构分包合同》外，再补签1.35亿元的合同，明确项目实际权益归属。四川鑫绵兴建筑工程有限公司将工程款转给兴业建筑即有合同依据，兴业建筑也可以实际权益人对未付的工程款主张权益。

基于这两个分析，结合现行有效的法律法规对比分析，哪种方案对兴业建筑更为有利。"""

    result, report = await run_legal_consultation(test_question)

    if result:
        print("\n✅ 咨询成功！\n")
        print(f"分类结果：{result.classification_result}")
        print(f"\n法律依据：{result.legal_basis}")
        print(f"\n分析（前500字）：\n{result.analysis[:500]}...")
        print(f"\n建议（前500字）：\n{result.advice[:500]}...")
        print(f"\n风险提醒：{result.risk_warning[:300]}...")
        print(f"\n行动步骤（共{len(result.action_steps)}步）：")
        for i, step in enumerate(result.action_steps, 1):
            print(f"  {i}. {step}")

        print("\n" + "=" * 80)
        print("完整报告：")
        print("=" * 80)
        print(report)
    else:
        print(f"❌ 咨询失败：{report}")


async def test_labor_case():
    """测试劳动法案例"""
    print("\n\n" + "=" * 80)
    print("测试3：劳动法案例 - 公司无故辞退")
    print("=" * 80)

    test_question = "公司无故辞退了我，没有支付赔偿金，我该怎么办？"

    result, report = await run_legal_consultation(test_question)

    if result:
        print("\n✅ 咨询成功！\n")
        print(f"分类结果：{result.classification_result}")
        print(f"\n分析（前300字）：\n{result.analysis[:300]}...")
        print(f"\n行动步骤：{result.action_steps}")
    else:
        print(f"❌ 咨询失败：{report}")


async def main():
    """运行所有测试"""
    print("🚀 开始测试重构后的 LangGraph 法律咨询工作流\n")

    # 测试1：简单问题
    await test_simple_question()

    # 测试2：复杂建工纠纷
    # await test_complex_case()

    # 测试3：劳动法案例
    # await test_labor_case()

    print("\n\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
