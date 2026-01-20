from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# 导入状态定义
from .state import AgentState

# 导入各类节点逻辑
from .nodes.basic import extract_metadata_node, human_gate_node, final_report_node
from .nodes.ai_reviewer import ai_reviewer_node

def build_contract_review_graph():
    """
    构建并编译合同审查的状态图
    """
    # 1. 初始化图
    builder = StateGraph(AgentState)

    # 2. 添加节点 (注册功能模块)
    builder.add_node("extract_metadata", extract_metadata_node)
    builder.add_node("ai_reviewer", ai_reviewer_node)
    builder.add_node("human_gate", human_gate_node)
    builder.add_node("final_report", final_report_node)

    # 3. 定义边 (连接流程)
    # Start -> 元数据提取
    builder.set_entry_point("extract_metadata")
    
    # 元数据提取 -> AI 审查 (三阶段)
    builder.add_edge("extract_metadata", "ai_reviewer")
    
    # AI 审查 -> 人工确认 (中断点)
    builder.add_edge("ai_reviewer", "human_gate")
    
    # 人工确认 -> 最终报告
    builder.add_edge("human_gate", "final_report")
    
    # 最终报告 -> End
    builder.add_edge("final_report", END)

    # 4. 配置内存 (用于持久化状态，支持断点续传)
    memory = MemorySaver()

    # 5. 编译图
    # interrupt_before=["human_gate"]: 告诉系统运行到 human_gate 之前必须停下来
    app = builder.compile(
        checkpointer=memory,
        interrupt_before=["human_gate"]
    )
    
    return app