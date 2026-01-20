# Legal Document Assistant V3 - 三层合同生成架构优化总结

## 优化完成时间
2026-01-08

## 优化背景

之前系统在合同模板匹配上存在核心问题：
- ❌ 使用 `similarity_score * x + rerank * y` "总能选一个模板"
- ❌ 缺少结构化匹配逻辑
- ❌ 模板不是生成起点，而是被错误地当作"生成输入"

## 优化目标

将合同模板定位为：
1. **结构锚点（Structure Anchor）** - 用于结构匹配
2. **合规参考（Compliance Reference）** - 用于合规审查

## 优化成果

### ✅ 第一层：合同类型与交易结构判定（Analysis Layer）

**位置**：[`requirement_analyzer.py`](app/services/contract_generation/agents/requirement_analyzer.py)

**功能**：
- 识别主合同类型（10种典型合同）
- 识别次要合同类型（复合合同）
- 判定交付模型（单一/分期/持续/复合）
- 判定付款模型（一次性/分期/定期/混合）
- 判定风险等级（低/中/高）

**输出示例**：
```json
{
  "contract_classification": {
    "primary_type": "建设工程合同",
    "secondary_types": ["买卖合同"]
  },
  "transaction_structure": {
    "delivery_model": "复合交付",
    "payment_model": "混合模式",
    "risk_level": "中"
  }
}
```

**关键点**：❗这一层不允许出现模板 ID，这是一个"法律识别问题"，不是检索问题。

---

### ✅ 第二层：模板"候选池"过滤（Structural Filtering Layer）

**位置**：[`template_matcher.py`](app/services/contract_generation/structural/__init__.py)

**功能**：
- 基于第一层的输出，进行结构化匹配
- 不再使用向量相似度"总能选一个"
- 如果没有结构匹配，返回 `NO_TEMPLATE`

**匹配级别**：
- `HIGH`（≥0.75）：高度匹配，可直接用于模板填充
- `STRUCTURAL`（0.4–0.75）：结构一致，仅用于结构参考
- `NONE`（<0.4）：不匹配，不使用模板

**数据库模型升级**：[`contract_template.py`](app/models/contract_template.py)

新增字段：
```python
primary_contract_type      # 主合同类型（必填）
secondary_types             # 次要合同类型（数组）
delivery_model             # 交付模型（必填）
payment_model              # 付款模型
industry_tags              # 行业标签
allowed_party_models       # 允许的签约主体
risk_level                 # 风险等级
is_recommended             # 推荐级别
```

**输出示例**：
```json
{
  "match_level": "high",
  "template_id": "xxx",
  "template_name": "设备供货与安装合同",
  "match_reason": "找到高度匹配的模板",
  "structural_differences": []
}
```

---

### ✅ 第三层：生成策略选择（Generation Strategy Layer）

**位置**：[`generation_strategy.py`](app/services/contract_generation/strategy/__init__.py)

**功能**：
- 基于第一层和第二层的结果，选择最合适的生成策略
- 这是"成熟系统"和"玩具系统"的分水岭

**三种生成策略**：

| 场景 | 系统行为 | 预期质量 |
|------|----------|----------|
| 找到高度匹配模板（HIGH） | 模板填充 + AI 审查 | 0.85 |
| 只有结构一致模板（STRUCTURAL） | 生成新合同 + 模板对照 | 0.75 |
| 无模板（NONE） | 纯条款骨架生成 | 0.65 |

**输出示例**：
```json
{
  "generation_type": "template_based",
  "template_id": "xxx",
  "template_name": "设备供货与安装合同",
  "reasoning": "找到高度匹配的模板，将使用模板填充方式生成合同",
  "expected_quality": 0.85,
  "requires_review": false
}
```

---

### ✅ LangGraph 工作流升级

**位置**：[`workflow.py`](app/services/contract_generation/workflow.py)

**新流程**：
```
用户输入
  → 【第一层】需求分析（analyze_requirement）
  → 【第二层】模板匹配（match_template）
  → 【第三层】策略选择（select_strategy）
  → 合同起草（draft_single_contract）
  → 返回结果
```

**状态更新**：
```python
class ContractGenerationState(TypedDict):
    # 第一层：需求分析结果
    analysis_result: Optional[Dict]

    # 第二层：模板匹配结果
    template_match_result: Optional[Dict]

    # 第三层：生成策略
    generation_strategy: Optional[Dict]
```

