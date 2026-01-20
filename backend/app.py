from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import os
import asyncio
from enum import Enum
import json

# 导入各个AI功能模块
from contract_review_graph import run_contract_review
from legal_consultation_graph import run_legal_consultation, ConsultationTypeClassification  # 导入新的分类结果
from legal_rag_system import create_legal_rag_system

app = FastAPI(title="Legal Document Assistant API", version="1.0.0")

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模拟数据库存储
contract_storage = {}
review_results = {}
consultation_results = {}
uploaded_files = {}  # 存储上传的文件信息：{file_id: {filename, file_path, content, metadata}}

class ContractUploadResponse(BaseModel):
    contract_id: int
    message: str = "上传成功"

class ContractMetadata(BaseModel):
    contract_name: Optional[str] = None
    parties: Optional[str] = None
    amount: Optional[str] = None
    contract_type: Optional[str] = None
    core_terms: Optional[str] = None

class MetadataResponse(BaseModel):
    metadata: ContractMetadata

class ReviewItem(BaseModel):
    id: int
    issue_type: str
    quote: str
    explanation: str
    suggestion: str
    severity: str
    action_type: str
    item_status: str

class ReviewResult(BaseModel):
    status: str
    review_items: List[ReviewItem]

class ReviewRequest(BaseModel):
    stance: str
    metadata: ContractMetadata

class ReviewResponse(BaseModel):
    message: str

# 咨询请求和响应模型
class ConsultationRequest(BaseModel):
    question: str
    context: Dict[str, Any] = {}
    uploaded_files: Optional[List[str]] = None  # 已上传文件ID列表

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_type: str
    content_preview: str  # 文件内容预览
    message: str

class ConsultationResponse(BaseModel):
    answer: str
    specialist_role: Optional[str] = None
    primary_type: Optional[str] = None
    confidence: Optional[float] = None
    relevant_laws: Optional[List[str]] = None
    need_confirmation: Optional[bool] = None  # 是否需要用户确认转向专业律师
    response: Optional[str] = None  # 保持兼容性
    follow_up_questions: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None
    action_buttons: Optional[List[Dict[str, str]]] = None

@app.post("/api/consultation/upload", response_model=FileUploadResponse)
async def upload_consultation_file(file: UploadFile = File(...)):
    """
    上传文件用于法律咨询
    支持的格式：.pdf, .docx, .doc, .txt
    """
    # 验证文件类型
    file_extension = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    supported_formats = ["pdf", "docx", "doc", "txt"]

    if file_extension not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式。支持的格式：{', '.join(supported_formats)}"
        )

    # 生成文件ID
    file_id = str(uuid.uuid4())

    # 创建上传目录
    upload_dir = "uploads/consultation"
    os.makedirs(upload_dir, exist_ok=True)

    # 保存文件
    file_location = f"{upload_dir}/{file_id}.{file_extension}"

    try:
        with open(file_location, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败：{str(e)}")

    # 使用统一文档服务提取内容
    try:
        from app.services.unified_document_service import get_unified_document_service
        doc_service = get_unified_document_service()

        # 处理文档
        result = doc_service.process_document(
            file_path=file_location,
            extract_content=True,
            extract_metadata=True
        )

        if result.status.value == "success":
            # 提取成功
            content_preview = result.content[:500] if len(result.content) > 500 else result.content
            if len(result.content) > 500:
                content_preview += "..."

            # 存储文件信息
            uploaded_files[file_id] = {
                "file_id": file_id,
                "filename": file.filename,
                "file_path": file_location,
                "file_type": file_extension,
                "content": result.content,
                "metadata": result.metadata,
                "uploaded_at": str(asyncio.get_event_loop().time())
            }

            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                file_type=file_extension,
                content_preview=content_preview,
                message=f"文件上传成功，已提取 {len(result.content)} 个字符"
            )
        else:
            # 提取失败
            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                file_type=file_extension,
                content_preview="",
                message=f"文件上传成功，但内容提取失败：{result.error}"
            )

    except Exception as e:
        # 文档服务不可用，只保存文件
        uploaded_files[file_id] = {
            "file_id": file_id,
            "filename": file.filename,
            "file_path": file_location,
            "file_type": file_extension,
            "content": "",
            "metadata": {},
            "uploaded_at": str(asyncio.get_event_loop().time())
        }

        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_type=file_extension,
            content_preview="",
            message=f"文件上传成功，但文档处理服务不可用"
        )


