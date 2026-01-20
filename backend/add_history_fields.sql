-- 手动执行 SQL 脚本：为 risk_analysis_sessions 表添加历史任务管理字段
--
-- 使用方法：
-- 1. 连接到您的 PostgreSQL 数据库
-- 2. 执行以下 SQL 语句
--
-- 或者使用 psql 命令行：
-- psql -U your_username -d your_database -f add_history_fields.sql

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
