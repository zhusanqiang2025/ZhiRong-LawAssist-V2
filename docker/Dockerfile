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
ENV DEEPSEEK_API_KEY=sk-KTBuFAEubEOFBpGeVEVisvORtTkvny6OHAiPPGaHQuLAvJ
ENV DEEPSEEK_API_URL=https://newapi.dev.azshentong.com/v1
ENV DEEPSEEK_MODEL=Qwen3-235B-A22B-Thinking-2507
ENV DEEPSEEK_TEMPERATURE=0.7
ENV DEEPSEEK_MAX_TOKENS=2000
ENV DEEPSEEK_TIMEOUT=60

# LangChain API (用于风险评估等核心功能)
ENV LANGCHAIN_API_KEY=sk-KTBuFAEubEOFBpGeVEVisvORtTkvny6OHAiPPGaHQuLAvJ
ENV LANGCHAIN_API_BASE_URL=https://newapi.dev.azshentong.com/v1
ENV MODEL_NAME=Qwen3-235B-A22B-Thinking-2507

# OpenAI API (用于合同生成模块)
ENV OPENAI_API_KEY=sk-KTBuFAEubEOFBpGeVEVisvORtTkvny6OHAiPPGaHQuLAvJ
ENV OPENAI_API_BASE=https://newapi.dev.azshentong.com/v1

# Qwen3-235B-Thinking 模型配置
ENV QWEN3_THINKING_API_KEY=sk-KTBuFAEubEOFBpGeVEVisvORtTkvny6OHAiPPGaHQuLAvJ
ENV QWEN3_THINKING_API_URL=https://newapi.dev.azshentong.com/v1
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

# ==================== Redis 配置（已移除，使用内存缓存）====================
# ENV REDIS_HOST=redis7.gms.svc.cluster.local
# ENV REDIS_PORT=6379
# ENV REDIS_DB=0
# ENV REDIS_URL=redis://redis7.gms.svc.cluster.local:6379/0
# ENV CELERY_BROKER_URL=redis://redis:6379/0
# ENV CELERY_RESULT_BACKEND=redis://redis:6379/0

# ==================== 其他服务配置 ====================
ENV SECRET_KEY=a_very_long_and_super_secret_random_string_that_is_hard_to_guess
ENV ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENV ONLYOFFICE_JWT_SECRET=legal_doc_secret_2025
ENV BACKEND_PUBLIC_URL=http://localhost:8000

# Dify 配置 (暂时禁用)
ENV DIFY_ENABLED=false
ENV DIFY_GUIDANCE_ANALYSIS_ENABLED=false
ENV DIFY_EXPERT_CONSULTATION_ENABLED=false

# MinerU PDF 解析服务（公网地址）
ENV MINERU_API_URL=https://newapi.dev.azshentong.com/v1
ENV MINERU_API_KEY=sk-qu85R6PvJu89AAnVdUph5qW1zisvrydVHBAopLluM650TTlE
ENV MINERU_API_TIMEOUT=120
ENV MINERU_ENABLED=true

# OCR 服务（公网地址）
ENV OCR_API_URL=https://newapi.dev.azshentong.com/v1
ENV OCR_API_KEY=sk-EQOScNCvMG5SHHmfiwVOI1IdnS47bF6lPrtvQEZTFxsTyH2S
ENV OCR_API_TIMEOUT=60
ENV OCR_ENABLED=true

# AI 文档预处理
ENV AI_POSTPROCESS_ENABLED=true
ENV AI_POSTPROCESS_MODEL=qwen3-vl:32b-thinking-q8_0
ENV AI_POSTPROCESS_API_URL=https://newapi.dev.azshentong.com/v1
ENV AI_POSTPROCESS_API_KEY=sk-KTBuFAEubEOFBpGeVEVisvORtTkvny6OHAiPPGaHQuLAvJ
ENV AI_AUTH_TYPE=bearer
ENV AI_POSTPROCESS_TIMEOUT=30
ENV AI_POSTPROCESS_BATCH_SIZE=5
ENV AI_POSTPROCESS_CONFIDENCE_THRESHOLD=0.7
ENV AI_POSTPROCESS_ONLY_AMBIGUOUS=true

# GPT-OSS-120B 模型
ENV GPT_OSS_120B_API_URL=http://101.126.134.56:11434/v1
ENV GPT_OSS_120B_MODEL=gpt-oss:120b

# BGE 嵌入模型（公网地址）
ENV BGE_EMBEDDING_API_URL=https://newapi.dev.azshentong.com/v1
ENV BGE_EMBEDDING_API_KEY=sk-ZLvhvOzb6KriMr961O8AGo73wG9nRblmDiECFybokz6r3iM8
ENV BGE_RERANKER_API_URL=https://newapi.dev.azshentong.com/v1
ENV BGE_RERANKER_API_KEY=sk-moDTih3CzjnCB8YP9RB829O1ckRPFXbzZC4VAi1Juf5gt2Nw
ENV BGE_MODEL_NAME=bge-m3
ENV BGE_EMBEDDING_DIM=1024
ENV BGE_TIMEOUT=30

# Celery 任务队列（已禁用，需要 Redis）
ENV CELERY_ENABLED=false
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

# 7.5. 安装 Node.js 20.x 并构建前端
# 使用 npm 中国镜像加速下载
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    cd /app/frontend && \
    npm config set registry https://registry.npmmirror.com && \
    npm ci --verbose && \
    npx vite build && \
    # 将构建好的前端复制到后端静态文件目录
    mkdir -p /app/backend/static/frontend && \
    cp -r dist/* /app/backend/static/frontend/ && \
    cd /app && \
    apt-get remove -y nodejs && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /app/frontend/node_modules /app/frontend/dist

# 8. 安装 Python 依赖 (使用清华源加速)
# 使用根目录的 requirements.txt，包含完整的依赖包（redis, celery, langchain 等）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 9. 暴露端口（与 K8s Service 端口匹配）
EXPOSE 8000

# 10. ✅ [必须修改] 启动命令指向 simple_main.py
CMD ["python", "simple_main.py"]