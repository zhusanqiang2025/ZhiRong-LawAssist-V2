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
# 确保 requirements.txt 在项目根目录
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 9. 暴露端口
EXPOSE 7860

# 10. ✅ [必须修改] 启动命令指向 simple_main.py
CMD ["python", "simple_main.py"]