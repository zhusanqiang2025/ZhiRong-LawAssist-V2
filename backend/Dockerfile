# backend/Dockerfile (极简版 - 仅构建，无配置)
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 国内镜像源加速
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（保留 LibreOffice/OCR 等关键组件）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libreoffice fonts-liberation \
    tesseract-ocr tesseract-ocr-chi-sim graphviz && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app/

# 国内 PyPI 源加速
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--ws-ping-interval", "20", "--ws-ping-timeout", "300"]