# backend/app/api/cost_calculation_router.py
"""
费用测算 API 路由

提供完整的费用测算服务 API，支持：
1. 上传案件资料
2. AI 提取案件信息（案件类型、当事人、诉讼请求等）
3. 计算各类费用（诉讼费、保全费、执行费、律师费等）
"""
import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.unified_document_service import get_unified_document_service

# 导入费用计算模块
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cost_calculation import calculate_litigation_costs

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Cost Calculation"]
)

UPLOAD_DIR = "storage/uploads/cost_calculation"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== 请求/响应模型 ====================

class CaseExtractionRequest(BaseModel):
    """案件信息提取请求"""
    upload_id: str
    file_names: List[str]


class CostCalculationRequest(BaseModel):
    """费用计算请求（简单版本 - 用于手动输入模式）"""
    case_type: str  # 案件类型（英文代码，如 contract_dispute, labor_dispute 等）
    case_description: str  # 案件描述
    case_amount: Optional[float] = None  # 案件标的额
    context: Optional[Dict[str, Any]] = None  # 上下文信息


class CaseInfo(BaseModel):
    """案件信息"""
    case_type: str  # 案件类型
    case_description: str  # 案件概况
    parties: List[str]  # 当事人信息
    litigation_requests: List[str]  # 诉讼请求
    case_amount: Optional[float] = None  # 标的额
    procedural_position: Optional[str] = None  # 程序地位（一审/二审/再审）
    case_nature: Optional[str] = None  # 案件性质（民事/刑事/行政）


class CostCalculationRequestV2(BaseModel):
    """费用计算请求 V2"""
    case_info: CaseInfo
    stance: str  # 立场：plaintiff(原告)/defendant(被告)/applicant(申请人)/respondent(被申请人)
    include_lawyer_fee: bool = True  # 是否计算律师费
    lawyer_fee_basis: Optional[str] = None  # 律师费计费依据（用户上传）
    lawyer_fee_rate: Optional[float] = None  # 律师费率（%）


class CostItem(BaseModel):
    """费用项"""
    name: str
    description: str
    amount: float
    unit: str = "元"
    quantity: float = 1


class CostCalculationResponseV2(BaseModel):
    """费用计算响应 V2"""
    success: bool
    total_cost: float
    cost_breakdown: List[CostItem]
    calculation_basis: str
    disclaimer: str
    warnings: List[str] = []


class FileInfo(BaseModel):
    """文件信息"""
    file_id: str
    filename: str
    file_type: str
    upload_time: str


class UploadResponse(BaseModel):
    """上传响应"""
    success: bool
    upload_id: str
    files: List[FileInfo]
    message: str


class ExtractionResponse(BaseModel):
    """信息提取响应"""
    success: bool
    case_info: Optional[CaseInfo] = None
    error: Optional[str] = None
    warnings: List[str] = []


# ==================== API 端点 ====================

@router.post("/upload", response_model=UploadResponse)
async def upload_case_documents(
    files: List[UploadFile] = File(...)
):
    """
    上传案件资料

    支持上传多个文件，包括起诉状、答辩状、证据材料等。
    返回 upload_id 用于后续的信息提取和费用计算。

    支持的文件格式：.docx, .doc, .pdf, .txt, .jpg, .jpeg, .png
    """
    try:
        upload_id = f"upload_{uuid.uuid4().hex[:12]}"
        uploaded_files = []

        for file in files:
            # 验证文件类型
            file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
            allowed_types = ["docx", "doc", "pdf", "txt", "jpg", "jpeg", "png"]

            if file_ext not in allowed_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(allowed_types)}"
                )

            # 保存文件
            unique_name = f"{upload_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
            file_path = os.path.join(UPLOAD_DIR, unique_name)

            with open(file_path, "wb") as buffer:
                from shutil import copyfileobj
                copyfileobj(file.file, buffer)

            uploaded_files.append(FileInfo(
                file_id=unique_name,
                filename=file.filename,
                file_type=file_ext,
                upload_time=datetime.now().isoformat()
            ))

        logger.info(f"[CostCalculation] 上传成功: upload_id={upload_id}, 文件数={len(files)}")

        return UploadResponse(
            success=True,
            upload_id=upload_id,
            files=uploaded_files,
            message=f"成功上传 {len(files)} 个文件"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CostCalculation] 上传失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/extract", response_model=ExtractionResponse)
