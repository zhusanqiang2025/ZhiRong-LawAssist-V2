#!/bin/bash
# ========================================
# 法律文档助手 - 自动化部署脚本 v1.0
# ========================================
# 使用说明：
# 1. 将此脚本上传到服务器 ~/legal-assistant/ 目录
# 2. 确保项目文件已上传到同一目录
# 3. 修改下方配置区域的变量
# 4. 运行: bash deploy.sh
# ========================================

set -e  # 遇到错误立即退出

# ========================================
# 配置区域 - 请根据实际情况修改
# ========================================

# 服务器 IP（修改为您的实际 IP）
SERVER_IP="YOUR_SERVER_IP"

# 项目目录
PROJECT_DIR="$(pwd)"
echo "项目目录: $PROJECT_DIR"

# Docker 镜像前缀
IMAGE_PREFIX="legal_document_assistantv3"

# ========================================
# 颜色输出函数
# ========================================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ========================================
# 步骤 1: 环境检查
# ========================================
info "========================================="
info "步骤 1: 环境检查"
info "========================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    error "Docker 未安装，请先安装 Docker"
    exit 1
fi
info "Docker 版本: $(docker --version)"

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi
info "Docker Compose 版本: $(docker-compose --version)"

# 检查必要的文件
info "检查项目文件..."
REQUIRED_FILES=("docker-compose.yml" "backend/Dockerfile" "frontend/Dockerfile" "backend/requirements.txt" ".env")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$PROJECT_DIR/$file" ]; then
        error "缺少必要文件: $file"
        exit 1
    fi
    info "✓ 找到: $file"
done

# 检查 .env 配置
info "检查环境变量配置..."
if grep -q "changeme" "$PROJECT_DIR/.env"; then
    warn "检测到 .env 文件中有默认密码，建议修改！"
    warn "请修改以下配置项："
    warn "  - POSTGRES_PASSWORD"
    warn "  - SECRET_KEY"
    warn "  - ONLYOFFICE_JWT_SECRET"
    read -p "是否继续部署？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "部署已取消"
        exit 1
    fi
fi

# ========================================
# 步骤 2: 更新 docker-compose.yml 中的服务器 IP
# ========================================
info ""
info "========================================="
info "步骤 2: 更新前端配置"
info "========================================="

if [ "$SERVER_IP" != "YOUR_SERVER_IP" ]; then
    info "更新前端 API 地址为: $SERVER_IP"
    sed -i "s|VITE_API_BASE_URL=http://localhost:8000|VITE_API_BASE_URL=http://${SERVER_IP}:8000|g" docker-compose.yml
    sed -i "s|VITE_ONLYOFFICE_URL=http://localhost:8082|VITE_ONLYOFFICE_URL=http://${SERVER_IP}:8082|g" docker-compose.yml
else
    warn "未配置服务器 IP，使用默认 localhost"
    warn "部署后请手动修改 docker-compose.yml 中的 IP 地址"
fi

# ========================================
# 步骤 3: 停止并清理旧容器
# ========================================
info ""
info "========================================="
info "步骤 3: 清理旧容器"
info "========================================="

info "停止现有容器..."
docker-compose down 2>/dev/null || true

info "清理旧镜像..."
docker images | grep "$IMAGE_PREFIX" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true

# ========================================
# 步骤 4: 创建必要的目录
# ========================================
info ""
info "========================================="
info "步骤 4: 创建数据目录"
info "========================================="

mkdir -p "$PROJECT_DIR/storage/uploads"
mkdir -p "$PROJECT_DIR/storage/chroma_db"
info "✓ 创建 storage 目录"

# ========================================
# 步骤 5: 构建 Docker 镜像
# ========================================
info ""
info "========================================="
info "步骤 5: 构建 Docker 镜像"
info "========================================="

info "构建后端镜像..."
docker-compose build backend

info "构建前端镜像..."
docker-compose build frontend

info "✓ 镜像构建完成"

# ========================================
# 步骤 6: 启动服务
# ========================================
info ""
info "========================================="
info "步骤 6: 启动服务"
info "========================================="

info "启动所有容器..."
docker-compose up -d

info "等待服务启动..."
sleep 10

# ========================================
# 步骤 7: 检查服务状态
# ========================================
info ""
info "========================================="
info "步骤 7: 检查服务状态"
info "========================================="

info "容器状态："
docker-compose ps

# 检查关键服务是否健康
info ""
info "检查服务健康状态..."

# 检查数据库
if docker-compose ps | grep -q "db.*Up"; then
    info "✓ PostgreSQL 运行中"
else
    error "✗ PostgreSQL 未启动"
fi

# 检查后端
if docker-compose ps | grep -q "backend.*Up"; then
    info "✓ Backend 运行中"
else
    error "✗ Backend 未启动"
fi

# 检查前端
if docker-compose ps | grep -q "frontend.*Up"; then
    info "✓ Frontend 运行中"
else
    error "✗ Frontend 未启动"
fi

# ========================================
# 步骤 8: 数据库迁移
# ========================================
info ""
info "========================================="
info "步骤 8: 运行数据库迁移"
info "========================================="

info "等待数据库完全启动..."
sleep 5

info "运行 Alembic 迁移..."
docker-compose exec -T backend alembic upgrade head || {
    error "数据库迁移失败，请检查日志"
    docker-compose logs backend
    exit 1
}

info "✓ 数据库迁移完成"

# ========================================
# 步骤 9: 初始化 pgvector 扩展
# ========================================
info ""
info "========================================="
info "步骤 9: 初始化 pgvector 扩展"
info "========================================="

info "创建 pgvector 扩展..."
docker-compose exec -T db psql -U admin -d legal_assistant_db -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
    warn "pgvector 扩展创建失败（可能已存在）"
}

info "✓ pgvector 扩展已就绪"

# ========================================
# 步骤 10: 初始化基础数据（可选）
# ========================================
info ""
info "========================================="
info "步骤 10: 初始化基础数据"
info "========================================="

warn "以下初始化步骤为可选，如需跳过请按 Ctrl+C"

# 初始化合同分类
if [ -f "backend/scripts/init_category_tree.py" ]; then
    info "初始化合同分类树..."
    docker-compose exec -T backend python scripts/init_category_tree.py 2>/dev/null || warn "合同分类初始化失败（可能已存在）"
fi

# 初始化合同模板
if [ -f "backend/init_contract_templates.py" ]; then
    info "初始化合同模板..."
    docker-compose exec -T backend python init_contract_templates.py 2>/dev/null || warn "合同模板初始化失败（可能已存在）"
fi

# ========================================
# 部署完成
# ========================================
info ""
info "========================================="
info "🎉 部署完成！"
info "========================================="
info ""
info "访问地址："
info "  前端界面:     http://${SERVER_IP}:3000"
info "  后端 API:     http://${SERVER_IP}:8000"
info "  API 文档:     http://${SERVER_IP}:8000/docs"
info "  Celery 监控:  http://${SERVER_IP}:5555"
info "  ONLYOFFICE:   http://${SERVER_IP}:8082"
info ""
info "常用命令："
info "  查看日志:     docker-compose logs -f"
info "  查看状态:     docker-compose ps"
info "  重启服务:     docker-compose restart"
info "  停止服务:     docker-compose down"
info ""
info "如遇问题，请查看日志："
info "  docker-compose logs backend"
info "  docker-compose logs frontend"
info ""
