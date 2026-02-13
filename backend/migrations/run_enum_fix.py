"""
数据库迁移脚本：修复 consultation_phase 枚举类型
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

def run_migration():
    print("开始执行数据库迁移：修复 consultation_phase 枚举类型...")
    
    # SQL脚本内容
    sql_script = """
    -- =====================================================
    -- 数据库迁移脚本：修复 consultation_phase 枚举类型
    -- 文件：fix_consultation_phase_enum.sql
    -- 说明：为 consultation_phase 枚举类型添加缺失的 'initial' 状态值
    -- =====================================================

    -- PostgreSQL 不允许直接向现有枚举类型添加值，因此需要创建临时类型进行过渡

    -- 步骤1：检查并创建临时枚举类型，包含所有原有值及新增的 'initial' 值
    DO $$ 
    BEGIN
        -- 检查是否已经存在包含'initial'的新枚举类型
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t 
            JOIN pg_enum e ON t.oid = e.enumtypid 
            WHERE t.typname = 'consultation_phase' 
            AND e.enumlabel = 'initial'
        ) THEN
            -- 创建新的枚举类型，包含所有值
            CREATE TYPE consultation_phase_new AS ENUM (
                'initial',              -- 初始状态
                'assistant',            -- 律师助理阶段
                'waiting_confirmation', -- 等待用户确认
                'specialist',           -- 专业律师阶段
                'completed'             -- 已完成
            );

            -- 更新表结构，将列类型改为新枚举类型
            ALTER TABLE consultation_history 
            ALTER COLUMN current_phase TYPE consultation_phase_new 
            USING current_phase::text::consultation_phase_new;

            -- 删除旧枚举类型
            DROP TYPE IF EXISTS consultation_phase;

            -- 将新枚举类型重命名为原来的名字
            ALTER TYPE consultation_phase_new RENAME TO consultation_phase;

            -- 更新默认值
            ALTER TABLE consultation_history
            ALTER COLUMN current_phase SET DEFAULT 'initial';

            -- 添加或更新列注释
            COMMENT ON COLUMN consultation_history.current_phase IS '当前会话阶段：initial(初始) | assistant(律师助理) | waiting_confirmation(等待确认) | specialist(专业律师) | completed(已完成)';

            RAISE NOTICE '✅ consultation_phase 枚举类型修复完成，已添加 ''initial'' 状态值';
        ELSE
            RAISE NOTICE 'ℹ️  consultation_phase 枚举类型已包含 ''initial'' 状态值，无需修改';
        END IF;
    END $$;

    -- 验证更改
    SELECT 
        e.enumlabel as enum_value
    FROM pg_enum e 
    JOIN pg_type t ON e.enumtypid = t.oid 
    WHERE t.typname = 'consultation_phase'
    ORDER BY e.enumsortorder;
    """
    
    try:
        with engine.connect() as conn:
            # 执行事务
            trans = conn.begin()
            try:
                result = conn.execute(text(sql_script))
                # 如果查询有结果，打印出来
                rows = result.fetchall() if result.returns_rows else None
                trans.commit()
                
                print("数据库迁移执行成功！")
                
                if rows:
                    print("当前枚举值：")
                    for row in rows:
                        print(f"  - {row[0]}")
                        
            except Exception as e:
                trans.rollback()
                print(f"数据库迁移执行失败: {str(e)}")
                raise

    except Exception as e:
        print(f"连接数据库失败: {str(e)}")
        raise

if __name__ == "__main__":
    run_migration()