# backend/scripts/update_template_classification.py
"""
更新合同模板分类体系

基于 Contract Classification.txt 的完整分类体系
更新数据库中所有模板的分类信息
"""
import sys
import os
from typing import Dict, List, Set, Optional
import logging

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.contract_template import ContractTemplate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# 完整的合同分类体系（基于 Contract Classification.txt）
# ============================================

# 民法典典型合同（19种）
TYPICAL_CONTRACTS = [
    "买卖合同", "赠与合同", "借款合同", "保证合同", "租赁合同",
    "承揽合同", "建设工程合同", "运输合同", "技术合同", "保管合同",
    "委托合同", "物业服务合同", "行纪合同", "中介合同", "合伙合同"
]

# 非典型合同
ATYPICAL_CONTRACTS = {
    "股权类协议": ["股东", "股权", "出资", "并购", "增资", "合并", "代持", "回购"],
    "劳动合同": ["劳动", "劳务", "竞业", "员工"],
    "商业协议": ["加盟", "特许经营", "知识产权", "债权", "资产重组", "项目合作", "联合经营"],
    "合伙协议": ["普通合伙", "有限合伙"]
}

# 行业特定合同
INDUSTRY_CONTRACTS = {
    "互联网合同": ["SaaS", "API", "用户协议", "隐私政策", "数据保护", "软件授权"],
    "金融合同": ["贷款", "担保", "投资", "金融产品", "资产管理"],
    "房地产合同": ["房产", "不动产", "装修", "物业托管"],
    "医疗合同": ["医疗", "临床试验", "医药"],
    "教育合同": ["教育", "培训", "教材"],
    "供应链合同": ["采购", "供应链", "生产合作", "质量保证"],
    "娱乐合同": ["版权", "创作", "经纪", "演出", "影视"]
}

# 个人创客及自由职业者合同
FREELANCE_CONTRACTS = {
    "服务合同": ["视频", "直播", "带货", "内容创作", "广告", "咨询"],
    "委托合同": ["外包", "短期项目"],
    "承包合同": ["独立承包", "分包"],
    "技术合同": ["软件开发"],
    "短期雇佣合同": ["自由职业", "短期雇佣"],
    "营销协议": ["品牌代言", "合作推广", "营销"]
}

# 跨境与国际合同
CROSS_BORDER_CONTRACTS = ["跨境", "国际"]

# 补充与特殊合同类型
SPECIAL_CONTRACTS = ["电子商务", "环保", "食品安全", "危机管理"]


# ============================================
# 合同类型推断函数
# ============================================

