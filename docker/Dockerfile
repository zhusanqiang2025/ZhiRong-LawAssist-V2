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

# 7. 安装 Python 依赖
# 先复制 requirements.txt
COPY requirements.txt ./
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 8. 复制项目所有代码 (包括 backend 和 frontend/dist)
COPY . .

# 9. 暴露端口 (必须是 7860)
EXPOSE 7860

# 10. 启动命令
# 指向 backend/main.py，端口 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860", "--ws-ping-interval", "20", "--ws-ping-timeout", "300"]