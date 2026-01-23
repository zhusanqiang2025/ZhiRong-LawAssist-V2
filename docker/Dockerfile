ARG CI_PROJECT_TITLE
FROM registry.cn-hangzhou.aliyuncs.com/starzz/az:${CI_PROJECT_TITLE}_vendor AS builder

# 环境变量在  docker/Dockerfile.vendor

ENV REDIS_URL=redis://:123myredissecret@redis7.gms.svc.cluster.local:6379/1
ENV CELERY_BROKER_URL=redis://:123myredissecret@redis7.gms.svc.cluster.local:6379/1
ENV CELERY_RESULT_BACKEND=redis://:123myredissecret@redis7.gms.svc.cluster.local:6379/1

# 6. 设置工作目录
WORKDIR /app

# 7. 复制所有文件
COPY . /app/

# 7.5. 安装 Node.js 20.x 并构建前端
# 使用 npm 中国镜像加速下载
RUN cd /app/frontend && \
    npm config set registry https://registry.npmmirror.com && \
    npm ci --verbose && \
    npx vite build && \
    mkdir -p /app/backend/static/frontend && \
    cp -r dist/* /app/backend/static/frontend/ 


# 9. 暴露端口（与 K8s Service 端口匹配）
EXPOSE 8000

# 10. ✅ [必须修改] 启动命令指向 simple_main.py
CMD ["python", "simple_main.py"]