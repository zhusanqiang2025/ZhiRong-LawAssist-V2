import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

# 引入数据库依赖
from app.database import SessionLocal
# 引入新模型
from app.models.rule import ReviewRule
from app.models.category import Category
# 引入知识图谱服务 (保留用于动态推演)
from app.services.common.contract_knowledge_db_service import contract_knowledge_db_service as kg_service

logger = logging.getLogger(__name__)

class RuleAssembler:
    """
    规则组装器 (v3.2 - Hub-and-Spoke ID关联版)

    核心逻辑变更：
    不再依赖规则名称的字符串匹配 (如 "[特征]...")，
    而是基于 Category ID 和 Stance 字段进行精确的数据库关联查询。
    """

    def __init__(self):
        pass

    def _get_db_session(self) -> Session:
        return SessionLocal()

    def _resolve_category_id(self, db: Session, contract_type_name: str) -> Optional[int]:
        """
        [内部辅助] 将合同类型名称解析为 Category ID
        """
        if not contract_type_name:
            return None
        
        # 1. 精确匹配
        category = db.query(Category).filter(Category.name == contract_type_name).first()
        if category:
            return category.id
            
        # 2. 尝试别名匹配或模糊匹配 (可根据需求扩展)
        # category = db.query(Category).filter(Category.aliases.contains(contract_type_name)).first()
        
        logger.warning(f"[RuleAssembler] 未能找到合同类型 '{contract_type_name}' 对应的 Category ID")
        return None

    def _get_system_rules(
        self, 
        db: Session, 
        category_id: Optional[int], 
        stance: Optional[str]
    ) -> Dict[str, List[ReviewRule]]:
        """
        一次性获取所有相关的系统级规则 (Universal + Feature + Stance)
        
        Args:
            db: 数据库会话
            category_id: 解析后的分类ID
            stance: 原始立场字符串 (如 "甲方", "buyer")

        Returns:
            分类好的规则字典
        """
        # 标准化立场 (简单的映射逻辑，需根据前端传值约定调整)
        target_stance = None
        if stance:
            if any(s in stance for s in ["甲", "买", "发包", "buyer"]):
                target_stance = "buyer"
            elif any(s in stance for s in ["乙", "卖", "承包", "seller"]):
                target_stance = "seller"
            else:
                target_stance = "neutral"

        # 构建查询
        # 基础条件: 系统规则 + 已启用
        query = db.query(ReviewRule).filter(
            ReviewRule.is_system == True,
            ReviewRule.is_active == True
        )

        # 内存过滤策略 (Python-side filtering)
        # 原因: JSON 字段的包含查询在不同 DB (SQLite vs PG) 下语法差异大。
        # 且系统规则数量通常不多(<1000)，全量查出后在内存筛选性能可控且最稳健。
        all_system_rules = query.all()

        classified_rules = {
            "universal": [],
            "feature": [],
            "stance": []
        }

        for rule in all_system_rules:
            # 1. 通用规则
            if rule.rule_category == "universal":
                classified_rules["universal"].append(rule)
                continue

            # 如果没有 Category ID，则无法匹配 Feature 和 Stance 规则，跳过
            if not category_id:
                continue

            # 检查规则是否适用于当前 Category
            # 逻辑: rule.apply_to_category_ids 必须包含 category_id
            applicable_ids = rule.apply_to_category_ids or []
            # 兼容处理: 如果是 JSON 存的是字符串列表，需转 int 比较 (视存入逻辑而定)
            is_applicable_category = category_id in [int(i) for i in applicable_ids if str(i).isdigit()]

            if not is_applicable_category:
                continue

            # 2. 特征规则 (绑定分类)
            if rule.rule_category == "feature":
                classified_rules["feature"].append(rule)
            
            # 3. 立场规则 (绑定分类 + 绑定立场)
            elif rule.rule_category == "stance":
                # 规则未指定立场(视为通用立场) OR 规则立场与用户立场一致
                rule_stance = rule.target_stance
                if not rule_stance or (target_stance and rule_stance == target_stance):
                    classified_rules["stance"].append(rule)

        # 按优先级排序
        for key in classified_rules:
            classified_rules[key].sort(key=lambda x: x.priority)

        return classified_rules

    def _get_user_custom_rules(self, db: Session, user_id: int) -> List[ReviewRule]:
        """获取用户自定义规则"""
        return db.query(ReviewRule).filter(
            ReviewRule.is_system == False,
            ReviewRule.creator_id == user_id,
            ReviewRule.is_active == True
        ).order_by(ReviewRule.priority).all()

    def _get_dynamic_deduction_prompt(self, contract_type_name: str) -> List[str]:
        """
        [保留原有逻辑] 基于知识图谱的动态推演
        这部分逻辑很棒，利用了 KG 的描述性信息，是对硬性规则的补充。
        """
        if not contract_type_name:
            return []

        kg_data = kg_service.get_by_name(contract_type_name)
        if not kg_data:
            return []

        features = kg_data.get("legal_features", {})
        
        deduction_lines = []
        deduction_lines.append(f"本合同识别为：【{kg_data.get('name')}】")
        
        # 如果有交易特征描述，加入 Prompt
        if features.get('transaction_characteristics'):
            deduction_lines.append(f"• 交易特征模型：{features.get('transaction_characteristics')}")
        
        deduction_lines.append("\n**>>> 深度推演指令 (Knowledge Graph Deduction) <<<**")
        deduction_lines.append("请结合上述交易特征，运用法律逻辑反向审查：")
        deduction_lines.append("1. 鉴于上述特征，合同是否构建了完整的闭环？")
        deduction_lines.append("2. 是否存在该类交易特有的隐蔽风险（如权利瑕疵、交付陷阱）？")

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
        核心方法：组装最终审查指令集

        Args:
            legal_features: 包含 'contract_type' 等信息
            stance: 审查立场
            user_id: 用户ID (优先使用 DB 中的自定义规则)
            user_custom_rules: 纯文本规则列表 (兼容旧逻辑)
        """
        contract_type = legal_features.get("contract_type")
        logger.info(f"[RuleAssembler] 开始组装 - 类型: {contract_type}, 立场: {stance}, 用户ID: {user_id}")

        db = self._get_db_session()
        try:
            # 1. 解析 Category ID (这是关联的核心)
            category_id = self._resolve_category_id(db, contract_type)
            if category_id:
                logger.info(f"[RuleAssembler] 解析到 Category ID: {category_id}")
            else:
                logger.warning(f"[RuleAssembler] 无法解析 Category ID，将只加载通用规则")

            # 2. 从数据库获取并分类系统规则
            sys_rules = self._get_system_rules(db, category_id, stance)

            # 3. 获取用户自定义规则
            db_custom_rules = []
            if user_id:
                db_custom_rules = self._get_user_custom_rules(db, user_id)

            # ========== 开始构建 Prompt ==========
            final_instructions = []

            # Priority 1: 用户自定义规则 (User Custom)
            if db_custom_rules:
                final_instructions.append("### 1. 用户自定义规则 (User Custom - Highest Priority)")
                for idx, rule in enumerate(db_custom_rules, 1):
                    final_instructions.append(f"{idx}. {rule.content}")
            elif user_custom_rules:
                final_instructions.append("### 1. 用户特别关注点 (User Defined)")
                for idx, rule in enumerate(user_custom_rules, 1):
                    final_instructions.append(f"{idx}. {rule}")

            # Priority 2: 行业/特征专项规则 (Feature Specific - Linked by Category)
            # 原有的 'Industry' 和 'Transaction Structure' 规则现在统一归并到 Feature 规则中
            # 只要在后台将它们挂载到对应的 Category 上即可
            if sys_rules["feature"]:
                final_instructions.append("\n### 2. 业务类型专项规则 (Category Specific)")
                for rule in sys_rules["feature"]:
                    final_instructions.append(f"- [{rule.name}] {rule.content}")
                logger.info(f"加载特征规则: {len(sys_rules['feature'])} 条")

            # Priority 3: 立场防御规则 (Stance Defense)
            if sys_rules["stance"]:
                final_instructions.append("\n### 3. 立场防御指南 (Stance Defense)")
                # 插入立场提示
                final_instructions.append(f"当前立场设定为: {stance}。请重点审查：")
                for rule in sys_rules["stance"]:
                    final_instructions.append(f"- {rule.content}")
                logger.info(f"加载立场规则: {len(sys_rules['stance'])} 条")

            # Priority 4: 通用基础规则 (System Standard)
            if sys_rules["universal"]:
                final_instructions.append("\n### 4. 通用法律合规标准 (General Standard)")
                for rule in sys_rules["universal"]:
                    final_instructions.append(f"- {rule.content}")

            # Priority 5: 动态推演 (Knowledge Graph)
            deduction = self._get_dynamic_deduction_prompt(contract_type)
            if deduction:
                final_instructions.append("\n### 5. 深度风险推演 (Deep Reasoning)")
                final_instructions.extend(deduction)

            result = "\n".join(final_instructions)
            
            # 统计日志
            total_rules = len(db_custom_rules) + len(sys_rules['feature']) + len(sys_rules['stance']) + len(sys_rules['universal'])
            logger.info(f"[RuleAssembler] 组装完成，共包含 {total_rules} 条硬性规则 + 动态推演。")
            
            return result

        except Exception as e:
            logger.error(f"[RuleAssembler] 组装规则时发生错误: {str(e)}", exc_info=True)
            # 降级策略: 返回空或基础提示，防止整个审查失败
            return "请依据通用法律法规进行合同审查。"
        finally:
            db.close()

# 单例导出
rule_assembler = RuleAssembler()