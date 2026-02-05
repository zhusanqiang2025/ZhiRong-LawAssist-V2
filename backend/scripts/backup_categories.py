"""
合同分类数据备份脚本 (直接使用 SQLite)
"""
import os
import sys
import sqlite3
import json
from datetime import datetime

# ==================== 0. Windows 控制台编码修复 ====================
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 1. 环境路径配置 ====================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
DB_PATH = os.path.join(BACKEND_DIR, "app.db")
BACKUP_DIR = os.path.join(BACKEND_DIR, "backups")

# ==================== 2. 核心逻辑 ====================

def build_category_tree(categories, parent_id=None):
    """递归构建分类树结构"""
    result = []
    for cat in categories:
        if cat.get("parent_id") == parent_id:
            # 查找子分类
            cat["children"] = build_category_tree(categories, cat.get("id"))
            result.append(cat)
    return result

def backup_categories():
    print("=" * 60)
    print("合同分类数据备份工具")
    print("=" * 60)

    # 创建备份目录
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # 检查数据库文件
    if not os.path.exists(DB_PATH):
        print(f"错误: 数据库文件不存在: {DB_PATH}")
        return

    # 连接数据库
    print(f"连接数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 查询所有分类
        print("读取分类数据...")
        cursor.execute('SELECT * FROM categories ORDER BY sort_order')
        rows = cursor.fetchall()

        if not rows:
            print("警告: 数据库中没有找到任何分类数据")
            return

        # 转换为字典列表
        all_categories = []
        for row in rows:
            cat = dict(row)
            # 解析 JSON 字段
            if cat.get('meta_info'):
                try:
                    cat['meta_info'] = json.loads(cat['meta_info'])
                except:
                    cat['meta_info'] = {}
            all_categories.append(cat)

        # 构建树形结构
        print("构建分类树结构...")
        category_tree = build_category_tree(all_categories)

        # 准备备份数据（扁平格式，兼容 categories.json）
        backup_data = {
            "version": "2.1",
            "backup_time": datetime.now().isoformat(),
            "total_count": len(all_categories),
            "primary_categories": []
        }

        # 按照初始化脚本的格式组织数据
        for l1_cat in category_tree:
            primary_cat = {
                "id": l1_cat.get("code") or str(l1_cat["id"]),
                "name": l1_cat["name"],
                "description": l1_cat.get("description", ""),
                "sub_types": []
            }

            for l2_cat in l1_cat.get("children", []):
                meta = l2_cat.get("meta_info", {})
                sub_type = {
                    "name": l2_cat["name"],
                    "contract_type": meta.get("contract_type"),
                    "industry": meta.get("industry"),
                    "usage_scene": meta.get("usage_scene"),
                    "jurisdiction": meta.get("jurisdiction", "中国大陆"),
                    "sub_categories": [l3["name"] for l3 in l2_cat.get("children", [])]
                }
                primary_cat["sub_types"].append(sub_type)

            backup_data["primary_categories"].append(primary_cat)

        # 生成备份文件名（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"categories_backup_{timestamp}.json")

        # 写入 JSON 文件
        print(f"保存备份文件: {backup_file}")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        # 同时保存为默认的 categories.json（方便直接使用）
        default_file = os.path.join(BACKUP_DIR, "categories.json")
        with open(default_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        # 统计信息
        l1_count = len(category_tree)
        l2_count = sum(len(l1.get("children", [])) for l1 in category_tree)
        l3_count = sum(
            len(l2.get("children", []))
            for l1 in category_tree
            for l2 in l1.get("children", [])
        )

        print("\n" + "=" * 60)
        print("备份完成!")
        print("=" * 60)
        print(f"统计信息:")
        print(f"   - 一级分类: {l1_count} 个")
        print(f"   - 二级分类: {l2_count} 个")
        print(f"   - 三级分类: {l3_count} 个")
        print(f"   - 总计: {backup_data['total_count']} 条记录")
        print(f"\n备份文件:")
        print(f"   - {backup_file}")
        print(f"   - {default_file} (默认版本)")
        print("=" * 60)

    except Exception as e:
        print(f"\n备份失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    backup_categories()
