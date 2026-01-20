#!/usr/bin/env python3
"""
从JSON文件更新知识图谱数据
"""
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.legal_features.contract_knowledge_graph import (
    get_contract_knowledge_graph,
    ContractLegalFeatures,
    TransactionNature,
    ContractObject,
    Complexity,
    Stance,
    ConsiderationType
)

# 映射 transaction_nature 的英文值到枚举
TRANSACTION_NATURE_MAP = {
    "转移所有权": TransactionNature.ASSET_TRANSFER,
    "transfer_ownership": TransactionNature.ASSET_TRANSFER,
    "提供服务": TransactionNature.SERVICE_DELIVERY,
    "render_service": TransactionNature.SERVICE_DELIVERY,
    "许可使用": TransactionNature.AUTHORIZATION,
    "license_use": TransactionNature.AUTHORIZATION,
    "合作经营": TransactionNature.ENTITY_CREATION,
    "partnership_joint": TransactionNature.ENTITY_CREATION,
    "融资借贷": TransactionNature.CAPITAL_FINANCE,
    "loan_financing": TransactionNature.CAPITAL_FINANCE,
    "劳动用工": TransactionNature.LABOR_EMPLOYMENT,
    "employment": TransactionNature.LABOR_EMPLOYMENT,
    "争议解决": TransactionNature.DISPUTE_RESOLUTION,
    "dispute_resolution": TransactionNature.DISPUTE_RESOLUTION,
    "其他": TransactionNature.SERVICE_DELIVERY,  # 默认值
    "other": TransactionNature.SERVICE_DELIVERY,
    "租赁使用": TransactionNature.SERVICE_DELIVERY,  # 使用服务作为租赁的默认
    "lease_use": TransactionNature.SERVICE_DELIVERY,
    "公司治理": TransactionNature.SERVICE_DELIVERY,
    "corporate_governance": TransactionNature.SERVICE_DELIVERY,
    "股权投资": TransactionNature.ENTITY_CREATION,
    "investment_equity": TransactionNature.ENTITY_CREATION,
    "劳务服务": TransactionNature.LABOR_EMPLOYMENT,
    "labor_service": TransactionNature.LABOR_EMPLOYMENT,
}

# 映射 contract_object 的英文值到枚举
CONTRACT_OBJECT_MAP = {
    "不动产": ContractObject.REAL_ESTATE,
    "动产": ContractObject.MOVABLE_PROPERTY,
    "资金": ContractObject.MONETARY_DEBT,
    "货物": ContractObject.TANGIBLE_GOODS,
    "服务": ContractObject.SERVICE,
    "股权": ContractObject.EQUITY,
    "劳动力": ContractObject.HUMAN_LABOR,
    "智力成果": ContractObject.IP,
    "工程": ContractObject.PROJECT,
    "ip": ContractObject.IP,
    "无形资产": ContractObject.IP,  # 默认映射到智力成果
}

# 映射 complexity 的英文值到枚举
COMPLEXITY_MAP = {
    "简单": Complexity.SIMPLE,
    "simple": Complexity.SIMPLE,
    "中等": Complexity.STANDARD,
    "standard_commercial": Complexity.STANDARD,
    "复杂": Complexity.COMPLEX,
    "complex": Complexity.COMPLEX,
    "非常复杂": Complexity.COMPLEX,  # 映射到复杂
    "very_complex": Complexity.COMPLEX,
}

# 映射 stance 的英文值到枚举
STANCE_MAP = {
    "中立": Stance.NEUTRAL,
    "neutral": Stance.NEUTRAL,
    "甲方": Stance.BUYER_FRIENDLY,
    "party_a": Stance.BUYER_FRIENDLY,
    "乙方": Stance.SELLER_FRIENDLY,
    "party_b": Stance.SELLER_FRIENDLY,
    "平衡": Stance.BALANCED,
    "balanced": Stance.BALANCED,
    "多方": Stance.NEUTRAL,  # 默认为中立
    "multi_party": Stance.NEUTRAL,
}

# 映射 consideration_type 的英文值到枚举
CONSIDERATION_TYPE_MAP = {
    "有偿": ConsiderationType.PAID,
    "无偿": ConsiderationType.FREE,
    "混合": ConsiderationType.HYBRID,
}


