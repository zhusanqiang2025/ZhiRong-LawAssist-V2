from typing import TypedDict, Dict, Any, Optional, List, Tuple
from .schemas import ReviewOutput

class AgentState(TypedDict):
    # 输入
    contract_text: str
    metadata: Dict[str, Any]
    stance: str

    # 中间推理结果
    contract_profile: Optional[Dict[str, Any]]
    legal_relationships: Optional[Dict[str, Any]]

    # 输出
    review_result: Optional[ReviewOutput]
    human_feedback: Optional[str]
    final_output: Optional[str]
    status: str

    # ⭐ 新增: 长文本分块支持
    chunks: List[Tuple[str, Tuple[int, int]]]  # 分块文本列表 [(chunk_text, (start, end)), ...]
    chunk_review_mode: bool  # 是否启用分块审查模式