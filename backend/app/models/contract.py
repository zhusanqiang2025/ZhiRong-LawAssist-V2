# backend/app/models/contract.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


# 定义合同流程状态枚举
class ContractStatus(str, enum.Enum):
    DRAFT = "draft"                 # 草稿/上传中
    PARSING = "parsing"             # 解析中（可选）
    REVIEWING = "reviewing"         # AI 审查中
    WAITING_HUMAN = "waiting_human" # 等待人工确认
    APPROVED = "approved"           # 通过
    REJECTED = "rejected"           # 驳回


# 2. 合同主表
class ContractDoc(Base):
    __tablename__ = "contract_docs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True, comment="合同标题/文件名")

    # ==================== 🔗 核心连接 (Hub-and-Spoke 新增) ====================
    # 确定的分类ID (由 AI 解析或用户手动指定)
    # 这让 RuleAssembler 可以直接用 ID 查找规则，而不需要猜名字
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)

    # 流程状态
    status = Column(String(32), default=ContractStatus.DRAFT.value, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="上传用户ID")

    # 文件路径
    original_file_path = Column(String(512), nullable=True, comment="原始文件路径")
    pdf_converted_path = Column(String(512), nullable=True, comment="PDF 版本路径（用于解析）")
    final_docx_path = Column(String(512), nullable=True, comment="最终修订版路径")

    # AI 提取的元数据（JSON）
    metadata_info = Column(JSON, nullable=True, comment="提取的当事人、金额、类型等")
    stance = Column(String(16), nullable=True, comment="审查立场：甲方/乙方")

    # ⭐ 新增字段：交易结构和主体风险缓存
    transaction_structures = Column(JSON, nullable=True, comment="用户选择的交易结构列表")
    entity_risk_cache = Column(JSON, nullable=True, comment="主体风险缓存信息")
    current_review_task_id = Column(Integer, ForeignKey("contract_review_tasks.id"), nullable=True, comment="当前审查任务ID")

    # 可选：LangGraph 线程ID（后续可扩展状态机）
    thread_id = Column(String(128), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ==================== 关系定义 ====================
    # 1. 关联分类 (Hub-and-Spoke 新增)
    # 允许通过 contract.category 访问分类信息
    category = relationship("Category", foreign_keys=[category_id])

    # 关系：一对多 → 审查项
    review_items = relationship(
        "ContractReviewItem",
        back_populates="contract",
        cascade="all, delete-orphan"
    )

    # 关系：当前审查任务（多对一）
    current_review_task = relationship(
        "ContractReviewTask",
        foreign_keys=[current_review_task_id],
        post_update=True
    )

    # ⭐ 新增关系：一对多 → 审查任务历史
    # 注意：明确指定 foreign_keys 指向 ContractReviewTask.contract_id
    review_tasks = relationship(
        "ContractReviewTask",
        foreign_keys="ContractReviewTask.contract_id",
        back_populates="contract",
        cascade="all, delete-orphan"
    )


# 3. 合同审查详情表（每个风险点一条）
class ContractReviewItem(Base):
    __tablename__ = "contract_review_items"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contract_docs.id"), nullable=False, index=True)

    issue_type = Column(String(64), nullable=False, comment="问题类型，如：付款条款")
    quote = Column(String(512), nullable=False, comment="原文引用")
    explanation = Column(Text, nullable=False, comment="风险解释")
    suggestion = Column(Text, nullable=False, comment="修改建议或警告")
    legal_basis = Column(Text, nullable=True, default="", comment="审查依据（法律法规、标准条款等）")
    severity = Column(String(16), nullable=False, comment="严重程度：Low/Medium/High/Critical")
    action_type = Column(String(16), default="Revision", comment="Revision 或 Alert")

    # 人工确认状态
    item_status = Column(String(16), default="Pending", comment="Pending/Approved/Rejected/Solved")
    final_text = Column(Text, nullable=True, comment="人工最终定稿文本")
    human_comment = Column(String(512), nullable=True, comment="人工备注")

    # ⭐ 新增字段：主体风险信息
    entity_risk = Column(JSON, nullable=True, comment="主体风险信息 (单个关联主体)")
    related_entities = Column(JSON, nullable=True, comment="⚠️ 关联的主体名称列表; 用途: 存储该审查项涉及的所有主体名称; 示例: ['XX公司', 'YY科技有限公司']; 说明: 便于前端快速定位相关风险,无需解析 entity_risk")

    created_at = Column(DateTime, default=datetime.utcnow)

    # 反向关系
    contract = relationship("ContractDoc", back_populates="review_items")


# 4. 后台任务运行记录，用于追踪 PoC/Graph 执行状态
class TaskRun(Base):
    __tablename__ = "task_runs"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contract_docs.id"), nullable=True, index=True)
    task_name = Column(String(128), nullable=False, comment="任务名，例如: langgraph:contract-review")
    status = Column(String(32), default="pending", comment="pending/running/success/failed")
    message = Column(Text, nullable=True, comment="可选的运行信息或错误堆栈")
    result = Column(JSON, nullable=True, comment="可选：结构化结果")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<TaskRun {self.task_name} {self.status} for {self.contract_id}>"