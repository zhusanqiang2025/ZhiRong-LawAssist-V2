from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
# ==========================================
# ✅ 新增导入：静态文件服务
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
# ==========================================
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import os
import asyncio
from enum import Enum

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

# Pydantic 模型定义
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

# 模拟合同ID生成器
contract_id_counter = 0

# ==================== API 接口实现 ====================

@app.post("/api/contract/upload", response_model=ContractUploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    global contract_id_counter
    contract_id_counter += 1
    
    # 模拟文件处理
    file_extension = file.filename.split(".")[-1]
    if file_extension not in ["docx", "pdf"]:
        raise HTTPException(status_code=400, detail="仅支持 .docx 或 .pdf 文件")
    
    # 保存文件
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
    
    return ContractUploadResponse(
        contract_id=contract_id_counter,
        message="上传成功"
    )

@app.get("/api/contract/{contract_id}/metadata", response_model=MetadataResponse)
async def extract_contract_metadata(contract_id: int):
    if contract_id not in contract_storage:
        raise HTTPException(status_code=404, detail="合同未找到")
    
    # 模拟元数据提取
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
    
    review_results[contract_id] = {
        "status": "processing",
        "review_items": []
    }
    
    background_tasks.add_task(process_contract_review, contract_id, request)
    
    return ReviewResponse(message="深度审查已启动")

def process_contract_review(contract_id: int, request: ReviewRequest):
    """在后台处理合同审查"""
    import time
    time.sleep(3)  # 模拟处理时间
    
    sample_review_items = [
        ReviewItem(
            id=1,
            issue_type="付款条款风险",
            quote="乙方应在合同签署后3日内支付全部款项",
            explanation="付款时间过短",
            suggestion="建议修改为30日",
            severity="High",
            action_type="Revision",
            item_status="pending"
        ),
        ReviewItem(
            id=2,
            issue_type="违约责任不对等",
            quote="甲方违约需支付双倍赔偿",
            explanation="不对等",
            suggestion="增加乙方责任",
            severity="Critical",
            action_type="Alert",
            item_status="pending"
        )
    ]
    
    review_results[contract_id] = {
        "status": "waiting_human",
        "review_items": sample_review_items
    }

@app.get("/api/contract/{contract_id}/review-results", response_model=ReviewResult)
async def get_review_results(contract_id: int):
    if contract_id not in contract_storage:
        raise HTTPException(status_code=404, detail="合同未找到")
    
    if contract_id not in review_results:
        return ReviewResult(status="not_started", review_items=[])
    
    result = review_results[contract_id]
    return ReviewResult(
        status=result["status"],
        review_items=result["review_items"]
    )

@app.post("/api/contract/{contract_id}/onlyoffice-config")
async def get_onlyoffice_config(contract_id: int):
    if contract_id not in contract_storage:
        raise HTTPException(status_code=404, detail="合同未找到")
    
    config = {
        "document": {
            "title": contract_storage[contract_id]["filename"],
            "url": f"http://localhost:8000/uploads/{contract_storage[contract_id]['file_id']}.pdf"
        },
        "documentType": "word",
        "editorConfig": {
            "callbackUrl": f"http://localhost:8000/api/contract/{contract_id}/callback"
        }
    }
    
    return {"config": config, "token": "sample_token"}

# =================================================================
# ✅ 新增：前端静态文件托管 (解决 404 问题的核心)
# =================================================================

# 1. 定位前端构建目录
# 当前文件在 backend/main.py，所以需要往上走一级 (..) 找到 frontend/dist
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dist_path = os.path.join(current_dir, "..", "frontend", "dist")

# 打印路径方便调试日志查看
print(f"🔍 正在寻找前端资源: {frontend_dist_path}")

if os.path.exists(frontend_dist_path):
    print(f"✅ 成功加载前端构建目录")
    
    # 2. 挂载静态资源 (JS/CSS/图片)
    # 对应 vite 构建出的 assets 目录
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    # 3. 捕获所有页面路由，返回 index.html
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        # 排除 API 请求
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API Not Found")
        
        # 返回 index.html
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))
else:
    print(f"❌ 警告: 未找到前端构建目录: {frontend_dist_path}")
    print("请确认已执行 npm run build 且已将 dist 目录提交到 Git")

if __name__ == "__main__":
    import uvicorn
    # ✅ 端口改为 7860，匹配 .gitlab-ci.yml 的配置
    print("🚀 启动服务在端口 7860...")
    uvicorn.run(app, host="0.0.0.0", port=7860)