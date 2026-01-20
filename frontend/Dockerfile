# frontend/Dockerfile (国内加速版 - 多阶段构建)
# Stage 1: Build the React app
FROM node:lts-alpine as builder

# 使用阿里云 Alpine 镜像源加速 apk 安装
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

WORKDIR /app

# 复制 package 文件并安装依赖
COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

# 添加版本标识ARG，用于强制重建
ARG BUILD_VERSION=latest
ENV BUILD_VERSION=$BUILD_VERSION

# 复制源码
COPY . .

# 接收构建时的环境变量
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_ONLYOFFICE_URL=http://localhost:8082
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_ONLYOFFICE_URL=$VITE_ONLYOFFICE_URL

# 构建应用
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# 同样更换 Alpine 源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 复制构建产物到 Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
