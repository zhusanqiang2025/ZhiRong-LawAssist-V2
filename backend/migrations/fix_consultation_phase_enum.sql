-- =====================================================
-- 数据库迁移脚本：修复 consultation_phase 枚举类型
-- 文件：fix_consultation_phase_enum.sql
-- 说明：为 consultation_phase 枚举类型添加缺失的 'initial' 状态值
-- =====================================================

-- PostgreSQL 不允许直接向现有枚举类型添加值，因此需要创建临时类型进行过渡

-- 步骤1：创建临时枚举类型，包含所有原有值及新增的 'initial' 值
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'consultation_phase_new') THEN
        CREATE TYPE consultation_phase_new AS ENUM (
            'initial',              -- 初始状态
            'assistant',            -- 律师助理阶段
            'waiting_confirmation', -- 等待用户确认
            'specialist',           -- 专业律师阶段
            'completed'             -- 已完成
        );
        RAISE NOTICE '✅ 创建了新的枚举类型 consultation_phase_new';
    ELSE
        RAISE NOTICE 'ℹ️  枚举类型 consultation_phase_new 已存在';
    END IF;
END $$;

-- 步骤2：更新表结构，将列类型改为新枚举类型
ALTER TABLE consultation_history 
ALTER COLUMN current_phase TYPE consultation_phase_new 
USING current_phase::text::consultation_phase_new;

-- 步骤3：删除旧枚举类型
DROP TYPE IF EXISTS consultation_phase;

-- 步骤4：将新枚举类型重命名为原来的名字
ALTER TYPE consultation_phase_new RENAME TO consultation_phase;

-- 步骤5：更新默认值
ALTER TABLE consultation_history
ALTER COLUMN current_phase SET DEFAULT 'initial';

-- 步骤6：添加或更新列注释
COMMENT ON COLUMN consultation_history.current_phase IS '当前会话阶段：initial(初始) | assistant(律师助理) | waiting_confirmation(等待确认) | specialist(专业律师) | completed(已完成)';

RAISE NOTICE '✅ consultation_phase 枚举类型修复完成';

-- 验证更改
SELECT 
    e.enumlabel as enum_value
FROM pg_enum e 
JOIN pg_type t ON e.enumtypid = t.oid 
WHERE t.typname = 'consultation_phase'
ORDER BY e.enumsortorder;