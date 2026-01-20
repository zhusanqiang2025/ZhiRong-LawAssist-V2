#!/bin/bash
# ========================================
# 文件上传脚本 - 用于 Windows 上传项目到 Linux 服务器
# ========================================
# 使用方法：
# 1. 安装 WinSCP 或使用 Git Bash 的 scp 命令
# 2. 修改下方配置
# 3. 运行: bash upload.sh
# ========================================

# ========================================
# 配置区域 - 请修改为您的实际信息
# ========================================

# 服务器信息
SERVER_USER="root"              # SSH 用户名
SERVER_HOST="YOUR_SERVER_IP"    # 服务器 IP
SERVER_PATH="~/legal-assistant" # 服务器目标路径

# ========================================

echo "========================================="
echo "法律文档助手 - 文件上传工具"
echo "========================================="
echo ""
echo "目标服务器: $SERVER_USER@$SERVER_HOST"
echo "目标路径:   $SERVER_PATH"
echo ""

# 检查 scp 命令是否可用
if ! command -v scp &> /dev/null; then
    echo "错误: scp 命令不可用"
    echo ""
    echo "请选择以下方式之一："
    echo "1. 安装 Git for Windows (包含 scp)"
    echo "2. 使用 WinSCP 图形界面"
    echo "3. 使用 Termius 的 SFTP 功能"
    exit 1
fi

# 确认上传
read -p "是否开始上传？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

# 创建远程目录
echo "创建远程目录..."
ssh "$SERVER_USER@$SERVER_HOST" "mkdir -p $SERVER_PATH/storage/uploads $SERVER_PATH/storage/chroma_db"

# 上传核心文件
echo "上传文件..."
echo "  [1/6] docker-compose.yml"
scp docker-compose.yml "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

echo "  [2/6] .env"
scp .env "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

echo "  [3/6] backend/"
scp -r backend/ "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

echo "  [4/6] frontend/"
scp -r frontend/ "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

echo "  [5/6] deploy.sh"
scp deploy.sh "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

echo "  [6/6] 添加执行权限"
ssh "$SERVER_USER@$SERVER_HOST" "chmod +x $SERVER_PATH/deploy.sh"

echo ""
echo "========================================="
echo "✓ 文件上传完成！"
echo "========================================="
echo ""
echo "下一步操作："
echo "1. SSH 登录到服务器: ssh $SERVER_USER@$SERVER_HOST"
echo "2. 进入项目目录:   cd $SERVER_PATH"
echo "3. 编辑配置文件:   nano .env"
echo "4. 运行部署脚本:   bash deploy.sh"
echo ""
