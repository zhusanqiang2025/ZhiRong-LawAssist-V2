#!/bin/bash
# 彻底清理重建前端脚本

echo "========================================="
echo "🧹 清理 Docker 构建缓存和旧镜像..."
echo "========================================="

# 1. 停止并删除前端容器
echo "📦 停止前端容器..."
docker-compose stop frontend
docker-compose rm -f frontend

# 2. 删除前端镜像
echo "🗑️  删除前端镜像..."
docker rmi legal_document_assistantv3-frontend:latest 2>/dev/null || true

# 3. 清理 BuildKit 缓存
echo "🧹 清理 BuildKit 缓存..."
docker builder prune -af

# 4. 清理悬空镜像和缓存
echo "🧹 清理悬空资源..."
docker image prune -af

# 5. 重新构建（不使用缓存）
echo "🔨 重新构建前端（无缓存）..."
docker-compose build --no-cache --pull frontend

# 6. 启动新容器
echo "🚀 启动新容器..."
docker-compose up -d frontend

# 7. 验证新镜像
echo "✅ 验证新镜像..."
docker images | grep frontend

echo "========================================="
echo "✨ 重建完成！"
echo "========================================="