def infer_primary_contract_type(template: ContractTemplate) -> str:
    """
    根据模板名称推断主合同类型

    Args:
        template: 模板对象

    Returns:
        str: 主合同类型
    """
    name = template.name or ""
    category = template.category or ""
    text = f"{name} {category}"

    # 民法典典型合同
    if any(keyword in text for keyword in ["买卖", "购销", "采购", "供货", "销售"]):
        return "买卖合同"
    if "赠与" in text:
        return "赠与合同"
    if any(keyword in text for keyword in ["借款", "借贷", "融资"]):
        return "借款合同"
    if "保证" in text:
        return "保证合同"
    if "租赁" in text:
        return "租赁合同"
    if any(keyword in text for keyword in ["承揽", "加工", "定制"]):
        return "承揽合同"
    if any(keyword in text for keyword in ["建设", "工程", "施工", "EPC", "总承包", "分包"]):
        return "建设工程合同"
    if "运输" in text:
        return "运输合同"
    if any(keyword in text for keyword in ["技术", "专利", "软件许可", "研发"]):
        return "技术合同"
    if "保管" in text:
        return "保管合同"
    if any(keyword in text for keyword in ["委托", "代理", "中介", "行纪"]):
        return "委托合同"
    if "物业" in text:
        return "物业服务合同"
    if any(keyword in text for keyword in ["合伙", "有限合伙", "普通合伙"]):
        return "合伙合同"

    # 非典型合同
    if any(keyword in text for keyword in ATYPICAL_CONTRACTS["股权类协议"]):
        return "股权类协议"
    if any(keyword in text for keyword in ATYPICAL_CONTRACTS["劳动合同"]):
        return "劳动合同"
    if any(keyword in text for keyword in ATYPICAL_CONTRACTS["商业协议"]):
        return "商业协议"

    # 行业特定合同
    if any(keyword in text for keyword in INDUSTRY_CONTRACTS["互联网合同"]):
        return "互联网合同"
    if any(keyword in text for keyword in INDUSTRY_CONTRACTS["金融合同"]):
        return "金融合同"
    if any(keyword in text for keyword in INDUSTRY_CONTRACTS["房地产合同"]):
        return "房地产合同"
    if any(keyword in text for keyword in INDUSTRY_CONTRACTS["医疗合同"]):
        return "医疗合同"
    if any(keyword in text for keyword in INDUSTRY_CONTRACTS["教育合同"]):
        return "教育合同"
    if any(keyword in text for keyword in INDUSTRY_CONTRACTS["供应链合同"]):
        return "供应链合同"
    if any(keyword in text for keyword in INDUSTRY_CONTRACTS["娱乐合同"]):
        return "娱乐合同"

    # 个人创客及自由职业者
    if any(keyword in text for keyword in FREELANCE_CONTRACTS["服务合同"]):
        return "服务合同"
    if any(keyword in text for keyword in FREELANCE_CONTRACTS["委托合同"]):
        return "委托合同"
    if any(keyword in text for keyword in FREELANCE_CONTRACTS["承包合同"]):
        return "承包合同"
    if any(keyword in text for keyword in FREELANCE_CONTRACTS["技术合同"]):
        return "技术合同"
    if any(keyword in text for keyword in FREELANCE_CONTRACTS["短期雇佣合同"]):
        return "短期雇佣合同"
    if any(keyword in text for keyword in FREELANCE_CONTRACTS["营销协议"]):
        return "营销协议"

    # 跨境与国际合同
    if any(keyword in text for keyword in CROSS_BORDER_CONTRACTS):
        return "跨境合同"

    # 补充与特殊合同类型
    if any(keyword in text for keyword in SPECIAL_CONTRACTS):
        return "特殊协议"

    # 默认值
    return "买卖合同"


def infer_industry_tags(template: ContractTemplate) -> List[str]:
    """推断行业标签"""
    name = template.name or ""
    category = template.category or ""
    text = f"{name} {category}"

    industry_map = {
        "互联网": ["互联网", "SaaS", "API", "软件", "电商"],
        "房地产": ["房地产", "房产", "物业", "不动产"],
        "建筑业": ["建筑", "建设", "工程", "施工"],
        "物流": ["物流", "运输"],
        "医疗": ["医疗", "医药", "临床试验"],
        "制造业": ["制造", "采购", "供应链", "生产"],
        "商业": ["商业", "加盟", "特许经营"],
        "金融": ["金融", "投资", "贷款", "担保"],
        "教育": ["教育", "培训"],
        "文化创意": ["文化", "创意", "娱乐", "影视", "演出"],
        "能源": ["能源", "光伏", "储能", "EPC"],
        "跨境电商": ["跨境", "电商"],
        "自由职业": ["自由职业", "外包"],
    }

    tags = []
    for industry, keywords in industry_map.items():
        if any(keyword in text for keyword in keywords):
            tags.append(industry)

    return tags if tags else ["通用"]


def infer_allowed_party_models(template: ContractTemplate) -> List[str]:
    """推断允许的签约主体模型"""
    name = template.name or ""

    # B2B（企业对企业）
    b2b_keywords = ["建设工程", "工程", "总承包", "分包", "采购", "供应链",
                   "股权", "股东", "并购", "增资", "合并", "合伙",
                   "技术合作", "SaaS", "API", "数据保护",
                   "金融产品", "资产管理"]
    if any(keyword in name for keyword in b2b_keywords):
        return ["B2B"]

    # B2C（企业对个人）
    b2c_keywords = ["住宅租赁", "房屋租赁", "房产买卖",
                   "劳动", "劳务", "员工",
                   "用户协议", "隐私政策", "软件授权", "电子商务",
                   "教育服务", "医疗"]
    if any(keyword in name for keyword in b2c_keywords):
        return ["B2C"]

    # B2P（企业对自由职业者/个人）
    b2p_keywords = ["视频制作", "直播", "带货", "内容创作", "外包", "自由职业"]
    if any(keyword in name for keyword in b2p_keywords):
        return ["B2P"]

    # 混合模式（B2B + B2C）
    mixed_keywords = ["买卖", "购销", "供货", "销售", "服务", "咨询",
                     "租赁", "装修", "物业", "加盟", "特许经营",
                     "品牌代言", "合作推广"]
    if any(keyword in name for keyword in mixed_keywords):
        return ["B2B", "B2C"]

    # 默认值：B2B 和 B2C
    return ["B2B", "B2C"]