async def extract_case_info(request: CaseExtractionRequest):
    """
    提取案件信息

    使用统一文档服务处理上传的文件，AI 提取以下信息：
    - 案件类型
    - 当事人信息
    - 诉讼请求（核心）
    - 案件概况
    - 标的额
    """
    try:
        doc_service = get_unified_document_service()
        all_content = []
        warnings = []

        # 处理所有上传的文件
        for file_name in request.file_names:
            file_path = os.path.join(UPLOAD_DIR, file_name)

            if not os.path.exists(file_path):
                warnings.append(f"文件不存在: {file_name}")
                continue

            # 使用统一文档服务提取文本
            result = doc_service.process_document(file_path)

            if result.status.value == "success":
                all_content.append(result.content)
                logger.info(f"[CostCalculation] 文件处理成功: {file_name}")
            elif result.status.value == "partial":
                all_content.append(result.content)
                warnings.extend(result.warnings)
                logger.warning(f"[CostCalculation] 文件部分成功: {file_name}")
            else:
                warnings.append(f"文件处理失败: {file_name} - {result.error}")

        if not all_content:
            return ExtractionResponse(
                success=False,
                case_info=None,
                error="未能从任何文件中提取内容",
                warnings=warnings
            )

        # 合并所有内容
        combined_content = "\n\n".join(all_content)

        # 使用 AI 提取结构化信息
        case_info = await _extract_case_info_with_ai(combined_content)

        logger.info(f"[CostCalculation] 信息提取完成: 案件类型={case_info.case_type}")

        return ExtractionResponse(
            success=True,
            case_info=case_info,
            warnings=warnings
        )

    except Exception as e:
        logger.error(f"[CostCalculation] 信息提取失败: {str(e)}", exc_info=True)
        return ExtractionResponse(
            success=False,
            case_info=None,
            error=f"信息提取失败: {str(e)}",
            warnings=warnings
        )


