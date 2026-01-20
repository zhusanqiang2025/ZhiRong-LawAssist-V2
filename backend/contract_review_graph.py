# 此文件为兼容层，实际逻辑已迁移至 app.services.contract_review
import sys
import os

# 确保能找到 app 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 引入新的图构建函数
from app.services.contract_review.graph import build_contract_review_graph

def run_contract_review(text: str, metadata: dict, stance: str = "甲方"):
    """
    统一入口函数：供 app.py 调用
    """
    # 1. 获取编译好的图
    graph = build_contract_review_graph()
    
    # 2. 配置线程 ID (用于区分不同的审查任务)
    # 在实际生产中，这里应该由前端传来的 contract_id 决定，例如: f"review_{contract_id}"
    thread_config = {"configurable": {"thread_id": "review_v2_demo"}}
    
    # 3. 构造初始状态
    initial_input = {
        "contract_text": text,
        "metadata": metadata,
        "stance": stance,
        "status": "started",
        # 初始化中间字段为空，防止报错
        "contract_profile": None,
        "legal_relationships": None,
        "review_result": None
    }
    
    print("🚀 [V2] 合同审查服务启动...")
    
    # 4. 执行流程 (Stream 模式)
    # 循环执行直到遇到中断点 (human_gate) 或结束
    for event in graph.stream(initial_input, thread_config):
        pass 
    
    # 5. 获取当前状态快照
    final_state = graph.get_state(thread_config)
    
    # 6. 返回结果给 API
    # 此时如果刚过 ai_reviewer，human_gate 还没跑，但 review_result 已经生成了
    return final_state.values.get("review_result"), final_state.values.get("final_output")