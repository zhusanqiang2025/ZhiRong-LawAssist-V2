# backend/app/services/legal_features/category_feature_mapping.py
"""
合同分类与法律特征映射配置系统

建立分类标签（category）与V2四维法律特征之间的映射关系。
支持：
1. 通过分类快速定位对应法律特征
2. 通过用户需求提取特征，反向推荐分类
3. 分类-特征双重验证，提高检索准确率
"""
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================

class TransactionNature(str, Enum):
    """交易性质"""
    ASSET_TRANSFER = "转移所有权"
    SERVICE_DELIVERY = "提供服务"
    AUTHORIZATION = "许可使用"
    ENTITY_CREATION = "合作经营"
    CAPITAL_FINANCE = "融资借贷"
    LABOR_EMPLOYMENT = "劳动用工"
    DISPUTE_RESOLUTION = "争议解决"


class ContractObject(str, Enum):
    """合同标的"""
    TANGIBLE_GOODS = "货物"
    PROJECT = "工程"
    IP = "智力成果"
    SERVICE = "服务"
    EQUITY = "股权"
    MONETARY_DEBT = "资金"
    HUMAN_LABOR = "劳动力"
    REAL_ESTATE = "不动产"


class Complexity(str, Enum):
    """复杂程度"""
    SIMPLE = "简单"
    STANDARD = "中等"
    COMPLEX = "复杂"


class Stance(str, Enum):
    """起草立场"""
    BUYER_FRIENDLY = "甲方"
    SELLER_FRIENDLY = "乙方"
    NEUTRAL = "中立"
    BALANCED = "平衡"


# ==================== 数据结构 ====================

@dataclass
class V2Features:
    """V2四维法律特征"""
    transaction_nature: TransactionNature
    contract_object: ContractObject
    complexity: Complexity
    stance: Stance

    # 置信度（用于多模板情况）
    confidence: float = 1.0

    # 备选值（可选，用于多种特征）
    alternative_natures: List[TransactionNature] = field(default_factory=list)
    alternative_objects: List[ContractObject] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "transaction_nature": self.transaction_nature.value,
            "contract_object": self.contract_object.value,
            "complexity": self.complexity.value,
            "stance": self.stance.value,
            "confidence": self.confidence,
            "alternatives": {
                "transaction_natures": [n.value for n in self.alternative_natures],
                "contract_objects": [o.value for o in self.alternative_objects]
            }
        }


@dataclass
class CategoryFeatureMapping:
    """分类-特征映射"""
    # 分类信息
    category: str  # 一级分类：如"买卖合同"
    subcategory: Optional[str] = None  # 二级分类：如"设备买卖"

    # V2特征（核心）
    v2_features: V2Features = None

    # 结构锚点（V1特征）
    primary_contract_type: str = ""
    secondary_types: List[str] = field(default_factory=list)
    delivery_model: str = "单一交付"
    payment_model: str = "一次性付款"

    # 行业与场景
    industry_tags: List[str] = field(default_factory=list)
    usage_scenario: str = ""

    # 检索关键词（用于用户输入匹配）
    keywords: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)  # 别名

    # 特殊说明
    notes: str = ""

    def __post_init__(self):
        """自动填充默认值"""
        if self.v2_features is None:
            self.v2_features = V2Features(
                transaction_nature=TransactionNature.SERVICE_DELIVERY,
                contract_object=ContractObject.SERVICE,
                complexity=Complexity.STANDARD,
                stance=Stance.NEUTRAL
            )

        if not self.primary_contract_type:
            self.primary_contract_type = self.category


# ==================== 映射配置库 ====================