**节点更新**：
- `analyze_requirement` - 第一层节点
- `match_template` - 第二层节点（新增）
- `select_generation_strategy` - 第三层节点（新增）
- `draft_single_contract` - 根据策略选择不同的起草方式

---

## 数据库迁移

### SQL 迁移脚本
**位置**：[`migrations/add_structural_anchor_fields.sql`](migrations/add_structural_anchor_fields.sql)

### 模型更新脚本
**位置**：[`scripts/update_template_models.py`](scripts/update_template_models.py)

**执行步骤**：
1. 运行 SQL 迁移脚本添加新字段
2. 运行模型更新脚本为现有模板设置默认值

```bash
# 1. SQL 迁移
mysql -u root -p legal_doc_assistant < migrations/add_structural_anchor_fields.sql

# 2. 模型更新
cd backend
python -m scripts.update_template_models
```

---

## 核心改进点

### 1. 模板定位转变
- ❌ 旧：模板是"从300份文件里找一个最像的"
- ✅ 新：模板是"结构锚点"和"合规参考"

### 2. 匹配逻辑转变
- ❌ 旧：`similarity_score * x + rerank * y` 总能选一个
- ✅ 新：基于结构锚点的严格匹配，不匹配则返回 `NO_TEMPLATE`

### 3. 生成策略多样化
- ❌ 旧：只有一种"模板填充"方式
- ✅ 新：三种策略（模板填充、混合模式、纯AI生成）

### 4. 透明度提升
- ❌ 旧：用户不知道为什么选择了某个模板
- ✅ 新：每层都有详细的 `reasoning` 和 `match_reason`

---

## 待完成的工作

### TODO: 实现基于模板的填充逻辑
位置：[`workflow.py:269`](app/services/contract_generation/workflow.py#L269)

需要实现：
1. 读取模板文件内容
2. 识别模板中的占位符
3. 根据用户需求填充占位符
4. AI 审查填充后的内容

### TODO: 实现混合模式逻辑
位置：[`workflow.py:281`](app/services/contract_generation/workflow.py#L281)

需要实现：
1. AI 生成新合同内容
2. 与模板进行结构对照
3. 标注差异部分
4. 提供修改建议

### TODO: 实现纯条款骨架生成
位置：[`workflow.py:297`](app/services/contract_generation/workflow.py#L297)

需要实现：
1. 基于合同类型的法律要素
2. 生成标准条款骨架
3. 填充用户提供的具体信息
4. 添加法律风险提示

---

## 文件清单

### 新增文件
1. `app/services/contract_generation/structural/__init__.py` - 结构化模板匹配服务
2. `app/services/contract_generation/strategy/__init__.py` - 生成策略选择服务
3. `migrations/add_structural_anchor_fields.sql` - 数据库迁移脚本
4. `scripts/update_template_models.py` - 模型更新脚本

### 修改文件
1. `app/models/contract_template.py` - 添加结构锚点字段
2. `app/services/contract_generation/workflow.py` - 升级 LangGraph 工作流

### 无需修改的文件
1. `app/services/contract_generation/agents/requirement_analyzer.py` - 已正确实现第一层
2. 其他 RAG 相关文件 - 仍可用于模板检索，但不再是核心流程

---

## 架构对比

### 旧架构（单层）
```
用户输入 → 模板检索（向量相似度）→ 模板填充 → 返回结果
```

**问题**：
- 模板检索不够准确
- 没有考虑结构匹配
- 总是强制使用模板

### 新架构（三层）
```
用户输入
  → 【第一层】合同类型识别（法律问题）
  → 【第二层】结构匹配（结构锚点）
  → 【第三层】策略选择（生成策略）
  → 合同生成
  → 返回结果
```

**优势**：
- 每层职责明确
- 可以选择不使用模板
- 生成策略多样化
- 透明度高，可解释性强

---

## 总结

这次优化完成了从"玩具系统"到"成熟系统"的核心转变：

1. ✅ **模板定位转变** - 从"生成输入"到"评估坐标系"
2. ✅ **三层架构实现** - Analysis → Structural → Strategy
3. ✅ **数据库模型升级** - 添加结构锚点字段
4. ✅ **LangGraph 工作流升级** - 添加模板匹配和策略选择节点
5. ✅ **透明度提升** - 每层都有详细的 reasoning

下一步需要完善三种生成策略的具体实现。
