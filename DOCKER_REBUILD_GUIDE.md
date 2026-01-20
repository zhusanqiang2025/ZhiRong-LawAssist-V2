# Docker构建问题解决方案

## 问题概述

在Windows环境下使用Docker Desktop构建前端镜像时，即使源代码已修改，Docker构建仍使用旧的缓存版本，导致镜像不包含最新代码。

## 根本原因

### 1. Docker Desktop for Windows的文件系统层问题

Docker Desktop在Windows上使用WSL2后端时，文件变更检测存在延迟和缓存问题。

### 2. Git Bash路径转换问题

在Git Bash中执行Docker命令时，Unix路径被错误转换为Windows路径：
```bash
# 输入: /app/src/context/
# 实际: C:/Program Files/Git/app/src/context/
```

### 3. Docker BuildKit的缓存机制

BuildKit有复杂的缓存机制，`--no-cache` 参数不能完全清除所有缓存层。

## 解决方案

### 方案A：使用自动化脚本（推荐）

#### 1. 完整重建（用于生产部署）

双击运行：`rebuild-frontend.bat` 或 `rebuild-frontend.ps1`

脚本会自动执行：
1. 停止并删除旧容器
2. 删除旧镜像
3. 清理Docker构建缓存
4. 重新构建镜像（使用BUILD_VERSION时间戳强制重建）
5. 启动新容器
6. 验证文件更新

#### 2. 快速更新（用于开发调试）

双击运行：`quick-update.bat`

脚本会：
1. 本地构建前端（npm run build）
2. 直接复制dist到容器
3. 验证文件更新

**优点：** 速度快（约10-20秒），适合频繁修改
**缺点：** 容器重启后更新会丢失

### 方案B：手动命令（理解原理）

#### PowerShell中执行

```powershell
# 1. 停止并删除
docker-compose stop frontend
docker-compose rm -f frontend
docker rmi legal_document_assistantv3-frontend

# 2. 清理缓存
docker builder prune -af

# 3. 重新构建（传入时间戳）
$version = Get-Date -Format "yyyyMMddHHmmss"
docker-compose build --no-cache --build-arg BUILD_VERSION=$version frontend

# 4. 启动
docker-compose up -d frontend
```

#### CMD中执行

```batch
REM 1. 停止并删除
docker-compose stop frontend
docker-compose rm -f frontend
docker rmi legal_document_assistantv3-frontend

REM 2. 清理缓存
docker builder prune -f

REM 3. 重新构建
docker-compose build --no-cache --build-arg BUILD_VERSION=%date%%time% frontend

REM 4. 启动
docker-compose up -d frontend
```

### 方案C：修改docker-compose.yml（一次性配置）

在 `docker-compose.yml` 中添加：

```yaml
frontend:
  container_name: legal_assistant_v3_frontend
  build:
    context: ./frontend
    dockerfile: Dockerfile
    args:
      - VITE_API_BASE_URL=http://localhost:8000
      - VITE_ONLYOFFICE_URL=http://localhost:8082
    # 添加这些
    cache_from: []
  ports:
    - "3000:80"
```

## 日常使用流程

### 开发阶段（频繁修改）

```bash
# 方式1：使用快速更新脚本（推荐）
quick-update.bat

# 方式2：手动执行
cd frontend
npm run build
docker cp frontend/dist/. legal_assistant_v3_frontend:/usr/share/nginx/html/
```

### 测试阶段（验证构建）

```bash
# 使用完整重建脚本
rebuild-frontend.bat
```

### 生产部署（确保最新）

```bash
# 1. 使用完整重建脚本
rebuild-frontend.bat

# 2. 验证文件
docker exec legal_assistant_v3_frontend sh -c "cat /usr/share/nginx/html/assets/index-*.js | head -1"

# 3. 强制刷新浏览器
# Windows: Ctrl+Shift+R
# Mac: Cmd+Shift+R
```

## 验证更新成功

### 1. 检查容器中的文件

```bash
# 查看JS文件名（包含哈希值）
docker exec legal_assistant_v3_frontend sh -c "ls -lh /usr/share/nginx/html/assets/index-*.js"

# 应该看到类似：
# index-xtgfmozo.js  (新版本)
# 而不是：
# index-DuWCpoCT.js  (旧版本)
```

### 2. 检查浏览器加载的文件

在浏览器开发者工具中：
1. 打开 Network 标签
2. 刷新页面
3. 查看 `index-*.js` 文件名
4. 确认是最新版本

### 3. 清除浏览器缓存

如果文件名正确但内容仍旧：
- **Chrome:** F12 → Application → Clear storage → Clear site data
- **Firefox:** Ctrl+Shift+Delete → Cache
- **Edge:** Ctrl+Shift+Delete → 缓存

## 故障排除

### 问题1：脚本执行失败

**原因：** 可能是在Git Bash中执行
**解决：** 右键脚本 → "使用PowerShell运行"

### 问题2：构建后还是旧版本

**原因：** Docker缓存未清理
**解决：**
```bash
# 完全清理Docker
docker-compose down
docker system prune -af --volumes
docker volume prune -f

# 重新构建
rebuild-frontend.bat
```

### 问题3：容器启动失败

**原因：** 端口被占用
**解决：**
```bash
# 查看占用3000端口的进程
netstat -ano | findstr :3000

# 终止进程（替换PID）
taskkill /PID <进程ID> /F
```

## 技术细节

### BUILD_VERSION的作用

在Dockerfile中：
```dockerfile
ARG BUILD_VERSION=latest
ENV BUILD_VERSION=$BUILD_VERSION
```

每次构建时传入不同的时间戳：
```bash
--build-arg BUILD_VERSION=20260114091530
```

这会改变ENV层，强制重建后续所有层。

### 为什么--no-cache不够

`--no-cache` 只禁用BuildKit的元数据缓存，但：
1. 不清除层缓存（layer cache）
2. 不清除构建上下文缓存
3. 在Windows上有额外的文件系统缓存

完整的清理需要：
```bash
docker builder prune -af  # 清除所有构建缓存
docker system prune -af     # 清除所有系统缓存
```

## 最佳实践

### 1. 开发环境

使用 `quick-update.bat` 快速迭代：
- 优点：速度快（10-20秒）
- 缺点：容器重启后丢失

### 2. 测试环境

使用 `rebuild-frontend.bat` 确保一致性：
- 优点：完整的构建流程
- 缺点：较慢（1-2分钟）

### 3. 生产环境

除完整重建外，还应：
1. 标记镜像版本
2. 推送到镜像仓库
3. 使用docker-compose.prod.yml

## 相关文件

- `rebuild-frontend.ps1` - PowerShell完整重建脚本
- `rebuild-frontend.bat` - CMD完整重建脚本
- `quick-update.bat` - 快速更新脚本
- `DOCKER_BUILD_FIX.md` - 详细技术文档
- `frontend/Dockerfile` - 已添加BUILD_VERSION支持

## 支持

如遇到其他问题，请检查：
1. Docker Desktop是否正常运行
2. 是否有足够的磁盘空间（至少10GB）
3. WSL2是否正确安装（如使用WSL2后端）
