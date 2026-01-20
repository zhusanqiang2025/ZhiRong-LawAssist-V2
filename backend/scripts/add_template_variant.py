#!/usr/bin/env python3
"""添加 template_variant 字段到 contract_templates 表"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text

def add_template_variant_column():
    """添加 template_variant 字段"""
    with engine.connect() as conn:
        # 检查字段是否已存在
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'contract_templates' AND column_name = 'template_variant'
        """))
        exists = result.fetchone()

        if not exists:
            conn.execute(text('ALTER TABLE contract_templates ADD COLUMN template_variant VARCHAR(100)'))
            conn.commit()
            print('[OK] Added template_variant column to contract_templates table')
        else:
            print('[INFO] template_variant column already exists')
        conn.close()

if __name__ == "__main__":
    add_template_variant_column()
