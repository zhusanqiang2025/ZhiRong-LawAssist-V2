import os
import httpx
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
import json
import re

# ================= 配置区 =================
# 从 Settings 获取 API 配置（统一使用 QWEN3_API_*）
from app.core.config import settings
API_KEY = settings.QWEN3_API_KEY
API_BASE_URL = settings.QWEN3_API_BASE
MODEL_NAME = settings.QWEN3_MODEL
# =========================================

# --- 1. 定义数据结构 ---

class CostItem(BaseModel):
    """费用项"""
    name: str = Field(description="费用项目名称")
    description: str = Field(description="费用项目描述")
    amount: float = Field(description="费用金额")
    unit: str = Field(description="费用单位")
    quantity: float = Field(description="数量")

class CostCalculationResult(BaseModel):
    """费用计算结果"""
    total_cost: float = Field(description="总费用")
    cost_breakdown: List[CostItem] = Field(description="费用明细")
    calculation_basis: str = Field(description="计算依据")
    disclaimer: str = Field(description="免责声明")

class CostCalculationRequest(BaseModel):
    """费用计算请求"""
    case_type: str = Field(description="案件类型，如合同纠纷、劳动争议、知识产权等")
    case_description: str = Field(description="案件简要描述")
    case_amount: Optional[float] = Field(description="案件标的额（如有）")
    context: Optional[Dict[str, Any]] = Field(description="上下文信息")


# --- 2. 费用计算工具函数 ---

def calculate_litigation_fee(amount: Optional[float]) -> tuple:
    """
    根据《诉讼费用交纳办法》计算诉讼费
    参数: amount - 案件标的额
    返回: (费用金额, 计算说明)
    """
    if amount is None or amount <= 0:
        # 非财产案件
        return 300, "非财产案件，按件收取诉讼费"

    # 根据标的额分段计算
    if amount <= 10000:
        fee = 50
        desc = f"财产案件，标的额{amount:.2f}元，不超过1万元，每件交纳50元"
    elif amount <= 100000:
        fee = amount * 0.025 - 200
        desc = f"财产案件，标的额{amount:.2f}元，1万-10万元部分按2.5%交纳，速算扣除200元"
    elif amount <= 200000:
        fee = amount * 0.02 + 300
        desc = f"财产案件，标的额{amount:.2f}元，10万-20万元部分按2%交纳，速算增加300元"
    elif amount <= 500000:
        fee = amount * 0.015 + 1300
        desc = f"财产案件，标的额{amount:.2f}元，20万-50万元部分按1.5%交纳，速算增加1300元"
    elif amount <= 1000000:
        fee = amount * 0.01 + 3800
        desc = f"财产案件，标的额{amount:.2f}元，50万-100万元部分按1%交纳，速算增加3800元"
    elif amount <= 2000000:
        fee = amount * 0.009 + 4800
        desc = f"财产案件，标的额{amount:.2f}元，100万-200万元部分按0.9%交纳，速算增加4800元"
    elif amount <= 5000000:
        fee = amount * 0.008 + 6800
        desc = f"财产案件，标的额{amount:.2f}元，200万-500万元部分按0.8%交纳，速算增加6800元"
    elif amount <= 10000000:
        fee = amount * 0.007 + 11800
        desc = f"财产案件，标的额{amount:.2f}元，500万-1000万元部分按0.7%交纳，速算增加11800元"
    elif amount <= 20000000:
        fee = amount * 0.006 + 21800
        desc = f"财产案件，标的额{amount:.2f}元，1000万-2000万元部分按0.6%交纳，速算增加21800元"
    else:
        fee = amount * 0.005 + 41800
        desc = f"财产案件，标的额{amount:.2f}元，超过2000万元部分按0.5%交纳，速算增加41800元"

    return fee, desc


def calculate_preservation_fee(amount: Optional[float]) -> tuple:
    """
    计算保全费
    参数: amount - 保全财产金额
    返回: (费用金额, 计算说明)
    """
    if amount is None or amount <= 0:
        return 30, "不涉及财产数额，每件交纳30元"

    # 保全费最多不超过5000元
    if amount <= 1000:
        fee = 30
        desc = f"保全财产金额{amount:.2f}元，不超过1000元，每件交纳30元"
    elif amount <= 100000:
        fee = amount * 0.01 + 20
        desc = f"保全财产金额{amount:.2f}元，1000元-10万元部分按1%交纳，速算增加20元"
    else:
        fee = amount * 0.005 + 520
        desc = f"保全财产金额{amount:.2f}元，超过10万元部分按0.5%交纳，速算增加520元"

    # 保全费最多不超过5000元
    if fee > 5000:
        fee = 5000
        desc += "，但保全费最多不超过5000元"

    return fee, desc


