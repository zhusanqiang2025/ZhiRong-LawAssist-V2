"""
数据库数据修复脚本（使用原始SQL）：修正错误的状态枚举值

该脚本使用原始SQL绕过ORM的枚举验证，直接修复数据库中的错误数据：
- 将错误设置到status字段的'waiting_confirmation'值修正为'active'
- 确保current_phase字段正确设置
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from sqlalchemy import text


def fix_status_enum_data_raw_sql():
    """使用原始SQL修复数据库中的错误状态数据"""
    print("开始修复数据库中的错误状态数据（使用原始SQL）...")

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 使用原始SQL查询并更新，绕过ORM的枚举验证
        # 1. 首先检查有多少条记录需要修复
        check_sql = text("""
            SELECT COUNT(*) as count
            FROM consultation_history
            WHERE status = 'waiting_confirmation'
        """)

        result = db.execute(check_sql).fetchone()
        wrong_count = result[0] if result else 0

        print(f"发现 {wrong_count} 条需要修复的记录")

        if wrong_count == 0:
            print("没有需要修复的记录")
            return

        # 2. 使用原始SQL更新记录
        update_sql = text("""
            UPDATE consultation_history
            SET
                status = 'active',
                current_phase = CASE
                    WHEN current_phase != 'waiting_confirmation' THEN 'waiting_confirmation'
                    ELSE current_phase
                END
            WHERE status = 'waiting_confirmation'
        """)

        db.execute(update_sql)
        db.commit()

        print(f"✅ 数据修复完成! 共修复 {wrong_count} 条记录")

        # 3. 验证修复结果
        verify_sql = text("""
            SELECT COUNT(*) as count
            FROM consultation_history
            WHERE status = 'waiting_confirmation'
        """)

        remaining = db.execute(verify_sql).fetchone()
        remaining_count = remaining[0] if remaining else 0

        if remaining_count == 0:
            print("✅ 验证通过：没有发现status字段为'waiting_confirmation'的记录")
        else:
            print(f"⚠️  警告：仍有 {remaining_count} 条记录的status字段为'waiting_confirmation'")

        # 4. 显示修复后的样本数据
        sample_sql = text("""
            SELECT session_id, status, current_phase, user_decision
            FROM consultation_history
            WHERE current_phase = 'waiting_confirmation'
            LIMIT 5
        """)

        samples = db.execute(sample_sql).fetchall()
        if samples:
            print("\n等待确认的会话样本：")
            for sample in samples:
                print(f"  - session_id={sample[0]}, status={sample[1]}, phase={sample[2]}, decision={sample[3]}")

    except Exception as e:
        print(f"❌ 修复过程出错: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_status_enum_data_raw_sql()
