import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

# 【数据库版本】引入知识图谱服务 - 使用数据库而非JSON文件
from app.services.common.contract_knowledge_db_service import contract_knowledge_db_service as kg_service
from app.database import SessionLocal
from app.models.rule import ReviewRule  # ✅ 从 contract.py 移动到独立的 rule.py

logger = logging.getLogger(__name__)


class RuleAssembler:
    """
    规则组装器

    从数据库动态加载审查规则，支持：
    1. 通用规则 (universal)
    2. 特征规则 (feature) - 基于交易性质和合同标的
    3. 立场规则 (stance) - party_a/party_b
    4. 用户自定义规则 (custom)

    管理员在后台修改规则后，下一次审查立即生效
    """

    def __init__(self):
        """初始化规则组装器（不再缓存规则，每次从数据库读取）"""
        pass

    def _get_db_session(self) -> Session:
        """获取数据库会话"""
        return SessionLocal()

    def _get_universal_rules_from_db(self) -> List[ReviewRule]:
        """从数据库获取启用的通用规则"""
        db = self._get_db_session()
        try:
            rules = db.query(ReviewRule).filter(
                ReviewRule.rule_category == "universal",
                ReviewRule.is_system == True,
                ReviewRule.is_active == True
            ).order_by(ReviewRule.priority).all()
            logger.info(f"[RuleAssembler] 加载通用规则: {len(rules)} 条")
            return rules
        finally:
            db.close()

    def _get_feature_rules_from_db(self, feature_type: str, feature_value: str) -> List[ReviewRule]:
        """
        从数据库获取特征规则

        Args:
            feature_type: 特征类型（交易性质/合同标的）- 用于日志
            feature_value: 特征值（如：转移所有权/不动产）

        Returns:
            匹配的特征规则列表
        """
        db = self._get_db_session()
        try:
            # 规则名称格式: [特征值] 关注点
            pattern = f"[{feature_value}]"
            rules = db.query(ReviewRule).filter(
                ReviewRule.name.like(f"{pattern}%"),
                ReviewRule.rule_category == "feature",
                ReviewRule.is_system == True,
                ReviewRule.is_active == True
            ).order_by(ReviewRule.priority).all()
            logger.info(f"[RuleAssembler] 加载特征规则 [{feature_type}]{feature_value}: {len(rules)} 条")
            return rules
        finally:
            db.close()

    def _get_stance_rules_from_db(self, party: str) -> List[ReviewRule]:
        """
        从数据库获取立场规则

        Args:
            party: 立场（party_a/party_b）

        Returns:
            匹配的立场规则列表
        """
        db = self._get_db_session()
        try:
            # 规则名称格式: [立场-party_a] 关注点
            pattern = f"[立场-{party}]"
            rules = db.query(ReviewRule).filter(
                ReviewRule.name.like(f"{pattern}%"),
                ReviewRule.rule_category == "stance",
                ReviewRule.is_system == True,
                ReviewRule.is_active == True
            ).order_by(ReviewRule.priority).all()
            logger.info(f"[RuleAssembler] 加载立场规则 [{party}]: {len(rules)} 条")
            return rules
        finally:
            db.close()

    def _get_user_custom_rules_from_db(self, user_id: int) -> List[ReviewRule]:
        """
        从数据库获取用户自定义规则

        Args:
            user_id: 用户ID

        Returns:
            用户的自定义规则列表
        """
        db = self._get_db_session()
        try:
            return db.query(ReviewRule).filter(
                ReviewRule.rule_category == "custom",
                ReviewRule.creator_id == user_id,
                ReviewRule.is_active == True
            ).order_by(ReviewRule.priority).all()
        finally:
            db.close()

    def _get_transaction_structure_rules_from_db(self, transaction_structures: List[str]) -> List[ReviewRule]:
        """
        从数据库获取交易结构规则

        ⚠️ 重要说明:
        - rule_category 必须严格等于 "transaction_structure"
        - 规则命名格式: "[交易结构-{structure_name}] {规则描述}"
        - 示例: "[交易结构-买卖] 需明确标的物交付标准"

        Args:
            transaction_structures: 用户选择的交易结构列表
                例如: ["买卖", "租赁", "承揽"]

        Returns:
            匹配的规则列表 (按优先级排序)
        """
        if not transaction_structures:
            return []

        db = self._get_db_session()
        try:
            rules = []

            # 对每个交易结构查找匹配的规则
            for ts in transaction_structures:
                # 匹配规则: name 包含 "[交易结构-{ts}]"
                pattern = f"[交易结构-{ts}]"
                matched_rules = db.query(ReviewRule).filter(
                    ReviewRule.name.like(f"{pattern}%"),
                    ReviewRule.rule_category == "transaction_structure",
                    ReviewRule.is_active == True
                ).order_by(ReviewRule.priority).all()

                if matched_rules:
                    rules.extend(matched_rules)
                    logger.info(f"[RuleAssembler] 交易结构 '{ts}' 匹配到 {len(matched_rules)} 条规则")

            return rules
        finally:
            db.close()

    def _infer_transaction_structures_from_kg(
        self,
        contract_type: str,
        legal_features: Dict
    ) -> List[str]:
        """
        ⭐ 新增: 从知识图谱智能推断交易结构

        智能映射逻辑:
        1. 根据 contract_type 查询知识图谱
        2. 提取 legal_features 中的关键字段
        3. 映射到交易结构标签

        Args:
            contract_type: 合同类型名称 (如 "劳动合同")
            legal_features: 法律特征字典

        Returns:
            推断的交易结构列表
            例如: ["劳动用工", "持续性服务", "人身依附性"]
        """
        if not contract_type:
            return []

        # 1️⃣ 查询知识图谱
        kg_data = kg_service.get_by_name(contract_type)
        if not kg_data:
            logger.warning(f"[RuleAssembler] 未找到合同类型 '{contract_type}' 的知识图谱数据")
            return []

        # 2️⃣ 提取特征
        features = kg_data.get("legal_features", {})

        # 3️⃣ 智能映射表 (特征值 → 交易结构)
        transaction_structures = []

        # 映射规则 1: 交易性质直接映射
        nature_mapping = {
            "转移所有权": "买卖",
            "提供服务": "服务",
            "许可使用": "许可",
            "租赁使用": "租赁",
            "借款融资": "借贷",
            "劳动用工": "劳动",
            "承揽": "承揽",
            "委托": "委托",
            "技术合作": "技术",
        }

        transaction_nature = features.get("transaction_nature")
        if transaction_nature:
            # 尝试精确匹配
            if transaction_nature in nature_mapping:
                ts = nature_mapping[transaction_nature]
                if ts not in transaction_structures:
                    transaction_structures.append(ts)
            else:
                # 如果没有精确匹配，直接使用原值
                if transaction_nature not in transaction_structures:
                    transaction_structures.append(transaction_nature)

        # 映射规则 2: 从交易特征中提取关键词
        characteristics = features.get("transaction_characteristics", "")
        if characteristics:
            # 关键词映射
            keyword_mapping = {
                "持续性": "持续性服务",
                "人身依附": "人身依附性",
                "分期": "分期履行",
                "预付款": "预付款",
                "交付": "交付验收",
                "保密": "保密义务",
                "知识产权": "知识产权",
                "竞业限制": "竞业限制",
            }

            for keyword, ts in keyword_mapping.items():
                if keyword in characteristics and ts not in transaction_structures:
                    transaction_structures.append(ts)

        # 映射规则 3: 从合同标的推断
        contract_object = features.get("contract_object")
        if contract_object:
            # 标的物通常对应特定的交易结构
            if contract_object not in transaction_structures:
                transaction_structures.append(contract_object)

        logger.info(
            f"[RuleAssembler] 从知识图谱推断交易结构: "
            f"合同类型={contract_type}, 推断结果={transaction_structures}"
        )

        return transaction_structures

    def _get_industry_rules_from_db(self, contract_type: str) -> List[ReviewRule]:
        """
        从数据库获取行业规则

        根据合同类型名称推断所属行业，加载对应的行业专项规则

        Args:
            contract_type: 合同类型名称 (如 "外商投资协议")

        Returns:
            匹配的行业规则列表
        """
        if not contract_type:
            return []

        # 行业关键词映射表
        industry_keywords = {
            "外商投资": ["外商投资", "外资", "中外合资"],
            "建筑工程": ["建筑", "工程", "施工", "装修"],
            "房地产": ["房地产", "房产", "土地", "商品房"],
            "金融": ["借款", "借贷", "贷款", "融资", "担保"],
            "劳动": ["劳动", "用工", "雇佣"],
            "医疗器械": ["医疗", "器械", "医院"],
            "教育": ["教育", "培训", "学校", "辅导"],
            "电商": ["电商", "平台", "网络购物"]
        }

        db = self._get_db_session()
        try:
            rules = []

            for industry, keywords in industry_keywords.items():
                if any(keyword in contract_type for keyword in keywords):
                    # 查询该行业的所有规则
                    pattern = f"[行业-{industry}]"
                    industry_rules = db.query(ReviewRule).filter(
                        ReviewRule.name.like(f"{pattern}%"),
                        ReviewRule.rule_category == "industry",
                        ReviewRule.is_system == True,
                        ReviewRule.is_active == True
                    ).order_by(ReviewRule.priority).all()

                    if industry_rules:
                        rules.extend(industry_rules)
                        logger.info(f"[RuleAssembler] 加载行业规则 [{industry}]: {len(industry_rules)} 条")

            return rules
        finally:
            db.close()

    def _get_feature_rules(self, legal_features: Dict) -> List[str]:
        """
        策略一：基于特征映射获取规则

        Args:
            legal_features: 法律特征字典，包含 transaction_nature, contract_object 等

        Returns:
            规则指令列表
        """
        rules = []

        # 1. 映射交易性质
        nature = legal_features.get("transaction_nature")
        if nature:
            feature_rules = self._get_feature_rules_from_db("交易性质", nature)
            for rule in feature_rules:
                rules.append(f"【交易性质-{nature}】{rule.content}")

        # 2. 映射合同标的
        obj = legal_features.get("contract_object")
        if obj:
            feature_rules = self._get_feature_rules_from_db("合同标的", obj)
            for rule in feature_rules:
                rules.append(f"【标的-{obj}】{rule.content}")

        return rules

    def _get_stance_rules(self, stance: str) -> List[str]:
        """
        获取立场防御规则

        Args:
            stance: 用户立场（如：甲方、乙方、买方、卖方等）

        Returns:
            立场规则指令列表
        """
        rules = []
        # 简单判断立场
        key = "party_a" if "甲" in stance or "买" in stance or "发包" in stance else "party_b"

        stance_rules = self._get_stance_rules_from_db(key)
        if stance_rules:
            # 从第一条规则中提取角色定义
            role_def = stance_rules[0].description.split("的")[0] if stance_rules[0].description else key
            rules.append(f"您的立场设定为：{stance} ({role_def})。请重点防范以下风险：")

            for rule in stance_rules:
                # 从 content 中提取关注点和指令
                rules.append(f"- {rule.content}")

        return rules

    def _get_dynamic_deduction_prompt(self, contract_type_name: str) -> List[str]:
        """
        策略二：动态推演

        查阅知识图谱（数据库），将合同定义转化为 AI 的推理指令

        Args:
            contract_type_name: 合同类型名称

        Returns:
            动态推演指令列表
        """
        if not contract_type_name:
            return []

        # 1. 查图谱（使用新的数据库服务）
        kg_data = kg_service.get_by_name(contract_type_name)
        if not kg_data:
            return []

        # 2. 提取核心定义（使用英文键名）
        features = kg_data.get("legal_features", {})

        # 3. 生成推演 Prompt
        deduction_lines = []
        deduction_lines.append(f"本合同被识别为标准类型：【{kg_data.get('name')}】")
        deduction_lines.append(f"• 交易特征：{features.get('transaction_characteristics', '未定义')}")
        deduction_lines.append(f"• 适用场景：{features.get('usage_scenario', '未定义')}")
        deduction_lines.append(f"• 核心法律依据：{', '.join(features.get('legal_basis', []))}")

        deduction_lines.append("\n**>>> 动态审查指令 (Dynamic Instruction) <<<**")
        deduction_lines.append("请基于上述「交易特征」和「适用场景」，运用你的法律专业知识，反向推导并审查以下风险点：")
        deduction_lines.append("1. 既然交易特征包含上述要素，合同是否遗漏了必要的履行环节？")
        deduction_lines.append("2. 针对该特定场景，是否存在常见的行业陷阱？")
        deduction_lines.append("3. 条款是否符合上述列出的法律依据？")

        return deduction_lines

    def assemble_prompt_context(
        self,
        legal_features: Dict,
        stance: str,
        user_custom_rules: List[str] = None,
        user_id: Optional[int] = None,
        transaction_structures: List[str] = None
    ) -> str:
        """
        核心方法：组装最终的审查指令集

        规则加载优先级 (从高到低):
        Priority 1: 用户自定义规则 (Custom)
        Priority 2: 行业规则 (Industry) ⭐ 新增
        Priority 3: 交易结构规则 (TransactionStructure) - 智能推断
        Priority 4: 立场规则 (Stance)
        Priority 5: 特征规则 (Feature)
        Priority 6: 通用规则 (Universal)
        Priority 7: 动态推演 (Knowledge Graph)

        Args:
            legal_features: 法律特征字典（包含 transaction_nature, contract_object, contract_type 等）
            stance: 审查立场（甲方/乙方）
            user_custom_rules: 用户自定义规则列表（可选，与 user_id 二选一）
            user_id: 用户ID（可选，用于从数据库加载用户的自定义规则）
            transaction_structures: 用户选择的交易结构列表 (可选，为空则自动推断)

        Returns:
            完整的审查指令集字符串
        """
        logger.info(f"[RuleAssembler] 开始组装审查指令集 - 合同类型: {legal_features.get('contract_type')}, 立场: {stance}, 用户指定交易结构: {transaction_structures}")

        # ========== ⭐ 智能推断交易结构 ==========
        # 如果用户未指定交易结构，则从知识图谱自动推断
        if not transaction_structures:
            contract_type = legal_features.get("contract_type")
            if contract_type:
                transaction_structures = self._infer_transaction_structures_from_kg(
                    contract_type=contract_type,
                    legal_features=legal_features
                )
                logger.info(f"[RuleAssembler] 智能推断交易结构: {transaction_structures}")

        final_instructions = []

        # ========== Priority 1: 用户自定义规则 (最高优先级) ==========
        if user_id:
            # 从数据库加载用户的自定义规则
            user_rules_from_db = self._get_user_custom_rules_from_db(user_id)
            if user_rules_from_db:
                final_instructions.append("### 1. 用户自定义审查规则 (User Custom Rules - 最高优先级)")
                for idx, rule in enumerate(user_rules_from_db, 1):
                    final_instructions.append(f"{idx}. [{rule.name}] {rule.content}")
                logger.info(f"[RuleAssembler] 加载用户自定义规则: {len(user_rules_from_db)} 条")

        # 或者使用传入的自定义规则列表（兼容旧接口）
        if user_custom_rules and len(user_custom_rules) > 0:
            if not user_id:  # 如果没有通过 user_id 加载，才使用传入的列表
                final_instructions.append("### 1. 用户特别关注点 (User Defined - 最高优先级)")
                for idx, rule in enumerate(user_custom_rules, 1):
                    final_instructions.append(f"{idx}. {rule}")

        # ========== ⭐ Priority 2: 行业规则 ==========
        contract_type = legal_features.get("contract_type")
        industry_rules = self._get_industry_rules_from_db(contract_type)
        if industry_rules:
            final_instructions.append("\n### 2. 行业专项规则 (Industry Specific)")
            for rule in industry_rules:
                final_instructions.append(f"- {rule.content}")
            logger.info(f"[RuleAssembler] 加载行业规则: {len(industry_rules)} 条")

        # ========== Priority 3: 交易结构规则 (智能推断) ==========
        if transaction_structures:
            ts_rules = self._get_transaction_structure_rules_from_db(transaction_structures)
            if ts_rules:
                final_instructions.append("\n### 3. 交易结构专项规则 (Transaction Structure Rules)")
                for rule in ts_rules:
                    final_instructions.append(f"- {rule.content}")
                logger.info(f"[RuleAssembler] 加载交易结构规则: {len(ts_rules)} 条")

        # ========== Priority 4: 立场规则 ==========
        stance_instructions = self._get_stance_rules(stance)
        if stance_instructions:
            final_instructions.append("\n### 4. 立场防御指南 (Stance Defense)")
            final_instructions.extend(stance_instructions)

        # ========== Priority 5: 特征规则 (策略一：基于交易性质和合同标的) ==========
        feature_instructions = self._get_feature_rules(legal_features)
        if feature_instructions:
            final_instructions.append("\n### 5. 业务特征专项审查 (Feature Specific)")
            final_instructions.extend([f"- {r}" for r in feature_instructions])

        # ========== Priority 6: 通用基础规则 ==========
        universal_rules = self._get_universal_rules_from_db()
        if universal_rules:
            final_instructions.append("\n### 6. 通用基础合规审查 (System Standard)")
            for rule in universal_rules:
                final_instructions.append(f"- {rule.content}")

        # ========== Priority 7: 动态推演 (策略二：基于知识图谱) ==========
        deduction_instructions = self._get_dynamic_deduction_prompt(contract_type)

        if deduction_instructions:
            final_instructions.append("\n### 7. 基于知识图谱的深度推演 (Knowledge Graph Deduction)")
            final_instructions.extend(deduction_instructions)

        result = "\n".join(final_instructions)
        logger.info(f"[RuleAssembler] 审查指令集组装完成 - 总规则数: {len(final_instructions)} 条")
        return result


# 单例模式
rule_assembler = RuleAssembler()
