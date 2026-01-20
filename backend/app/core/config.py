# backend/app/core/config.py (Pydantic V2 兼容版)
import secrets
from typing import Any, Dict, List, Optional, Union

# [修复] 导入 SettingsConfigDict 用于新版 Pydantic 配置
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, PostgresDsn, validator


class Settings(BaseSettings):
    """
    应用配置类，使用 Pydantic 的 BaseSettings 来自动从环境变量读取配置。
    """

    # --- 应用基本配置 ---
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "default-secret-key-change-in-production-min-32-chars"  # 默认值，生产环境必须覆盖
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    SERVER_NAME: str = "localhost"
    SERVER_HOST: str = "http://localhost:8000"
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # --- 文件上传配置 ---
    UPLOAD_DIR: str = "./storage/uploads"  # 文件上传目录

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # --- 数据库配置 ---
    PROJECT_NAME: str = "zhirong_fazhu_v2"
    POSTGRES_SERVER: str = "localhost"  # 默认值
    POSTGRES_USER: str = "postgres"  # 默认值
    POSTGRES_PASSWORD: str = "postgres"  # 默认值
    POSTGRES_DB: str = "legal_assistant"  # 默认值
    DATABASE_URL: str = "sqlite:///./storage/app.db"  # 默认使用 SQLite

    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    # --- Redis 配置 ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # --- DeepSeek 配置 ---
    # DeepSeek API 配置（用于智能对话功能）
    # 注意：API_URL 已配置为火山引擎 Qwen 模型端点
    DEEPSEEK_API_URL: str = ""  # 可选
    DEEPSEEK_API_KEY: str = "default-api-key-change-in-production"  # 默认值
    DEEPSEEK_MODEL: str = "Qwen3-235B-A22B-Thinking-2507"  # 使用 Qwen3 Thinking 模型
    DEEPSEEK_TEMPERATURE: float = 0.7
    DEEPSEEK_MAX_TOKENS: int = 2000
    DEEPSEEK_TIMEOUT: int = 60

    # --- MinerU PDF 解析服务配置 ---
    MINERU_API_URL: str = ""  # MinerU 服务地址，例如: http://mineru-server:8001
    MINERU_API_TIMEOUT: int = 120  # MinerU 请求超时时间（秒）
    MINERU_ENABLED: bool = False  # 是否启用 MinerU 服务

    # --- OCR 服务配置 ---
    OCR_API_URL: str = ""  # OCR 服务地址
    OCR_API_TIMEOUT: int = 60  # OCR 请求超时时间（秒）
    OCR_ENABLED: bool = False  # 是否启用 OCR 服务

    # --- AI 文档预处理配置 ---
    # AI 辅助文档后处理（使用 Qwen3-VL 等视觉语言模型）
    AI_POSTPROCESS_ENABLED: bool = False  # 是否启用 AI 辅助后处理
    AI_POSTPROCESS_MODEL: str = ""  # 视觉分析模型（用于文档页面图像分析）
    AI_POSTPROCESS_API_URL: str = ""  # AI 模型 API 地址
    AI_POSTPROCESS_API_KEY: str = ""  # AI 模型 API 密钥
    AI_POSTPROCESS_TIMEOUT: int = 30  # AI 请求超时时间（秒）
    AI_POSTPROCESS_BATCH_SIZE: int = 5  # 批量处理时每次发送的段落数

    # ⭐ 新增：AI 文本分类模型配置（用于段落分类等纯文本任务）
    AI_TEXT_CLASSIFICATION_ENABLED: bool = False  # 是否启用 AI 文本分类
    AI_TEXT_CLASSIFICATION_MODEL: str = ""  # 文本分类模型（使用更强的文本模型）
    AI_TEXT_CLASSIFICATION_API_URL: str = ""  # 文本分类 API 地址
    AI_TEXT_CLASSIFICATION_API_KEY: str = ""  # 文本分类 API 密钥
    AI_TEXT_CLASSIFICATION_TIMEOUT: int = 30  # 文本分类超时时间（秒）

    # AI 后处理策略配置
    AI_POSTPROCESS_CONFIDENCE_THRESHOLD: float = 0.7  # 规则置信度阈值，低于此值使用 AI
    AI_POSTPROCESS_ONLY_AMBIGUOUS: bool = True  # 仅对不确定的内容使用 AI

    # --- OpenAI 兼容 API 配置 ---
    # 用于合同生成和 V2 特征自动提取
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = ""
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"  # 默认模型名称

    # --- LangChain 配置 ---
    # 用于风险评估工作流、文档预整理等
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_API_BASE_URL: str = ""
    MODEL_NAME: str = "Qwen3-235B-A22B-Thinking-2507"  # 默认模型名称

    # --- RAG 服务配置 ---
    # 向量数据库配置
    VECTOR_DB_TYPE: str = "chroma"  # 向量数据库类型: chroma, qdrant, pgvector
    CHROMA_PERSIST_DIR: str = "./storage/chroma_db"  # Chroma 持久化目录

    # 公司 BGE 服务配置
    BGE_EMBEDDING_API_URL: str = "http://115.190.43.141:11434/api/embed"
    BGE_RERANKER_API_URL: str = "http://115.190.43.141:9997/v1/rerank"
    BGE_MODEL_NAME: str = "bge-m3"
    BGE_EMBEDDING_DIM: int = 1024  # BGE-M3 输出维度
    BGE_TIMEOUT: int = 30  # API 请求超时时间（秒）

    # ==================== Celery 任务队列配置 ====================
    # 功能开关：是否启用 Celery 任务队列系统
    CELERY_ENABLED: bool = False  # 默认关闭，通过环境变量启用
    # 任务追踪启用
    CELERY_TASK_TRACK_STARTED: bool = True
    # 任务硬超时（秒）
    CELERY_TASK_TIME_LIMIT: int = 3600
    # 任务软超时（秒）
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300

    @validator("MINERU_ENABLED", "OCR_ENABLED", "AI_POSTPROCESS_ENABLED", "CELERY_ENABLED", pre=True)
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
        # 只在非生产环境警告，生产环境必须配置完整
        if self.ENVIRONMENT != "production":
            self._warn_default_config()

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