def infer_delivery_model(template: ContractTemplate) -> str:
    """推断交付模型"""
    name = template.name or ""

    # 单一交付
    if any(keyword in name for keyword in ["买卖", "购销", "采购", "供货", "赠与", "保管"]):
        return "单一交付"

    # 分期交付
    if any(keyword in name for keyword in ["建设", "工程", "施工", "总承包", "分包", "研发", "培训"]):
        return "分期交付"

    # 持续交付
    if any(keyword in name for keyword in ["租赁", "劳动", "劳务", "物业", "SaaS",
                                            "用户协议", "服务", "咨询", "外包"]):
        return "持续交付"

    # 复合交付（商品+服务）
    if any(keyword in name for keyword in ["EPC", "设备", "安装", "供货", "施工", "装修"]):
        return "复合交付"

    return "单一交付"


def infer_payment_model(template: ContractTemplate) -> Optional[str]:
    """推断付款模型"""
    name = template.name or ""

    # 一次性付款
    if any(keyword in name for keyword in ["买卖", "购销", "采购", "赠与", "保管"]):
        return "一次性付款"

    # 分期付款
    if any(keyword in name for keyword in ["建设", "工程", "施工", "租赁", "装修", "培训"]):
        return "分期付款"

    # 定期结算
    if any(keyword in name for keyword in ["劳动", "劳务", "物业", "SaaS",
                                            "服务", "咨询", "外包", "自由职业"]):
        return "定期结算"

    # 混合模式
    if any(keyword in name for keyword in ["EPC", "设备", "安装", "加盟", "特许经营"]):
        return "混合模式"

    return None


def infer_risk_level(template: ContractTemplate) -> str:
    """推断风险等级"""
    name = template.name or ""

    # 高风险
    high_risk_keywords = ["劳动", "劳务", "建设工程", "工程", "股权", "并购",
                          "增资", "合并", "技术开发", "医疗", "临床试验"]
    if any(keyword in name for keyword in high_risk_keywords):
        return "high"

    # 中风险
    mid_risk_keywords = ["合作", "合资", "合伙", "租赁", "加盟", "特许经营",
                         "知识产权", "数据保护", "外包", "自由职业", "直播", "带货"]
    if any(keyword in name for keyword in mid_risk_keywords):
        return "mid"

    # 低风险
    return "low"


def infer_is_recommended(template: ContractTemplate) -> bool:
    """判断是否为推荐模板"""
    name = template.name or ""

    # 推荐的高频标准合同
    recommended_templates = [
        "一般商品买卖合同（简单版）",
        "房屋买卖合同",
        "货物买卖合同",
        "一般住宅房屋租赁合同（简单版）",
        "商业房屋租赁合同",
        "劳动合同",
        "劳务合同",
        "技术咨询合同",
        "技术服务合同",
        "咨询服务合同",
        "采购合同（适用于机械设备类货物采购）",
        "采购合同（适用物资采购）",
        "建设工程设计合同",
        "软件开发合同",
        "保密协议",
        "和解协议"
    ]

    return any(rec in name for rec in recommended_templates)


