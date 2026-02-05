"""
系统管理后台数据综合备份脚本
备份: 合同知识图谱、审查规则、风险评估规则、案件分析规则
"""
import os
import sys
import sqlite3
import json
from datetime import datetime

# Windows 控制台编码修复
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 路径配置
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
DB_PATH = os.path.join(BACKEND_DIR, "app.db")
BACKUP_DIR = os.path.join(BACKEND_DIR, "backups")

# ==================== 备份函数 ====================

def backup_table(cursor, table_name):
    """备份单个表的数据"""
    try:
        cursor.execute(f'SELECT * FROM {table_name}')
        rows = cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            # 解析 JSON 字段
            for key, value in item.items():
                if isinstance(value, str):
                    try:
                        item[key] = json.loads(value)
                    except:
                        pass
            result.append(item)
        return result
    except Exception as e:
        print(f"  警告: 备份 {table_name} 失败 - {e}")
        return []

def backup_contract_knowledge_types(cursor):
    """备份合同法律特征知识图谱"""
    print("\n[1/4] 备份合同法律特征知识图谱...")
    data = backup_table(cursor, 'contract_knowledge_types')
    print(f"  完成: {len(data)} 条记录")
    return data

def backup_contract_review_rules(cursor):
    """备份合同审查规则"""
    print("\n[2/4] 备份合同审查规则...")
    data = backup_table(cursor, 'contract_review_rules')
    print(f"  完成: {len(data)} 条记录")
    return data

def backup_risk_analysis(cursor):
    """备份风险评估规则"""
    print("\n[3/4] 备份风险评估规则...")
    rules = backup_table(cursor, 'risk_analysis_rules')
    packages = backup_table(cursor, 'risk_rule_packages')
    print(f"  完成: {len(rules)} 条分析规则, {len(packages)} 条规则包")
    return {"rules": rules, "packages": packages}

def backup_litigation_analysis(cursor):
    """备份案件分析规则"""
    print("\n[4/4] 备份案件分析规则...")
    packages = backup_table(cursor, 'litigation_case_packages')
    items = backup_table(cursor, 'litigation_case_items')
    print(f"  完成: {len(packages)} 个案件包, {len(items)} 条案件项")
    return {"packages": packages, "items": items}

def backup_categories(cursor):
    """备份合同分类体系"""
    print("\n[额外] 备份合同分类体系...")
    cursor.execute('SELECT * FROM categories ORDER BY sort_order')
    rows = cursor.fetchall()
    all_categories = []
    for row in rows:
        cat = dict(row)
        if cat.get('meta_info'):
            try:
                cat['meta_info'] = json.loads(cat['meta_info'])
            except:
                pass
        all_categories.append(cat)

    # 构建树形结构
    def build_tree(categories, parent_id=None):
        result = []
        for cat in categories:
            if cat.get("parent_id") == parent_id:
                cat["children"] = build_tree(categories, cat.get("id"))
                result.append(cat)
        return result

    category_tree = build_tree(all_categories)
    print(f"  完成: {len(all_categories)} 条记录")
    return {"flat": all_categories, "tree": category_tree}

# ==================== 主函数 ====================

def backup_all_data():
    print("=" * 70)
    print("         系统管理后台数据综合备份工具")
    print("=" * 70)

    # 创建备份目录
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # 检查数据库
    if not os.path.exists(DB_PATH):
        print(f"错误: 数据库文件不存在: {DB_PATH}")
        return

    # 连接数据库
    print(f"\n连接数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 准备备份数据结构
        backup_data = {
            "version": "1.0",
            "backup_time": datetime.now().isoformat(),
            "database": os.path.basename(DB_PATH),
            "data": {}
        }

        # 执行各类备份
        backup_data["data"]["contract_knowledge_types"] = backup_contract_knowledge_types(cursor)
        backup_data["data"]["contract_review_rules"] = backup_contract_review_rules(cursor)
        backup_data["data"]["risk_analysis"] = backup_risk_analysis(cursor)
        backup_data["data"]["litigation_analysis"] = backup_litigation_analysis(cursor)
        backup_data["data"]["categories"] = backup_categories(cursor)

        # 生成备份文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"system_data_backup_{timestamp}.json")

        print(f"\n保存备份文件: {backup_file}")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        # 统计摘要
        print("\n" + "=" * 70)
        print("                    备份完成!")
        print("=" * 70)
        print("数据摘要:")
        print(f"  - 合同知识图谱: {len(backup_data['data']['contract_knowledge_types'])} 条")
        print(f"  - 合同审查规则: {len(backup_data['data']['contract_review_rules'])} 条")
        print(f"  - 风险评估规则: {len(backup_data['data']['risk_analysis']['rules'])} 条")
        print(f"  - 风险规则包: {len(backup_data['data']['risk_analysis']['packages'])} 条")
        print(f"  - 案件分析包: {len(backup_data['data']['litigation_analysis']['packages'])} 条")
        print(f"  - 合同分类: {len(backup_data['data']['categories']['flat'])} 条")
        print(f"\n备份文件: {backup_file}")
        print("=" * 70)

        # 同时生成单独的备份文件
        print("\n生成单独备份文件...")

        # 合同知识图谱
        knowledge_file = os.path.join(BACKUP_DIR, f"contract_knowledge_types_{timestamp}.json")
        with open(knowledge_file, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "1.0",
                "backup_time": backup_data["backup_time"],
                "data": backup_data["data"]["contract_knowledge_types"]
            }, f, ensure_ascii=False, indent=2)
        print(f"  - {os.path.basename(knowledge_file)}")

        # 合同审查规则
        review_rules_file = os.path.join(BACKUP_DIR, f"contract_review_rules_{timestamp}.json")
        with open(review_rules_file, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "1.0",
                "backup_time": backup_data["backup_time"],
                "data": backup_data["data"]["contract_review_rules"]
            }, f, ensure_ascii=False, indent=2)
        print(f"  - {os.path.basename(review_rules_file)}")

        # 风险评估规则
        risk_rules_file = os.path.join(BACKUP_DIR, f"risk_analysis_rules_{timestamp}.json")
        with open(risk_rules_file, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "1.0",
                "backup_time": backup_data["backup_time"],
                "data": backup_data["data"]["risk_analysis"]
            }, f, ensure_ascii=False, indent=2)
        print(f"  - {os.path.basename(risk_rules_file)}")

        # 案件分析规则
        litigation_file = os.path.join(BACKUP_DIR, f"litigation_analysis_rules_{timestamp}.json")
        with open(litigation_file, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "1.0",
                "backup_time": backup_data["backup_time"],
                "data": backup_data["data"]["litigation_analysis"]
            }, f, ensure_ascii=False, indent=2)
        print(f"  - {os.path.basename(litigation_file)}")

    except Exception as e:
        print(f"\n备份失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    backup_all_data()
