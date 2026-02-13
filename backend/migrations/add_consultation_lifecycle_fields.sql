-- =====================================================
-- 数据库迁移脚本：增加会话生命周期管理字段
-- 文件：add_consultation_lifecycle_fields.sql
-- 说明：为 consultation_history 表增加会话阶段和用户决策字段
-- =====================================================

-- 步骤1：增加新的枚举类型
DO $$ BEGIN
    -- 检查枚举类型是否存在，不存在则创建
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'assistant' AND enumtypid = (
        SELECT oid FROM pg_type WHERE typname = 'consultation_phase'
    )) THEN
        CREATE TYPE consultation_phase AS ENUM (
            'assistant',           -- 律师助理阶段
            'waiting_confirmation', -- 等待用户确认
            'specialist',          -- 专业律师阶段
            'completed'            -- 已完成
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'confirmed' AND enumtypid = (
        SELECT oid FROM pg_type WHERE typname = 'user_decision'
    )) THEN
        CREATE TYPE user_decision AS ENUM (
            'confirmed',  -- 用户确认转交专家
            'cancelled',  -- 用户取消转交
            'pending'     -- 等待用户决策
        );
    END IF;
END $$;

-- 步骤2：增加新字段
ALTER TABLE consultation_history
    ADD COLUMN IF NOT EXISTS current_phase consultation_phase DEFAULT 'assistant',
    ADD COLUMN IF NOT EXISTS user_decision user_decision DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS current_task_id VARCHAR(64);

-- 步骤3：为 status 枚举增加 'cancelled' 值
-- 注意：PostgreSQL 不支持直接修改枚举类型，需要重建
-- 以下是安全的迁移方式：

-- 3.1 创建新的枚举类型（包含 cancelled）
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'consultation_status_new') THEN
        CREATE TYPE consultation_status_new AS ENUM ('active', 'archived', 'cancelled');
    END IF;
END $$;

-- 3.2 转换现有数据
ALTER TABLE consultation_history
    ALTER COLUMN status TYPE consultation_status_new
    USING status::text::consultation_status_new;

-- 3.3 删除旧枚举类型
DROP TYPE IF EXISTS consultation_status;

-- 3.4 重命名新枚举类型
ALTER TYPE consultation_status_new RENAME TO consultation_status;

-- 步骤4：设置默认值
ALTER TABLE consultation_history
    ALTER COLUMN current_phase SET DEFAULT 'assistant',
    ALTER COLUMN user_decision SET DEFAULT 'pending';

-- 步骤5：添加注释
COMMENT ON COLUMN consultation_history.current_phase IS '当前会话阶段：assistant(律师助理) | waiting_confirmation(等待确认) | specialist(专业律师) | completed(已完成)';
COMMENT ON COLUMN consultation_history.user_decision IS '用户决策：confirmed(确认转交) | cancelled(取消转交) | pending(等待决策)';
COMMENT ON COLUMN consultation_history.current_task_id IS '当前执行的 Celery 任务ID';

-- 步骤6：创建索引（提升查询性能）
CREATE INDEX IF NOT EXISTS idx_consultation_status_phase
    ON consultation_history(status, current_phase);

CREATE INDEX IF NOT EXISTS idx_consultation_user_decision
    ON consultation_history(user_decision) WHERE user_decision = 'pending';

-- 步骤7：更新现有数据（为历史记录设置合理的默认值）
UPDATE consultation_history
SET
    current_phase = CASE
        WHEN specialist_type IS NOT NULL THEN 'specialist'
        WHEN classification IS NOT NULL THEN 'waiting_confirmation'
        ELSE 'assistant'
    END,
    user_decision = CASE
        WHEN specialist_type IS NOT NULL THEN 'confirmed'
        ELSE 'pending'
    END
WHERE current_phase IS NULL OR user_decision IS NULL;

COMMIT;

-- 验证迁移结果
SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'consultation_history'
    AND column_name IN ('status', 'current_phase', 'user_decision', 'current_task_id')
ORDER BY ordinal_position;
