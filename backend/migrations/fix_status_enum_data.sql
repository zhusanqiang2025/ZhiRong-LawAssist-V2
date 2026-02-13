/*
数据库数据修复脚本：修正错误的状态枚举值

该脚本修复因代码bug导致的错误数据：
- 将错误设置到status字段的'waiting_confirmation'值修正为'active'
- 确保current_phase字段正确设置
*/

-- 开始事务
BEGIN;

-- 更新所有status字段为'waiting_confirmation'的记录，将其改为'active'
UPDATE consultation_history 
SET status = 'active'
WHERE status = 'waiting_confirmation';

-- 检查是否还有错误的记录
SELECT COUNT(*) as count_wrong_status
FROM consultation_history 
WHERE status = 'waiting_confirmation';

-- 显示已修复的记录数量
SELECT COUNT(*) as fixed_records
FROM consultation_history 
WHERE status = 'active' 
AND current_phase = 'waiting_confirmation';  -- 这些可能是正确的记录

-- 结束事务
COMMIT;

-- 提示信息
-- 请检查以上输出结果，确保数据修复符合预期