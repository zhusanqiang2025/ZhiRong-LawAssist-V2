from fastapi import APIRouter

# 临时注释掉有依赖问题的路由
# from app.api.v1.endpoints import auth, rag_management, contract_templates, admin, categories, legal_features_management, tasks, smart_chat
from app.api.v1.endpoints import auth, contract_templates, admin, categories, tasks, smart_chat, rag_management
from app.api.v1.endpoints import contract_knowledge_graph_db, risk_analysis, risk_analysis_v2
from app.api.v1.endpoints import litigation_analysis, document_drafting, search
# from app.api.v1.endpoints import celery_monitor  # 临时注释 - 需要 celery
from app.api.v1.endpoints import knowledge_base, consultation_history, health

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])

# ⚠️ RAG管理路由暂时禁用 - ChromaDB与当前环境(pydantic 2.x + Python 3.14)存在兼容性问题
# 需要修复ChromaDB依赖后才能启用
api_router.include_router(rag_management.router, prefix="/rag", tags=["RAG Management"])  # 临时注释

api_router.include_router(contract_templates.router, prefix="/contract", tags=["Contract Templates"])
# api_router.include_router(legal_features_management.router, tags=["Legal Features Management"])  # 临时注释
# 使用数据库版本的知识图谱API
api_router.include_router(contract_knowledge_graph_db.router, tags=["Contract Knowledge Graph"])
# 风险评估 API
api_router.include_router(risk_analysis.router, prefix="/risk-analysis", tags=["Risk Analysis"])
# 风险评估 API v2（新架构）
api_router.include_router(risk_analysis_v2.router, prefix="/risk-analysis-v2", tags=["Risk Analysis V2"])
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
# Celery 监控 API
# api_router.include_router(celery_monitor.router, prefix="/admin/celery", tags=["Celery Monitor"])  # 临时注释
# 知识库管理 API
api_router.include_router(knowledge_base.router, prefix="/knowledge-base", tags=["Knowledge Base"])
# 对话历史管理 API
api_router.include_router(consultation_history.router, tags=["Consultation History"])
# 健康检查 API
api_router.include_router(health.router, prefix="/health", tags=["Health"])