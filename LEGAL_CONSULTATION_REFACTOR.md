# 法律咨询模块 - LangGraph 重构说明

## 架构概述

本次重构将智能咨询模块从硬编码模板改为真正的 **LangGraph 工作流架构**，实现了两阶段 AI 咨询流程。

## 架构对比

### 重构前（模板化）- 存在的问题

```
用户问题 → 关键词匹配 → 硬编码模板 → 固定回复
```

**问题**：
1. **完全未使用大模型**：`generate_legal_advice()` 函数使用硬编码字符串
2. **回复千篇一律**：无论问题多复杂，都返回相同的模板建议
3. **无法分析具体案情**：对于复杂的法律关系梳理需求，只能返回通用建议
4. **分类逻辑简单**：仅基于关键词匹配，无法理解语义

### 重构后（LangGraph 工作流）- 真正的智能

```
用户问题 → 律师助理节点（LLM分类）→ 专业律师节点（LLM咨询）→ 结构化输出
```

**优势**：
1. **真正的 AI 驱动**：每个节点都调用 LLM 进行分析和生成
2. **角色扮演机制**：律师助理 + 专业律师两阶段处理
3. **针对性建议**：根据具体案情提供个性化的法律建议
4. **语义理解**：使用 LLM 进行问题分类，而非简单关键词匹配

---

## 工作流设计

### 流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     用户输入（问题 + 上下文）                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  节点1：律师助理 (assistant_node)                              │
│  - 职责：问题分类、意图识别、信息提取                            │
│  - 输入：question, context                                     │
│  - 输出：classification_result, specialist_role               │
│  - LLM：使用结构化提示词，要求返回 JSON 格式                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                    ┌───────┴────────┐
                    │  条件路由        │
                    │  (检查分类结果)  │
                    └───────┬────────┘
                            │
                ┌───────────┴──────────┐
                │ 是否成功分类？         │
                └───────────┬──────────┘
                            │
               ┌────────────┴────────────┐
               │                         │
          [YES]                       [NO]
               │                         │
               ▼                         ▼
┌──────────────────────────┐    ┌─────────────┐
│  节点2：专业律师           │    │    END      │
│  (specialist_node)        │    │  (返回错误)  │
│  - 职责：提供专业法律咨询   │    └─────────────┘
│  - 输入：问题 + 分类结果    │
│  - 输出：结构化法律建议      │
│  - LLM：使用专业角色提示词   │
└──────────────────┬────────┘
                   │
                   ▼
          ┌────────────────┐
          │      END        │
          │  (返回最终报告)  │
          └────────────────┘
```

### 状态定义

```python
class ConsultationState(TypedDict):
    # 输入
    question: str                          # 用户问题
    context: Dict[str, Any]                # 上下文（文件内容等）
    conversation_history: List[BaseMessage]  # 对话历史

    # 律师助理节点输出
    classification_result: Optional[Dict]  # 分类结果
    specialist_role: Optional[str]         # 专业律师角色
    confidence: Optional[float]            # 置信度

    # 专业律师节点输出
    legal_analysis: Optional[str]          # 法律分析
    legal_advice: Optional[str]            # 法律建议
    risk_warning: Optional[str]            # 风险提醒
    action_steps: Optional[List[str]]      # 行动步骤
    relevant_laws: Optional[List[str]]     # 相关法律

    # 最终输出
    final_report: Optional[str]            # 最终报告
    error: Optional[str]                   # 错误信息
```

---

## 节点详解

### 节点1：律师助理 (assistant_node)

**职责**：
- 识别问题的法律领域（合同法、劳动法、公司法、建工法等）
- 提取关键事实和当事人
- 评估问题的紧急程度和复杂程度
- 确定应该由哪位专业律师处理

**LLM 提示词策略**：
```python
ASSISTANT_SYSTEM_PROMPT = """
你是一位经验丰富的律师事务所前台助理...

请按以下 JSON 格式返回分析结果：
{
    "primary_type": "法律领域名称",
    "specialist_role": "专业律师角色",
    "confidence": 0.85,
    "urgency": "high/medium/low",
    "complexity": "simple/medium/complex",
    "key_entities": ["关键当事人"],
    "key_facts": ["关键事实"],
    "relevant_laws": ["相关法律"],
    "preliminary_assessment": "初步评估"
}
"""
```

**JSON 解析**：
- 使用正则表达式提取 JSON 代码块
- 提供默认值作为降级方案
- 错误处理确保流程不中断

### 节点2：专业律师 (specialist_node)

**职责**：
- 根据律师助理的分类结果，扮演相应的专业律师角色
- 提供具体、可操作的法律建议
- 引用相关法律条文
- 评估法律风险
- 提供行动步骤

**角色扮演机制**：
```python
SPECIALIST_SYSTEM_PROMPT_TEMPLATE = """
你是一位{specialist_role}，拥有15年执业经验的资深律师。

专业背景：
- 15年执业经验，处理过500+法律案件
- 专注领域：{legal_domain}
- 具备律师资格证和法学硕士学位
...
"""
```

**关键设计**：
- 使用 `{specialist_role}` 和 `{legal_domain}` 动态生成提示词
- 明确要求**不使用模板化语言**
- 要求提供**具体的行动步骤**而非通用建议
- 使用正则表达式解析结构化输出

---

## LLM 配置优先级

```python
def get_consultation_llm() -> ChatOpenAI:
    # 优先级1：Qwen3-Thinking（深度思考）
    try:
        return get_qwen3_thinking_llm()
    except Exception:
        # 优先级2：DeepSeek（性价比高）
        try:
            return get_deepseek_llm()
        except Exception:
            # 优先级3：默认 OpenAI 配置
            return get_default_llm()
