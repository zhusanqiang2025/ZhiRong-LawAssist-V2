# backend/scripts/update_template_models.py
"""
更新合同模板模型的脚本

功能：
1. 为现有模板设置结构锚点字段
2. 标注推荐模板（is_recommended）
3. 设置风险等级

使用方法：
python -m scripts.update_template_models
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.contract_template import ContractTemplate
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 推荐模板列表（A 类：标准高频合同）
RECOMMENDED_TEMPLATES = [
    # 常见买卖合同
    "设备采购合同",
    "商品买卖合同",
    "货物销售合同",

    # 常见服务合同
    "技术服务合同",
    "咨询服务合同",
    "维护服务合同",

    # 常见劳动合同
    "劳动合同",
    "劳务合同",

    # 常见租赁合同
    "房屋租赁合同",
    "设备租赁合同",
]

# 合同类型映射
PRIMARY_TYPE_MAPPING = {
    # 买卖合同
    "采购": "买卖合同",
    "买卖": "买卖合同",
    "购销": "买卖合同",
    "销售": "买卖合同",
    "供货": "买卖合同",

    # 建设工程合同
    "建设": "建设工程合同",
    "工程": "建设工程合同",
    "施工": "建设工程合同",
    "安装": "建设工程合同",

    # 承揽合同
    "承揽": "承揽合同",
    "加工": "承揽合同",
    "定制": "承揽合同",

    # 技术转让合同
    "技术": "技术转让合同",
    "专利": "技术转让合同",
    "软件": "技术转让合同",

    # 租赁合同
    "租赁": "租赁合同",
    "融资租赁": "租赁合同",

    # 借款合同
    "借款": "借款合同",
    "借贷": "借款合同",

    # 劳动合同
    "劳动": "劳动合同",
    "劳务": "劳动合同",

    # 委托合同
    "委托": "委托合同",
    "代理": "委托合同",
    "中介": "委托合同",

    # 服务合同
    "服务": "服务合同",
    "咨询": "服务合同",
    "维护": "服务合同",

    # 合作协议
    "合作": "合作协议",
    "合资": "合作协议",
    "联营": "合作协议",
}


def infer_primary_contract_type(template: ContractTemplate) -> str:
    """
    根据模板名称和类别推断主合同类型

    Args:
        template: 模板对象

    Returns:
        str: 主合同类型
    """
    name = template.name or ""
    category = template.category or ""
    text = f"{name} {category}"

    # 遍历映射表
    for keyword, contract_type in PRIMARY_TYPE_MAPPING.items():
        if keyword in text:
            return contract_type

    # 默认返回买卖合同
    return "买卖合同"


def infer_delivery_model(template: ContractTemplate) -> str:
    """
    根据模板类型推断交付模型

    Args:
        template: 模板对象

    Returns:
        str: 交付模型
    """
    name = template.name or ""
    category = template.category or ""
    text = f"{name} {category}"

    # 持续交付
    if any(keyword in text for keyword in ["租赁", "劳动", "劳务", "服务", "维护", "运营"]):
        return "持续交付"

    # 分期交付
    if any(keyword in text for keyword in ["建设", "工程", "施工", "分期"]):
        return "分期交付"

    # 复合交付
    if any(keyword in text for keyword in ["设备", "安装", "供货", "施工"]):
        return "复合交付"

    # 默认单一交付
    return "单一交付"


def infer_risk_level(template: ContractTemplate) -> str:
    """
    根据模板类型推断风险等级

    Args:
        template: 模板对象

    Returns:
        str: 风险等级
    """
    name = template.name or ""
    category = template.category or ""
    text = f"{name} {category}"

    # 高风险
    if any(keyword in text for keyword in ["劳动", "建设", "工程", "股权", "投资"]):
        return "high"

    # 中风险
    if any(keyword in text for keyword in ["合作", "合资", "技术", "专利"]):
        return "mid"

    # 默认低风险
    return "low"


def infer_is_recommended(template: ContractTemplate) -> bool:
    """
    判断是否为推荐模板

    Args:
        template: 模板对象

    Returns:
        bool: 是否推荐
    """
    name = template.name or ""

    # 检查是否在推荐列表中
    for recommended_name in RECOMMENDED_TEMPLATES:
        if recommended_name in name:
            return True

    return False


def update_templates(db: Session):
    """
    更新所有模板的结构锚点字段

    Args:
        db: 数据库会话
    """
    logger.info("[Update] 开始更新合同模板的结构锚点字段")

    # 获取所有模板
    templates = db.query(ContractTemplate).all()
    logger.info(f"[Update] 找到 {len(templates)} 个模板")

    updated_count = 0
    for template in templates:
        # 只有当字段为空时才更新
        needs_update = False

        if not template.primary_contract_type:
            template.primary_contract_type = infer_primary_contract_type(template)
            needs_update = True

        if not template.delivery_model:
            template.delivery_model = infer_delivery_model(template)
            needs_update = True

        if not template.risk_level:
            template.risk_level = infer_risk_level(template)
            needs_update = True

        if template.is_recommended is None or template.is_recommended is False:
            template.is_recommended = infer_is_recommended(template)
            needs_update = True

        if needs_update:
            updated_count += 1
            logger.info(
                f"[Update] 更新模板: {template.name} "
                f"(type={template.primary_contract_type}, "
                f"delivery={template.delivery_model}, "
                f"risk={template.risk_level}, "
                f"recommended={template.is_recommended})"
            )

    # 提交更改
    db.commit()

    logger.info(f"[Update] 完成！共更新 {updated_count}/{len(templates)} 个模板")


def main():
    """主函数"""
    logger.info("[Update] 开始执行模板更新脚本")

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 更新模板
        update_templates(db)

        logger.info("[Update] 模板更新成功完成")

    except Exception as e:
        logger.error(f"[Update] 模板更新失败: {str(e)}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
