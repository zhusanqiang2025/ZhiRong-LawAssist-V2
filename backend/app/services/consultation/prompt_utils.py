from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from app.models.category import Category
import logging

logger = logging.getLogger(__name__)


def get_category_reference_table(db: Session) -> str:
    """
    从数据库加载知识分类参考表
    用于律师助理节点 Prompt
    """
    try:
        categories = db.query(Category).filter(Category.is_active == True, Category.parent_id == None).all()

        if not categories:
            # Fallback to default if DB is empty
            return _get_default_reference_table()

        # Build table header
        table = "| 用户问题关键词 | 法律领域 |\n"
        table += "|--------------|----------|\n"

        for cat in categories:
            # Get keywords from description or meta_info
            keywords = []
            if cat.meta_info and "keywords" in cat.meta_info:
                keywords = cat.meta_info["keywords"]
            elif cat.description:
                # Simple extraction or usage of description
                keywords = [cat.description[:20]]
            else:
                keywords = [cat.name]

            keywords_str = "、".join(keywords)
            table += f"| {keywords_str} | {cat.name} |\n"

        return table
    except Exception as e:
        logger.error(f"[PromptUtils] Failed to load categories: {e}")
        return _get_default_reference_table()


def get_rag_strategy(db: Session, category_name: str) -> Dict[str, Any]:
    """
    获取指定分类的 RAG 策略配置
    """
    try:
        category = db.query(Category).filter(Category.name == category_name).first()
        if category and category.meta_info:
            return category.meta_info.get("rag_config", {})
    except Exception as e:
        logger.error(f"[PromptUtils] Failed to get RAG strategy: {e}")
    return {}


def _get_default_reference_table() -> str:
    """默认参考表（硬编码备份）"""
    return """| 用户问题关键词 | 法律领域 |
|--------------|----------|
| 交通事故、人身损害、财产损害、医疗纠纷 | 侵权责任法 |
| 工资拖欠、违法解除、工伤赔偿 | 劳动法 |
| 违约、欠款、借款、租赁、买卖 | 合同法 |
| 股权、股东、公司治理 | 公司法 |
| 离婚、抚养权、赡养费、财产分割 | 婚姻家庭法 |
| 工程款、施工、质量纠纷 | 建设工程 |
| 刑事案件、辩护、取保候审 | 刑法 |
| 罚款、拘留、行政复议 | 行政法 |"""
