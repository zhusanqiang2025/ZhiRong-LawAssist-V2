from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

app = FastAPI(
    title="Gradio资产估值API",
    description="提供土地估值计算和敏感性分析功能的API接口",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 基础数据模型（用于请求验证）
class InfoExtractionRequest(BaseModel):
    project_id: str

class UploadRequest(BaseModel):
    file_paths: List[str]
    file_type: Optional[str] = None

class BatchUpdateRequest(BaseModel):
    updates: List[Dict[str, Any]]

class ParseTaskRequest(BaseModel):
    project_id: str
    file_ids: Optional[List[str]] = None
    parse_type: str = "all"
    priority: int = 5

# 固定假数据
FAKE_LAND_INFO = {
    "land_area_square_meters": [63825],
    "land_area_mu": [95.74],
    "floor_area_ratio": ["2.5"],
    "calculable_area": ["159562.5"],
    "commercial_ratio_lower_limit": "0.3",
    "residential_area": ["111693.75"],
    "commercial_area": ["47868.75"],
    "address": "山东省聊城市阳谷县阳谷伏城文化路南侧 金光大道西侧"
}

FAKE_LEGAL_INFO = {
    "right_holder_name": "阳谷瑞璟置业有限公司",
    "property_certificate_number": "鲁(2020)阳谷县不动产权第0001003号",
    "land_transfer_contract": "未提及",
    "mortgage_status": "有抵押",
    "pledge_status": "未提及",
    "seizure_status": "有查封",
    "freeze_status": "未提及",
    "risk_transfer_status": "未提及",
    "tax_burden_party": "未提及",
    "tax_status": "未提及"
}

FAKE_EXTRACTION_CONFIDENCE = {
    "overall": 0.85,
    "land_info": 0.9,
    "legal_info": 0.8
}

FAKE_PROJECTS = [
    {
        "id": "PROJ001",
        "asset_name": "某某商业大厦",
        "asset_type": "土地",
        "city": "成都市",
        "starting_price": 1500.5,
        "valuation_price": 2000.0,
        "valuation_discount_rate": 0.75,
        "auction_date": "2023-12-01T10:00:00Z",
        "auction_status": "一拍"
    },
    {
        "id": "PROJ002",
        "asset_name": "阳谷瑞璟置业土地资产项目",
        "asset_type": "土地",
        "city": "聊城市",
        "starting_price": 800.0,
        "valuation_price": 1200.0,
        "valuation_discount_rate": 0.67,
        "auction_date": "2023-12-15T14:00:00Z",
        "auction_status": "一拍"
    }
]

FAKE_FILES = [
    {
        "file_id": "FILE_123456789",
        "original_path": "C:/documents/土地权属证明.pdf",
        "filename": "土地权属证明.pdf",
        "file_type": "land_document",
        "file_size": 2048576,
        "file_extension": "pdf",
        "mime_type": "application/pdf",
        "create_time": "2023-10-01T15:30:00Z",
        "access_url": "https://cdn.example.com/files/PROJ_20231001_123456/土地权属证明.pdf",
        "thumbnail_url": None,
        "upload_status": "success",
        "error_message": ""
    }
]

# 健康检查接口
@app.get("/api/health")
async def api_health():
    return {
        "code": 200,
        "message": "API服务运行正常",
        "data": {}
    }

@app.get("/")
async def api_health_v2():
    return {
        "code": 200,
        "message": "API服务运行正常",
        "data": {}
    }

# API信息接口
@app.get("/api/info")
async def api_info():
    return [
        {"name": "张三", "age": 25},
        {"name": "李四", "age": 30},
        {"name": "王五", "age": 28}
    ]

# 项目列表查询
@app.get("/api/projects")
async def query_project_list(
    page: int = 1,
    page_size: int = 10,
    asset_type: Optional[str] = None,
    city: Optional[str] = None,
    auction_status: Optional[str] = None
):
    return {
        "code": 200,
        "message": "success",
        "data": {
            "total": len(FAKE_PROJECTS),
            "page": page,
            "page_size": page_size,
            "projects": FAKE_PROJECTS
        }
    }

# 信息抽取接口
@app.post("/api/info-extraction")
async def extract_info_by_project(request: InfoExtractionRequest):
    return {
        "code": 200,
        "message": "success",
        "data": {
            "project_id": request.project_id,
            "project_name": "阳谷瑞璟置业土地资产项目",
            "land_info": FAKE_LAND_INFO,
            "legal_info": FAKE_LEGAL_INFO,
            "extraction_confidence": FAKE_EXTRACTION_CONFIDENCE,
            "extraction_time": datetime.now().isoformat() + "Z"
        }
    }

# 文件上传接口
@app.post("/api/upload")
async def upload_files_by_path(request: UploadRequest):
    return {
        "code": 200,
        "message": "文件上传成功",
        "data": {
            "project_id": "PROJ_20231001_123456",
            "total_files": len(request.file_paths),
            "total_size": 5242880,
            "upload_time": datetime.now().isoformat() + "Z",
            "files": [
                {
                    **file,
                    "file_id": f"FILE_{i+1}",
                    "original_path": path,
                    "filename": path.split('/')[-1] if '/' in path else path.split('\\')[-1]
                }
                for i, (file, path) in enumerate(zip([FAKE_FILES[0]] * len(request.file_paths), request.file_paths))
            ]
        }
    }

# 批量更新参数
@app.post("/api/batch-update")
async def batch_update_parameters(request: BatchUpdateRequest):
    results = []
    for update in request.updates:
        project_id = update.get('project_id')
        results.append({
            "project_id": project_id,
            "status": "success",
            "updated_fields": list(update.get('updates', {}).keys()),
            "failed_fields": [],
            "error_message": "",
            "update_time": datetime.now().isoformat() + "Z"
        })

    return {
        "code": 200,
        "message": "批量更新成功",
        "data": {
            "total_count": len(request.updates),
            "success_count": len(request.updates),
            "failed_count": 0,
            "results": results
        }
    }

# 创建解析任务
@app.post("/api/tasks/parse")
async def create_parse_task(request: ParseTaskRequest):
    return {
        "code": 200,
        "message": "任务创建成功",
        "data": {
            "task_id": f"TASK_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "project_id": request.project_id,
            "status": "pending",
            "create_time": datetime.now().isoformat() + "Z",
            "start_time": None,
            "complete_time": None,
            "estimated_duration": 60,
            "progress": 0.0,
            "file_count": len(request.file_ids) if request.file_ids else 1,
            "parse_type": request.parse_type
        }
    }

# 错误处理
@app.exception_handler(400)
async def bad_request_handler(request, exc):
    return {
        "code": 400,
        "message": "参数错误",
        "data": {"detail": str(exc.detail)}
    }

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "code": 404,
        "message": "项目不存在",
        "data": {"detail": str(exc.detail)}
    }

@app.exception_handler(413)
async def payload_too_large_handler(request, exc):
    return {
        "code": 413,
        "message": "文件总大小超过限制",
        "data": {"detail": str(exc.detail)}
    }

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {
        "code": 500,
        "message": "服务器内部错误",
        "data": {"detail": str(exc.detail)}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)