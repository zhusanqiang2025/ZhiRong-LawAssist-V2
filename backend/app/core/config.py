# backend/app/core/config.py (生产环境硬编码配置版)
import secrets
from typing import Any, Dict, List, Optional, Union

# [修复] 导入 SettingsConfigDict 用于新版 Pydantic 配置
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, PostgresDsn, validator


class Settings(BaseSettings):
    """
    应用配置类 - 生产环境硬编码配置
    所有线上服务配置已硬编码，部署后可直接使用
    """

    # --- 应用基本配置 ---
    ENVIRONMENT: str = "production"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "legal-assistant-production-secret-key-2025-min-32-chars-change-if-needed"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    SERVER_NAME: str = "legal-assistant-v3.azgpu02.azshentong.com"
    SERVER_HOST: str = "https://legal-assistant-v3.azgpu02.azshentong.com"
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # --- 文件上传配置 ---
    UPLOAD_DIR: str = "./storage/uploads"

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # ==================== 数据库配置（硬编码生产环境）====================
    PROJECT_NAME: str = "legal_assistant_v3"
    POSTGRES_SERVER: str = "postgres18-0.postgres18.gms.svc.cluster.local"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "legal_assistant_db"
    DATABASE_URL: str = "postgresql://postgres:postgres@postgres18-0.postgres18.gms.svc.cluster.local:5432/legal_assistant_db"

    # ==================== Redis 配置（已移除，使用内存缓存）====================
    # REDIS_HOST: str = "localhost"
    # REDIS_PORT: int = 6379
    # REDIS_DB: int = 0

    # ==================== 线上 API 服务配置（硬编码）====================
    # 统一 API 基础配置
    API_BASE_URL: str = "https://newapi.dev.azshentong.com/v1"
    API_KEY: str = "sk-KTBuFAEubEOFBpGeVEVisvORtTkvny6OHAiPPGaHQuLAvJ"

    # --- DeepSeek/Qwen 配置（用于智能对话）---
    # 【修复】使用有效的 API Key
    DEEPSEEK_API_URL: str = "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1"
    DEEPSEEK_API_KEY: str = "7adb34bf-3cb3-4dea-af41-b79de8c08ca3"
    DEEPSEEK_MODEL: str = "Qwen3-235B-A22B-Thinking-2507"
    DEEPSEEK_TEMPERATURE: float = 0.7
    DEEPSEEK_MAX_TOKENS: int = 2000
    DEEPSEEK_TIMEOUT: int = 60

    # --- Qwen3-Thinking 专用配置（用于合同审查等核心功能）---
    # 【修复】使用有效的 API Key
    QWEN3_THINKING_API_URL: str = "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1"
    QWEN3_THINKING_API_KEY: str = "7adb34bf-3cb3-4dea-af41-b79de8c08ca3"
    QWEN3_THINKING_MODEL: str = "Qwen3-235B-A22B-Thinking-2507"
    QWEN3_THINKING_TIMEOUT: int = 120
    QWEN3_THINKING_ENABLED: bool = True

    # --- LangChain 配置（用于风险评估工作流）---
    # 【修复】使用有效的 API Key
    LANGCHAIN_API_KEY: str = "7adb34bf-3cb3-4dea-af41-b79de8c08ca3"
    LANGCHAIN_API_BASE_URL: str = "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1"
    MODEL_NAME: str = "Qwen3-235B-A22B-Thinking-2507"

    # --- OpenAI 兼容 API 配置（用于合同生成）---
    # 【修复】使用有效的 API Key
    OPENAI_API_KEY: str = "7adb34bf-3cb3-4dea-af41-b79de8c08ca3"
    OPENAI_API_BASE: str = "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1"
    OPENAI_MODEL_NAME: str = "Qwen3-235B-A22B-Thinking-2507"

    # ==================== AI 文档预处理配置（硬编码）====================
    # 视觉模型配置（用于文档页面图像分析）
    AI_POSTPROCESS_ENABLED: bool = True
    AI_POSTPROCESS_MODEL: str = "qwen3-vl:32b-thinking-q8_0"
    AI_POSTPROCESS_API_URL: str = "https://newapi.dev.azshentong.com/v1"
    AI_POSTPROCESS_API_KEY: str = "sk-KTBuFAEubEOFBpGeVEVisvORtTkvny6OHAiPPGaHQuLAvJ"
    AI_POSTPROCESS_TIMEOUT: int = 30
    AI_POSTPROCESS_BATCH_SIZE: int = 5

    # 文本分类模型配置（用于段落分类等纯文本任务）
    AI_TEXT_CLASSIFICATION_ENABLED: bool = True
    AI_TEXT_CLASSIFICATION_MODEL: str = "Qwen3-235B-A22B-Thinking-2507"
    AI_TEXT_CLASSIFICATION_API_URL: str = "https://newapi.dev.azshentong.com/v1"
    AI_TEXT_CLASSIFICATION_API_KEY: str = "sk-KTBuFAEubEOFBpGeVEVisvORtTkvny6OHAiPPGaHQuLAvJ"
    AI_TEXT_CLASSIFICATION_TIMEOUT: int = 30

    # AI 后处理策略配置
    AI_POSTPROCESS_CONFIDENCE_THRESHOLD: float = 0.7
    AI_POSTPROCESS_ONLY_AMBIGUOUS: bool = True

    # ==================== 外部服务配置（公网地址硬编码）====================
    # --- MinerU PDF 解析服务配置 ---
    MINERU_API_URL: str = "https://newapi.dev.azshentong.com/v1"
    MINERU_API_KEY: str = "sk-qu85R6PvJu89AAnVdUph5qW1zisvrydVHBAopLluM650TTlE"
    MINERU_API_TIMEOUT: int = 120
    MINERU_ENABLED: bool = True

    # --- DeepSeek OCR 服务配置 ---
    OCR_API_URL: str = "https://newapi.dev.azshentong.com/v1"
    OCR_API_KEY: str = "sk-EQOScNCvMG5SHHmfiwVOI1IdnS47bF6lPrtvQEZTFxsTyH2S"
    OCR_API_TIMEOUT: int = 60
    OCR_ENABLED: bool = True

    # ==================== 向量检索配置（公网地址硬编码）====================
    # 向量数据库配置
    VECTOR_DB_TYPE: str = "pgvector"
    CHROMA_PERSIST_DIR: str = "./storage/chroma_db"

    # BGE Embedding 模型配置
    BGE_EMBEDDING_API_URL: str = "https://newapi.dev.azshentong.com/v1"
    BGE_EMBEDDING_API_KEY: str = "sk-ZLvhvOzb6KriMr961O8AGo73wG9nRblmDiECFybokz6r3iM8"
    BGE_MODEL_NAME: str = "bge-m3"
    BGE_EMBEDDING_DIM: int = 1024
    BGE_TIMEOUT: int = 30

    # BGE Reranker 模型配置
    BGE_RERANKER_API_URL: str = "https://newapi.dev.azshentong.com/v1"
    BGE_RERANKER_API_KEY: str = "sk-moDTih3CzjnCB8YP9RB829O1ckRPFXbzZC4VAi1Juf5gt2Nw"
    BGE_RERANKER_MODEL_NAME: str = "bge-reranker-v2-m3"

    # ==================== Celery 任务队列配置 ====================
    CELERY_ENABLED: bool = True   # ✅ 已启用（使用 K8s Redis）
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300

    # ==================== ONLYOFFICE 配置 ====================
    ONLYOFFICE_JWT_SECRET: str = "legal_doc_secret_2025"

    @validator("MINERU_ENABLED", "OCR_ENABLED", "AI_POSTPROCESS_ENABLED", "AI_TEXT_CLASSIFICATION_ENABLED", "CELERY_ENABLED", "QWEN3_THINKING_ENABLED", pre=True)
    def parse_bool_fields(cls, v):
        """解析布尔值，处理可能的空格问题"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("true", "1", "yes", "on"):
                return True
            elif v_clean in ("false", "0", "no", "off", ""):
                return False
        return v

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 生产环境不警告默认配置
        # if self.ENVIRONMENT != "production":
        #     self._warn_default_config()

    def _warn_default_config(self):
        """开发环境警告默认配置"""
        import warnings
        warnings.warn(
            "⚠️  Using default configuration values. "
            "This is NOT suitable for production! "
            "Please set proper environment variables.",
            UserWarning,
            stacklevel=2
        )


# 创建配置实例
settings = Settings()