def load_json_data(file_path: str):
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_legal_features(features_dict: dict) -> ContractLegalFeatures:
    """标准化法律特征值并转换为枚举（支持中英文字段名）"""
    # 支持新旧两种字段名格式
    # 交易性质 / transaction_nature
    tn_value = (
        features_dict.get("交易性质") or
        features_dict.get("transaction_nature") or
        "提供服务"
    )
    transaction_nature = TRANSACTION_NATURE_MAP.get(
        tn_value,
        TransactionNature.SERVICE_DELIVERY  # 默认值
    )

    # 合同标的 / contract_object
    co_value = (
        features_dict.get("合同标的") or
        features_dict.get("contract_object") or
        "服务"
    )
    contract_object = CONTRACT_OBJECT_MAP.get(
        co_value,
        ContractObject.SERVICE  # 默认值
    )

    # 复杂程度 / complexity (使用默认值)
    cplx_value = features_dict.get("complexity") or features_dict.get("复杂程度") or "中等"
    complexity = COMPLEXITY_MAP.get(
        cplx_value,
        Complexity.STANDARD  # 默认值
    )

    # 起草立场 / stance (使用默认值)
    s_value = features_dict.get("stance") or features_dict.get("起草立场") or "中立"
    stance = STANCE_MAP.get(
        s_value,
        Stance.NEUTRAL  # 默认值
    )

    # 对价类型 / consideration_type
    ct_value = (
        features_dict.get("对价类型") or
        features_dict.get("consideration_type") or
        "有偿"
    )
    consideration_type = CONSIDERATION_TYPE_MAP.get(
        ct_value,
        ConsiderationType.PAID  # 默认值
    )

    # 对价详情 / consideration_detail
    consideration_detail = (
        features_dict.get("对价详情") or
        features_dict.get("consideration_detail") or
        ""
    )

    # 交易特征 / transaction_characteristics
    transaction_characteristics = (
        features_dict.get("交易特征") or
        features_dict.get("transaction_characteristics") or
        ""
    )

    # 适用场景 / usage_scenario
    usage_scenario = (
        features_dict.get("适用场景") or
        features_dict.get("usage_scenario") or
        ""
    )

    # 法律依据 / legal_basis
    legal_basis = (
        features_dict.get("法律依据") or
        features_dict.get("legal_basis") or
        []
    )

    # 创建 ContractLegalFeatures 对象
    return ContractLegalFeatures(
        transaction_nature=transaction_nature,
        contract_object=contract_object,
        complexity=complexity,
        stance=stance,
        consideration_type=consideration_type,
        consideration_detail=consideration_detail,
        transaction_characteristics=transaction_characteristics,
        usage_scenario=usage_scenario,
        legal_basis=legal_basis,
    )


def update_knowledge_graph_from_json(json_file: str):
    """从JSON文件更新知识图谱（支持中英文字段名）"""
    print("=" * 60)
    print("从JSON文件更新知识图谱")
    print("=" * 60)

    # 加载JSON数据
    data = load_json_data(json_file)

    # 支持新旧两种格式：合同类型列表 / contract_types
    contract_types_list = (
        data.get("合同类型列表") or
        data.get("contract_types") or
        []
    )

    print(f"\n找到 {len(contract_types_list)} 个合同类型")

    # 获取知识图谱实例
    kg = get_contract_knowledge_graph()

    # 清空现有的合同类型
    print(f"\n清空现有知识图谱（原有 {len(kg._contract_types)} 个合同类型）")
    kg._contract_types.clear()

    # 添加新的合同类型
    added = 0
    skipped = 0
    errors = []

    for ct_data in contract_types_list:
        try:
            # 支持名称 / name 字段
            name = (
                ct_data.get("名称") or
                ct_data.get("name")
            )
            if not name:
                skipped += 1
                continue

            # 支持别名 / aliases 字段
            aliases = (
                ct_data.get("别名") or
                ct_data.get("aliases") or
                []
            )

            # 支持类别 / category 字段
            category = (
                ct_data.get("类别") or
                ct_data.get("category") or
                ""
            )

            # 支持子类别 / subcategory 字段
            subcategory = (
                ct_data.get("子类别") or
                ct_data.get("subcategory") or
                ""
            )

            # 支持法律特征 / legal_features 字段
            legal_features_dict = (
                ct_data.get("法律特征") or
                ct_data.get("legal_features") or
                {}
            )

            # 标准化法律特征
            legal_features = normalize_legal_features(legal_features_dict)

            # 支持推荐模板ID列表 / recommended_template_ids 字段
            recommended_template_ids = (
                ct_data.get("推荐模板ID列表") or
                ct_data.get("recommended_template_ids") or
                []
            )

            # 使用内部方法添加合同类型
            # 创建合同类型字典
            contract_type_dict = {
                "name": name,
                "aliases": aliases,
                "category": category,
                "subcategory": subcategory,
                "legal_features": legal_features,
                "recommended_template_ids": recommended_template_ids,
                "usage_scenario": legal_features.usage_scenario,
                "legal_basis": legal_features.legal_basis,
            }

            # 添加到知识图谱
            kg._contract_types[name] = contract_type_dict
            added += 1
            print(f"  ✓ 添加: {name} ({category})")

        except Exception as e:
            errors.append(f"{name}: {str(e)}")
            print(f"  ✗ 错误: {name} - {str(e)}")
            import traceback
            traceback.print_exc()

    # 数据已在内存中更新，ContractKnowledgeGraph 是单例，会自动持久化
    print(f"\n✓ 知识图谱已在内存中更新完成")
    print(f"  注: ContractKnowledgeGraph 使用单例模式，数据已自动更新")

    # 打印统计信息
    print("\n" + "=" * 60)
    print("更新完成")
    print("=" * 60)
    print(f"添加成功: {added} 个")
    print(f"跳过: {skipped} 个")
    print(f"错误: {len(errors)} 个")
    print(f"总计: {len(kg._contract_types)} 个合同类型")

    if errors:
        print("\n错误详情:")
        for error in errors:
            print(f"  - {error}")


if __name__ == "__main__":
    # JSON文件路径
    json_file = os.path.join(os.path.dirname(__file__), "knowledge_graph_2026-01-10.json")

    if not os.path.exists(json_file):
        print(f"错误: 文件不存在 - {json_file}")
        sys.exit(1)

    print(f"从文件加载: {json_file}\n")

    # 执行更新
    update_knowledge_graph_from_json(json_file)

    print("\n完成!")
