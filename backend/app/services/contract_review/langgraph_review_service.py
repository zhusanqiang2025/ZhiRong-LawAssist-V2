"""
基于 LangGraph 的合同审查执行器

使用新的三阶段审查流程 + RuleAssembler 动态规则加载
替换旧的 ContractReviewService
"""

import logging
import json
from typing import Dict, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.contract import ContractDoc, ContractReviewItem, ContractStatus
from app.models.user import User
from app.services.contract_review.graph import build_contract_review_graph
from app.services.contract_review.state import AgentState
from app.services.risk_analysis.entity_risk_service import EntityRiskService  # ⭐ 新增: 主体风险服务

logger = logging.getLogger(__name__)


class LangGraphReviewService:
    """
    基于 LangGraph 的合同审查服务

    使用三阶段审查流程：
    1. Stage 1: 合同法律画像 (Profile)
    2. Stage 2: 法律关系与适用法 (Relationships)
    3. Stage 3: 风险与责任审查 (Review) - 使用 RuleAssembler 动态加载规则
    """

    def __init__(self, db: Session):
        self.db = db
        self.graph = build_contract_review_graph()

    def _extract_text_from_file(self, file_path: str) -> str:
        """从文件中提取文本"""
        from docx import Document

        try:
            if file_path.endswith('.docx'):
                doc = Document(file_path)
                text = '\n'.join([para.text for para in doc.paragraphs])
                return text
            else:
                # 其他格式可以扩展
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"提取文件文本失败: {e}")
            return ""

    async def _query_entity_risks_for_contract(self, metadata: Dict) -> Dict[str, Dict]:
        """
        ⭐ 新增: 查询合同所有当事人的风险信息

        Args:
            metadata: 合同元数据 (包含 parties 信息)

        Returns:
            {主体名称: 风险信息}
        """
        # ⭐ 使用统一的工具函数解析当事人信息
        from app.services.contract_review.utils import parse_parties_from_metadata

        entities = parse_parties_from_metadata(metadata, return_format="dicts")

        if not entities:
            logger.info("[LangGraph] 未找到当事人信息，跳过主体风险查询")
            return {}

        # 转换为 EntityRiskService 需要的格式
        # [{"name": "雇主", "type": "individual"}, ...]
        entity_list = []
        for entity in entities:
            if isinstance(entity, dict) and entity.get("name"):
                entity_list.append({
                    "name": entity["name"],
                    "type": entity.get("type", "unknown")
                })
                logger.info(f"[LangGraph] 解析当事人: {entity['name']} ({entity.get('type', 'unknown')})")

        if not entity_list:
            logger.info("[LangGraph] 未找到有效的当事人信息，跳过主体风险查询")
            return {}

        # 查询每个主体的风险
        entity_risk_service = EntityRiskService(self.db)
        entity_risk_map = await entity_risk_service.query_multiple_entities(entity_list)

        return entity_risk_map

    async def run_deep_review(
        self,
        contract_id: int,
        stance: str = "甲方",
        updated_metadata: Optional[dict] = None,
        enable_custom_rules: bool = False,
        user_id: Optional[int] = None,
        transaction_structures: Optional[list] = None  # ⭐ 新增: 交易结构列表
    ) -> bool:
        """
        执行深度审查（使用 LangGraph 三阶段流程）

        Args:
            contract_id: 合同ID
            stance: 审查立场（甲方/乙方）
            updated_metadata: 更新的元数据
            enable_custom_rules: 是否启用用户自定义规则
            user_id: 用户ID（用于加载用户自定义规则）
            transaction_structures: 用户选择的交易结构列表 (新增)

        Returns:
            bool: 审查是否成功
        """
        # 1. 获取合同记录
        contract = self.db.query(ContractDoc).filter(
            ContractDoc.id == contract_id
        ).first()

        if not contract:
            logger.error(f"合同 {contract_id} 不存在")
            return False

        try:
            # 2. 更新合同状态
            contract.status = ContractStatus.REVIEWING.value
            if updated_metadata:
                # 修复：确保 updated_metadata 是字典类型
                # 如果是字符串，尝试解析为字典
                if isinstance(updated_metadata, str):
                    import json
                    try:
                        updated_metadata = json.loads(updated_metadata)
                    except json.JSONDecodeError:
                        logger.error(f"[LangGraph] 无法解析 updated_metadata JSON 字符串")
                        updated_metadata = {}
                # 现在赋值字典
                contract.metadata_info = updated_metadata
            contract.stance = stance
            self.db.commit()

            # 3. 提取合同文本
            text = self._extract_text_from_file(contract.original_file_path)
            if not text:
                logger.error(f"无法提取合同文本: {contract.original_file_path}")
                return False

            # 3.5 ========== ⭐ 新增: 长文本分块处理 ==========
            text_length = len(text)
            logger.info(f"合同文本长度: {text_length} 字符")

            chunks = None
            chunk_mode = False

            if text_length > 5000:  # 长文本阈值
                logger.info("启用长文本分块处理 (LangGraph)")

                # 导入分块工具
                from app.services.contract_review.utils import chunk_contract_text

                # 分块处理
                chunks = chunk_contract_text(
                    text,
                    max_chunk_size=4000,
                    overlap=200,
                    split_by_section=True
                )

                if chunks:
                    chunk_mode = True
                    logger.info(f"文本分为 {len(chunks)} 块")
                else:
                    logger.warning("分块失败,使用全文审查模式")

            # 4. 准备初始状态
            metadata = contract.metadata_info or {}

            # ⭐ 新增: 添加交易结构到元数据
            if transaction_structures:
                metadata["transaction_structures"] = transaction_structures
                logger.info(f"[LangGraph] 使用交易结构: {transaction_structures}")

            # ========== ⭐ 新增: 主体风险查询 ==========
            entity_risk_map = await self._query_entity_risks_for_contract(metadata)
            if entity_risk_map:
                metadata["entity_risks"] = entity_risk_map
                logger.info(f"[LangGraph] 查询到 {len(entity_risk_map)} 个主体的风险信息")

            if enable_custom_rules and user_id:
                # 加载用户自定义规则
                from app.models.rule import ReviewRule  # ✅ 从 contract.py 移动到独立的 rule.py
                custom_rules = self.db.query(ReviewRule).filter(
                    ReviewRule.rule_category == "custom",
                    ReviewRule.creator_id == user_id,
                    ReviewRule.is_active == True
                ).all()
                metadata["custom_rules"] = [r.content for r in custom_rules]

            initial_state: AgentState = {
                "contract_text": text,
                "metadata": metadata,
                "stance": stance,
                "contract_profile": None,
                "legal_relationships": None,
                "review_result": None,
                "human_feedback": None,
                "final_output": None,
                "status": "processing",
                # ⭐ 新增: 分块信息
                "chunks": chunks if chunk_mode else [],
                "chunk_review_mode": chunk_mode
            }

            # 5. 执行 LangGraph 状态图
            logger.info(f"开始执行合同 {contract_id} 的 LangGraph 审查流程")

            # 使用 thread_id 用于状态持久化
            config = {"configurable": {"thread_id": f"contract_{contract_id}"}}

            # 运行状态图（同步运行到 human_gate 节点之前）
            result = self.graph.invoke(initial_state, config)

            logger.info(f"LangGraph 审查完成，状态: {result.get('status')}")

            # 6. 保存审查结果
            if result.get("review_result"):
                self._save_review_results(contract_id, result["review_result"], stance)
                return True
            else:
                logger.error(f"审查失败，未返回结果")
                return False

        except Exception as e:
            logger.error(f"执行深度审查失败: {e}", exc_info=True)
            contract.status = ContractStatus.DRAFT.value
            self.db.commit()
            return False

    def _get_relevant_entity_risk(
        self,
        issue_dict: Dict,
        entity_risk_map: Dict[str, Dict],
        all_parties: list
    ) -> tuple:
        """
        ⭐ 关键函数: 关联审查项与主体风险

        实现逻辑:
        1. 从审查项的 quote 和 explanation 中提取主体名称
        2. 匹配 entity_risk_map 中的风险信息
        3. 返回最相关的风险和关联主体列表

        Args:
            issue_dict: 单个审查项字典
            entity_risk_map: 主体名称 -> 风险信息的映射
            all_parties: 所有当事人名称列表

        Returns:
            (entity_risk_info, related_entities)
            - entity_risk_info: 最相关的主体风险信息 (如果有)
            - related_entities: 该审查项涉及的所有主体名称列表
        """
        from typing import Dict, List, Tuple, Optional

        related_entities = []
        entity_risk_info = None

        # 1️⃣ 从审查项中提取主体名称
        item_text = f"{issue_dict.get('quote', '')} {issue_dict.get('explanation', '')}"

        # 简单匹配: 检查所有当事人名称是否出现在审查项文本中
        for party_name in all_parties:
            if party_name in item_text:
                related_entities.append(party_name)

        # 2️⃣ 如果找到关联主体,获取风险信息
        if related_entities:
            # 优先返回风险等级最高的主体
            risky_entities = [
                (name, entity_risk_map.get(name, {}))
                for name in related_entities
                if name in entity_risk_map
            ]

            if risky_entities:
                # 按风险等级排序: High > Medium > Low > None
                risk_order = {"High": 4, "Medium": 3, "Low": 2, "None": 1}
                risky_entities.sort(
                    key=lambda x: risk_order.get(x[1].get("risk_level", "None"), 0),
                    reverse=True
                )

                # 返回最高风险等级的主体信息
                entity_risk_info = risky_entities[0][1]

        return entity_risk_info, related_entities

    def _save_review_results(self, contract_id: int, review_result, stance: str):
        """保存审查结果到数据库"""
        from app.schemas import ReviewOutput

        # 清空旧的审查记录
        self.db.query(ContractReviewItem).filter(
            ContractReviewItem.contract_id == contract_id
        ).delete()

        # ========== ⭐ 获取主体风险映射 ==========
        contract = self.db.query(ContractDoc).filter(
            ContractDoc.id == contract_id
        ).first()

        # 从元数据中提取当事人和风险信息
        metadata = contract.metadata_info or {}

        # ⭐ 使用统一的工具函数解析当事人信息
        from app.services.contract_review.utils import parse_parties_from_metadata

        all_parties = parse_parties_from_metadata(metadata, return_format="names")
        entity_risk_map = metadata.get('entity_risks', {})

        # 写入新的审查项
        if hasattr(review_result, 'issues'):
            issues = review_result.issues
        elif isinstance(review_result, dict):
            issues = review_result.get('issues', [])
        else:
            issues = []

        for issue in issues:
            # 统一处理 Pydantic 对象和字典
            if hasattr(issue, 'model_dump'):
                # Pydantic v2 对象
                issue_dict = issue.model_dump()
            elif hasattr(issue, 'dict'):
                # Pydantic v1 对象
                issue_dict = issue.dict()
            elif isinstance(issue, dict):
                issue_dict = issue
            else:
                logger.warning(f"无法识别的 issue 类型: {type(issue)}")
                continue

            # ========== ⭐ 新增: 关联主体风险 ==========
            entity_risk_info, related_entities = self._get_relevant_entity_risk(
                issue_dict=issue_dict,
                entity_risk_map=entity_risk_map,
                all_parties=all_parties
            )

            item = ContractReviewItem(
                contract_id=contract_id,
                issue_type=issue_dict.get('issue_type', '未知'),
                quote=issue_dict.get('quote', ''),
                explanation=issue_dict.get('explanation', ''),
                suggestion=issue_dict.get('suggestion', ''),
                legal_basis=issue_dict.get('legal_basis', ''),
                severity=issue_dict.get('severity', 'Medium'),
                action_type=issue_dict.get('action_type', 'Revision'),
                item_status="Pending",
                # ⭐ 新增: 保存关联的主体风险
                entity_risk=entity_risk_info,
                related_entities=related_entities  # 关联的所有主体名称列表
            )
            self.db.add(item)

        # 更新合同状态
        contract = self.db.query(ContractDoc).filter(
            ContractDoc.id == contract_id
        ).first()
        contract.status = ContractStatus.WAITING_HUMAN.value
        self.db.commit()

        logger.info(f"合同 {contract_id} 审查结果已保存，共 {len(issues)} 条问题")


