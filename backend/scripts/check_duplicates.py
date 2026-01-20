"""检查重复模板状态"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SessionLocal
from app.models.contract_template import ContractTemplate

db = SessionLocal()

try:
    # 查找重复的模板
    duplicates = db.query(
        ContractTemplate.name,
        func.count().label('count')
    ).group_by(
        ContractTemplate.name
    ).having(
        func.count() > 1
    ).limit(10).all()

    print(f"前10个重复模板：")
    for name, count in duplicates:
        templates = db.query(ContractTemplate).filter(
            ContractTemplate.name == name
        ).all()

        print(f"\n{name}: {count} 条记录")
        for t in templates:
            print(f"  - {t.id[:8]}... status={t.status}, created_at={t.created_at}")

finally:
    db.close()
