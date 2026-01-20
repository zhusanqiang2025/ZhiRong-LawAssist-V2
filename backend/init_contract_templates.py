#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合同模板数据初始化脚本
用于创建示例合同模板数据
"""

import asyncio
import sys
import os
import uuid

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, Base, engine
from app.models.contract_template import ContractTemplate
from app.models.user import User
from sqlalchemy.orm import Session

# 示例模板数据
SAMPLE_TEMPLATES = [
    {
        "name": "标准劳动合同模板",
        "category": "劳动合同",
        "subcategory": "标准合同",
        "description": "适用于一般企业的标准劳动合同，包含基本条款和保障，符合最新劳动法规定",
        "keywords": ["劳动", "用工", "雇佣", "员工", "工作", "职位", "薪资"],
        "tags": ["标准", "常用", "企业必备"],
        "file_url": "/templates/standard_labor_contract.docx",
        "file_name": "标准劳动合同模板.docx",
        "file_size": 45678,
        "file_type": "docx",
        "is_featured": True,
        "is_free": True,
        "language": "zh-CN",
        "jurisdiction": "中国大陆",
        "usage_scenario": "适用于企业与员工建立劳动关系，明确双方权利义务",
        "content_summary": "包含合同期限、工作内容、工作地点、工作时间、劳动报酬、社会保险、劳动保护等核心条款"
    },
    {
        "name": "房屋租赁合同模板",
        "category": "租赁合同",
        "subcategory": "房屋租赁",
        "description": "适用于个人或企业房屋租赁的标准合同模板，保障出租方和承租方权益",
        "keywords": ["租赁", "出租", "承租", "房租", "房屋", "住房", "物业"],
        "tags": ["房地产", "常用", "民生"],
        "file_url": "/templates/house_rental_contract.docx",
        "file_name": "房屋租赁合同模板.docx",
        "file_size": 38456,
        "file_type": "docx",
        "is_featured": True,
        "is_free": True,
        "language": "zh-CN",
        "jurisdiction": "中国大陆",
        "usage_scenario": "适用于个人房屋出租、企业员工宿舍租赁等场景",
        "content_summary": "包含租赁物描述、租赁期限、租金及支付方式、双方权利义务、违约责任等条款"
    },
    {
        "name": "保密协议模板",
        "category": "保密协议",
        "subcategory": "NDA",
        "description": "保护商业机密和知识产权的保密协议，适用于企业间合作或员工保密",
        "keywords": ["保密", "nda", "机密", "商业秘密", "知识产权", "保护"],
        "tags": ["企业必备", "风险防范", "法律保护"],
        "file_url": "/templates/confidentiality_agreement.docx",
        "file_name": "保密协议模板.docx",
        "file_size": 32145,
        "file_type": "docx",
        "is_featured": False,
        "is_free": True,
        "language": "zh-CN",
        "jurisdiction": "中国大陆",
        "usage_scenario": "适用于企业合作、员工入职、技术交流等需要保密的场景",
        "content_summary": "明确保密信息的范围、保密义务、违约责任、协议期限等关键条款"
    },
    {
        "name": "借款合同模板",
        "category": "借款合同",
        "subcategory": "民间借贷",
        "description": "适用于个人或企业间借款的标准合同模板，明确借款金额、利息、还款方式等",
        "keywords": ["借款", "贷款", "借钱", "利息", "还款", "资金", "融资"],
        "tags": ["金融", "民间借贷", "常用"],
        "file_url": "/templates/loan_contract.docx",
        "file_name": "借款合同模板.docx",
        "file_size": 41234,
        "file_type": "docx",
        "is_featured": False,
        "is_free": True,
        "language": "zh-CN",
        "jurisdiction": "中国大陆",
        "usage_scenario": "适用于个人借贷、企业融资、股东借款等资金往来场景",
        "content_summary": "包含借款金额、借款用途、利率、还款计划、担保条款、违约责任等"
    },
    {
        "name": "设备租赁合同模板",
        "category": "租赁合同",
        "subcategory": "设备租赁",
        "description": "适用于机器设备、车辆、办公设备等租赁的专业合同模板",
        "keywords": ["设备", "租赁", "机械", "车辆", "办公", "资产", "融资租赁"],
        "tags": ["企业", "资产", "设备管理"],
        "file_url": "/templates/equipment_rental_contract.docx",
        "file_name": "设备租赁合同模板.docx",
        "file_size": 48923,
        "file_type": "docx",
        "is_featured": False,
        "is_free": False,
        "language": "zh-CN",
        "jurisdiction": "中国大陆",
        "usage_scenario": "适用于机械设备租赁、车辆租赁、办公设备租赁等企业资产使用场景",
        "content_summary": "明确租赁设备状况、租赁期限、租金及支付方式、设备维护、保险责任等"
    },
    {
        "name": "股权转让协议模板",
        "category": "股权转让",
        "subcategory": "股权交易",
        "description": "适用于公司股权转让的专业协议模板，保障交易安全和法律效力",
        "keywords": ["股权", "转让", "股份", "投资", "股东", "公司", "收购"],
        "tags": ["公司法", "投资", "企业", "高风险"],
        "file_url": "/templates/equity_transfer_agreement.docx",
        "file_name": "股权转让协议模板.docx",
        "file_size": 65432,
        "file_type": "docx",
        "is_featured": True,
        "is_free": False,
        "language": "zh-CN",
        "jurisdiction": "中国大陆",
        "usage_scenario": "适用于公司股东之间股权转让、投资者收购股权等股权交易场景",
        "content_summary": "包含转让标的、转让价格、支付方式、交割条件、陈述保证、违约责任等"
    },
    {
        "name": "技术服务合同模板",
        "category": "服务合同",
        "subcategory": "技术服务",
        "description": "适用于各类技术服务的专业合同模板，明确服务内容和标准",
        "keywords": ["技术", "服务", "咨询", "顾问", "开发", "维护", "支持"],
        "tags": ["技术", "IT", "专业服务"],
        "file_url": "/templates/technical_service_contract.docx",
        "file_name": "技术服务合同模板.docx",
        "file_size": 52341,
        "file_type": "docx",
        "is_featured": False,
        "is_free": True,
        "language": "zh-CN",
        "jurisdiction": "中国大陆",
        "usage_scenario": "适用于软件开发、系统集成、技术咨询、IT维护等技术类服务",
        "content_summary": "明确服务内容、服务标准、验收标准、费用支付、知识产权归属等"
    },
    {
        "name": "合作经营协议模板",
        "category": "合作协议",
        "subcategory": "合作经营",
        "description": "适用于企业间合作经营、项目合作的综合性协议模板",
        "keywords": ["合作", "合伙", "联合", "经营", "项目", "合资", "联盟"],
        "tags": ["企业经营", "战略合作", "项目合作"],
        "file_url": "/templates/cooperation_agreement.docx",
        "file_name": "合作经营协议模板.docx",
        "file_size": 56789,
        "file_type": "docx",
        "is_featured": False,
        "is_free": False,
        "language": "zh-CN",
        "jurisdiction": "中国大陆",
        "usage_scenario": "适用于企业战略合作、项目联合开发、渠道合作等商业合作场景",
        "content_summary": "包含合作范围、投资方式、收益分配、风险承担、争议解决等核心条款"
    }
]

def create_sample_templates(db: Session, admin_user_id: str):
    """创建示例模板数据"""
    print("开始创建示例合同模板数据...")

    created_count = 0

    for template_data in SAMPLE_TEMPLATES:
        # 检查是否已存在相同名称的模板
        existing = db.query(ContractTemplate).filter(
            ContractTemplate.name == template_data["name"]
        ).first()

        if existing:
            print(f"模板 '{template_data['name']}' 已存在，跳过")
            continue

        # 创建新模板
        template = ContractTemplate(
            id=str(uuid.uuid4()),  # 生成唯一的UUID字符串
            created_by=admin_user_id,
            updated_by=admin_user_id,
            **template_data
        )

        db.add(template)
        created_count += 1
        print(f"已创建模板: {template_data['name']}")

    db.commit()
    print(f"✅ 成功创建 {created_count} 个示例模板")

def get_admin_user(db: Session) -> str:
    """获取管理员用户ID"""
    # 先尝试查找管理员用户
    admin = db.query(User).filter(User.email == "admin@example.com").first()

    if admin:
        return admin.id

    # 如果没有找到，查找第一个用户
    user = db.query(User).first()
    if user:
        return user.id

    raise Exception("数据库中没有用户，请先创建用户")

def main():
    """主函数"""
    print("🚀 开始初始化合同模板数据...")

    # 创建数据库表
    print("📋 创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 获取管理员用户ID
        admin_user_id = get_admin_user(db)
        print(f"👤 使用用户ID: {admin_user_id}")

        # 创建示例模板
        create_sample_templates(db, admin_user_id)

        print("\n🎉 合同模板数据初始化完成！")
        print("\n📊 模板统计:")

        # 统计模板数量
        total_templates = db.query(ContractTemplate).count()
        categories = db.query(ContractTemplate.category).distinct().all()

        print(f"  总模板数: {total_templates}")
        print(f"  分类数: {len(categories)}")

        for category in categories:
            count = db.query(ContractTemplate).filter(
                ContractTemplate.category == category[0]
            ).count()
            print(f"  - {category[0]}: {count} 个")

    except Exception as e:
        print(f"❌ 初始化失败: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()