async def run_langgraph_review(
    contract_id: int,
    stance: str = "甲方",
    updated_metadata: Optional[dict] = None,
    enable_custom_rules: bool = False,
    user_id: Optional[int] = None,
    transaction_structures: Optional[list] = None  # ⭐ 新增: 交易结构列表
) -> Dict:
    """
    运行 LangGraph 合同审查的便捷函数

    Args:
        contract_id: 合同ID
        stance: 审查立场
        updated_metadata: 更新的元数据
        enable_custom_rules: 是否启用用户自定义规则
        user_id: 用户ID
        transaction_structures: 用户选择的交易结构列表 (新增)

    Returns:
        执行结果字典
    """
    db = SessionLocal()
    try:
        service = LangGraphReviewService(db)
        success = await service.run_deep_review(
            contract_id=contract_id,
            stance=stance,
            updated_metadata=updated_metadata,
            enable_custom_rules=enable_custom_rules,
            user_id=user_id,
            transaction_structures=transaction_structures  # ⭐ 新增: 传递交易结构
        )

        if success:
            return {"success": True, "message": "审查完成"}
        else:
            return {"success": False, "message": "审查失败"}
    except Exception as e:
        logger.error(f"LangGraph 审查异常: {e}", exc_info=True)
        return {"success": False, "message": str(e)}
    finally:
        db.close()


async def run_langgraph_review_async(contract_id: int) -> None:
    """
    异步运行 LangGraph 审查（用于后台任务）

    Args:
        contract_id: 合同ID
    """
    db = SessionLocal()
    try:
        contract = db.query(ContractDoc).filter(
            ContractDoc.id == contract_id
        ).first()

        if not contract:
            logger.error(f"合同 {contract_id} 不存在")
            return

        stance = contract.stance or "甲方"
        metadata = contract.metadata_info

        service = LangGraphReviewService(db)
        await service.run_deep_review(
            contract_id=contract_id,
            stance=stance,
            updated_metadata=metadata
        )

    except Exception as e:
        logger.error(f"异步 LangGraph 审查失败: {e}", exc_info=True)
    finally:
        db.close()
