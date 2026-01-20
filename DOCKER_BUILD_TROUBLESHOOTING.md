# Docker 构建缓存问题诊断与修复指南

## 问题现象
修改前端代码后执行 `docker-compose build frontend`，构建成功但运行时仍然是旧代码。

## 根本原因

### 1. Docker BuildKit 层缓存
- BuildKit 使用内容哈希来决定是否重用层
- 即使文件修改了，如果某些元数据相同，可能误用缓存
- `COPY /app/dist /usr/share/nginx/html` 这一层特别容易被缓存

### 2. 多个镜像标签混乱
```bash
# 存在多个前端镜像，容易混淆
legal_document_assistantv3-frontend:latest  # 当前使用
legal_document_assistant-frontend:latest     # 旧版本
legal-doc-frontend:latest                    # 更旧版本
```

### 3. 容器未完全重启
- `docker-compose up -d` 可能不会完全替换容器
- 旧容器进程可能仍在使用旧的内存映射

## 诊断步骤

### 步骤 1：检查当前运行的镜像
```bash
docker inspect legal_assistant_v3_frontend --format '{{.Image}}'
```

### 步骤 2：检查镜像创建时间
```bash
docker images | grep frontend
```

### 步骤 3：检查容器中的文件
```bash
docker exec legal_assistant_v3_frontend ls -la /usr/share/nginx/html/assets/ | grep UserKnowledge
docker exec legal_assistant_v3_frontend cat /usr/share/nginx/html/assets/UserKnowledgeBasePage-*.js | grep -o "disabled:[^,}]*" | head -5
```

### 步骤 4：检查 Docker 缓存
```bash
docker system df
docker builder ls
```

## 解决方案

### 方案 A：快速修复（适用于小改动）
```bash
# 1. 停止并删除容器
docker-compose stop frontend
docker-compose rm -f frontend

# 2. 删除镜像
docker rmi legal_document_assistantv3-frontend:latest

# 3. 重新构建
docker-compose build --no-cache frontend

# 4. 启动
docker-compose up -d frontend
```

### 方案 B：彻底清理（适用于大改动或缓存严重时）
```bash
# 1. 清理所有构建缓存
docker builder prune -af

# 2. 清理悬空镜像
docker image prune -af

# 3. 停止并删除容器和镜像
docker-compose down
docker rmi legal_document_assistantv3-frontend:latest

# 4. 强制重建
docker-compose build --no-cache --pull frontend

# 5. 启动
docker-compose up -d frontend
```

### 方案 C：使用专用构建脚本（推荐）
```bash
# 使用项目中的重建脚本
bash rebuild-frontend-clean.sh

# 或者使用 Docker Compose 构建配置
docker-compose -f docker-compose.build.yml build --no-cache frontend
```

## 预防措施

### 1. 优化 Dockerfile
确保 Dockerfile 使用最佳实践：

```dockerfile
# frontend/Dockerfile
FROM node:lts-alpine AS builder

# 设置工作目录
WORKDIR /app

# 先复制 package 文件，利用缓存
COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

# 复制源代码
COPY . .

# 强制每次都重新构建（开发环境）
ARG BUILD_TIMESTAMP
ENV BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

# 构建
RUN npm run build

# 生产镜像
FROM nginx:alpine
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 使用 BUILD_TIMESTAMP 强制使层失效
ARG BUILD_TIMESTAMP
ENV BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 2. 使用构建参数
```bash
# 每次构建时传入时间戳
docker-compose build \
  --build-arg BUILD_TIMESTAMP=$(date +%s) \
  frontend
```

### 3. 修改 docker-compose.yml
```yaml
services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - VITE_API_BASE_URL=http://localhost:8000
        - VITE_ONLYOFFICE_URL=http://localhost:8082
        - BUILD_TIMESTAMP=${TIMESTAMP}
    image: legal_document_assistantv3-frontend:latest
    pull_policy: build  # 强制使用本地构建的镜像
```

### 4. 添加健康检查
```yaml
services:
  frontend:
    # ... 其他配置
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:80"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