```

---

## API 接口

### 请求

```http
POST /api/consultation
Content-Type: application/json

{
    "question": "公司设立法律要求",
    "context": {},
    "uploaded_files": ["file_id_1", "file_id_2"]
}
```

### 响应

```json
{
    "answer": "# 法律咨询报告\n\n...",
    "specialist_role": "公司法律师",
    "primary_type": "公司法",
    "confidence": 0.9,
    "relevant_laws": ["《中华人民共和国公司法》"],
    "need_confirmation": true
}
```

---

## 测试方法

### 1. 直接测试工作流

```bash
python test_langgraph_consultation.py
```

### 2. 通过 API 测试

```bash
curl -X POST http://localhost:8000/api/consultation \
  -H "Content-Type: application/json" \
  -d '{"question": "公司设立法律要求"}'
```

### 3. 测试用例

| 测试场景 | 预期行为 |
|---------|---------|
| 简单问题（如"公司设立"） | 正确识别为公司法，提供具体建议 |
| 复杂建工纠纷 | 识别为建工法，分析两种方案的优劣 |
| 劳动纠纷 | 识别为劳动法，提供仲裁建议 |
| 文件上传 | 分析文件内容，提供针对性建议 |

---

## 关键改进

### 1. 消除模板化

**之前**：
```
分析：这属于公司法律事务。涉及公司治理、股东权益、投资融资等方面。
建议：1) 查阅公司章程和相关文件；2) 明确法律关系和权利义务...
```

**之后**（LLM 生成）：
```
分析：您咨询的是公司设立的法律要求。根据《中华人民共和国公司法》规定，
设立公司需要满足以下条件：1) 股东符合法定人数；2) 有符合公司章程规定的...
建议：1. 确定公司类型和名称（建议准备3-5个备选名称）；2. 确定注册资本...
```

### 2. 针对性分析

**之前**：无法分析复杂的法律关系

**之后**：能够梳理复杂的法律关系，对比不同方案的优劣

### 3. 智能分类

**之前**：简单的关键词匹配

**之后**：LLM 语义理解，能够识别复杂问题的主要领域

---

## 文件清单

| 文件 | 说明 |
|------|------|
| [backend/legal_consultation_graph.py](backend/legal_consultation_graph.py) | LangGraph 工作流实现（核心） |
| [backend/app/api/consultation_router.py](backend/app/api/consultation_router.py) | API 路由层 |
| [test_langgraph_consultation.py](test_langgraph_consultation.py) | 测试文件 |
| [backend/app/core/llm_config.py](backend/app/core/llm_config.py) | LLM 配置管理 |
| [backend/app/services/deepseek_service.py](backend/app/services/deepseek_service.py) | DeepSeek 服务（备用） |

---

## 常见问题

### Q1: 为什么不直接使用 deepseek_service.py？

**A**: `deepseek_service.py` 是直接的单次 LLM 调用，而 LangGraph 工作流提供了：
- 状态管理（在节点间传递数据）
- 条件路由（根据结果决定下一步）
- 可扩展性（易于添加新节点）
- 可观测性（每个节点的执行都可以被监控）

### Q2: LLM 调用失败会怎样？

**A**:
1. 律师助理节点失败 → 设置默认分类，继续流程
2. 专业律师节点失败 → 返回错误信息，不中断服务
3. 整体流程失败 → API 返回 500 错误，记录日志

### Q3: 如何调试工作流？

**A**:
```python
# 开启日志
import logging
logging.basicConfig(level=logging.INFO)

# 查看状态
result_state = await graph.ainvoke(initial_state)
print(result_state["current_step"])  # 当前步骤
print(result_state.get("error"))     # 错误信息
```

### Q4: 如何添加新的节点？

**A**:
```python
# 1. 定义节点函数
async def new_node(state: ConsultationState) -> ConsultationState:
    # ... 处理逻辑
    return state

# 2. 添加到工作流
workflow.add_node("new_node", new_node)

# 3. 添加边
workflow.add_edge("specialist", "new_node")
workflow.add_edge("new_node", END)
```

---

## 后续优化建议

1. **添加记忆节点**：支持多轮对话
2. **添加检索节点**：结合 RAG 检索相关法条和案例
3. **添加验证节点**：检查建议的法律准确性
4. **添加人工审核**：对于复杂案件，支持人工介入
5. **性能优化**：缓存常见问题的分类结果
