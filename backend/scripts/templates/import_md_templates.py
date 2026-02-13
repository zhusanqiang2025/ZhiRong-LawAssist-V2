"""
导入 Markdown 模板到数据库（修正版）
"""
import os
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.contract_template import ContractTemplate
import uuid

# Markdown 模板目录（容器内路径）
TEMPLATE_SOURCE_DIR = "/app/templates_source"

def parse_filename_metadata(filename: str):
    """
    解析文件名获取元数据
    格式示例: 非典型合同_股权类协议_个人间股权代持解除_股权代持解除协议.md
    """
    name_no_ext = filename.replace('.md', '')
    parts = name_no_ext.split('_')

    # 提取分类信息
    if len(parts) >= 2:
        category = parts[0]  # 一级分类（如"非典型合同"）
        subcategory = '_'.join(parts[1:-1]) if len(parts) > 2 else None  # 二级分类
        name = parts[-1]  # 合同名称（最后一段）
    else:
        category = "通用合同"
        subcategory = None
        name = name_no_ext

    # 提取关键词
    keywords = [p for p in parts if len(p) > 1]  # 过滤掉单字符

    return {
        "category": category,
        "subcategory": subcategory,
        "name": name,
        "keywords": keywords
    }

def import_markdown_templates():
    """导入 Markdown 模板到数据库"""

    print("=" * 60)
    print("导入 Markdown 模板到数据库")
    print("=" * 60)
    print()

    # 检查目录
    if not os.path.exists(TEMPLATE_SOURCE_DIR):
        print(f"错误：目录不存在: {TEMPLATE_SOURCE_DIR}")
        return

    # 获取所有 Markdown 文件
    md_files = [f for f in os.listdir(TEMPLATE_SOURCE_DIR) if f.endswith('.md')]

    if not md_files:
        print(f"错误：目录中没有 .md 文件: {TEMPLATE_SOURCE_DIR}")
        return

    print(f"找到 {len(md_files)} 个 Markdown 文件")
    print(f"目录: {TEMPLATE_SOURCE_DIR}")
    print()

    db = SessionLocal()

    try:
        imported_count = 0
        skipped_count = 0
        error_count = 0

        for filename in md_files:
            try:
                # 解析文件名
                metadata = parse_filename_metadata(filename)

                # 构造文件路径（相对路径）
                file_url = f"templates_source/{filename}"

                # 检查是否已存在
                existing = db.query(ContractTemplate).filter(
                    ContractTemplate.name == metadata["name"]
                ).first()

                if existing:
                    # 更新现有记录
                    existing.file_url = file_url
                    existing.category = metadata["category"]
                    if metadata["subcategory"]:
                        existing.subcategory = metadata["subcategory"]
                    existing.keywords = metadata["keywords"]
                    existing.file_type = "md"
                    existing.description = f"从 {filename} 导入"
                    print(f"  [更新] {metadata['name']}")
                else:
                    # 创建新记录
                    template = ContractTemplate(
                        id=str(uuid.uuid4()),
                        name=metadata["name"],
                        category=metadata["category"],
                        subcategory=metadata["subcategory"] or "",
                        keywords=metadata["keywords"],
                        file_url=file_url,
                        file_name=filename,
                        file_type="md",
                        description=f"从 {filename} 导入",
                        is_public=True,
                        status="active",
                        language="zh-CN",
                        jurisdiction="中国",
                        # 必填字段
                        primary_contract_type=metadata["category"],  # 使用一级分类作为主合同类型
                        delivery_model="单一交付",  # 默认值
                        payment_model=None,  # 可选
                        risk_level=None,  # 可选
                        industry_tags=None,  # 可选
                        allowed_party_models=None,  # 可选
                        transaction_nature=None,  # 稍后由知识图谱匹配填充
                        contract_object=None,  # 稍后由知识图谱匹配填充
                        complexity=None,  # 可选
                        stance=None  # 可选
                    )
                    db.add(template)
                    print(f"  [新增] {metadata['name']}")

                imported_count += 1

            except Exception as e:
                error_count += 1
                print(f"  [错误] {filename}: {e}")

        # 提交事务
        db.commit()

        print()
        print("=" * 60)
        print(f"导入完成:")
        print(f"  处理: {imported_count}")
        print(f"  跳过: {skipped_count}")
        print(f"  错误: {error_count}")
        print("=" * 60)

    except Exception as e:
        print(f"错误: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    import_markdown_templates()
