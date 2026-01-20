# Docker构建缓存问题 - 完整解决方案

## 问题描述

在Windows环境下使用Docker Desktop构建前端镜像时，即使使用 `--no-cache` 参数，Docker也没有使用最新的源代码，导致构建的镜像始终是旧版本。

## 根本原因分析

### 1. Docker Desktop for Windows的文件系统层问题

**问题：** Docker Desktop在Windows上使用WSL2后端时，文件系统的变更检测存在延迟和缓存问题。

**具体表现：**
- 修改文件后，Docker构建时的COPY操作可能不会检测到文件变化
- 即使使用 `--no-cache`，BuildKit仍可能使用缓存层

### 2. Git Bash的路径转换问题

**问题：** 在Git Bash中执行Docker命令时，Unix风格路径会被转换为Windows路径。

**示例：**
```bash
# 命令
docker run --rm test-context ls /app/src/context/

# 实际执行
ls: C:/Program Files/Git/app/src/context/: No such file or directory
```

### 3. Docker BuildKit的缓存机制

**问题：** Docker BuildKit（默认构建引擎）有复杂的缓存机制，`--no-cache` 不能完全清除所有缓存。

## 完整解决方案

### 方案1：修改docker-compose.yml，添加构建参数（推荐）

修改 `docker-compose.yml` 中的frontend服务配置：

```yaml
frontend:
  container_name: legal_assistant_v3_frontend
  build:
    context: ./frontend
    dockerfile: Dockerfile
    # 添加这些参数禁用缓存
    args:
      - VITE_API_BASE_URL=http://localhost:8000
      - VITE_ONLYOFFICE_URL=http://localhost:8082
    # 强制不使用缓存
    cache_from: []
    # 禁用BuildKit缓存
    x-bake:
      no-cache: true
  ports:
    - "3000:80"
  depends_on:
    - backend
    - onlyoffice
  restart: always
  networks:
    - app-network
```

### 方案2：修改Dockerfile，添加版本标识

修改 `frontend/Dockerfile`，在每一层添加时间戳或版本号：

```dockerfile
# frontend/Dockerfile (国内加速版 - 多阶段构建)
# Stage 1: Build the React app
FROM node:lts-alpine as builder

# 使用阿里云 Alpine 镜像源加速 apk 安装
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

WORKDIR /app

# 复制 package 文件并安装依赖
COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

# 添加一个ARG作为版本标识，每次构建时传入不同值可强制重建
ARG BUILD_VERSION=latest
ENV BUILD_VERSION=$BUILD_VERSION

# 复制源码（添加时间戳注释）
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
```

构建时传入版本号：
```bash
docker-compose build --build-arg BUILD_VERSION=$(date +%s) frontend
```

### 方案3：使用PowerShell或CMD代替Git Bash（最可靠）

**问题：** Git Bash在Windows上有路径转换问题。

**解决：** 使用PowerShell或CMD执行Docker命令。

创建 `rebuild-frontend.ps1`（PowerShell脚本）：

```powershell
# rebuild-frontend.ps1
Write-Host "停止并删除旧容器..."
docker-compose stop frontend
docker-compose rm -f frontend

Write-Host "删除旧镜像..."
docker rmi legal_document_assistantv3-frontend

Write-Host "清理Docker构建缓存..."
docker builder prune -af

Write-Host "重新构建前端镜像..."
docker-compose build --no-cache --build-arg BUILD_VERSION=$(Get-Date -Format "yyyyMMddHHmmss") frontend

Write-Host "启动新容器..."
docker-compose up -d frontend

Write-Host "完成！"
```

使用方法：
```powershell
# 在PowerShell中执行
.\rebuild-frontend.ps1
```

### 方案4：修改.dockerignore确保不忽略关键文件

确认 `frontend/.dockerignore` 文件内容正确：

```
# 忽略 node_modules 文件夹
node_modules

# 忽略构建输出文件夹
build
dist

# 忽略 npm 调试日志
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# 忽略本地环境变量文件
.env.local
.env.*.local

# 忽略 Git 文件夹
.git

# 忽略编辑器配置
.vscode
.idea
*.swp
*.swo

# 忽略测试覆盖率
coverage
.nyc_output

# 忽略日志
logs
*.log

# ⚠️ 重要：不要忽略 src 目录
# 如果有这行，删除它：
# src
```

### 方案5：使用docker命令代替docker-compose（临时方案）

