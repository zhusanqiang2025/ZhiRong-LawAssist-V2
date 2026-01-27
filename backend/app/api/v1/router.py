# backend/app/api/v1/router.py
"""
统一 API v1 路由总管
所有业务逻辑 API 统一收归到 /api/v1 命名空间下
"""
from fastapi import APIRouter

# ==================== V1 端点模块（位于 app/api/v1/endpoints/） ====================
from app.api.v1.endpoints import auth, contract_templates, admin, categories, tasks, smart_chat, rag_management
from app.api.v1.endpoints import contract_knowledge_graph_db, risk_analysis
from app.api.v1.endpoints import litigation_analysis, document_drafting, search
from app.api.v1.endpoints import knowledge_base, consultation_history, health
# from app.api.v1.endpoints import feishu_callback  # ⚠️ 暂时禁用：导入时会自动启动长连接导致路由加载失败

# ==================== 游离路由模块（位于 app/api/ 或 app/api/v1/） ====================
# 合同审查模块
from app.api.contract_router import router as contract_review_router

# 文档生成模块
from app.api.document_router import router as document_generation_router

# 合同生成模块
from app.api.contract_generation_router import router as contract_generation_router

# 费用测算模块
from app.api.cost_calculation_router import router as cost_calculation_router

# 智能咨询模块
from app.api.consultation_router import router as consultation_router

# 文档预处理模块
from app.api.v1.preprocessor_router import router as preprocessor_router

# ==================== 创建主路由器 ====================
api_router = APIRouter()

# ==================== 注册 V1 端点路由 ====================
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])

# RAG管理路由 (ChromaDB 0.6.x 已兼容 Pydantic 2.x)
api_router.include_router(rag_management.router, prefix="/rag", tags=["RAG Management"])

api_router.include_router(contract_templates.router, prefix="/contract", tags=["Contract Templates"])

# 使用数据库版本的知识图谱API
api_router.include_router(contract_knowledge_graph_db.router, tags=["Contract Knowledge Graph"])

# 风险评估 API（新架构）
api_router.include_router(risk_analysis.router, prefix="/risk-analysis", tags=["Risk Analysis"])

# 任务管理 API
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])

# 案件分析 API
api_router.include_router(litigation_analysis.router, prefix="/litigation-analysis", tags=["Litigation Analysis"])

# 文书起草 API
api_router.include_router(document_drafting.router, prefix="/document-drafting", tags=["Document Drafting"])

# 智能对话 API (智能引导和智能咨询)
api_router.include_router(smart_chat.router, prefix="/smart-chat", tags=["Smart Chat"])

# 全局搜索 API
api_router.include_router(search.router, prefix="/search", tags=["Search"])

# 知识库管理 API
api_router.include_router(knowledge_base.router, prefix="/knowledge-base", tags=["Knowledge Base"])

# 对话历史管理 API
api_router.include_router(consultation_history.router, tags=["Consultation History"])

# 健康检查 API
api_router.include_router(health.router, prefix="/health", tags=["Health"])

# # 飞书集成本地开发：飞书回调接口  # ⚠️ 暂时禁用：导入时会自动启动长连接导致路由加载失败
# api_router.include_router(feishu_callback.router, prefix="/feishu", tags=["Feishu Integration (Local)"])

# ==================== 注册游离路由（收归到 v1 命名空间） ====================
# 合同审查模块 (原 /api/contract -> /api/v1/contract-review)
api_router.include_router(contract_review_router, prefix="/contract-review", tags=["Contract Review"])

# 文档生成模块 (原 /api/document -> /api/v1/document-generation)
api_router.include_router(document_generation_router, prefix="/document-generation", tags=["Document Generation"])

# 合同生成模块 (原 /api/contract-generation -> /api/v1/contract-generation)
api_router.include_router(contract_generation_router, prefix="/contract-generation", tags=["Contract Generation"])

# 费用测算模块 (原 /api/cost-calculation -> /api/v1/cost-calculation)
api_router.include_router(cost_calculation_router, prefix="/cost-calculation", tags=["Cost Calculation"])

# 智能咨询模块 (原 /api/consultation -> /api/v1/consultation)
api_router.include_router(consultation_router, prefix="/consultation", tags=["Intelligent Consultation"])

# 文档预处理模块 (原 /api/preprocessor -> /api/v1/preprocessor)
api_router.include_router(preprocessor_router, prefix="/preprocessor", tags=["Document Preprocessor"])
