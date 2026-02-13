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
    API_KEY: str = "your-api-key-change-in-production"

    # --- DeepSeek 配置（用于内容填充和一般对话）---
    # 【修复】使用 DeepSeek-R1-0528 模型
    DEEPSEEK_API_URL: str = "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1"
    DEEPSEEK_API_KEY: str = "your-deepseek-api-key"
    DEEPSEEK_MODEL: str = "DeepSeek-R1-0528"
    DEEPSEEK_TEMPERATURE: float = 0.7
    DEEPSEEK_MAX_TOKENS: int = 2000
    DEEPSEEK_TIMEOUT: int = 60

    # ==================== Qwen3 API 统一配置 ====================
    QWEN3_API_KEY: str = "your-qwen3-api-key"
    QWEN3_API_BASE: str = "https://sd4bijv1oh486npgbrkrg.apigateway-cn-beijing.volceapi.com/v1"
    QWEN3_MODEL: str = "Qwen3-235B-A22B-Thinking-2507"
    QWEN3_ENABLED: bool = True

    # --- GPT-OSS-120B 配置（用于多模型合同规划）---
    # 【新增】用于复杂推理和合同规划的第3个模型
    GPT_OSS_120B_API_URL: str = "http://101.126.134.56:11434/v1"
    GPT_OSS_120B_API_KEY: str = "your-gpt-oss-api-key-change-in-production"
    GPT_OSS_120B_MODEL: str = "gpt-oss:120b"
    GPT_OSS_120B_TIMEOUT: int = 90

    # ==================== AI 文档预处理配置（硬编码）====================
    # 文本分类模型配置（用于段落分类等纯文本任务）
    AI_TEXT_CLASSIFICATION_ENABLED: bool = True
    AI_TEXT_CLASSIFICATION_MODEL: str = "Qwen3-235B-A22B-Thinking-2507"
    AI_TEXT_CLASSIFICATION_API_URL: str = "https://newapi.dev.azshentong.com/v1"
    AI_TEXT_CLASSIFICATION_API_KEY: str = "your-text-classification-api-key-change-in-production"
    AI_TEXT_CLASSIFICATION_TIMEOUT: int = 30

    # AI 文档预处理配置（用于文档页面图像分析）
    # 【修复】使用正确的 Qwen3-VL-32B 模型名称
    AI_POSTPROCESS_ENABLED: bool = True
    AI_POSTPROCESS_MODEL: str = "qwen3-vl:32b-thinking-q8_0"
    AI_POSTPROCESS_API_URL: str = "http://115.190.40.198:11434/v1"
    AI_POSTPROCESS_API_KEY: str = "your-ai-postprocess-api-key-change-in-production"
    AI_POSTPROCESS_TIMEOUT: int = 30
    AI_POSTPROCESS_BATCH_SIZE: int = 5

    # AI 后处理策略配置
    AI_POSTPROCESS_CONFIDENCE_THRESHOLD: float = 0.7
    AI_POSTPROCESS_ONLY_AMBIGUOUS: bool = True

    # ==================== 外部服务配置（公网地址硬编码）====================
    # --- MinerU PDF 解析服务配置 ---
    MINERU_API_URL: str = "http://115.190.40.198:7231/v2/parse/file"
    MINERU_API_KEY: str = "your-mineru-api-key-change-in-production"
    MINERU_API_TIMEOUT: int = 120
    MINERU_ENABLED: bool = True

    # --- DeepSeek OCR 服务配置 ---
    OCR_API_URL: str = "http://115.190.43.141:8002/ocr/v1/recognize-text"
    OCR_API_KEY: str = "your-ocr-api-key-change-in-production"
    OCR_API_TIMEOUT: int = 60
    OCR_ENABLED: bool = True

    # ==================== 向量检索配置（公网地址硬编码）====================
    # 向量数据库配置
    VECTOR_DB_TYPE: str = "pgvector"
    CHROMA_PERSIST_DIR: str = "./storage/chroma_db"

    # BGE Embedding 模型配置
    BGE_EMBEDDING_API_URL: str = "http://115.190.43.141:11434/api/embed"
    BGE_EMBEDDING_API_KEY: str = "your-bge-embedding-api-key-change-in-production"
    BGE_MODEL_NAME: str = "bge-m3"
    BGE_EMBEDDING_DIM: int = 1024
    BGE_TIMEOUT: int = 30

    # BGE Reranker 模型配置
    BGE_RERANKER_API_URL: str = "http://115.190.43.141:9997/v1/rerank"
    BGE_RERANKER_API_KEY: str = "your-bge-reranker-api-key-change-in-production"
    BGE_RERANKER_MODEL_NAME: str = "bge-reranker-v2-m3"

    # ==================== Celery 任务队列配置 ====================
    CELERY_ENABLED: bool = True   # ✅ 已启用（使用 K8s Redis）

    # 【修复】Celery Broker 类型配置（智能降级方案）
    # 选项：
    #   - "auto": 自动检测（Redis → PostgreSQL → RabbitMQ → Memory）
    #   - "redis": 强制使用 Redis
    #   - "database": 强制使用 PostgreSQL（需要先创建表）
    #   - "rabbitmq": 强制使用 RabbitMQ
    #   - "memory": Memory broker（仅开发/单机）
    CELERY_BROKER_TYPE: str = "auto"  # 默认自动选择

    # 【修复】显式配置 Celery Broker URL（最高优先级）
    # 如果设置此项，将忽略 CELERY_BROKER_TYPE 的自动选择
    # 格式示例：
    #   Redis: "redis://localhost:6379/0"
    #   PostgreSQL: "db+postgresql://user:pass@host:port/db"
    #   RabbitMQ: "amqp://guest:guest@localhost:5672//"
    CELERY_BROKER_URL: Optional[str] = None  # 默认为 None，使用自动选择

    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300

    # ==================== 模型分层配置 (Model Tiering) ====================
    # Tier 1: 律师助理 (Assistant) - 快速响应，负责意图识别和简单交互
    # 默认使用 DeepSeek-R1-0528 (推理能力强)
    ASSISTANT_MODEL_API_URL: str = ""  # 在 __init__ 中设置为 DEEPSEEK_API_URL
    ASSISTANT_MODEL_API_KEY: str = ""  # 在 __init__ 中设置为 DEEPSEEK_API_KEY
    ASSISTANT_MODEL_NAME: str = ""     # 在 __init__ 中设置为 DEEPSEEK_MODEL
    ASSISTANT_MODEL_TIMEOUT: int = 60

    # Tier 2: 专业律师 (Specialist) - 深度思考，负责复杂法律分析
    # 默认使用 Qwen3-235B-Thinking (235B参数，逻辑强)
    SPECIALIST_MODEL_API_URL: str = ""  # 在 __init__ 中设置为 QWEN3_API_BASE
    SPECIALIST_MODEL_API_KEY: str = ""  # 在 __init__ 中设置为 QWEN3_API_KEY
    SPECIALIST_MODEL_NAME: str = ""     # 在 __init__ 中设置为 QWEN3_MODEL
    SPECIALIST_MODEL_TIMEOUT: int = 120

    # ==================== ONLYOFFICE 配置 ====================
    ONLYOFFICE_JWT_SECRET: str = "legal_doc_secret_2025"

    @validator("MINERU_ENABLED", "OCR_ENABLED", "AI_POSTPROCESS_ENABLED", "AI_TEXT_CLASSIFICATION_ENABLED", "CELERY_ENABLED", "QWEN3_ENABLED", pre=True)
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

        # ==================== 模型分层配置动态设置 ====================
        # Tier 1: 律师助理 - 使用 DeepSeek 配置
        if not self.ASSISTANT_MODEL_API_URL:
            self.ASSISTANT_MODEL_API_URL = self.DEEPSEEK_API_URL
        if not self.ASSISTANT_MODEL_API_KEY:
            self.ASSISTANT_MODEL_API_KEY = self.DEEPSEEK_API_KEY
        if not self.ASSISTANT_MODEL_NAME:
            self.ASSISTANT_MODEL_NAME = self.DEEPSEEK_MODEL

        # Tier 2: 专业律师 - 使用 Qwen3 配置
        if not self.SPECIALIST_MODEL_API_URL:
            self.SPECIALIST_MODEL_API_URL = self.QWEN3_API_BASE
        if not self.SPECIALIST_MODEL_API_KEY:
            self.SPECIALIST_MODEL_API_KEY = self.QWEN3_API_KEY
        if not self.SPECIALIST_MODEL_NAME:
            self.SPECIALIST_MODEL_NAME = self.QWEN3_MODEL

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
