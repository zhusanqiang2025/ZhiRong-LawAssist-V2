#!/usr/bin/env python
"""
直接执行数据库迁移的脚本

这个脚本绕过 Alembic 的配置问题，直接使用 psycopg2 执行 SQL。
适用于本地开发环境。
"""

import psycopg2
from psycopg2 import sql
import sys
import os

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'legal_assistant_db',
    'user': 'admin',
    'password': '01689101Abc'
}

# SQL 语句
SQL_STATEMENTS = [
    # 添加 title 字段
    sql.SQL("""
        ALTER TABLE risk_analysis_sessions
        ADD COLUMN IF NOT EXISTS title VARCHAR(255);
    """),

    # 添加 is_unread 字段
    sql.SQL("""
        ALTER TABLE risk_analysis_sessions
        ADD COLUMN IF NOT EXISTS is_unread BOOLEAN DEFAULT TRUE;
    """),

    # 添加 is_background 字段
    sql.SQL("""
        ALTER TABLE risk_analysis_sessions
        ADD COLUMN IF NOT EXISTS is_background BOOLEAN DEFAULT FALSE;
    """),

    # 添加注释
    sql.SQL("""
        COMMENT ON COLUMN risk_analysis_sessions.title IS '会话标题（用于历史记录显示）';
    """),

    sql.SQL("""
        COMMENT ON COLUMN risk_analysis_sessions.is_unread IS '是否未读';
    """),

    sql.SQL("""
        COMMENT ON COLUMN risk_analysis_sessions.is_background IS '是否为后台任务';
    """),
]

def execute_migration():
    """执行数据库迁移"""
    conn = None
    try:
        # 连接数据库
        print(f"正在连接数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()

        print("连接成功！开始执行迁移...")

        # 执行 SQL 语句
        for i, statement in enumerate(SQL_STATEMENTS, 1):
            try:
                print(f"执行语句 {i}/{len(SQL_STATEMENTS)}...")
                cursor.execute(statement)
                print(f"✓ 语句 {i} 执行成功")
            except psycopg2.Error as e:
                print(f"✗ 语句 {i} 执行失败: {e}")
                # 继续执行其他语句
                continue

        # 提交事务
        conn.commit()
        print("\n✓ 迁移完成！所有更改已提交。")

        # 验证结果
        print("\n验证迁移结果...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'risk_analysis_sessions'
              AND column_name IN ('title', 'is_unread', 'is_background')
            ORDER BY ordinal_position;
        """)

        results = cursor.fetchall()
        if results:
            print("\n新增字段:")
            print("-" * 80)
            print(f"{'字段名':<20} {'数据类型':<20} {'可空':<10} {'默认值':<20}")
            print("-" * 80)
            for row in results:
                column_name, data_type, is_nullable, column_default = row
                print(f"{column_name:<20} {data_type:<20} {is_nullable:<10} {str(column_default):<20}")
            print("-" * 80)
        else:
            print("⚠ 未找到新增字段，请检查表名或手动验证。")

        return True

    except psycopg2.OperationalError as e:
        print(f"✗ 数据库连接失败: {e}")
        print("\n请检查:")
        print("1. PostgreSQL 服务是否运行")
        print("2. 数据库配置是否正确")
        print("3. 如果使用 Docker，确保容器已启动")
        return False

    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭。")

if __name__ == "__main__":
    print("=" * 80)
    print("风险评估模块 - 历史任务功能数据库迁移")
    print("=" * 80)
    print()

    success = execute_migration()

    if success:
        print("\n" + "=" * 80)
        print("迁移成功！现在可以启动后端服务并使用历史任务功能了。")
        print("=" * 80)
        sys.exit(0)
    else:
        print("\n" + "=" * 80)
        print("迁移失败！请检查错误信息并解决后重试。")
        print("=" * 80)
        sys.exit(1)
