import os
import sys
import json

# ==================== 1. 环境路径配置 ====================
# 获取当前脚本所在目录 (backend/scripts)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取 backend 根目录
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
# 将 backend 加入 Python 搜索路径，以便能导入 app 模块
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.category import Category

# ==================== 2. 配置项 ====================

# ⚠️ 请确认数据库连接地址是否正确
DATABASE_URL = "postgresql://postgres:password@localhost:5432/legal_v3_db"

# ⚠️ 关键修改：categories.json 在 backend 根目录下
JSON_PATH = os.path.join(BACKEND_DIR, "categories.json")

# 初始化数据库连接
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# ==================== 3. 核心逻辑 ====================

def get_or_create(db, name, parent_id, defaults=None):
    """
    幂等写入函数：
    - 如果数据库里有了，就更新字段 (update)
    - 如果没有，就创建 (create)
    """
    if defaults is None:
        defaults = {}
        
    # 查询是否存在
    instance = db.query(Category).filter_by(name=name, parent_id=parent_id).first()
    
    if instance:
        # 更新现有记录的字段 (确保 json 改动后能同步到数据库)
        for key, value in defaults.items():
            setattr(instance, key, value)
    else:
        # 创建新记录
        instance = Category(name=name, parent_id=parent_id, **defaults)
        db.add(instance)
        # flush 用于立即生成 ID，供子级使用，但不提交事务
        db.flush()
        
    return instance

def init_categories():
    print("🚀 开始初始化合同分类数据库...")
    print(f"📂 读取配置文件: {JSON_PATH}")
    
    if not os.path.exists(JSON_PATH):
        print(f"❌ 错误：未找到配置文件！请检查路径。")
        return

    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ JSON 读取失败: {e}")
        return

    db = SessionLocal()
    
    try:
        # 读取一级分类列表
        primary_list = data.get("primary_categories", [])
        print(f"📄 发现 {len(primary_list)} 个一级分类")
        
        for p_idx, p_cat in enumerate(primary_list):
            # === Level 1: 一级分类 ===
            cat_l1 = get_or_create(db, p_cat["name"], None, {
                "code": p_cat.get("id"),
                "description": p_cat.get("description"),
                "sort_order": (p_idx + 1) * 10,
                "is_active": True
            })
            print(f"📂 [L1] {cat_l1.name}")
            
            # === Level 2: 二级分类 (sub_types) ===
            sub_types = p_cat.get("sub_types", [])
            for s_idx, s_cat in enumerate(sub_types):
                
                # 提取扩展信息到 meta_info JSON 字段
                meta = {
                    "contract_type": s_cat.get("contract_type"),
                    "industry": s_cat.get("industry"),
                    "usage_scene": s_cat.get("usage_scene"),
                    "jurisdiction": s_cat.get("jurisdiction", "中国大陆")
                }
                
                # 生成层级编码 (例如: 1-1)
                l2_code = f"{cat_l1.code}-{s_idx+1}"
                
                cat_l2 = get_or_create(db, s_cat["name"], cat_l1.id, {
                    "code": l2_code,
                    "sort_order": (s_idx + 1) * 10,
                    "meta_info": meta,
                    "is_active": True
                })
                print(f"   └── [L2] {cat_l2.name}")
                
                # === Level 3: 三级分类 (sub_categories) ===
                # 注意：json 中 sub_categories 是字符串列表 ["合同A", "合同B"]
                leaf_contracts = s_cat.get("sub_categories", [])
                for l_idx, l_name in enumerate(leaf_contracts):
                    
                    l3_code = f"{l2_code}-{l_idx+1}"
                    
                    # 三级分类通常没有额外的 meta，继承即可
                    get_or_create(db, l_name, cat_l2.id, {
                        "code": l3_code,
                        "sort_order": (l_idx + 1) * 10,
                        "is_active": True
                    })
                    # (可选) 打印太长了，此处注释掉
                    # print(f"       └── [L3] {l_name}")

        db.commit()
        print("\n🎉 分类初始化成功！数据库已更新。")
        
    except Exception as e:
        print(f"\n❌ 发生数据库错误: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_categories()