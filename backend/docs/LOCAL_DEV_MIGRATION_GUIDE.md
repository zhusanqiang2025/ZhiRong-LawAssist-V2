# 本地开发环境 - 数据库迁移指南

## 当前状态

您的数据库连接配置（从 .env 文件）：
- **主机名**: db
- **数据库**: legal_assistant_db
- **用户名**: admin
- **密码**: 01689101Abc
- **端口**: 5432

## 问题诊断

当前遇到的问题：**PostgreSQL 数据库服务未运行**

错误信息：
```
connection to server at "localhost", port 5432 failed: Connection refused
```

这表示：
1. Docker Desktop 未运行（如果您使用 Docker）
2. 或者本地 PostgreSQL 服务未启动（如果您使用本地安装）

## 解决方案

### 方案 A：使用 Docker（推荐）

#### 1. 启动 Docker Desktop
- 在 Windows 开始菜单中找到 "Docker Desktop" 并启动
- 等待 Docker 完全启动（系统托盘图标变为正常状态）

#### 2. 启动数据库容器
打开 PowerShell 或命令提示符，执行：
```bash
cd "e:\legal_document_assistant v3"
docker-compose up -d db
```

等待容器启动完成（约 5-10 秒）。

#### 3. 验证数据库运行
```bash
docker ps | grep postgres
```

应该看到容器 `legal_assistant_v3_db` 状态为 `Up`。

#### 4. 执行迁移
```bash
cd backend
python run_migration.py
```

### 方案 B：使用本地 PostgreSQL

如果您在本地安装了 PostgreSQL（不使用 Docker）：

#### 1. 启动 PostgreSQL 服务
打开 PowerShell（管理员权限）：
```bash
# 查找 PostgreSQL 服务名称
Get-Service | Where-Object {$_.Name -like "*postgres*"}

# 启动服务（将 SERVICE_NAME 替换为实际的服务名）
Start-Service SERVICE_NAME
```

或者通过 Windows 服务管理器：
- 按 `Win + R`，输入 `services.msc`
- 找到 PostgreSQL 服务
- 右键 > 启动

#### 2. 修改 .env 文件
将数据库主机名从 `db` 改为 `localhost`：
```env
# 原配置
POSTGRES_SERVER=db

# 修改为
POSTGRES_SERVER=localhost
```

#### 3. 执行迁移
```bash
cd "e:\legal_document_assistant v3\backend"
python run_migration.py
```

### 方案 C：使用数据库管理工具（最简单）

如果您不想处理命令行：

#### 1. 下载并安装 DBeaver
- 访问：https://dbeaver.io/download/
- 下载免费的 Community Edition

#### 2. 连接数据库
配置连接信息：
- **主机**: localhost
- **端口**: 5432
- **数据库**: legal_assistant_db
- **用户名**: admin
- **密码**: 01689101Abc

#### 3. 执行 SQL 脚本
在 DBeaver 的 SQL 编辑器中，复制并执行以下 SQL：

```sql
-- 添加 title 字段（会话标题）
ALTER TABLE risk_analysis_sessions
ADD COLUMN IF NOT EXISTS title VARCHAR(255);

-- 添加 is_unread 字段（是否未读）
ALTER TABLE risk_analysis_sessions
ADD COLUMN IF NOT EXISTS is_unread BOOLEAN DEFAULT TRUE;

-- 添加 is_background 字段（是否为后台任务）
ALTER TABLE risk_analysis_sessions
ADD COLUMN IF NOT EXISTS is_background BOOLEAN DEFAULT FALSE;

-- 添加注释
COMMENT ON COLUMN risk_analysis_sessions.title IS '会话标题（用于历史记录显示）';
COMMENT ON COLUMN risk_analysis_sessions.is_unread IS '是否未读';
COMMENT ON COLUMN risk_analysis_sessions.is_background IS '是否为后台任务';
```

## 验证迁移成功

执行以下 SQL 验证：

```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'risk_analysis_sessions'
  AND column_name IN ('title', 'is_unread', 'is_background')
ORDER BY ordinal_position;
```

预期结果：

| column_name | data_type | is_nullable | column_default |
|-------------|-----------|-------------|----------------|
| title | character varying | YES | NULL |
| is_unread | boolean | YES | true |
| is_background | boolean | YES | false |

## 完成后的步骤

迁移成功后：

1. **启动后端服务**
   ```bash
   cd "e:\legal_document_assistant v3"
   docker-compose up -d backend
   ```
   或
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. **测试历史任务功能**
   - 打开浏览器访问 `http://localhost:8000`
   - 进入风险评估模块
   - 在页面顶部应该看到"历史任务"按钮
   - 创建新任务并测试中途退出功能

## 常见问题排查

### Q: Docker Desktop 无法启动？
**A**:
- 检查 Windows 虚拟化是否启用：任务管理器 > 性能 > CPU > 虚拟化
- 确保已启用 WSL 2：在 PowerShell 运行 `wsl --install`
- 重启 Docker Desktop

### Q: 数据库容器启动失败？
**A**:
```bash
# 查看容器日志
docker logs legal_assistant_v3_db

# 重新创建容器
docker-compose down db
docker-compose up -d db
```

### Q: 本地 PostgreSQL 服务找不到？
**A**:
- 检查是否安装了 PostgreSQL
- 下载地址：https://www.postgresql.org/download/windows/
- 默认安装路径：`C:\Program Files\PostgreSQL\[版本]\bin`

### Q: 端口 5432 被占用？
**A**:
```bash
# 查看端口占用
netstat -ano | findstr :5432

# 如果被其他程序占用，可以：
# 1. 停止占用端口的程序
# 2. 或修改 PostgreSQL 配置使用其他端口
```

## 需要帮助？

如果遇到问题，请提供以下信息：
1. 您使用的是 Docker 还是本地 PostgreSQL？
2. 错误信息的完整输出
3. Docker 容器状态（如果使用 Docker）：`docker ps -a`

---

**下一步**: 确保数据库服务运行后，执行 `python run_migration.py` 完成迁移。
