-- 智能咨询模块迁移脚本：添加 session_state 字段
-- 修复 UndefinedColumn: consultation_history.session_state does not exist

-- 检查并添加 session_state 字段
DO $$
BEGIN
    -- 检查列是否存在
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'consultation_history'
        AND column_name = 'session_state'
    ) THEN
        -- 添加 session_state 列 (JSONB 类型，支持 JSON 查询)
        ALTER TABLE consultation_history
        ADD COLUMN session_state JSONB;

        RAISE NOTICE '✅ 已添加 session_state 列 (JSONB类型)';
    ELSE
        RAISE NOTICE 'ℹ️  session_state 列已存在，跳过添加';
    END IF;

    -- 检查并重命名旧的 session_data 列（如果存在）
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'consultation_history'
        AND column_name = 'session_data'
    ) THEN
        ALTER TABLE consultation_history
        RENAME COLUMN session_data TO session_state;

        RAISE NOTICE '✅ 已重命名 session_data 为 session_state';

        -- 检查列类型，如果不是 JSONB 则转换
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'consultation_history'
            AND column_name = 'session_state'
            AND data_type != 'jsonb'
        ) THEN
            ALTER TABLE consultation_history
            ALTER COLUMN session_state TYPE JSONB USING session_state::JSONB;

            RAISE NOTICE '✅ 已将 session_state 列类型转换为 JSONB';
        END IF;
    END IF;

    -- 添加列注释
    COMMENT ON COLUMN consultation_history.session_state IS '会话状态上下文(替代Redis缓存)，包含分类结果、律师输出等信息';

    RAISE NOTICE '✅ 迁移完成：session_state 字段已就绪';

END $$;

-- 验证：检查 session_state 列是否存在
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'consultation_history'
AND column_name = 'session_state';
