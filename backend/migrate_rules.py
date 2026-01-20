"""
数据库规则迁移脚本

功能：
1. 将历史 custom 规则整合到 universal 规则中
2. 新增行业规则
"""
from app.database import SessionLocal
from app.models.rule import ReviewRule


def migrate_custom_to_universal():
    """将历史 custom 规则整合到 universal 规则"""
    db = SessionLocal()
    try:
        # 查询所有 rule_category='custom' 的规则（无论 is_system 状态）
        # 因为这些是历史版本的自定义规则，应该整合到通用规则中
        custom_rules = db.query(ReviewRule).filter(
            ReviewRule.rule_category == "custom"
        ).all()

        print(f"找到 {len(custom_rules)} 条历史 custom 规则")

        for rule in custom_rules:
            # 更新为 universal 规则
            rule.rule_category = "universal"
            # 设置为系统规则
            rule.is_system = True
            # 确保名称以 [通用] 开头
            if not rule.name.startswith("[通用]"):
                rule.name = f"[通用] {rule.name}"
            print(f"  更新规则: {rule.name}")

        db.commit()
        print("✅ 历史规则整合完成")
    except Exception as e:
        print(f"❌ 整合失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def insert_industry_rules():
    """插入行业规则"""
    industry_rules = [
        {
            "name": "[行业-外商投资] 审批备案",
            "rule_category": "industry",
            "description": "外商投资企业需办理审批或备案手续",
            "content": "审查外商投资协议是否包含：1. 投资准入负面清单核查；2. 行业主管部门审批/备案条款；3. 外汇登记手续约定；4. 安全审查申报义务",
            "is_system": True,
            "priority": 100,
            "is_active": True
        },
        {
            "name": "[行业-建筑工程] 资质证书",
            "rule_category": "industry",
            "description": "建筑工程需审查承包方资质",
            "content": "审查建筑工程合同是否包含：1. 承包方资质等级要求；2. 施工许可证办理约定；3. 工程质量标准明确；4. 安全生产责任划分；5. 竣工验收程序",
            "is_system": True,
            "priority": 101,
            "is_active": True
        },
        {
            "name": "[行业-房地产] 开发资质",
            "rule_category": "industry",
            "description": "房地产开发需审查开发资质和土地权属",
            "content": "审查房地产合同是否包含：1. 开发商资质证书要求；2. 国有土地使用证复印件；3. 建设工程规划许可证；4. 预售许可证（如适用）；5. 面积差异处理条款",
            "is_system": True,
            "priority": 102,
            "is_active": True
        },
        {
            "name": "[行业-金融] 利率合规",
            "rule_category": "industry",
            "description": "金融借款合同需审查利率合规性",
            "content": "审查金融借款合同是否包含：1. 年化利率不超过法定上限（LPR的4倍）；2. 禁止砍头息条款；3. 费用透明化要求；4. 逾期利息和违约金合理约定；5. 个人信息授权条款",
            "is_system": True,
            "priority": 103,
            "is_active": True
        },
        {
            "name": "[行业-劳动] 社保公积金",
            "rule_category": "industry",
            "description": "劳动合同需审查社保公积金缴纳",
            "content": "审查劳动合同是否包含：1. 社保公积金缴纳基数和比例；2. 加班工资计算标准；3. 年休假安排；4. 竞业限制补偿金；5. 解除劳动合同经济补偿",
            "is_system": True,
            "priority": 104,
            "is_active": True
        },
        {
            "name": "[行业-医疗器械] 注册证照",
            "rule_category": "industry",
            "description": "医疗器械需审查注册证和经营许可",
            "content": "审查医疗器械合同是否包含：1. 医疗器械注册证有效期限；2. 经营许可证范围核查；3. 质量保证条款；4. 不良事件报告义务；5. 召回和赔偿责任",
            "is_system": True,
            "priority": 105,
            "is_active": True
        },
        {
            "name": "[行业-教育] 办学许可",
            "rule_category": "industry",
            "description": "教育培训需审查办学资质",
            "content": "审查教育培训合同是否包含：1. 办学许可证有效期限；2. 收费标准和退费条款；3. 教师资质要求；4. 安全保障责任；5. 教学质量保证",
            "is_system": True,
            "priority": 106,
            "is_active": True
        },
        {
            "name": "[行业-电商] 平台责任",
            "rule_category": "industry",
            "description": "电商合同需审查平台责任和数据合规",
            "content": "审查电商合同是否包含：1. 平台资质和ICP备案；2. 用户个人信息保护条款；3. 消费者权益保护承诺；4. 知识产权侵权处理；5. 七日无理由退货适用",
            "is_system": True,
            "priority": 107,
            "is_active": True
        }
    ]

    db = SessionLocal()
    try:
        for rule_data in industry_rules:
            # 检查是否已存在
            existing = db.query(ReviewRule).filter(
                ReviewRule.name == rule_data["name"]
            ).first()

            if not existing:
                rule = ReviewRule(**rule_data)
                db.add(rule)
                print(f"  新增规则: {rule_data['name']}")
            else:
                print(f"  跳过已存在规则: {rule_data['name']}")

        db.commit()
        print("✅ 行业规则插入完成")
    except Exception as e:
        print(f"❌ 插入行业规则失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("开始规则迁移...")
    print("=" * 50)

    print("\n步骤1：整合历史 custom 规则到 universal 规则")
    print("-" * 50)
    migrate_custom_to_universal()

    print("\n步骤2：插入行业规则")
    print("-" * 50)
    insert_industry_rules()

    print("\n" + "=" * 50)
    print("迁移完成！")
    print("=" * 50)
