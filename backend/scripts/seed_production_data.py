#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产环境数据种子脚本

统一调用所有现有的初始化函数，在应用启动时自动执行。

功能:
1. 创建管理员用户（如果不存在）
2. 导入系统审查规则（从 exported_review_rules.json，48条系统规则）
3. 初始化风险评估规则
4. 初始化案件分析规则包（6种案件类型）
5. 迁移知识图谱数据
6. 迁移分类数据（从 categories.json）

幂等性: 可以安全地重复执行
"""

import os
import sys
import logging
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User
from app.models.rule import ReviewRule
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


def create_admin_user_if_needed():
    """
    创建管理员用户（如果数据库中没有用户）
    如果指定的管理员用户已存在但不是管理员，则提升为管理员

    环境变量:
    - SEED_ADMIN_EMAIL: 管理员邮箱（必需）
    - SEED_ADMIN_PASSWORD: 管理员密码（必需，至少8位）

    降级处理: 如果环境变量未配置，跳过并记录警告
    """
    db = SessionLocal()
    try:
        # 检查环境变量
        admin_email = os.getenv("SEED_ADMIN_EMAIL")
        admin_password = os.getenv("SEED_ADMIN_PASSWORD")

        if not admin_email or not admin_password:
            logger.warning("[Seed] SEED_ADMIN_EMAIL or SEED_ADMIN_PASSWORD not set")
            logger.warning("[Seed] Skipping admin user creation. To create admin later:")
            logger.warning("[Seed]   1. Set environment variables SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD")
            logger.warning("[Seed]   2. Restart the application OR run: python scripts/seed_production_data.py")
            return

        # 验证密码长度
        if len(admin_password) < 8:
            logger.warning("[Seed] Admin password is too short (min 8 characters), skipping admin creation")
            return

        # 检查用户是否已存在
        existing_user = db.query(User).filter(User.email == admin_email).first()

        if existing_user:
            # 用户已存在，检查是否是管理员
            if existing_user.is_admin and existing_user.is_superuser:
                logger.info(f"[Seed] Admin user already exists: {admin_email}")
            else:
                # 提升为管理员
                existing_user.is_admin = True
                existing_user.is_superuser = True
                db.commit()
                logger.info(f"[Seed] ✓ Promoted existing user to admin: {admin_email}")
        else:
            # 检查是否已有其他用户
            user_count = db.query(User).count()
            if user_count > 0:
                logger.info(f"[Seed] Database already has {user_count} user(s), creating admin user anyway")
            else:
                logger.info("[Seed] Creating first admin user")

            # 创建管理员用户
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
                is_admin=True,
                is_active=True,
                is_superuser=True
            )
            db.add(admin_user)
            db.commit()

            logger.info(f"[Seed] ✓ Admin user created: {admin_email}")
            logger.warning("[Seed] SECURITY: Please change the default password after first login!")

    except Exception as e:
        logger.error(f"[Seed] ✗ Failed to create admin user: {e}")
        db.rollback()
    finally:
        db.close()


def import_system_rules_from_exported_json():
    """
    从 exported_review_rules.json 导入系统规则（is_system=true）

    仅导入系统规则，跳过用户自定义规则（is_system=false）
    如果规则已存在，则更新内容
    """
    db = SessionLocal()
    try:
        # 定位规则文件
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rule_file = os.path.join(current_dir, "..", "config", "exported_review_rules.json")

        if not os.path.exists(rule_file):
            logger.warning(f"[Seed] System rules file not found: {rule_file}")
            logger.warning("[Seed] Skipping system rules import")
            return

        # 读取 JSON 文件
        with open(rule_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total_rules = data.get("total_rules", 0)
        rules = data.get("rules", [])

        logger.info(f"[Seed] Found {total_rules} total rules in exported file")

        # 统计
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for rule_data in rules:
            # 仅导入系统规则
            if not rule_data.get("is_system", False):
                skipped_count += 1
                continue

            name = rule_data.get("name")
            if not name:
                continue

            # 检查是否已存在同名规则
            existing = db.query(ReviewRule).filter(
                ReviewRule.name == name
            ).first()

            if existing:
                # 更新现有规则
                existing.description = rule_data.get("description", "")
                existing.content = rule_data.get("content", "")
                existing.rule_category = rule_data.get("rule_category", "universal")
                existing.priority = rule_data.get("priority", 0)
                existing.is_system = rule_data.get("is_system", True)
                existing.is_active = rule_data.get("is_active", True)
                updated_count += 1
                logger.debug(f"[Seed] Updated system rule: {name}")
            else:
                # 创建新规则
                rule = ReviewRule(
                    name=name,
                    description=rule_data.get("description", ""),
                    content=rule_data.get("content", ""),
                    rule_category=rule_data.get("rule_category", "universal"),
                    priority=rule_data.get("priority", 0),
                    is_system=True,
                    is_active=rule_data.get("is_active", True),
                    created_at=datetime.utcnow()
                )
                db.add(rule)
                created_count += 1
                logger.info(f"[Seed] ✓ Created system rule: {name}")

        db.commit()

        logger.info(f"[Seed] System rules import completed:")
        logger.info(f"  - Created: {created_count} rules")
        logger.info(f"  - Updated: {updated_count} rules")
        logger.info(f"  - Skipped (non-system): {skipped_count} rules")

    except Exception as e:
        logger.error(f"[Seed] ✗ Failed to import system rules: {e}")
        db.rollback()
    finally:
        db.close()


def seed_production_data():
    """
    主函数：执行所有数据初始化

    调用所有现有的初始化函数，按正确顺序执行。
    每个函数已内置幂等性检查。
    """
    logger.info("=" * 60)
    logger.info("[Seed] Starting production data seeding...")
    logger.info("=" * 60)

    db = None
    try:
        # 1. 创建管理员用户（如果不存在）
        logger.info("[Seed] Step 1/5: Checking admin user...")
        create_admin_user_if_needed()

        # 2. 导入系统审查规则（从 exported_review_rules.json）
        logger.info("[Seed] Step 2/5: Importing system review rules...")
        try:
            import_system_rules_from_exported_json()
        except Exception as e:
            logger.error(f"[Seed] Failed to import system review rules: {e}")

        # 3. 初始化风险评估规则（调用现有函数）
        logger.info("[Seed] Step 3/5: Initializing risk assessment rules...")
        try:
            from app.data.risk_rules_init import init_risk_rules
            init_risk_rules()
        except ImportError:
            logger.warning("[Seed] risk_rules_init module not found, skipping")
        except Exception as e:
            logger.error(f"[Seed] Failed to initialize risk rules: {e}")

        # 4. 初始化案件分析规则包（调用现有函数）
        logger.info("[Seed] Step 4/5: Initializing litigation case packages...")
        try:
            db = SessionLocal()
            from scripts.init_litigation_packages import init_litigation_case_packages
            init_litigation_case_packages(db)
        except ImportError:
            logger.warning("[Seed] init_litigation_packages module not found, skipping")
        except Exception as e:
            logger.error(f"[Seed] Failed to initialize litigation packages: {e}")

        # 5. 迁移知识图谱（调用现有函数）
        logger.info("[Seed] Step 5/6: Migrating knowledge graph...")
        try:
            from scripts.migrate_knowledge_graph_to_db import migrate_knowledge_graph
            migrate_knowledge_graph()
        except ImportError:
            logger.warning("[Seed] migrate_knowledge_graph module not found, skipping")
        except Exception as e:
            logger.error(f"[Seed] Failed to migrate knowledge graph: {e}")

        # 6. 迁移分类数据（从 categories.json）
        logger.info("[Seed] Step 6/6: Migrating categories data...")
        try:
            from app.models.category import Category
            import json

            # 定位 categories.json
            categories_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "categories.json"
            )

            if not os.path.exists(categories_file):
                logger.warning(f"[Seed] categories.json not found at {categories_file}")
                logger.warning("[Seed] Skipping category migration. Run migrate_categories_from_json.py manually if needed.")
            else:
                with open(categories_file, 'r', encoding='utf-8') as f:
                    categories_data = json.load(f)

                db = SessionLocal()
                try:
                    # 检查现有数据
                    existing_count = db.query(Category).count()
                    if existing_count > 0:
                        logger.info(f"[Seed]  Found {existing_count} existing category records, skipping migration")
                        logger.info("[Seed]  To re-import: clear categories table first")
                    else:
                        # 执行迁移
                        total_count = 0

                        for primary_cat in categories_data.get("primary_categories", []):
                            primary_id = primary_cat.get("id")
                            primary_name = primary_cat.get("name")
                            primary_desc = primary_cat.get("description", "")

                            # 一级分类
                            primary_category = Category(
                                name=primary_name,
                                code=primary_id,
                                description=primary_desc,
                                parent_id=None,
                                sort_order=int(primary_id) if primary_id.isdigit() else 0,
                                meta_info={"level": "primary"},
                                is_active=True
                            )
                            db.add(primary_category)
                            db.flush()
                            primary_db_id = primary_category.id
                            total_count += 1

                            # 二级分类
                            for sub_type in primary_cat.get("sub_types", []):
                                sub_type_name = sub_type.get("name")

                                sub_category = Category(
                                    name=sub_type_name,
                                    code=f"{primary_id}-{sub_type_name[:2]}",
                                    description="",
                                    parent_id=primary_db_id,
                                    sort_order=0,
                                    meta_info={
                                        "level": "secondary",
                                        "sub_categories": sub_type.get("sub_categories", [])
                                    },
                                    is_active=True
                                )
                                db.add(sub_category)
                                db.flush()
                                total_count += 1

                                # 三级分类
                                for sub_cat_name in sub_type.get("sub_categories", []):
                                    tertiary_category = Category(
                                        name=sub_cat_name,
                                        code=f"{primary_id}-{sub_type_name[:2]}-{sub_cat_name[:2]}",
                                        description="",
                                        parent_id=sub_category.id,
                                        sort_order=0,
                                        meta_info={"level": "tertiary"},
                                        is_active=True
                                    )
                                    db.add(tertiary_category)
                                    total_count += 1

                        db.commit()
                        logger.info(f"[Seed] ✓ Migrated {total_count} category records")

                except Exception as e:
                    logger.error(f"[Seed] Failed to migrate categories: {e}")
                    db.rollback()
                finally:
                    db.close()

        except Exception as e:
            logger.error(f"[Seed] Category migration error: {e}")

        logger.info("=" * 60)
        logger.info("[Seed] Production data seeding completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"[Seed] ✗ Data seeding encountered an error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 执行数据种子
    seed_production_data()