def calculate_execution_fee(amount: Optional[float]) -> tuple:
    """
    计算执行费
    参数: amount - 执行金额
    返回: (费用金额, 计算说明)
    """
    if amount is None or amount <= 0:
        return 50, "没有执行金额，每件交纳50元"

    if amount <= 10000:
        fee = 50
        desc = f"执行金额{amount:.2f}元，不超过1万元，每件交纳50元"
    elif amount <= 500000:
        fee = amount * 0.015 - 100
        desc = f"执行金额{amount:.2f}元，1万-50万元部分按1.5%交纳，速算扣除100元"
    elif amount <= 5000000:
        fee = amount * 0.01 + 2400
        desc = f"执行金额{amount:.2f}元，50万-500万元部分按1%交纳，速算增加2400元"
    elif amount <= 10000000:
        fee = amount * 0.005 + 27400
        desc = f"执行金额{amount:.2f}元，500万-1000万元部分按0.5%交纳，速算增加27400元"
    else:
        fee = amount * 0.001 + 67400
        desc = f"执行金额{amount:.2f}元，超过1000万元部分按0.1%交纳，速算增加67400元"

    return fee, desc


def calculate_appraisal_fee(amount: Optional[float]) -> tuple:
    """
    计算鉴定费（按司法鉴定收费管理办法估算）
    参数: amount - 鉴定标的额
    返回: (费用金额, 计算说明)
    """
    if amount is None or amount <= 0:
        # 如果没有标的额，按照固定费用估算
        return 3000, "不涉及具体标的额，按常见鉴定费用估算"

    # 按照标的额分段计算鉴定费
    fee = 0
    remaining = amount

    if remaining > 0:
        if remaining <= 100000:
            fee += remaining * 0.02  # 假设10万以下按2%收取
            remaining = 0
        else:
            fee += 100000 * 0.02  # 前10万按2%
            remaining -= 100000

    if remaining > 0:
        if remaining <= 400000:  # 10万到50万之间
            fee += remaining * 0.01  # 按1%收取
            remaining = 0
        else:
            fee += 400000 * 0.01  # 10万到50万之间按1%
            remaining -= 400000

    if remaining > 0:
        if remaining <= 500000:  # 50万到100万之间
            fee += remaining * 0.008  # 按0.8%收取
            remaining = 0
        else:
            fee += 500000 * 0.008  # 50万到100万之间按0.8%
            remaining -= 500000

    if remaining > 0:
        if remaining <= 1000000:  # 100万到200万之间
            fee += remaining * 0.006  # 按0.6%收取
            remaining = 0
        else:
            fee += 1000000 * 0.006  # 100万到200万之间按0.6%
            remaining -= 1000000

    if remaining > 0:
        if remaining <= 3000000:  # 200万到500万之间
            fee += remaining * 0.004  # 按0.4%收取
            remaining = 0
        else:
            fee += 3000000 * 0.004  # 200万到500万之间按0.4%
            remaining -= 3000000

    if remaining > 0:
        fee += remaining * 0.002  # 超过500万部分按0.2%

    # 鉴定费一般不会低于1000元
    if fee < 1000:
        fee = 1000

    # 鉴定费一般也不会超过50000元（除非是特别复杂的案件）
    if fee > 50000:
        fee = 50000

    return fee, f"鉴定费根据鉴定标的额{amount:.2f}元估算"


def calculate_lawyer_fee(amount: Optional[float], case_type: str) -> tuple:
    """
    估算律师费（按通用标准估算）
    参数: amount - 案件标的额, case_type - 案件类型
    返回: (费用金额, 计算说明)
    """
    if amount is None or amount <= 0:
        # 没有标的额的案件，按件收费或基础费用
        if case_type in ["劳动争议", "刑事辩护", "婚姻家庭"]:
            fee = 5000  # 劳动争议、刑事辩护、婚姻家庭等按件收费
            desc = f"{case_type}案件，无明确标的额，按件收取律师费约5000元"
        else:
            fee = 3000  # 其他案件按基础费用收取
            desc = f"{case_type}案件，无明确标的额，按基础律师费约3000元"
    else:
        # 有标的额的案件，按标的额比例收费
        if amount <= 10000:
            fee = 2000  # 最低收费标准
            desc = f"{case_type}案件，标的额{amount:.2f}元，按最低律师费收取约2000元"
        elif amount <= 100000:
            fee = amount * 0.08  # 10万以下按8%
            desc = f"{case_type}案件，标的额{amount:.2f}元，按8%收取律师费"
        elif amount <= 500000:
            fee = amount * 0.07 + 1000  # 10万-50万按7%+1000
            desc = f"{case_type}案件，标的额{amount:.2f}元，按7%+1000收取律师费"
        elif amount <= 1000000:
            fee = amount * 0.06 + 6000  # 50万-100万按6%+6000
            desc = f"{case_type}案件，标的额{amount:.2f}元，按6%+6000收取律师费"
        elif amount <= 5000000:
            fee = amount * 0.05 + 16000  # 100万-500万按5%+16000
            desc = f"{case_type}案件，标的额{amount:.2f}元，按5%+16000收取律师费"
        elif amount <= 10000000:
            fee = amount * 0.04 + 66000  # 500万-1000万按4%+66000
            desc = f"{case_type}案件，标的额{amount:.2f}元，按4%+66000收取律师费"
        else:
            fee = amount * 0.03 + 166000  # 超过1000万按3%+166000
            desc = f"{case_type}案件，标的额{amount:.2f}元，按3%+166000收取律师费"

    # 律师费通常有最低收费标准
    if fee < 2000:
        fee = 2000

    return fee, desc


