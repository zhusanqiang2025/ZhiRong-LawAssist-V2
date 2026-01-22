# =================================================================
# 路径：docker/Dockerfile
# =================================================================

# 1. ✅ [必须修改] 使用华为云镜像源 (解决 timeout 问题)
# 原来的 python:3.11-slim 在国内拉不动，必须换成下面这个长地址：
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.11-slim

# 2. 接收 GitLab 传入的构建参数
ARG APP_VERSION
ARG CI_PROJECT_TITLE

# 3. 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

# ==================== API 密钥配置 ====================
# DeepSeek / LangChain / OpenAI API Key
ENV DEEPSEEK_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV DEEPSEEK_API_URL=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
ENV DEEPSEEK_MODEL=deepseek-chat
ENV DEEPSEEK_TEMPERATURE=0.7
ENV DEEPSEEK_MAX_TOKENS=2000
ENV DEEPSEEK_TIMEOUT=60

# LangChain API (用于风险评估等核心功能)
ENV LANGCHAIN_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV LANGCHAIN_API_BASE_URL=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
ENV MODEL_NAME=Qwen3-235B-A22B-Thinking-2507

# OpenAI API (用于合同生成模块)
ENV OPENAI_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV OPENAI_API_BASE=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1

# Qwen3-235B-Thinking 模型配置
ENV QWEN3_THINKING_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV QWEN3_THINKING_API_URL=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
ENV QWEN3_THINKING_MODEL=Qwen3-235B-A22B-Thinking-2507
ENV QWEN3_THINKING_TIMEOUT=120
ENV QWEN3_THINKING_ENABLED=true

# ==================== 数据库配置 ====================
ENV POSTGRES_SERVER=postgres18-0.postgres18.gms.svc.cluster.local
ENV POSTGRES_PORT=5432
ENV POSTGRES_DB=legal_assistant_db
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
ENV DATABASE_URL=postgresql://postgres:postgres@postgres18-0.postgres18.gms.svc.cluster.local:5432/legal_assistant_db

# ==================== Redis 配置 ====================
ENV REDIS_HOST=redis7.gms.svc.cluster.local
ENV REDIS_PORT=6379
ENV REDIS_DB=0
ENV REDIS_URL=redis://redis7.gms.svc.cluster.local:6379/0
ENV CELERY_BROKER_URL=redis://redis:6379/0
ENV CELERY_RESULT_BACKEND=redis://redis:6379/0

# ==================== 其他服务配置 ====================
ENV SECRET_KEY=a_very_long_and_super_secret_random_string_that_is_hard_to_guess
ENV ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENV ONLYOFFICE_JWT_SECRET=legal_doc_secret_2025
ENV BACKEND_PUBLIC_URL=http://localhost:8000

# Dify 配置 (暂时禁用)
ENV DIFY_ENABLED=false
ENV DIFY_GUIDANCE_ANALYSIS_ENABLED=false
ENV DIFY_EXPERT_CONSULTATION_ENABLED=false

# MinerU PDF 解析服务
ENV MINERU_API_URL=http://115.190.40.198:7231/v2/parse/file
ENV MINERU_API_TIMEOUT=120
ENV MINERU_ENABLED=true

# OCR 服务
ENV OCR_API_URL=http://115.190.43.141:8002/ocr/v1/recognize-text
ENV OCR_API_TIMEOUT=60
ENV OCR_ENABLED=true

# AI 文档预处理
ENV AI_POSTPROCESS_ENABLED=true
ENV AI_POSTPROCESS_MODEL=qwen3-vl:32b-thinking-q8_0
ENV AI_POSTPROCESS_API_URL=https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
ENV AI_POSTPROCESS_API_KEY=7adb34bf-3cb3-4dea-af41-b79de8c08ca3
ENV AI_AUTH_TYPE=bearer
ENV AI_POSTPROCESS_TIMEOUT=30
ENV AI_POSTPROCESS_BATCH_SIZE=5
ENV AI_POSTPROCESS_CONFIDENCE_THRESHOLD=0.7
ENV AI_POSTPROCESS_ONLY_AMBIGUOUS=true

# GPT-OSS-120B 模型
ENV GPT_OSS_120B_API_URL=http://101.126.134.56:11434/v1
ENV GPT_OSS_120B_MODEL=gpt-oss:120b

# BGE 嵌入模型
ENV BGE_EMBEDDING_API_URL=http://115.190.43.141:11434/api/embed
ENV BGE_RERANKER_API_URL=http://115.190.43.141:9997/v1/rerank
ENV BGE_MODEL_NAME=bge-m3
ENV BGE_EMBEDDING_DIM=1024
ENV BGE_TIMEOUT=30

# Celery 任务队列
ENV CELERY_ENABLED=true
ENV CELERY_TASK_TRACK_STARTED=true
ENV CELERY_TASK_TIME_LIMIT=3600
ENV CELERY_TASK_SOFT_TIME_LIMIT=3300

# Flower 监控
ENV FLOWER_PORT=5556

# 向量数据库
ENV CHROMA_PERSIST_DIR=./storage/chroma_db
ENV VECTOR_DB_TYPE=chroma

# 4. 更换 Debian 系统源 (加速 apt install)
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 5. 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libreoffice \
        fonts-liberation \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        graphviz \
        curl \
        && rm -rf /var/lib/apt/lists/*

# 6. 设置工作目录
WORKDIR /app

# 7. 复制所有文件
COPY . /app/

# 8. 安装 Python 依赖 (使用清华源加速)
# 使用根目录的 requirements.txt，包含完整的依赖包（redis, celery, langchain 等）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 9. 暴露端口（与 K8s Service 端口匹配）
EXPOSE 8000

# 10. ✅ [必须修改] 启动命令指向 simple_main.py
CMD ["python", "simple_main.py"]