@router.post("/", response_model=CostCalculationResponseV2)
async def calculate_costs_simple(request: CostCalculationRequest):
    """
    计算费用（简单版本 - 用于手动输入模式）

    根据输入的案件信息计算各类费用。
    这是一个简化版本，直接根据表单输入计算，不需要文件上传和AI提取。
    """
    try:
        logger.info(f"[CostCalculation] 开始计算费用(简单模式): 案件类型={request.case_type}, 标的额={request.case_amount}")

        # 案件类型映射（前端使用英文value，需要转换为中文）
        case_type_map = {
            'contract_dispute': '合同纠纷',
            'labor_dispute': '劳动争议',
            'intellectual_property': '知识产权',
            'marriage_family': '婚姻家庭',
            'traffic_accident': '交通事故',
            'criminal_case': '刑事案件',
            'administrative_litigation': '行政诉讼',
            'real_estate_dispute': '房产纠纷',
            'construction_project': '建设工程',
            'medical_dispute': '医疗纠纷',
            'company_law': '公司法务',
            'other': '其他类型'
        }

        # 转换案件类型为中文
        case_type_cn = case_type_map.get(request.case_type, request.case_type)

        # 调用原有的费用计算逻辑
        result = calculate_litigation_costs(
            case_type=case_type_cn,
            case_description=request.case_description,
            case_amount=request.case_amount
        )

        logger.info(f"[CostCalculation] 计算完成: 总费用={result.total_cost}")

        return CostCalculationResponseV2(
            success=True,
            total_cost=result.total_cost,
            cost_breakdown=[
                CostItem(
                    name=item.name,
                    description=item.description,
                    amount=item.amount,
                    unit=item.unit,
                    quantity=item.quantity
                )
                for item in result.cost_breakdown
            ],
            calculation_basis=result.calculation_basis,
            disclaimer=result.disclaimer,
            warnings=[]
        )

    except Exception as e:
        logger.error(f"[CostCalculation] 费用计算失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"费用计算失败: {str(e)}")


@router.post("/calculate-v2", response_model=CostCalculationResponseV2)
async def calculate_costs_v2(request: CostCalculationRequestV2):
    """
    计算费用（V2 版本）

    根据提取的案件信息和用户立场，计算各类费用：

    对公费用（法院收取）：
    - 诉讼费：根据标的额按《诉讼费用交纳办法》计算
    - 保全费：根据保全金额计算
    - 执行费：根据执行金额计算
    - 鉴定费：根据案件类型估算

    律师费：
    - 如果用户上传了计费依据，按依据计算
    - 否则按通用标准估算
    """
    try:
        case_info = request.case_info
        stance = request.stance

        logger.info(f"[CostCalculation] 开始计算费用: 案件类型={case_info.case_type}, 立场={stance}")

        # 调用原有的费用计算逻辑
        result = calculate_litigation_costs(
            case_type=case_info.case_type,
            case_description=case_info.case_description,
            case_amount=case_info.case_amount
        )

        # 如果有律师费计费依据，重新计算律师费
        if request.include_lawyer_fee and request.lawyer_fee_basis:
            result = _recalculate_lawyer_fee(
                result,
                request.lawyer_fee_basis,
                request.lawyer_fee_rate,
                case_info.case_amount
            )

        # 根据立场调整费用说明
        warnings = []
        if stance in ["defendant", "respondent"]:
            warnings.append("作为被告/被申请人，可能需要承担对方律师费（如败诉）")

        logger.info(f"[CostCalculation] 计算完成: 总费用={result.total_cost}")

        return CostCalculationResponseV2(
            success=True,
            total_cost=result.total_cost,
            cost_breakdown=[
                CostItem(
                    name=item.name,
                    description=item.description,
                    amount=item.amount,
                    unit=item.unit,
                    quantity=item.quantity
                )
                for item in result.cost_breakdown
            ],
            calculation_basis=result.calculation_basis,
            disclaimer=result.disclaimer,
            warnings=warnings
        )

    except Exception as e:
        logger.error(f"[CostCalculation] 费用计算失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"费用计算失败: {str(e)}")


# ==================== 辅助函数 ====================

async def _extract_case_info_with_ai(content: str) -> CaseInfo:
    """
    使用 AI 从文档内容中提取案件信息

    提取字段：
    - case_type: 案件类型
    - parties: 当事人（原告、被告等）
    - litigation_requests: 诉讼请求（核心）
    - case_description: 案件概况
    - case_amount: 标的额
    - procedural_position: 程序地位
    """
    import json
    import os
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    import httpx

    # 创建 LLM - 使用现有配置
    http_client = httpx.Client(verify=False, trust_env=False)

    # 优先使用 Qwen3 Thinking 模型，其次使用 DeepSeek
    api_key = os.getenv("QWEN3_THINKING_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "your-api-key-here"
    base_url = os.getenv("QWEN3_THINKING_API_URL") or os.getenv("DEEPSEEK_API_URL") or "https://api.openai.com/v1"
    model_name = os.getenv("QWEN3_THINKING_MODEL") or os.getenv("MODEL_NAME") or "gpt-4o-mini"

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.1,
        http_client=http_client
    )

    # 构建提取提示词
    system_prompt = """你是一个专业的法律文书分析助手。请从提供的法律文书内容中提取关键信息，并以 JSON 格式返回。

请提取以下信息：
1. case_type: 案件类型（如：合同纠纷、劳动争议、知识产权、婚姻家庭、交通事故、刑事案件、行政诉讼、房产纠纷、建设工程、医疗纠纷、公司法务等）
2. case_description: 案件概况（简洁描述案件基本情况）
3. parties: 当事人列表（提取所有当事人名称，包括原告、被告、申请人、被申请人等）
4. litigation_requests: 诉讼请求列表（提取所有诉讼请求，这是最核心的信息）
5. case_amount: 标的额（如果有明确的金额，提取为数字；如果没有，设为 null）
6. procedural_position: 程序地位（一审/二审/再审，如果无法判断设为 null）
7. case_nature: 案件性质（民事/刑事/行政，如果无法判断设为 null）

返回格式要求：
- 必须是有效的 JSON 格式
- 所有字符串必须用双引号包裹
- litigation_requests 必须是数组，包含每个诉讼请求
- parties 必须是数组，包含每个当事人名称
- case_amount 如果提取到，必须是数字类型（不要带单位），否则为 null
"""

    user_prompt = f"""请从以下法律文书内容中提取案件信息：

{content[:8000]}

请以 JSON 格式返回提取的信息。"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    response = await llm.ainvoke(messages)
    response_text = response.content

    # 解析 JSON 响应
    try:
        # 尝试提取 JSON 部分
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()

        data = json.loads(json_str)

        # 验证和清理数据
        case_type = data.get("case_type", "其他")
        case_description = data.get("case_description", "")[:500]  # 限制长度
        parties = data.get("parties", [])
        litigation_requests = data.get("litigation_requests", [])
        case_amount = data.get("case_amount")
        procedural_position = data.get("procedural_position")
        case_nature = data.get("case_nature")

        # 确保 parties 和 litigation_requests 是列表
        if not isinstance(parties, list):
            parties = [str(parties)]
        if not isinstance(litigation_requests, list):
            litigation_requests = [str(litigation_requests)]

        return CaseInfo(
            case_type=case_type,
            case_description=case_description,
            parties=parties[:10],  # 限制数量
            litigation_requests=litigation_requests[:20],  # 限制数量
            case_amount=float(case_amount) if case_amount and isinstance(case_amount, (int, float)) else None,
            procedural_position=procedural_position,
            case_nature=case_nature
        )

    except Exception as e:
        logger.error(f"[CostCalculation] AI 解析失败: {str(e)}")

        # 返回默认值
        return CaseInfo(
            case_type="其他",
            case_description=content[:200],
            parties=[],
            litigation_requests=[],
            case_amount=None,
            procedural_position=None,
            case_nature="民事"
        )


def _recalculate_lawyer_fee(
    original_result,
    fee_basis: str,
    fee_rate: Optional[float],
    case_amount: Optional[float]
):
    """
    根据用户提供的计费依据重新计算律师费

    Args:
        original_result: 原始计算结果
        fee_basis: 计费依据描述
        fee_rate: 律师费率（百分比）
        case_amount: 标的额
    """
    # 导入 cost_calculation 模块的 CostItem（避免与路由模型的 CostItem 冲突）
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from cost_calculation import CostItem as CalcCostItem, calculate_lawyer_fee

    # 移除原有的律师费
    new_breakdown = [
        item for item in original_result.cost_breakdown
        if item.name != "律师费"
    ]

    # 根据计费依据计算
    if case_amount and fee_rate:
        lawyer_fee = case_amount * (fee_rate / 100)
        description = f"根据用户提供的计费依据（{fee_basis}），按标的额的 {fee_rate}% 计算"
    elif fee_basis:
        # 如果只有依据没有费率，估算
        if "风险代理" in fee_basis:
            lawyer_fee = case_amount * 0.15 if case_amount else 10000
            description = f"根据用户提供的风险代理依据（{fee_basis}），按15%估算"
        else:
            lawyer_fee = 15000
            description = f"根据用户提供的计费依据（{fee_basis}），估算律师费"
    else:
        # 使用原有逻辑
        lawyer_fee, description = calculate_lawyer_fee(case_amount, "其他")

    new_breakdown.append(CalcCostItem(
        name="律师费",
        description=description,
        amount=lawyer_fee,
        unit="元",
        quantity=1
    ))

    # 重新计算总费用
    total_cost = sum(item.amount for item in new_breakdown)

    # 返回新结果
    from dataclasses import replace
    return replace(
        original_result,
        cost_breakdown=new_breakdown,
        total_cost=total_cost
    )


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "cost-calculation",
        "version": "2.0.0"
    }
