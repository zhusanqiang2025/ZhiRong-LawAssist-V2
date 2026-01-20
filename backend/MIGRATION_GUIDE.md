# 风险评估模块历史任务保存功能 - 数据库迁移指南

## 概述

已为风险评估模块添加了历史任务保存功能，需要在数据库中添加新的字段。

## 新增字段

在 `risk_analysis_sessions` 表中添加以下字段：

1. **title** (VARCHAR(255), nullable) - 会话标题，用于历史记录显示
2. **is_unread** (BOOLEAN, default TRUE) - 是否未读
3. **is_background** (BOOLEAN, default FALSE) - 是否为后台任务

## 执行方法

### 方法一：使用 Alembic（推荐）

当数据库服务正常运行时：

```bash
cd backend
alembic upgrade head
```

### 方法二：手动执行 SQL 脚本

如果数据库连接有问题，可以手动执行 SQL：

#### 1. 使用 psql 命令行

```bash
cd backend
psql -U postgres -d legal_document_assistant -f add_history_fields.sql
```

#### 2. 使用数据库管理工具

打开 `backend/add_history_fields.sql` 文件，复制 SQL 语句并在您的数据库管理工具（如 pgAdmin、DBeaver 等）中执行。

#### 3. 直接执行 SQL

```sql
-- 添加 title 字段
ALTER TABLE risk_analysis_sessions
ADD COLUMN IF NOT EXISTS title VARCHAR(255);

-- 添加 is_unread 字段
ALTER TABLE risk_analysis_sessions
ADD COLUMN IF NOT EXISTS is_unread BOOLEAN DEFAULT TRUE;

-- 添加 is_background 字段
ALTER TABLE risk_analysis_sessions
ADD COLUMN IF NOT EXISTS is_background BOOLEAN DEFAULT FALSE;

-- 添加注释
COMMENT ON COLUMN risk_analysis_sessions.title IS '会话标题（用于历史记录显示）';
COMMENT ON COLUMN risk_analysis_sessions.is_unread IS '是否未读';
COMMENT ON COLUMN risk_analysis_sessions.is_background IS '是否为后台任务';
```

## 验证迁移

执行以下 SQL 验证字段是否添加成功：

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
| is_unread | boolean | YES | TRUE |
| is_background | boolean | YES | FALSE |

## 故障排除

### 错误：could not translate host name "db"

这个错误表明数据库配置中的主机名 "db" 无法解析。解决方法：

1. **检查数据库是否运行**：
   ```bash
   docker ps | grep postgres
   ```

2. **检查配置文件**：
   查看 `backend/app/core/config.py` 中的 `DATABASE_URL` 设置

3. **使用本地数据库**：
   如果数据库运行在 localhost，可以使用：
   ```bash
   export DATABASE_URL="postgresql://postgres:password@localhost:5432/legal_document_assistant"
   alembic upgrade head
   ```

### 如果数据库在 Docker 中运行

```bash
# 进入 Docker 容器
docker exec -it <postgres_container_name> psql -U postgres -d legal_document_assistant

# 在 psql 中执行
\i /path/to/add_history_fields.sql
```

## 完成

迁移完成后，风险评估模块的历史任务保存功能即可正常使用。您可以：

1. 在风险评估页面顶部看到"历史任务"按钮
2. 点击按钮查看未完成和已完成的历史任务
3. 点击历史任务恢复之前的分析
4. 任务会自动保存并在中途退出后继续执行