# --- 3. 初始化模型 ---
def get_model():
    # 创建一个不验证 SSL 的 HTTP 客户端
    http_client = httpx.Client(verify=False, trust_env=False)

    llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=API_KEY,
        base_url=API_BASE_URL,
        temperature=0.1,
        http_client=http_client
    )
    return llm

# --- 4. 费用计算核心逻辑 ---

def calculate_litigation_costs(case_type: str, case_description: str, case_amount: Optional[float] = None) -> CostCalculationResult:
    """
    计算诉讼费用
    """
    print(f"[Cost Calculation] Calculating costs for {case_type}, amount: {case_amount}")

    # 初始化费用明细列表
    cost_breakdown = []

    # 计算诉讼费
    litigation_fee, litigation_desc = calculate_litigation_fee(case_amount)
    cost_breakdown.append(CostItem(
        name="诉讼费",
        description=litigation_desc,
        amount=litigation_fee,
        unit="元",
        quantity=1
    ))

    # 计算保全费（假设需要保全）
    preservation_fee, preservation_desc = calculate_preservation_fee(case_amount)
    cost_breakdown.append(CostItem(
        name="保全费",
        description=preservation_desc,
        amount=preservation_fee,
        unit="元",
        quantity=1
    ))

    # 计算执行费（假设后续需要执行）
    execution_fee, execution_desc = calculate_execution_fee(case_amount)
    cost_breakdown.append(CostItem(
        name="执行费（预估）",
        description=execution_desc,
        amount=execution_fee,
        unit="元",
        quantity=1
    ))

    # 计算鉴定费（根据案件类型判断是否需要）
    appraisal_needed = any(keyword in case_description for keyword in ["鉴定", "评估", "笔迹", "财务", "工程造价"])
    if appraisal_needed or case_type in ["知识产权", "建设工程", "医疗纠纷"]:
        appraisal_fee, appraisal_desc = calculate_appraisal_fee(case_amount)
        cost_breakdown.append(CostItem(
            name="鉴定费",
            description=appraisal_desc,
            amount=appraisal_fee,
            unit="元",
            quantity=1
        ))

    # 计算律师费
    lawyer_fee, lawyer_desc = calculate_lawyer_fee(case_amount, case_type)
    cost_breakdown.append(CostItem(
        name="律师费",
        description=lawyer_desc,
        amount=lawyer_fee,
        unit="元",
        quantity=1
    ))

    # 计算其他可能费用
    other_costs = 0
    other_descriptions = []

    # 根据案件类型添加特定费用
    if "公告" in case_description or "送达" in case_description:
        other_costs += 300  # 公告费
        other_descriptions.append("公告费约300元")

    if "差旅" in case_description or "异地" in case_description or "外地" in case_description:
        other_costs += 2000  # 差旅费
        other_descriptions.append("差旅费约2000元")

    if other_costs > 0:
        cost_breakdown.append(CostItem(
            name="其他费用",
            description="、".join(other_descriptions),
            amount=other_costs,
            unit="元",
            quantity=1
        ))

    # 计算总费用
    total_cost = sum(item.amount for item in cost_breakdown)

    # 生成计算依据说明
    calculation_basis = f"根据《诉讼费用交纳办法》等相关法规，对{case_type}案件进行费用估算。"

    # 生成免责声明
    disclaimer = "此为估算值，实际费用可能因具体情况、地区差异、法院收费标准、律师收费标准等因素而有所不同。建议在实际委托前与律师详细沟通具体收费标准。"

    result = CostCalculationResult(
        total_cost=total_cost,
        cost_breakdown=cost_breakdown,
        calculation_basis=calculation_basis,
        disclaimer=disclaimer
    )

    print(f"[Cost Calculation] Complete. Total cost: {result.total_cost}")

    return result


def run_cost_calculation(case_type: str, case_description: str, case_amount: Optional[float] = None, context: Optional[Dict[str, Any]] = None) -> CostCalculationResult:
    """
    执行费用计算
    """
    print(f"[Cost Calculation] Calculating {case_type}...")

    result = calculate_litigation_costs(case_type, case_description, case_amount)

    print(f"[Cost Calculation] Done. Total: {result.total_cost}")
    return result
