# backend/app/services/contract_generation/structural/template_matcher.py
"""
结构化模板匹配服务（严格版 · 可直接替换）

设计目标：
- 宁可不匹配，也不用错模板
- 模板 ≠ 兜底方案
- 结构不一致只能 STRUCTURAL，不能 HIGH
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from sqlalchemy.orm import Session
from app.models.contract_template import ContractTemplate

logger = logging.getLogger(__name__)


class MatchLevel(Enum):
    HIGH = "high"                # 可直接用于合同填充
    STRUCTURAL = "structural"    # 仅可作为结构参考
    NONE = "none"                # 禁止使用模板


@dataclass
class TemplateMatchResult:
    template_id: Optional[str]
    template_name: Optional[str]
    template_file_url: Optional[str]

    match_level: MatchLevel
    match_reason: str

    structural_differences: List[str]
    mismatch_reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "template_file_url": self.template_file_url,
            "match_level": self.match_level.value,
            "match_reason": self.match_reason,
            "structural_differences": self.structural_differences,
            "mismatch_reasons": self.mismatch_reasons,
        }


class StructuralTemplateMatcher:
    """
    基于知识图谱的模板匹配器

    核心逻辑：
    1. 根据识别的合同类型匹配模板
    2. 使用知识图谱的法律特征进行精确匹配
    3. 返回匹配结果
    """

    def __init__(self, db: Session):
        self.db = db

    # ===========================
    # 主入口
    # ===========================
    def match(
        self,
        analysis_result: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> TemplateMatchResult:

        classification = analysis_result.get("contract_classification", {})
        legal_features = analysis_result.get("legal_features", {})

        # 新的数据结构：contract_type（具体合同类型）
        contract_type = classification.get("contract_type")
        primary_type = classification.get("primary_type", contract_type)  # 兼容旧字段

        # 知识图谱法律特征
        transaction_nature = legal_features.get("transaction_nature")
        contract_object = legal_features.get("contract_object")
        stance = legal_features.get("stance")
        consideration_type = legal_features.get("consideration_type")

        # ===== Hard Gate 0：必须有合同类型 =====
        if not contract_type:
            return self._none(
                "缺少合同类型，禁止模板匹配",
                ["contract_type 缺失"]
            )

        # ===== Step 1：基于合同类型的基础查询 =====
        # 合同生成仅使用管理员公开模板（is_public=True）
        query = self.db.query(ContractTemplate).filter(
            ContractTemplate.status == "active",
            ContractTemplate.subcategory.contains(contract_type)  # 使用 subcategory 模糊匹配
        )

        if user_id:
            # 模糊查询场景：公开模板 + 用户私有模板
            query = query.filter(
                (ContractTemplate.is_public.is_(True)) |
                (ContractTemplate.owner_id == user_id)
            )
        else:
            # 合同生成场景：仅使用管理员公开模板
            query = query.filter(ContractTemplate.is_public.is_(True))

        candidates = query.all()

        if not candidates:
            # ===== 降级方案：使用知识图谱法律特征进行模糊匹配 =====
            logger.warning(f"[StructuralMatcher] 不存在合同类型为 {contract_type} 的模板，尝试使用知识图谱特征模糊匹配")

            fallback_query = self.db.query(ContractTemplate).filter(
                ContractTemplate.status == "active"
            )

            # 优先使用 transaction_nature 匹配
            if transaction_nature:
                fallback_query = fallback_query.filter(
                    ContractTemplate.transaction_nature == transaction_nature
                )
                logger.info(f"[StructuralMatcher] 使用 transaction_nature={transaction_nature} 进行模糊匹配")

            # 如果指定了 contract_object，进一步过滤
            if contract_object:
                fallback_query = fallback_query.filter(
                    ContractTemplate.contract_object == contract_object
                )

            # 应用相同的权限过滤规则
            if user_id:
                fallback_query = fallback_query.filter(
                    (ContractTemplate.is_public.is_(True)) |
                    (ContractTemplate.owner_id == user_id)
                )
            else:
                fallback_query = fallback_query.filter(ContractTemplate.is_public.is_(True))

            candidates = fallback_query.all()

            if not candidates:
                return self._none(
                    f"不存在合同类型为 {contract_type} 的模板，且知识图谱特征（{transaction_nature}/{contract_object}）也无匹配",
                    [f"contract_type={contract_type} 无模板", f"知识图谱特征 {transaction_nature}/{contract_object} 无匹配"]
                )

            logger.info(f"[StructuralMatcher] 知识图谱特征模糊匹配找到 {len(candidates)} 个候选模板")

        # ====================
        # 知识图谱法律特征匹配（核心）
        # ====================

        structural_only = False

        logger.info(f"[StructuralMatcher] 开始法律特征匹配，候选模板数: {len(candidates)}")
        logger.info(f"[StructuralMatcher] 需求特征: nature={transaction_nature}, object={contract_object}, stance={stance}")

        # Soft Gate 1：transaction_nature（交易性质）
        if transaction_nature:
            nature_ok = [t for t in candidates if t.transaction_nature == transaction_nature]
            if nature_ok:
                candidates = nature_ok
                logger.info(f"[StructuralMatcher] transaction_nature 匹配成功: {len(candidates)} 个候选")
            else:
                # 知识图谱特征不匹配，标记为 structural_only
                logger.warning(f"[StructuralMatcher] transaction_nature={transaction_nature} 无匹配，标记为 structural_only")
                structural_only = True

        # Soft Gate 2：contract_object（合同标的）
        if contract_object:
            object_ok = [t for t in candidates if t.contract_object == contract_object]
            if object_ok:
                candidates = object_ok
                logger.info(f"[StructuralMatcher] contract_object 匹配成功: {len(candidates)} 个候选")
            else:
                # 知识图谱特征不匹配，标记为 structural_only
                logger.warning(f"[StructuralMatcher] contract_object={contract_object} 无匹配，标记为 structural_only")
                structural_only = True

        # Soft Gate 3：stance（立场）
        if stance:
            # 立场优先匹配：中立 可用于任何立场
            stance_ok = []
            for t in candidates:
                if not t.stance or t.stance == "中立" or t.stance == stance:
                    stance_ok.append(t)

            if stance_ok:
                candidates = stance_ok
                logger.info(f"[StructuralMatcher] stance 匹配成功: {len(candidates)} 个候选")
            else:
                # 立场不匹配，降级到 structural_only
                logger.warning(f"[StructuralMatcher] stance={stance} 无匹配，标记为 structural_only")
                structural_only = True

        logger.info(f"[StructuralMatcher] 知识图谱特征匹配完成，剩余候选: {len(candidates)}, structural_only={structural_only}")

        if not candidates:
            return self._none(
                "筛选后不存在可用模板",
                ["合同类型 + 知识图谱法律特征无法同时满足"]
            )

        # ===== 选最优模板（而不是随便第一个）=====
        # 列出所有候选模板供调试
        logger.info(f"[StructuralMatcher] 候选模板列表:")
        for idx, t in enumerate(candidates, 1):
            logger.info(f"  {idx}. {t.name} (rec={t.is_recommended}, risk={t.risk_level}, sec_types={t.secondary_types})")

        best = self._choose_best(candidates)

        # 详细日志：选中的模板信息
        logger.info(f"[StructuralMatcher] 最终选中模板:")
        logger.info(f"  - ID: {best.id}")
        logger.info(f"  - 名称: {best.name}")
        logger.info(f"  - 分类: {best.category}/{best.subcategory}")
        logger.info(f"  - 知识图谱特征: nature={best.transaction_nature}, object={best.contract_object}, stance={best.stance}")
        logger.info(f"  - secondary_types: {best.secondary_types}")
        logger.info(f"  - is_recommended: {best.is_recommended}")
        logger.info(f"  - match_level: {'STRUCTURAL' if structural_only else 'HIGH'}")

        if structural_only:
            return TemplateMatchResult(
                template_id=best.id,
                template_name=best.name,
                template_file_url=best.file_url,
                match_level=MatchLevel.STRUCTURAL,
                match_reason="模板结构部分匹配，仅可作为结构参考",
                structural_differences=[
                    "部分交易结构字段与模板不完全一致"
                ],
                mismatch_reasons=[]
            )

        return TemplateMatchResult(
            template_id=best.id,
            template_name=best.name,
            template_file_url=best.file_url,
            match_level=MatchLevel.HIGH,
            match_reason="模板与需求结构高度一致，可直接填充",
            structural_differences=[],
            mismatch_reasons=[]
        )

    # ===========================
    # 内部工具方法
    # ===========================
    def _choose_best(self, templates: List[ContractTemplate]) -> ContractTemplate:
        """
        明确排序逻辑：
        1. is_recommended
        2. 风险等级高的优先
        3. 更新时间新
        """
        def score(t: ContractTemplate) -> Tuple:
            risk_order = {"low": 1, "mid": 2, "high": 3}
            # 处理 updated_at 可能为 None 或时区不一致的情况
            if t.updated_at is not None:
                # 如果是带时区的，转换为不带时区的
                if t.updated_at.tzinfo is not None:
                    updated_at = t.updated_at.replace(tzinfo=None)
                else:
                    updated_at = t.updated_at
            else:
                updated_at = datetime.min

            return (
                1 if t.is_recommended else 0,
                risk_order.get(t.risk_level or "mid", 2),
                updated_at
            )

        return sorted(templates, key=score, reverse=True)[0]

    def _none(self, reason: str, mismatches: List[str]) -> TemplateMatchResult:
        return TemplateMatchResult(
            template_id=None,
            template_name=None,
            template_file_url=None,
            match_level=MatchLevel.NONE,
            match_reason=reason,
            structural_differences=[],
            mismatch_reasons=mismatches
        )

    def get_template_by_id(self, template_id: str) -> Optional[ContractTemplate]:
        return (
            self.db.query(ContractTemplate)
            .filter(ContractTemplate.id == template_id)
            .first()
        )


# 单例
def get_structural_matcher(db: Session) -> StructuralTemplateMatcher:
    return StructuralTemplateMatcher(db)


# 别名导出（兼容性）
get_structural_template_matcher = get_structural_matcher

__all__ = [
    "StructuralTemplateMatcher",
    "MatchLevel",
    "TemplateMatchResult",
    "get_structural_matcher",
    "get_structural_template_matcher",
]