class CategoryFeatureLibrary:
    """
    分类-特征映射库

    维护合同分类与法律特征的映射关系。
    每个分类对应一组V2特征，支持快速查找和推荐。
    """

    def __init__(self):
        self._mappings: Dict[str, CategoryFeatureMapping] = {}
        self._initialize_default_mappings()

    def _initialize_default_mappings(self):
        """初始化默认映射关系"""

        # ========== 买卖合同 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="买卖合同",
            subcategory="货物买卖",
            v2_features=V2Features(
                transaction_nature=TransactionNature.ASSET_TRANSFER,
                contract_object=ContractObject.TANGIBLE_GOODS,
                complexity=Complexity.STANDARD,
                stance=Stance.BALANCED
            ),
            primary_contract_type="买卖合同",
            delivery_model="单一交付",
            payment_model="一次性付款",
            industry_tags=["制造业", "贸易", "零售"],
            keywords=["买", "卖", "购销", "销售", "采购", "供货", "货物"],
            aliases=["购销合同", "销售合同", "采购合同", "供货合同"],
            usage_scenario="适用于货物所有权转移的交易"
        ))

        self.add_mapping(CategoryFeatureMapping(
            category="买卖合同",
            subcategory="设备买卖",
            v2_features=V2Features(
                transaction_nature=TransactionNature.ASSET_TRANSFER,
                contract_object=ContractObject.TANGIBLE_GOODS,
                complexity=Complexity.COMPLEX,
                stance=Stance.BUYER_FRIENDLY,
                alternative_objects=[ContractObject.PROJECT]  # 可能涉及安装
            ),
            primary_contract_type="买卖合同",
            secondary_types=["承揽合同"],
            delivery_model="复合交付",  # 设备+安装
            payment_model="分期付款",
            industry_tags=["制造业", "设备", "工程"],
            keywords=["设备", "机械", "机器", "采购", "购买"],
            aliases=["设备采购合同", "设备供货合同"],
            usage_scenario="适用于设备采购及可能的安装调试"
        ))

        self.add_mapping(CategoryFeatureMapping(
            category="买卖合同",
            subcategory="房屋买卖",
            v2_features=V2Features(
                transaction_nature=TransactionNature.ASSET_TRANSFER,
                contract_object=ContractObject.REAL_ESTATE,
                complexity=Complexity.COMPLEX,
                stance=Stance.BALANCED
            ),
            primary_contract_type="买卖合同",
            delivery_model="单一交付",
            payment_model="分期付款",
            industry_tags=["房地产", "建筑"],
            keywords=["房子", "房产", "房屋", "不动产", "二手房", "商品房"],
            aliases=["房屋买卖合同", "房产买卖合同", "二手房买卖合同"],
            usage_scenario="适用于房屋所有权转让，包括一手房和二手房"
        ))

        # ========== 建设工程合同 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="建设工程合同",
            subcategory="工程施工",
            v2_features=V2Features(
                transaction_nature=TransactionNature.SERVICE_DELIVERY,
                contract_object=ContractObject.PROJECT,
                complexity=Complexity.COMPLEX,
                stance=Stance.BUYER_FRIENDLY
            ),
            primary_contract_type="建设工程合同",
            delivery_model="持续交付",
            payment_model="定期结算",
            industry_tags=["建筑", "工程", "施工"],
            keywords=["施工", "建设", "工程", "建筑", "装修"],
            aliases=["施工合同", "工程合同", "建筑合同"],
            usage_scenario="适用于各类工程施工、建设活动"
        ))

        # ========== 租赁合同 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="租赁合同",
            subcategory="房屋租赁",
            v2_features=V2Features(
                transaction_nature=TransactionNature.AUTHORIZATION,
                contract_object=ContractObject.REAL_ESTATE,
                complexity=Complexity.STANDARD,
                stance=Stance.BALANCED
            ),
            primary_contract_type="租赁合同",
            delivery_model="持续交付",
            payment_model="定期结算",
            industry_tags=["房地产", "租赁"],
            keywords=["租", "租赁", "出租", "承租", "房屋", "租房"],
            aliases=["租房合同", "房屋租赁合同", "商铺租赁"],
            usage_scenario="适用于房屋、商铺等不动产租赁"
        ))

        self.add_mapping(CategoryFeatureMapping(
            category="租赁合同",
            subcategory="设备租赁",
            v2_features=V2Features(
                transaction_nature=TransactionNature.AUTHORIZATION,
                contract_object=ContractObject.TANGIBLE_GOODS,
                complexity=Complexity.STANDARD,
                stance=Stance.NEUTRAL
            ),
            primary_contract_type="租赁合同",
            delivery_model="持续交付",
            payment_model="定期结算",
            industry_tags=["设备租赁", "机械"],
            keywords=["设备租赁", "机械租赁", "出租"],
            usage_scenario="适用于设备、机械等动产租赁"
        ))

        # ========== 借款合同 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="借款合同",
            subcategory=None,
            v2_features=V2Features(
                transaction_nature=TransactionNature.CAPITAL_FINANCE,
                contract_object=ContractObject.MONETARY_DEBT,
                complexity=Complexity.STANDARD,
                stance=Stance.SELLER_FRIENDLY  # 出借人优势
            ),
            primary_contract_type="借款合同",
            delivery_model="单一交付",
            payment_model="分期付款",
            industry_tags=["金融", "借贷"],
            keywords=["借款", "贷款", "借钱", "借入", "借出", "利息"],
            aliases=["贷款合同", "借贷合同", "借款协议"],
            usage_scenario="适用于民间借贷、金融借款等资金借贷行为"
        ))

        # ========== 劳动合同 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="劳动合同",
            subcategory=None,
            v2_features=V2Features(
                transaction_nature=TransactionNature.LABOR_EMPLOYMENT,
                contract_object=ContractObject.HUMAN_LABOR,
                complexity=Complexity.STANDARD,
                stance=Stance.BALANCED
            ),
            primary_contract_type="劳动合同",
            delivery_model="持续交付",
            payment_model="定期结算",
            industry_tags=["人力资源", "劳务"],
            keywords=["劳动", "用工", "雇佣", "员工", "入职"],
            aliases=["劳务合同", "雇佣合同", "用工协议"],
            usage_scenario="适用于建立劳动关系"
        ))

        # ========== 技术合同 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="技术合同",
            subcategory="技术开发",
            v2_features=V2Features(
                transaction_nature=TransactionNature.SERVICE_DELIVERY,
                contract_object=ContractObject.IP,
                complexity=Complexity.COMPLEX,
                stance=Stance.BUYER_FRIENDLY
            ),
            primary_contract_type="技术开发合同",
            secondary_types=["承揽合同"],
            delivery_model="分期交付",
            payment_model="分期付款",
            industry_tags=["科技", "研发", "技术服务"],
            keywords=["技术开发", "研发", "软件开发", "系统开发"],
            aliases=["软件开发合同", "研发合同"],
            usage_scenario="适用于委托开发技术成果、软件等"
        ))

        self.add_mapping(CategoryFeatureMapping(
            category="技术合同",
            subcategory="技术转让",
            v2_features=V2Features(
                transaction_nature=TransactionNature.ASSET_TRANSFER,
                contract_object=ContractObject.IP,
                complexity=Complexity.COMPLEX,
                stance=Stance.BALANCED
            ),
            primary_contract_type="技术转让合同",
            delivery_model="单一交付",
            payment_model="分期付款",
            industry_tags=["科技", "知识产权"],
            keywords=["技术转让", "专利转让", "技术许可"],
            aliases=["专利转让合同", "技术许可合同"],
            usage_scenario="适用于技术成果、专利等知识产权转让"
        ))

        # ========== 承揽合同 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="承揽合同",
            subcategory=None,
            v2_features=V2Features(
                transaction_nature=TransactionNature.SERVICE_DELIVERY,
                contract_object=ContractObject.TANGIBLE_GOODS,
                complexity=Complexity.STANDARD,
                stance=Stance.BUYER_FRIENDLY
            ),
            primary_contract_type="承揽合同",
            delivery_model="单一交付",
            payment_model="分期付款",
            industry_tags=["加工", "制造", "定制"],
            keywords=["承揽", "加工", "定做", "定制"],
            aliases=["加工承揽合同", "定作合同"],
            usage_scenario="适用于加工、定作、修缮等承揽业务"
        ))

        # ========== 委托合同 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="委托合同",
            subcategory=None,
            v2_features=V2Features(
                transaction_nature=TransactionNature.SERVICE_DELIVERY,
                contract_object=ContractObject.SERVICE,
                complexity=Complexity.STANDARD,
                stance=Stance.NEUTRAL
            ),
            primary_contract_type="委托合同",
            delivery_model="持续交付",
            payment_model="一次性付款",
            industry_tags=["服务", "代理"],
            keywords=["委托", "代理", "代办"],
            aliases=["代理合同", "代办合同"],
            usage_scenario="适用于委托他人处理事务"
        ))

        # ========== 合作协议 ==========
        self.add_mapping(CategoryFeatureMapping(
            category="合作协议",
            subcategory="合资合作",
            v2_features=V2Features(
                transaction_nature=TransactionNature.ENTITY_CREATION,
                contract_object=ContractObject.EQUITY,
                complexity=Complexity.COMPLEX,
                stance=Stance.BALANCED
            ),
            primary_contract_type="合作协议",
            delivery_model="持续交付",
            payment_model="混合模式",
            industry_tags=["投资", "创业", "商业"],
            keywords=["合资", "合作", "合伙", "联营"],
            aliases=["合资合同", "合伙协议", "联营协议"],
            usage_scenario="适用于多方共同投资、合作经营"
        ))

        logger.info(f"[CategoryFeatureLibrary] 初始化完成，共加载 {len(self._mappings)} 个分类-特征映射")

    def add_mapping(self, mapping: CategoryFeatureMapping):
        """添加映射关系"""
        key = self._get_mapping_key(mapping.category, mapping.subcategory)
        self._mappings[key] = mapping

    def get_mapping(self, category: str, subcategory: Optional[str] = None) -> Optional[CategoryFeatureMapping]:
        """获取映射关系"""
        # 先尝试精确匹配（含子分类）
        key = self._get_mapping_key(category, subcategory)
        if key in self._mappings:
            return self._mappings[key]

        # 再尝试只匹配一级分类
        key = self._get_mapping_key(category, None)
        return self._mappings.get(key)

    def search_by_keywords(self, query: str) -> List[CategoryFeatureMapping]:
        """根据关键词搜索映射"""
        query_lower = query.lower()
        results = []

        for mapping in self._mappings.values():
            # 检查分类名称
            if mapping.category.lower() in query_lower:
                results.append((mapping, 10))  # 高权重
                continue

            if mapping.subcategory and mapping.subcategory.lower() in query_lower:
                results.append((mapping, 10))
                continue

            # 检查关键词
            keyword_score = 0
            for keyword in mapping.keywords:
                if keyword.lower() in query_lower:
                    keyword_score += 3

            # 检查别名
            for alias in mapping.aliases:
                if alias.lower() in query_lower:
                    keyword_score += 5

            if keyword_score > 0:
                results.append((mapping, keyword_score))

        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [m for m, s in results]

    def search_by_features(
        self,
        transaction_nature: Optional[str] = None,
        contract_object: Optional[str] = None,
        complexity: Optional[str] = None,
        stance: Optional[str] = None
    ) -> List[CategoryFeatureMapping]:
        """
        根据V2特征反向搜索分类

        当通过LLM提取到用户需求的特征后，可以反向推荐合适的分类。
        """
        results = []

        for mapping in self._mappings.values():
            score = 0
            features = mapping.v2_features

            # 交易性质匹配
            if transaction_nature:
                if features.transaction_nature.value == transaction_nature:
                    score += 4
                elif transaction_nature in [n.value for n in features.alternative_natures]:
                    score += 2

            # 标的匹配
            if contract_object:
                if features.contract_object.value == contract_object:
                    score += 3
                elif contract_object in [o.value for o in features.alternative_objects]:
                    score += 1

            # 复杂度匹配
            if complexity and features.complexity.value == complexity:
                score += 1

            # 立场匹配
            if stance and features.stance.value == stance:
                score += 1

            if score > 0:
                results.append((mapping, score))

        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [m for m, s in results]

    def get_all_categories(self) -> List[str]:
        """获取所有一级分类"""
        categories = set()
        for mapping in self._mappings.values():
            categories.add(mapping.category)
        return sorted(list(categories))

    def get_subcategories(self, category: str) -> List[str]:
        """获取指定分类的所有子分类"""
        subcategories = []
        for mapping in self._mappings.values():
            if mapping.category == category and mapping.subcategory:
                subcategories.append(mapping.subcategory)
        return sorted(list(set(subcategories)))

    def _get_mapping_key(self, category: str, subcategory: Optional[str] = None) -> str:
        """生成映射键"""
        if subcategory:
            return f"{category}::{subcategory}"
        return f"{category}::"


# ==================== 单例模式 ====================

_library_instance: Optional[CategoryFeatureLibrary] = None


def get_category_feature_library() -> CategoryFeatureLibrary:
    """获取分类-特征映射库单例"""
    global _library_instance
    if _library_instance is None:
        _library_instance = CategoryFeatureLibrary()
    return _library_instance
