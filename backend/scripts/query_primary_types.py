"""
查询数据库中所有不重复的 primary_contract_type 值

使用方法：
    docker-compose exec backend python scripts/query_primary_types.py
"""
import os
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.contract_template import ContractTemplate

# 数据库连接
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:01689101Abc@db:5432/legal_assistant_db")

# 初始化数据库连接
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def query_primary_types():
    """查询所有不重复的 primary_contract_type"""
    db = SessionLocal()

    try:
        # 使用原生 SQL 查询
        result = db.execute(text("""
            SELECT DISTINCT primary_contract_type, COUNT(*) as count
            FROM contract_templates
            WHERE status = 'active'
            GROUP BY primary_contract_type
            ORDER BY count DESC
        """))

        print(f"\n{'='*80}")
        print(f"数据库中所有不重复的 primary_contract_type 值:")
        print(f"{'='*80}\n")

        for row in result:
            print(f"{row.primary_contract_type}: {row.count} 个模板")

        print(f"\n{'='*80}\n")

    finally:
        db.close()


if __name__ == "__main__":
    query_primary_types()
