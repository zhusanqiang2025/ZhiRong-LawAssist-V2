# backend/app/api/v1/router.py
"""
统一 API v1 路由总管
所有业务逻辑 API 统一收归到 /api/v1 命名空间下
"""
from fastapi import APIRouter
import os
import logging

logger = logging.getLogger(__name__)

# ==================== V1 端点模块（位于 app/api/v1/endpoints/） ====================
from app.api.v1.endpoints import auth, contract_templates, admin, categories, tasks, smart_chat, rag_management
from app.api.v1.endpoints import contract_knowledge_graph_db, risk_analysis
from app.api.v1.endpoints import litigation_analysis, document_drafting, search
from app.api.v1.endpoints import knowledge_base, consultation_history, health, system, consultation_context

# ==================== 飞书集成条件导入 ====================
# 飞书集成模块导入可能导致事件循环冲突，需要特殊处理
def _try_import_feishu_callback():
    """
    尝试导入飞书集成模块（不依赖 Redis）

    返回: (success, feishu_router_or_None)
    """
    feishu_enabled = os.getenv("FEISHU_ENABLED", "false").lower() == "true"
    if not feishu_enabled:
        logger.info("ℹ️ 飞书集成未启用（FEISHU_ENABLED=false），跳过路由注册")
        return False, None

    # ⚠️ 移除 Redis 强制依赖 - 使用内存存储代替
    # 飞书集成模块内部已有降级处理（token_manager.py）
    # 只要 FEISHU_ENABLED=true，就尝试导入

    # 尝试导入飞书模块
    try:
        from app.api.v1.endpoints import feishu_callback
        logger.info("✅ 飞书集成模块导入成功（使用内存存储）")
        return True, feishu_callback.router
    except ImportError as e:
        logger.warning(f"⚠️ 飞书集成模块导入失败: {e}")
        logger.warning("   可能是 lark_oapi 依赖问题或事件循环冲突")
        return False, None
    except Exception as e:
        logger.warning(f"⚠️ 飞书集成模块导入异常: {e}")
        return False, None

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

# 咨询上下文提取 API
api_router.include_router(consultation_context.router, prefix="/consultation/context", tags=["Consultation Context"])

# 健康检查 API
api_router.include_router(health.router, prefix="/health", tags=["Health"])

# 系统管理 API（管理员权限管理）
api_router.include_router(system.router, prefix="/system", tags=["System Management"])

# ==================== 飞书集成回调 API（条件注册） ====================
# 只有在 Redis 可用且模块导入成功时才注册飞书路由
# 这样可以避免 lark_oapi 事件循环冲突导致所有路由注册失败
feishu_import_success, feishu_router = _try_import_feishu_callback()
if feishu_import_success and feishu_router is not None:
    api_router.include_router(feishu_router, prefix="/feishu", tags=["Feishu Integration"])
    logger.info("✅ 飞书集成路由已注册: /feishu/*")
else:
    logger.info("ℹ️ 飞书集成路由未注册（Redis 不可用或模块导入失败）")
    logger.info("   不影响其他功能的正常运行")


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