def infer_secondary_types(template: ContractTemplate) -> Optional[List[str]]:
    """推断次要合同类型"""
    name = template.name or ""

    # 设备供货+安装
    if "设备" in name and "安装" in name:
        return ["买卖合同", "建设工程合同"]
    if "供货" in name and "施工" in name:
        return ["买卖合同", "建设工程合同"]

    # 技术+服务
    if "技术转让" in name and "服务" in name:
        return ["技术转让合同", "服务合同"]
    if "技术开发" in name and "服务" in name:
        return ["技术开发合同", "服务合同"]

    # 融资+租赁
    if "融资租赁" in name:
        return ["借款合同", "租赁合同"]

    # 股权+劳动
    if "股权激励" in name and "劳动" in name:
        return ["股权类协议", "劳动合同"]

    # EPC
    if "EPC" in name:
        return ["建设工程合同", "买卖合同", "承揽合同"]

    # 特许经营
    if "特许经营" in name:
        return ["商业协议", "知识产权许可"]

    # 供应链
    if "供应链" in name:
        return ["买卖合同", "运输合同", "保管合同"]

    # 单一合同类型，无次要类型
    return None


# ============================================
# 主更新函数
# ============================================

def update_templates(db: Session):
    """
    更新所有模板的分类信息

    Args:
        db: 数据库会话
    """
    logger.info("[Update] 开始更新合同模板分类体系（基于完整分类）")

    # 获取所有模板
    templates = db.query(ContractTemplate).all()
    logger.info(f"[Update] 找到 {len(templates)} 个模板")

    updated_count = 0
    for template in templates:
        needs_update = False

        # 更新主合同类型
        if not template.primary_contract_type or template.primary_contract_type == "买卖合同":
            template.primary_contract_type = infer_primary_contract_type(template)
            needs_update = True

        # 更新行业标签
        if not template.industry_tags or len(template.industry_tags) == 0:
            template.industry_tags = infer_industry_tags(template)
            needs_update = True

        # 更新允许的签约主体模型
        if not template.allowed_party_models or len(template.allowed_party_models) == 0:
            template.allowed_party_models = infer_allowed_party_models(template)
            needs_update = True

        # 更新交付模型
        if not template.delivery_model or template.delivery_model == "单一交付":
            template.delivery_model = infer_delivery_model(template)
            needs_update = True

        # 更新付款模型
        if not template.payment_model:
            template.payment_model = infer_payment_model(template)
            needs_update = True

        # 更新风险等级
        if not template.risk_level or template.risk_level == "low":
            template.risk_level = infer_risk_level(template)
            needs_update = True

        # 更新推荐级别
        if template.is_recommended is None or template.is_recommended is False:
            template.is_recommended = infer_is_recommended(template)
            needs_update = True

        # 更新次要合同类型
        if not template.secondary_types:
            template.secondary_types = infer_secondary_types(template)
            needs_update = True

        if needs_update:
            updated_count += 1
            logger.info(
                f"[Update] 更新模板: {template.name} "
                f"(type={template.primary_contract_type}, "
                f"industry={template.industry_tags}, "
                f"party_models={template.allowed_party_models}, "
                f"delivery={template.delivery_model}, "
                f"payment={template.payment_model}, "
                f"risk={template.risk_level}, "
                f"recommended={template.is_recommended})"
            )

    # 提交更改
    db.commit()

    logger.info(f"[Update] 完成！共更新 {updated_count}/{len(templates)} 个模板")
    logger.info("[Update] 分类体系特点：")
    logger.info("  - 民法典典型合同（19种）")
    logger.info("  - 非典型合同（4大类）")
    logger.info("  - 行业特定合同（8个行业）")
    logger.info("  - 个人创客及自由职业者合同（6类）")
    logger.info("  - 跨境与国际合同")
    logger.info("  - 补充与特殊合同类型")


def main():
    """主函数"""
    logger.info("[Update] 开始执行合同分类更新脚本")

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 更新模板
        update_templates(db)

        logger.info("[Update] 合同分类更新成功完成")

        # 显示统计信息
        templates = db.query(ContractTemplate).all()

        # 统计各类合同类型数量
        type_counts = {}
        for template in templates:
            contract_type = template.primary_contract_type
            type_counts[contract_type] = type_counts.get(contract_type, 0) + 1

        logger.info("\n[Update] 合同类型统计：")
        for contract_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {contract_type}: {count} 个")

        # 统计推荐模板数量
        recommended_count = sum(1 for t in templates if t.is_recommended)
        logger.info(f"\n[Update] 推荐模板数量: {recommended_count} 个")

    except Exception as e:
        logger.error(f"[Update] 更新失败: {str(e)}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
