"""
数据库数据修复脚本：修正错误的状态枚举值

该脚本修复因代码bug导致的错误数据：
- 将错误设置到status字段的'waiting_confirmation'值修正为'active'
- 确保current_phase字段正确设置
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.consultation_history import ConsultationHistory
from sqlalchemy import and_


def fix_status_enum_data():
    print("开始修复数据库中的错误状态数据...")
    
    # 创建数据库会话
    db = SessionLocal()
    
    try:
        # 查找所有status字段为'waiting_confirmation'的记录（这是错误的值）
        wrong_status_records = db.query(ConsultationHistory).filter(
            ConsultationHistory.status == 'waiting_confirmation'
        ).all()
        
        fixed_count = 0
        for record in wrong_status_records:
            print(f"修复记录: session_id={record.session_id}, 旧status={record.status}, 旧phase={record.current_phase}")
            
            # 保存原始的current_phase值（如果它是'waiting_confirmation'，需要保留）
            original_phase = record.current_phase
            
            # 修正status字段为'active'（正确的值）
            record.status = 'active'
            
            # 如果current_phase不是'waiting_confirmation'，则将其设为'waiting_confirmation'（这是合理的假设）
            if original_phase != 'waiting_confirmation':
                record.current_phase = 'waiting_confirmation'
            
            print(f"  -> 修正后: 新status=active, 新phase={record.current_phase}")
            fixed_count += 1
        
        # 提交更改
        db.commit()
        print(f"✅ 数据修复完成! 共修复 {fixed_count} 条记录")
        
        # 验证修复结果
        remaining_wrong_status = db.query(ConsultationHistory).filter(
            ConsultationHistory.status == 'waiting_confirmation'
        ).count()
        
        if remaining_wrong_status == 0:
            print("✅ 验证通过：没有发现status字段为'waiting_confirmation'的记录")
        else:
            print(f"⚠️  警告：仍有 {remaining_wrong_status} 条记录的status字段为'waiting_confirmation'")
        
    except Exception as e:
        print(f"❌ 修复过程出错: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_status_enum_data()