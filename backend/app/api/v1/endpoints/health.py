# backend/app/api/v1/endpoints/health.py
"""
健康检查端点

提供系统健康状态检查，包括 LLM 服务状态
"""
import os
import logging
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from app.core.llm_config import get_qwen3_llm as get_qwen3_llm, validate_llm_config

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/llm-status")
async def check_llm_status():
    """
    检查 LLM 服务状态

    返回 LLM 初始化状态和配置验证结果
    """
    try:
        # 测试 LLM 初始化
        llm = get_qwen3_llm()
        validation = validate_llm_config()

        # 提取模型信息
        model_info = {}
        if llm:
            try:
                model_info = {
                    "model": getattr(llm, 'model_name', getattr(llm, 'model', 'unknown')),
                    "base_url": getattr(llm, 'base_url', 'unknown'),
                }
            except Exception as e:
                logger.warning(f"获取 LLM 信息失败: {e}")
                model_info = {"error": str(e)}

        return {
            "status": "ok" if llm else "error",
            "llm_initialized": llm is not None,
            "config_validation": validation,
            "model_info": model_info
        }
    except Exception as e:
        logger.error(f"LLM 健康检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM 健康检查失败: {str(e)}")


@router.get("/system")
async def check_system_health():
    """
    系统健康检查

    检查各个子系统的状态
    """
    try:
        llm_status = await check_llm_status()

        return {
            "status": "healthy" if llm_status["llm_initialized"] else "degraded",
            "timestamp": "2025-01-01T00:00:00Z",
            "services": {
                "llm": llm_status
            }
        }
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }
