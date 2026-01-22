# backend/Dockerfile (使用国内镜像源版 v12.0)
# 更改说明：
# 1. 使用国内镜像源避免网络连接问题
# 2. 添加清华/阿里 PyPI 镜像源

# 使用官方Python基础镜像
FROM python:3.11-slim

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive

# 更换为国内镜像源
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（包含 LibreOffice 用于文档转换，Tesseract 用于 OCR，Graphviz 用于图表）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libreoffice \
        fonts-liberation \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-chi-tra \
        graphviz \
        && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt ./

# 使用国内镜像源安装Python依赖
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# ==================== 环境变量配置 ====================
# Environment Configuration
ENV ENVIRONMENT=development

# Default Admin Configuration
ENV DEFAULT_ADMIN_PASSWORD=admin123

# Redis Configuration (K8s 环境 - 使用 gms.svc.cluster.local 格式)
ENV REDIS_HOST=redis7.gms.svc.cluster.local
ENV REDIS_PORT=6379
ENV REDIS_DB=0
ENV REDIS_URL=redis://redis7.gms.svc.cluster.local:6379/0

# PostgreSQL Database Configuration (K8s 环境)
ENV POSTGRES_SERVER=postgres18-0.postgres18.gms.svc.cluster.local
ENV POSTGRES_PORT=5432
ENV POSTGRES_DB=legal_assistant_db
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
ENV DATABASE_URL=postgresql://postgres:postgres@postgres18-0.postgres18.gms.svc.cluster.local:5432/legal_assistant_db

# Application Secret Key
ENV SECRET_KEY=a_very_long_and_super_secret_random_string_that_is_hard_to_guess
ENV ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ONLYOFFICE Configuration
ENV ONLYOFFICE_JWT_SECRET=legal_doc_secret_2025
ENV BACKEND_PUBLIC_URL=http://localhost:8000

# Dify Configuration (暂时禁用)
ENV DIFY_ENABLED=false
ENV DIFY_GUIDANCE_ANALYSIS_ENABLED=false
ENV DIFY_EXPERT_CONSULTATION_ENABLED=false

# --- DeepSeek API Configuration ---
ENV DEEPSEEK_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV DEEPSEEK_API_URL=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
ENV DEEPSEEK_MODEL=deepseek-chat
ENV DEEPSEEK_TEMPERATURE=0.7
ENV DEEPSEEK_MAX_TOKENS=2000
ENV DEEPSEEK_TIMEOUT=60

# --- LangChain API Configuration (用于风险评估等核心功能) ---
ENV LANGCHAIN_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV LANGCHAIN_API_BASE_URL=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
ENV MODEL_NAME=Qwen3-235B-A22B-Thinking-2507

# --- OpenAI API Configuration (用于合同生成模块) ---
ENV OPENAI_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV OPENAI_API_BASE=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1

# --- MinerU PDF 解析服务配置 ---
ENV MINERU_API_URL=http://115.190.40.198:7231/v2/parse/file
ENV MINERU_API_TIMEOUT=120
ENV MINERU_ENABLED=true

# --- OCR 服务配置 ---
ENV OCR_API_URL=http://115.190.43.141:8002/ocr/v1/recognize-text
ENV OCR_API_TIMEOUT=60
ENV OCR_ENABLED=true

# --- AI 文档预处理配置 ---
ENV AI_POSTPROCESS_ENABLED=true
ENV AI_POSTPROCESS_MODEL=qwen3-vl:32b-thinking-q8_0
ENV AI_POSTPROCESS_API_URL=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
ENV AI_POSTPROCESS_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV AI_AUTH_TYPE=bearer
ENV AI_POSTPROCESS_TIMEOUT=30
ENV AI_POSTPROCESS_BATCH_SIZE=5
ENV AI_POSTPROCESS_CONFIDENCE_THRESHOLD=0.7
ENV AI_POSTPROCESS_ONLY_AMBIGUOUS=true

# --- Qwen3-235B-A22B-Thinking-2507 模型配置 ---
ENV QWEN3_THINKING_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV QWEN3_THINKING_API_URL=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
ENV QWEN3_THINKING_MODEL=Qwen3-235B-A22B-Thinking-2507
ENV QWEN3_THINKING_TIMEOUT=120
ENV QWEN3_THINKING_ENABLED=true

# --- GPT-OSS-120B 模型配置 ---
ENV GPT_OSS_120B_API_URL=http://101.126.134.56:11434/v1
ENV GPT_OSS_120B_MODEL=gpt-oss:120b

# --- BGE 嵌入模型配置 (用于向量检索) ---
ENV BGE_EMBEDDING_API_URL=http://115.190.43.141:11434/api/embed
ENV BGE_RERANKER_API_URL=http://115.190.43.141:9997/v1/rerank
ENV BGE_MODEL_NAME=bge-m3
ENV BGE_EMBEDDING_DIM=1024
ENV BGE_TIMEOUT=30

# --- Celery 任务队列配置 ---
ENV CELERY_BROKER_URL=redis://redis:6379/0
ENV CELERY_RESULT_BACKEND=redis://redis:6379/0
ENV CELERY_ENABLED=true
ENV CELERY_TASK_TRACK_STARTED=true
ENV CELERY_TASK_TIME_LIMIT=3600
ENV CELERY_TASK_SOFT_TIME_LIMIT=3300

# --- Flower 监控配置 ---
ENV FLOWER_PORT=5556

# --- 向量数据库配置 ---
ENV CHROMA_PERSIST_DIR=./storage/chroma_db
ENV VECTOR_DB_TYPE=chroma

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令 - 增加WebSocket ping超时时间到300秒（5分钟）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-ping-interval", "20", "--ws-ping-timeout", "300"]
