# Legal Document Assistant v3 - Production Dockerfile
# 多阶段构建：后端 + 前端一体化部署
# 开发环境：前端 Vite + 后端 Docker
# 生产环境：后端 FastAPI 直接服务前端静态文件

# ============ Stage 1: Vendor 基础镜像（Python 依赖层） ============
FROM docker.1ms.run/python:3.11-slim AS python-vendor

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 更换为阿里云 Debian 镜像源（加速）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装 Python 编译依赖（仅用于 vendor 阶段）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        curl \
        && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 工作目录
WORKDIR /app/vendor

# 仅复制依赖文件（利用 Docker 缓存层）
COPY backend/requirements.txt ./requirements.txt

# 使用清华镜像源安装 Python 依赖
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-deps -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple || \
    (pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple)


# ============ Stage 2: 前端构建（React + Vite） ============
FROM docker.1ms.run/node:lts-alpine AS frontend-builder

# 使用阿里云 Alpine 镜像源加速 apk 安装
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 安装必要的构建工具
RUN apk add --no-cache python3 make g++ bash

WORKDIR /app/frontend

# 复制前端依赖文件
COPY frontend/package*.json ./

# 安装依赖（使用 --legacy-peer-deps 解决版本冲突）
RUN npm install --registry=https://registry.npmmirror.com --legacy-peer-deps

# 复制前端源码
COPY frontend/ ./

# 构建参数 - 生产环境 API 地址
# 注意：前端和后端在同一个容器中，使用相对路径
ARG VITE_API_BASE_URL=
ARG VITE_ONLYOFFICE_URL=http://localhost:8082
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_ONLYOFFICE_URL=$VITE_ONLYOFFICE_URL

# 构建前端（使用 npm run build 并设置 NODE_ENV=production）
ENV NODE_ENV=production
RUN echo "VITE_API_BASE_URL=$VITE_API_BASE_URL" && \
    echo "VITE_ONLYOFFICE_URL=$VITE_ONLYOFFICE_URL" && \
    npm run build || \
    (echo "=== npm run build failed, trying direct vite ===" && \
    ls -la node_modules/.bin/vite && \
    node node_modules/vite/bin/vite.js build) || \
    (echo "=== All build attempts failed ===" && \
    exit 1)


# ============ Stage 3: 最终运行镜像（后端 + 前端） ============
FROM docker.1ms.run/python:3.11-slim

# 构建参数
ARG CI_PROJECT_TITLE=legal_assistant_v3
ARG VERSION=latest
# 前端和后端在同一容器，使用相对路径访问 API
ARG VITE_API_BASE_URL=
ARG VITE_ONLYOFFICE_URL=http://localhost:8082

# 环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VERSION=${VERSION} \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 更换为阿里云镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装运行时系统依赖
# - libpq5: PostgreSQL 客户端库
# - libreoffice*: 文档转换
# - tesseract-ocr*: OCR 文字识别
# - graphviz: 图表生成
# - curl: 健康检查工具
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        fonts-liberation \
        fonts-noto-cjk \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-chi-tra \
        graphviz \
        curl \
        && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从 python-vendor 镜像复制 Python 包
COPY --from=python-vendor /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-vendor /usr/local/bin /usr/local/bin

# 设置工作目录
WORKDIR /app

# 创建必要的目录
RUN mkdir -p /app/storage /app/uploads /app/logs /app/static

# 复制后端代码
COPY backend/app ./app
COPY backend/main.py ./
COPY backend/app.py ./app.py.bak
COPY backend/legal_consultation_graph.py ./
COPY backend/legal_rag_system.py ./
COPY backend/contract_review_graph.py ./
COPY backend/cost_calculation.py ./
COPY backend/config ./config
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/templates ./templates
COPY backend/langgraphs ./langgraphs
COPY backend/static ./static

# 从 frontend-builder 复制前端构建产物到 static 目录
COPY --from=frontend-builder /app/frontend/dist ./static/frontend

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令 - FastAPI with Uvicorn
# WebSocket 配置: ping 间隔 20s, 超时 300s (5分钟)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--ws-ping-interval", "20", "--ws-ping-timeout", "300"]