直接使用docker命令构建，可以更好地控制构建过程：

```bash
# 停止并删除旧容器和镜像
docker stop legal_assistant_v3_frontend
docker rm legal_assistant_v3_frontend
docker rmi legal_document_assistantv3-frontend

# 清理构建缓存
docker builder prune -af

# 构建新镜像（使用PowerShell或CMD）
cd frontend
docker build --no-cache --build-arg BUILD_VERSION=%date% -t legal_document_assistantv3-frontend .

# 启动新容器
docker run -d --name legal_assistant_v3_frontend -p 3000:80 --network legal_document_assistantv3_app-network legal_document_assistantv3-frontend
```

## 推荐的工作流程

### 日常开发流程

1. **修改前端代码**

2. **本地构建测试**
   ```bash
   cd frontend
   npm run build
   ```

3. **验证构建结果**
   ```bash
   ls -la dist/assets/index-*.js
   ```

4. **重新构建Docker镜像**
   ```powershell
   # 使用PowerShell执行
   .\rebuild-frontend.ps1
   ```

5. **验证容器中的文件**
   ```bash
   docker exec legal_assistant_v3_frontend ls -la /usr/share/nginx/html/assets/
   ```

6. **刷新浏览器**
   - 按 Ctrl+Shift+R（强制刷新）
   - 或清除浏览器缓存

### 快速更新流程（开发时）

如果只是修改了少量文件，可以直接复制到容器：

```bash
# 1. 本地构建
cd frontend
npm run build

# 2. 复制到容器
docker cp dist/. legal_assistant_v3_frontend:/usr/share/nginx/html/

# 3. 验证
docker exec legal_assistant_v3_frontend ls -la /usr/share/nginx/html/assets/
```

## 永久解决方案

创建自动化脚本 `dev-rebuild.bat`：

```batch
@echo off
echo ========================================
echo 前端自动重新构建脚本
echo ========================================

echo.
echo [1/6] 停止前端容器...
docker-compose stop frontend

echo [2/6] 删除前端容器...
docker-compose rm -f frontend

echo [3/6] 删除前端镜像...
docker rmi legal_document_assistantv3-frontend 2>nul

echo [4/6] 清理Docker缓存...
docker builder prune -f >nul 2>&1

echo [5/6] 重新构建前端镜像...
docker-compose build frontend --no-cache

echo [6/6] 启动前端容器...
docker-compose up -d frontend

echo.
echo ========================================
echo 重建完成！
echo ========================================
echo.
echo 请按 Ctrl+F5 刷新浏览器
echo.
pause
```

## 环境配置建议

### 1. Docker Desktop设置

在Docker Desktop中：
1. 打开 Settings → Resources
2. 确保磁盘空间充足（至少10GB）
3. 设置 "Disk image size" 为动态增长

### 2. 文件共享设置

在Docker Desktop中：
1. 打开 Settings → Resources → File Sharing
2. 确保项目路径已添加
3. 取消勾选 "Automatically sync changes"

### 3. WSL2配置（如果使用WSL2后端）

创建 `~/.wslconfig` 文件：

```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
localhostForwarding=true
```

## 故障排除

### 问题1：构建后文件还是旧的

**解决：**
1. 完全退出Docker Desktop
2. 删除 `%APPDATA%\Docker\` 目录下的缓存
3. 重启Docker Desktop
4. 重新构建

### 问题2：构建时间过长

**解决：**
使用多阶段构建缓存（仅在依赖变化时重建）：

```dockerfile
# 仅在package.json变化时重新安装依赖
COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

# 添加版本ARG
ARG BUILD_VERSION
ENV BUILD_VERSION=$BUILD_VERSION

# 复制源码
COPY . .
```

### 问题3：浏览器缓存问题

**解决：**
1. 在nginx.conf中添加禁用缓存头
2. 或使用构建哈希（Vite默认已启用）

## 总结

**最可靠的方法：**
1. 使用PowerShell或CMD代替Git Bash执行Docker命令
2. 每次修改后运行 `dev-rebuild.bat` 脚本
3. 使用 `BUILD_VERSION` 参数强制重建
4. 清除浏览器缓存（Ctrl+Shift+R）

**避免的做法：**
1. ❌ 在Git Bash中执行docker命令
2. ❌ 依赖 `--no-cache` 参数（不可靠）
3. ❌ 多次快速重新构建（会导致缓存混乱）
