from ..state import AgentState

def extract_metadata_node(state: AgentState) -> AgentState:
    """
    元数据提取节点
    目前作为透传节点，未来可以在这里接入专门的提取 Chain
    """
    print("\n🔍 [节点: 元数据提取] 正在校验元数据...")
    # 在这里可以对 metadata 做预处理或校验
    return state

def human_gate_node(state: AgentState) -> dict:
    """
    人工介入节点
    这是一个"断点"，LangGraph 会在这里暂停，等待人工确认后继续
    """
    print("\n👤 [节点: 人工介入] 流程暂停，等待前端确认...")
    # 此节点不修改状态，只作为中断标记
    return {}

def final_report_node(state: AgentState) -> dict:
    """
    最终报告生成节点
    """
    print("\n📝 [节点: 生成最终报告]")
    
    review_result = state.get("review_result")
    
    if review_result:
        # 简单的报告格式化，实际业务中可能生成 PDF 或 Markdown
        issues_count = len(review_result.issues)
        summary = review_result.summary
        report = f"【审查完成】\n总体评价：{summary}\n共发现 {issues_count} 个风险点。"
        return {"final_output": report, "status": "finished"}
    else:
        return {"final_output": "审查过程中断或失败", "status": "error"}