@app.get("/api/consultation/file/{file_id}")
async def get_consultation_file(file_id: str):
    """获取已上传文件的信息"""
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="文件未找到")

    file_info = uploaded_files[file_id]
    return {
        "file_id": file_info["file_id"],
        "filename": file_info["filename"],
        "file_type": file_info["file_type"],
        "content": file_info["content"],
        "metadata": file_info["metadata"]
    }


@app.delete("/api/consultation/file/{file_id}")
async def delete_consultation_file(file_id: str):
    """删除已上传的文件"""
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="文件未找到")

    file_info = uploaded_files[file_id]

    # 删除物理文件
    try:
        if os.path.exists(file_info["file_path"]):
            os.remove(file_info["file_path"])
    except Exception as e:
        print(f"删除文件失败：{str(e)}")

    # 删除记录
    del uploaded_files[file_id]

    return {"message": "文件删除成功"}


@app.post("/api/consultation", response_model=ConsultationResponse)
async def legal_consultation(request: ConsultationRequest):
    """法律咨询API - 实现两阶段咨询流程，支持文件内容分析"""
    # 收集已上传文件的内容
    file_contents = []
    file_metadata = []

    if request.uploaded_files:
        for file_id in request.uploaded_files:
            if file_id in uploaded_files:
                file_info = uploaded_files[file_id]
                # 文件信息通过 context.uploaded_files 传递给文档分析节点
                # 不再将完整内容添加到 question 中，避免 LLM 复述
                if file_info.get("content"):
                    file_metadata.append({
                        "filename": file_info["filename"],
                        "file_type": file_info["file_type"]
                    })

    # 不再将完整文件内容添加到问题中，避免专业律师节点复述
    # 文件内容通过 context.uploaded_files 传递给文档分析节点处理
    enhanced_question = request.question

    # 更新上下文
    enhanced_context = request.context.copy()
    if file_metadata:
        enhanced_context["uploaded_files"] = file_metadata
        enhanced_context["has_file_content"] = True

    # 调用LangGraph法律咨询工作流
    consultation_result, final_advice = run_legal_consultation(
        enhanced_question,
        enhanced_context
    )
    
    if consultation_result:
        # 从咨询结果中提取信息
        advice = consultation_result.advice
        classification_result = getattr(consultation_result, 'classification_result', None)
        
        # 构建响应
        response_content = f"问题：{advice.question}\n\n法律依据：{advice.legal_basis}\n\n分析：{advice.analysis}\n\n建议：{advice.advice}\n\n风险提醒：{advice.risk_warning}\n\n行动步骤：{', '.join(advice.action_steps)}"
        
        # 如果有分类结果，使用它；否则使用默认值
        if hasattr(consultation_result, 'classification_result'):
            primary_type = classification_result.primary_type
            specialist_role = classification_result.specialist_role
            confidence = classification_result.confidence
            need_confirmation = classification_result.need_confirmation
            relevant_laws = classification_result.relevant_laws
        else:
            # 使用模拟值（在实际实现中，需要从工作流状态中获取这些值）
            primary_type = "合同法"
            specialist_role = "专业律师"
            confidence = 0.9
            need_confirmation = True
            relevant_laws = ["合同法", "民法典"]
        
        return ConsultationResponse(
            answer=response_content,
            specialist_role=specialist_role,
            primary_type=primary_type,
            confidence=confidence,
            relevant_laws=relevant_laws,
            need_confirmation=need_confirmation,
            response=response_content  # 保持兼容性
        )
    else:
        raise HTTPException(status_code=500, detail="咨询失败")

# 模拟合同ID生成器
contract_id_counter = 0

