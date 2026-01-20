"""
合同模板导入脚本

功能：
1. 从 backend/templates_source/ 读取合同模板文件
2. 复制文件到 storage/templates/ (使用 UUID 重命名)
3. 将模板元数据导入到 contract_templates 表

支持格式：.docx, .doc, .md
"""
import os
import sys
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime

# --- 环境适配 ---
# 将 backend 目录加入 python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
sys.path.append(BACKEND_DIR)

# --- 数据库配置 ---
# 从 docker-compose.yml 中的配置
# 注意：根据运行环境选择正确的主机

import os

# 检测运行环境
if os.path.exists('/.dockerenv'):  # 在 Docker 容器内运行
    DB_HOST = "db"
    print(f"🐳 检测到 Docker 环境，使用主机名: {DB_HOST}")
else:  # 在宿主机运行
    # 尝试获取 Docker 容器 IP
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", "legal_assistant_v3_db"],
            capture_output=True,
            text=True,
            check=True
        )
        db_host = result.stdout.strip()
        if db_host:
            DB_HOST = db_host
            print(f"🔍 检测到 Docker 容器 IP: {DB_HOST}")
        else:
            DB_HOST = "localhost"
    except:
        DB_HOST = "localhost"
        print(f"⚠️  无法获取容器 IP，使用 localhost")

DB_USER = "admin"
DB_PASSWORD = "01689101Abc"
DB_PORT = "5432"
DB_NAME = "legal_assistant_db"
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- 目录配置 ---
# 源目录：backend/templates_source/
SOURCE_DIR = os.path.join(BACKEND_DIR, "templates_source")
# 目标目录：storage/templates/ (运行时模板存储)
TARGET_DIR = os.path.join(PROJECT_ROOT, "storage", "templates")

# --- 初始化数据库 ---
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def parse_filename_metadata(filename):
    """
    从文件名解析元数据

    支持的命名格式：
    1. 分类_子分类_场景_名称.docx
    2. 分类_名称.docx
    3. 名称.docx
    """
    name_no_ext = os.path.splitext(filename)[0]
    parts = name_no_ext.split('_')

    if len(parts) >= 4:
        category = parts[0]
        subcategory = parts[1]
        scenario = parts[2]
        name = '_'.join(parts[3:])  # 剩余部分作为名称
        keywords = parts
    elif len(parts) >= 2:
        category = parts[0]
        subcategory = parts[1] if len(parts) > 2 else None
        scenario = None
        name = '_'.join(parts[1:])
        keywords = parts
    else:
        category = "通用合同"
        subcategory = None
        scenario = None
        name = name_no_ext
        keywords = [name_no_ext]

    return {
        "name": name,
        "category": category,
        "subcategory": subcategory,
        "scenario": scenario,
        "keywords": keywords
    }


def get_file_size(file_path):
    """获取文件大小（字节）"""
    return os.path.getsize(file_path)


def import_templates(dry_run=False):
    """
    导入模板文件

    Args:
        dry_run: 是否为试运行（不实际修改数据库和文件）
    """
    print("=" * 60)
    print("🚀 合同模板导入脚本")
    print("=" * 60)
    print(f"📂 源目录: {SOURCE_DIR}")
    print(f"📁 目标目录: {TARGET_DIR}")
    print(f"🗄️  数据库: {DB_NAME}")
    print(f"🧪 试运行模式: {'是' if dry_run else '否'}")
    print("=" * 60)

    # 检查源目录
    if not os.path.exists(SOURCE_DIR):
        print(f"❌ 源目录不存在: {SOURCE_DIR}")
        return

    # 创建目标目录
    if not dry_run:
        os.makedirs(TARGET_DIR, exist_ok=True)

    # 扫描支持的文件
    supported_extensions = {'.docx', '.doc', '.md'}
    files = [
        f for f in os.listdir(SOURCE_DIR)
        if os.path.isfile(os.path.join(SOURCE_DIR, f))
        and os.path.splitext(f)[1].lower() in supported_extensions
    ]

    # 跳过子目录（如：合同模板需求统计表_附件）
    files = [
        f for f in files
        if not os.path.isdir(os.path.join(SOURCE_DIR, f))
    ]

    print(f"\n📄 发现 {len(files)} 个支持的文件")

    if len(files) == 0:
        print("⚠️  没有找到可导入的文件")
        return

    # 连接数据库
    db = SessionLocal()

    try:
        success_count = 0
        skip_count = 0
        error_count = 0

        for filename in files:
            source_path = os.path.join(SOURCE_DIR, filename)
            file_ext = os.path.splitext(filename)[1].lower()

            try:
                # 解析文件名元数据
                metadata = parse_filename_metadata(filename)

                # 生成 UUID 文件名
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                target_path = os.path.join(TARGET_DIR, unique_filename)

                # 构造数据库记录
                template_id = uuid.uuid4().hex
                file_size = get_file_size(source_path)
                file_url = f"storage/templates/{unique_filename}"

                # 打印导入信息
                print(f"\n📋 处理: {filename}")
                print(f"   名称: {metadata['name']}")
                print(f"   分类: {metadata['category']}")
                print(f"   UUID: {template_id}")

                if dry_run:
                    print(f"   ⚠️  试运行：跳过文件复制和数据库写入")
                    success_count += 1
                    continue

                # 1. 复制文件到目标目录
                shutil.copy2(source_path, target_path)
                print(f"   ✅ 文件已复制: {unique_filename}")

                # 2. 插入数据库记录
                sql = text("""
                    INSERT INTO contract_templates (
                        id, name, category, subcategory, description,
                        file_url, file_name, file_size, file_type,
                        keywords, is_public, owner_id, status, created_at, updated_at
                    ) VALUES (
                        :id, :name, :category, :subcategory, :description,
                        :file_url, :file_name, :file_size, :file_type,
                        :keywords, :is_public, :owner_id, :status, NOW(), NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        file_url = EXCLUDED.file_url,
                        updated_at = NOW()
                """)

                db.execute(sql, {
                    "id": template_id,
                    "name": metadata['name'],
                    "category": metadata['category'],
                    "subcategory": metadata['subcategory'],
                    "description": f"从 {filename} 导入",
                    "file_url": file_url,
                    "file_name": filename,
                    "file_size": file_size,
                    "file_type": file_ext[1:],  # 去掉点号
                    "keywords": json.dumps(metadata['keywords'], ensure_ascii=False),
                    "is_public": True,
                    "owner_id": 1,  # 默认管理员用户
                    "status": "approved"
                })

                success_count += 1
                print(f"   ✅ 数据库记录已创建")

            except Exception as e:
                error_count += 1
                print(f"   ❌ 错误: {str(e)}")
                continue

        # 提交事务
        if not dry_run:
            db.commit()
            print("\n" + "=" * 60)
            print(f"🎉 导入完成！")
            print(f"   ✅ 成功: {success_count}")
            print(f"   ⏭️  跳过: {skip_count}")
            print(f"   ❌ 失败: {error_count}")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print(f"🧪 试运行完成！共 {success_count} 个文件可导入")
            print(f"💡 使用 --execute 参数执行实际导入")
            print("=" * 60)

    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="导入合同模板到系统")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式，不实际修改数据库和文件"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行实际导入"
    )

    args = parser.parse_args()

    # 默认为试运行模式，需要 --execute 才实际执行
    dry_run = not args.execute

    import_templates(dry_run=dry_run)
