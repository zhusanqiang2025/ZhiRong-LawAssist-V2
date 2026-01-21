# =================================================================
# 路径：E:\legal_document_assistant v3\docker\Dockerfile
# =================================================================

# 1. 基础镜像
FROM python:3.11-slim

# 2. 接收 GitLab 传入的构建参数
ARG APP_VERSION
ARG CI_PROJECT_TITLE

# 3. 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# 4. 更换为国内镜像源 (加快构建速度)
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 5. 安装系统依赖 (保持与 backend/Dockerfile 一致)
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

# 确保复制所有文件
COPY . /app/

# 如果有 .env 注入逻辑 (根据之前的 .gitlab-ci.yml 修改)
RUN if [ -n "$PROJECT_ENV_FILE" ]; then echo "$PROJECT_ENV_FILE" > .env; fi

# 暴露端口
EXPOSE 7860

# ✅ 修改启动命令，指向 backend 目录下的 main.py
CMD ["python", "backend/main.py"]