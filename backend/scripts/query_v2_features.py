"""
查询数据库中的合同模板 V2 四维法律特征

使用方法：
    python scripts/query_v2_features.py
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


def query_all_templates():
    """查询所有模板及其 V2 特征"""
    db = SessionLocal()

    try:
        templates = db.query(ContractTemplate).filter(
            ContractTemplate.status == "active"
        ).all()

        print(f"\n{'='*120}")
        print(f"数据库中共有 {len(templates)} 个活跃的合同模板")
        print(f"{'='*120}\n")

        for idx, t in enumerate(templates, 1):
            print(f"{idx}. {t.name}")
            print(f"   ID: {t.id}")
            print(f"   分类: {t.category} / {t.subcategory}")
            print(f"   主合同类型: {t.primary_contract_type}")
            print(f"   次要类型: {t.secondary_types}")
            print(f"   交付模型: {t.delivery_model}")
            print(f"   付款模型: {t.payment_model}")
            print(f"   风险等级: {t.risk_level}")
            print(f"   是否推荐: {t.is_recommended}")
            print(f"\n   V2 四维法律特征:")
            print(f"   - 交易性质 (transaction_nature): {t.transaction_nature}")
            print(f"   - 合同标的 (contract_object): {t.contract_object}")
            print(f"   - 复杂程度 (complexity): {t.complexity}")
            print(f"   - 立场 (stance): {t.stance}")
            print(f"\n   其他信息:")
            print(f"   - 文件路径: {t.file_url}")
            print(f"   - 关键词: {t.keywords}")
            print(f"   - 描述: {t.description[:100] if t.description else 'N/A'}...")
            print(f"\n{'-'*120}\n")

    finally:
        db.close()


def query_service_contract_templates():
    """只查询服务类合同模板（软件开发相关）"""
    db = SessionLocal()

    try:
        # 查询主合同类型为"服务合同"的模板
        templates = db.query(ContractTemplate).filter(
            ContractTemplate.primary_contract_type == "服务合同",
            ContractTemplate.status == "active"
        ).all()

        print(f"\n{'='*120}")
        print(f"服务类合同模板: {len(templates)} 个")
        print(f"{'='*120}\n")

        for idx, t in enumerate(templates, 1):
            print(f"{idx}. {t.name}")
            print(f"   ID: {t.id}")
            print(f"   分类: {t.category} / {t.subcategory}")
            print(f"   次要类型: {t.secondary_types}")
            print(f"   V2 特征:")
            print(f"   - nature: {t.transaction_nature}")
            print(f"   - object: {t.contract_object}")
            print(f"   - complexity: {t.complexity}")
            print(f"   - stance: {t.stance}")
            print(f"   推荐等级: is_recommended={t.is_recommended}, risk={t.risk_level}")
            print(f"   关键词: {t.keywords}")
            print(f"\n{'-'*120}\n")

    finally:
        db.close()


def query_v2_distribution():
    """统计 V2 特征的分布情况"""
    db = SessionLocal()

    try:
        templates = db.query(ContractTemplate).filter(
            ContractTemplate.status == "active"
        ).all()

        print(f"\n{'='*120}")
        print(f"V2 四维法律特征分布统计")
        print(f"{'='*120}\n")

        # 交易性质分布
        print("【交易性质 (transaction_nature) 分布】")
        nature_dist = {}
        for t in templates:
            nature = t.transaction_nature or "NULL"
            nature_dist[nature] = nature_dist.get(nature, 0) + 1

        for nature, count in sorted(nature_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"  {nature}: {count} 个")

        # 合同标分布
        print("\n【合同标的 (contract_object) 分布】")
        object_dist = {}
        for t in templates:
            obj = t.contract_object or "NULL"
            object_dist[obj] = object_dist.get(obj, 0) + 1

        for obj, count in sorted(object_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"  {obj}: {count} 个")

        # 复杂程度分布
        print("\n【复杂程度 (complexity) 分布】")
        complexity_dist = {}
        for t in templates:
            comp = t.complexity or "NULL"
            complexity_dist[comp] = complexity_dist.get(comp, 0) + 1

        for comp, count in sorted(complexity_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"  {comp}: {count} 个")

        # 立场分布
        print("\n【立场 (stance) 分布】")
        stance_dist = {}
        for t in templates:
            st = t.stance or "NULL"
            stance_dist[st] = stance_dist.get(st, 0) + 1

        for st, count in sorted(stance_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"  {st}: {count} 个")

        print(f"\n{'='*120}\n")

    finally:
        db.close()


def query_by_secondary_type(tag: str):
    """根据次要类型标签查询模板"""
    db = SessionLocal()

    try:
        templates = db.query(ContractTemplate).filter(
            ContractTemplate.status == "active",
            ContractTemplate.secondary_types.isnot(None)
        ).all()

        # 筛选包含指定标签的模板
        filtered = [t for t in templates if t.secondary_types and tag in t.secondary_types]

        print(f"\n{'='*120}")
        print(f"包含次要类型标签 '{tag}' 的模板: {len(filtered)} 个")
        print(f"{'='*120}\n")

        for idx, t in enumerate(filtered, 1):
            print(f"{idx}. {t.name}")
            print(f"   ID: {t.id}")
            print(f"   次要类型: {t.secondary_types}")
            print(f"   V2 特征: nature={t.transaction_nature}, object={t.contract_object}")
            print(f"   推荐等级: is_recommended={t.is_recommended}")
            print(f"\n{'-'*120}\n")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="查询数据库中的 V2 特征")
    parser.add_argument("--all", action="store_true", help="查询所有模板")
    parser.add_argument("--service", action="store_true", help="只查询服务类合同")
    parser.add_argument("--stats", action="store_true", help="统计 V2 特征分布")
    parser.add_argument("--tag", type=str, help="根据次要类型标签查询")

    args = parser.parse_args()

    if args.all:
        query_all_templates()
    elif args.service:
        query_service_contract_templates()
    elif args.stats:
        query_v2_distribution()
    elif args.tag:
        query_by_secondary_type(args.tag)
    else:
        # 默认查询服务类合同
        query_service_contract_templates()