@app.post("/api/contract/upload", response_model=ContractUploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    global contract_id_counter
    contract_id_counter += 1
    
    # 模拟文件处理
    file_extension = file.filename.split(".")[-1]
    if file_extension not in ["docx", "pdf"]:
        raise HTTPException(status_code=400, detail="仅支持 .docx 或 .pdf 文件")
    
    # 保存文件（实际应用中应保存到存储系统）
    file_id = str(uuid.uuid4())
    file_location = f"uploads/{file_id}.{file_extension}"
    
    # 创建上传目录
    os.makedirs("uploads", exist_ok=True)
    
    with open(file_location, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 存储合同信息
    contract_storage[contract_id_counter] = {
        "file_id": file_id,
        "filename": file.filename,
        "file_location": file_location,
        "status": "uploaded"
    }
    
    # 模拟OnlyOffice配置（实际应用中应根据需求生成）
    config = {
        "document": {
            "title": file.filename
        },
        "documentType": "word" if file_extension == "docx" else "word",
        "editorConfig": {
            "callbackUrl": f"http://localhost:8000/api/contract/{contract_id_counter}/callback"
        }
    }
    
    return ContractUploadResponse(
        contract_id=contract_id_counter,
        message="上传成功"
    )

@app.get("/api/contract/{contract_id}/metadata", response_model=MetadataResponse)
async def extract_contract_metadata(contract_id: int):
    if contract_id not in contract_storage:
        raise HTTPException(status_code=404, detail="合同未找到")
    
    # 模拟元数据提取（实际应用中应使用AI模型进行提取）
    metadata = ContractMetadata(
        contract_name="技术服务合同",
        parties="甲方：某科技公司；乙方：某咨询公司",
        amount="人民币 500,000 元",
        contract_type="技术服务合同",
        core_terms="技术开发、服务期限12个月、保密条款"
    )
    
    return MetadataResponse(metadata=metadata)

@app.post("/api/contract/{contract_id}/deep-review", response_model=ReviewResponse)
async def start_deep_review(contract_id: int, request: ReviewRequest, background_tasks: BackgroundTasks):
    if contract_id not in contract_storage:
        raise HTTPException(status_code=404, detail="合同未找到")
    
    # 启动后台任务执行AI审查
    background_tasks.add_task(process_contract_review, contract_id, request)
    
    # 初始化审查结果
    review_results[contract_id] = {
        "status": "processing",
        "review_items": []
    }
    
    return ReviewResponse(message="深度审查已启动")

def process_contract_review(contract_id: int, request: ReviewRequest):
    """在后台处理合同审查"""
    import time
    
    # 模拟从存储中获取合同内容（实际应用中需要解析文件内容）
    contract_text = "甲方：某某科技有限公司\n乙方：某某服务有限公司\n\n甲方委托乙方提供技术服务，服务期限为一年，服务费用为100万元。\n\n乙方应在合同签署后3日内支付全部款项。\n甲方违约需支付双倍赔偿。\n所有开发成果归乙方所有。"
    
    # 调用LangGraph合同审查工作流
    review_result, final_report = run_contract_review(
        contract_text, 
        request.metadata.dict(), 
        request.stance
    )
    
    if review_result:
        # 将结果转换为API格式
        review_items = []
        for i, issue in enumerate(review_result.issues):
            review_items.append(ReviewItem(
                id=i+1,
                issue_type=issue.issue_type,
                quote=issue.quote,
                explanation=issue.explanation,
                suggestion=issue.suggestion,
                severity=issue.severity,
                action_type=issue.action_type,
                item_status="pending"
            ))
        
        # 更新审查结果
        review_results[contract_id] = {
            "status": "waiting_human",
            "review_items": review_items
        }
    else:
        # 审查失败
        review_results[contract_id] = {
            "status": "error",
            "review_items": []
        }

@app.get("/api/contract/{contract_id}/review-results", response_model=ReviewResult)
async def get_review_results(contract_id: int):
    if contract_id not in contract_storage:
        raise HTTPException(status_code=404, detail="合同未找到")
    
    if contract_id not in review_results:
        raise HTTPException(status_code=404, detail="审查结果未找到")
    
    return review_results[contract_id]

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "legal-document-assistant-api"}

# ==================== 费用计算相关模型 ====================

class CostCalculationRequest(BaseModel):
    case_type: str  # 案件类型
    case_description: str  # 案件描述
    case_amount: Optional[float] = None  # 案件标的额
    context: Optional[Dict[str, Any]] = None  # 上下文信息

class CostItemResponse(BaseModel):
    name: str
    description: str
    amount: float
    unit: str
    quantity: float

class CostCalculationResponse(BaseModel):
    total_cost: float
    cost_breakdown: List[CostItemResponse]
    calculation_basis: str
    disclaimer: str

# ==================== 费用计算API ====================

@app.post("/api/cost-calculation", response_model=CostCalculationResponse)
async def calculate_cost(request: CostCalculationRequest):
    """费用计算API"""
    try:
        from cost_calculation import run_cost_calculation

        result = run_cost_calculation(
            case_type=request.case_type,
            case_description=request.case_description,
            case_amount=request.case_amount,
            context=request.context
        )

        # 转换 cost_breakdown 中的 CostItem 为响应模型
        cost_breakdown_response = [
            CostItemResponse(
                name=item.name,
                description=item.description,
                amount=item.amount,
                unit=item.unit,
                quantity=item.quantity
            )
            for item in result.cost_breakdown
        ]

        return CostCalculationResponse(
            total_cost=result.total_cost,
            cost_breakdown=cost_breakdown_response,
            calculation_basis=result.calculation_basis,
            disclaimer=result.disclaimer
        )
    except Exception as e:
        print(f"费用计算错误: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"费用计算失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)