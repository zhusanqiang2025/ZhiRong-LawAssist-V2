# Windows 环境下的数据库迁移指南

## 当前数据库配置

根据您的 .env 文件：
- **主机名**: db
- **数据库**: legal_assistant_db
- **用户名**: admin
- **密码**: 01689101Abc
- **端口**: 5432

## 执行迁移的三种方法

### 方法一：使用数据库管理工具（最简单）

#### 选项 A：使用 DBeaver（推荐）

1. **下载并安装 DBeaver**
   - 访问：https://dbeaver.io/download/
   - 下载 Windows 版本并安装

2. **创建数据库连接**
   - 打开 DBeaver
   - 点击"新建数据库连接"
   - 选择 PostgreSQL
   - 配置连接：
     - **主机**: localhost（如果 Docker 运行中）
     - **端口**: 5432
     - **数据库**: legal_assistant_db
     - **用户名**: admin
     - **密码**: 01689101Abc
   - 点击"测试连接"确认

3. **执行 SQL 脚本**
   - 连接成功后，打开 SQL 编辑器
   - 复制 [add_history_fields.sql](backend/add_history_fields.sql) 的内容
   - 粘贴到 SQL 编辑器
   - 点击执行（▶ 按钮）

4. **验证结果**
   ```sql
   SELECT column_name, data_type, is_nullable, column_default
   FROM information_schema.columns
   WHERE table_name = 'risk_analysis_sessions'
     AND column_name IN ('title', 'is_unread', 'is_background')
   ORDER BY ordinal_position;
   ```

#### 选项 B：使用 pgAdmin

1. **下载并安装 pgAdmin 4**
   - 访问：https://www.pgadmin.org/download/
   - 下载 Windows 版本并安装

2. **创建服务器连接**
   - 打开 pgAdmin
   - 右键"Servers" > "创建" > "服务器"
   - 常规标签页：
     - 名称：Legal Assistant DB
   - 连接标签页：
     - 主机：localhost
     - 端口：5432
     - 数据库：legal_assistant_db
     - 用户名：admin
     - 密码：01689101Abc

3. **执行 SQL**
   - 展开服务器 > Databases > legal_assistant_db
   - 点击"工具" > "查询工具"
   - 复制并执行 SQL 脚本

### 方法二：在 Docker 容器中执行

如果您的数据库在 Docker 中运行：

1. **启动 Docker Desktop**

2. **启动数据库容器**
   ```bash
   cd "e:\legal_document_assistant v3"
   docker-compose up -d db
   ```

3. **执行 SQL 脚本**
   ```bash
   # 将 SQL 文件复制到容器
   docker cp backend/add_history_fields.sql legal_assistant_v3_db:/tmp/

   # 在容器内执行
   docker exec -it legal_assistant_v3_db psql -U admin -d legal_assistant_db -f /tmp/add_history_fields.sql
   ```

### 方法三：使用 Python 直接连接

如果无法使用上述方法，可以使用 Python 脚本直接执行：

1. **创建执行脚本**
   ```bash
   cd "e:\legal_document_assistant v3\backend"
   ```

2. **运行迁移脚本**
   ```bash
   # 首先确保数据库服务运行
   docker-compose up -d db

   # 等待数据库启动（约5-10秒）

   # 运行 Alembic 迁移
   alembic upgrade head
   ```

   如果仍然出现 "could not translate host name" 错误，临时修改 DATABASE_URL：

   ```bash
   # 临时设置环境变量
   set DATABASE_URL=postgresql://admin:01689101Abc@localhost:5432/legal_assistant_db
   alembic upgrade head
   ```

## 推荐步骤

根据您的环境，我推荐按以下顺序尝试：

1. **首选：使用 DBeaver**（图形界面，最简单）
2. **备选：Docker 容器执行**（如果数据库在 Docker 中）
3. **最后：使用 Alembic**（需要解决主机名解析问题）

## 验证迁移成功

执行以下任一方法验证：

### 在 SQL 编辑器中：
```sql
-- 查看新增的字段
\d risk_analysis_sessions
-- 或者
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'risk_analysis_sessions'
  AND column_name IN ('title', 'is_unread', 'is_background');
```

### 使用 Alembic 检查：
```bash
cd backend
alembic current
```

应该显示：`add_history_fields`

## 完成后

迁移成功后，历史任务功能即可正常使用：
1. 启动后端服务：`docker-compose up -d backend`
2. 访问风险评估模块
3. 在页面顶部看到"历史任务"按钮
4. 测试创建任务、中途退出、恢复任务等功能

## 常见问题

### Q: Docker Desktop 没有运行？
**A**: 请先启动 Docker Desktop，然后运行：
```bash
docker-compose up -d db
```

### Q: localhost 连接失败？
**A**: 检查数据库容器是否运行：
```bash
docker ps | grep postgres
```

如果没有运行，启动它：
```bash
docker-compose up -d db
```

### Q: 端口冲突？
**A**: 如果 5432 端口被占用，检查端口占用：
```bash
netstat -ano | findstr :5432
```

或修改 docker-compose.yml 中的端口映射。

## SQL 脚本内容（直接复制）

如果您使用数据库管理工具，直接复制以下 SQL 执行：

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

-- 为新字段添加注释
COMMENT ON COLUMN risk_analysis_sessions.title IS '会话标题（用于历史记录显示）';
COMMENT ON COLUMN risk_analysis_sessions.is_unread IS '是否未读';
COMMENT ON COLUMN risk_analysis_sessions.is_background IS '是否为后台任务';
```

## 下一步

迁移完成后，请告诉我结果，我将帮助您：
1. 验证功能是否正常工作
2. 进行端到端测试
3. 解决可能出现的问题