## 验证修复

### 1. 检查镜像哈希
```bash
# 构建前后对比镜像 ID
docker images --digests | grep frontend
```

### 2. 检查文件修改时间
```bash
docker exec legal_assistant_v3_frontend stat /usr/share/nginx/html/assets/UserKnowledgeBasePage-*.js
```

### 3. 检查构建日志
```bash
# 查看构建日志中的关键文件
docker-compose build frontend 2>&1 | grep -E "(COPY|UserKnowledge|disabled)"
```

### 4. 浏览器验证
1. 打开开发者工具 (F12)
2. 勾选 "Disable cache"
3. 硬刷新 (Ctrl+Shift+R 或 Cmd+Shift+R)
4. 检查 Network 面板，确认加载的是新的 JS 文件

## 常见错误

### 错误 1：修改未生效
**症状**：修改代码后构建，但功能没变化
**原因**：浏览器缓存或 Docker 缓存
**解决**：
```bash
# 清理浏览器缓存
# 清理 Docker 缓存
docker builder prune -af
docker-compose build --no-cache frontend
```

### 错误 2：构建很快但代码是旧的
**症状**：构建时间异常短（<10秒）
**原因**：使用了缓存
**解决**：
```bash
docker-compose build --no-cache --pull frontend
```

### 错误 3：容器启动但无法访问
**症状**：容器运行中但页面 404
**原因**：镜像构建失败或文件未正确复制
**解决**：
```bash
# 检查镜像内容
docker run --rm legal_document_assistantv3-frontend:latest ls -la /usr/share/nginx/html

# 重新构建
docker-compose build --no-cache frontend
```

## 日常开发最佳实践

### 1. 开发模式
```bash
# 使用卷挂载直接修改
docker-compose -f docker-compose.dev.yml up -d frontend
```

### 2. 生产构建
```bash
# 使用构建脚本
bash rebuild-frontend-clean.sh
```

### 3. 调试构建问题
```bash
# 查看详细构建日志
DOCKER_BUILDKIT=1 docker-compose build --progress=plain frontend

# 进入构建环境调试
docker run --rm -it -v $(pwd)/frontend:/app -w /app node:lts-alpine sh
```

## 监控与维护

### 定期清理
```bash
# 每周执行一次
docker system prune -af --volumes
docker builder prune -af
```

### 监控磁盘使用
```bash
# 检查 Docker 占用空间
docker system df

# 检查镜像大小
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
```

### 清理旧镜像
```bash
# 删除一周前的镜像
docker images --format "{{.ID}}\t{{.CreatedAt}}" | grep "week ago" | awk '{print $1}' | xargs docker rmi -f
```

## 附录：完整清理脚本

```bash
#!/bin/bash
# complete-cleanup.sh - 完整清理 Docker 环境

echo "========================================="
echo "🧹 完整 Docker 清理"
echo "========================================="

# 停止所有容器
echo "📦 停止所有容器..."
docker-compose down

# 删除前端相关镜像
echo "🗑️  删除前端镜像..."
docker rmi legal_document_assistantv3-frontend:latest 2>/dev/null || true
docker rmi legal_document_assistant-frontend:latest 2>/dev/null || true
docker rmi legal-doc-frontend:latest 2>/dev/null || true

# 清理构建缓存
echo "🧹 清理构建缓存..."
docker builder prune -af

# 清理所有悬空对象
echo "🧹 清理悬空对象..."
docker system prune -af --volumes

# 重新构建
echo "🔨 重新构建..."
docker-compose build --no-cache frontend

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 显示状态
echo "📊 容器状态..."
docker-compose ps

echo "========================================="
echo "✨ 清理完成！"
echo "========================================="
```

## 联系与支持

如果问题仍然存在，请收集以下信息：
1. Docker 版本：`docker version`
2. Docker Compose 版本：`docker-compose version`
3. 构建日志：`docker-compose build frontend 2>&1 | tee build.log`
4. 容器日志：`docker-compose logs frontend`
