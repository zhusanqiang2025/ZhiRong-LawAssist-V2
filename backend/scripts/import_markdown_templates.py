import os
import sys
import json
from pathlib import Path
from datetime import datetime

# --- V3 环境适配 ---
# 将 backend 目录加入 python path，以便导入 app 模块
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
sys.path.append(BACKEND_DIR)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ⚠️ 读取 .env 配置或硬编码数据库连接
# 建议直接硬编码一次性使用，或者使用 python-dotenv 加载
# 格式: postgresql://user:password@host:port/dbname
DATABASE_URL = "postgresql://postgres:password@localhost:5432/legal_v3_db"

# 目标目录: backend/storage/templates/
TEMPLATE_DIR = os.path.join(BACKEND_DIR, "storage", "templates")

# 初始化 DB
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def import_templates():
    print(f"🚀 开始导入模板...")
    print(f"📂 扫描目录: {TEMPLATE_DIR}")
    
    if not os.path.exists(TEMPLATE_DIR):
        print("❌ 目录不存在！")
        return

    db = SessionLocal()
    files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith('.md')]
    print(f"📄 发现 {len(files)} 个 Markdown 文件")

    count = 0
    try:
        for filename in files:
            # === 1. 解析文件名元数据 ===
            # 格式: Category_SubCategory_Scenario_Name.md
            name_no_ext = filename.replace('.md', '')
            parts = name_no_ext.split('_')
            
            # 容错解析逻辑
            if len(parts) >= 4:
                category = parts[0]      # 一级分类
                # sub_category = parts[1] # 二级分类 (可存入 metadata)
                # scenario = parts[2]     # 场景 (可存入 metadata)
                name = parts[-1]          # 合同名称
                keywords = parts          # 全量关键词
            else:
                category = "通用合同"
                name = name_no_ext
                keywords = parts

            # === 2. 构造存储路径 ===
            # 注意：这里存的是相对于 backend 的路径，方便 Python 代码 open()
            # 或者是绝对路径，取决于你的 Loader 节点怎么写
            # 建议存相对路径: storage/templates/xxx.md
            file_path = f"storage/templates/{filename}"
            
            # === 3. 构造元数据 JSON (存入 metadata_info 字段，假设你的表有这个JSONB字段) ===
            metadata_info = {
                "original_filename": filename,
                "scenario": parts[2] if len(parts) >= 3 else "",
                "sub_category": parts[1] if len(parts) >= 2 else "",
                "format": "markdown"
            }

            # === 4. 入库 (适配 contract_templates 表结构) ===
            # 假设表结构为: id, name, category, keywords(ARRAY or JSON), file_url, metadata_info
            sql = text("""
                INSERT INTO contract_templates (name, category, keywords, file_url, created_at)
                VALUES (:name, :category, :keywords, :file_url, NOW())
                ON CONFLICT (name) DO UPDATE 
                SET file_url = EXCLUDED.file_url, 
                    category = EXCLUDED.category,
                    keywords = EXCLUDED.keywords;
            """)
            
            # 注意：PostgreSQL 的 ARRAY 类型需要传 list，如果是 JSON 类型需要 json.dumps
            # 这里假设 keywords 是 JSONB 类型，如果是 TEXT[] 类型，直接传 keywords 列表即可
            db.execute(sql, {
                "name": name,
                "category": category,
                "keywords": json.dumps(keywords, ensure_ascii=False), 
                "file_url": file_path
            })
            
            count += 1
            print(f"  [OK] {name}")

        db.commit()
        print(f"\n🎉 成功导入 {count} 个模板到数据库！")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import_templates()