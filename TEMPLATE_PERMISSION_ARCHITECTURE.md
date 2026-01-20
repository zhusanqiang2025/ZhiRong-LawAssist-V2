# 合同模板双重权限架构

## 概述

本系统采用**两类合同模板**的权限架构，明确区分管理员公开模板和用户私有模板的使用场景和权限控制。

---

## 一、模板分类

### 1. 一类模板：管理员公开模板

**标识**：`is_public = True`

**权限特征**：
- **上传权限**：仅管理员可上传
- **可见范围**：所有用户可见
- **模糊查询**：✅ 所有用户可查询
- **直接下载**：✅ 所有用户可下载
- **合同生成**：✅ 可作为AI改写依据
- **增删改查**：❌ 仅管理员权限

**使用场景**：
- 标准化的高频合同模板
- 经过法律审查的专业模板
- 适用于大多数用户的通用模板
- 需要AI生成合同时的基础模板

**数据库存储**：
```python
ContractTemplate(
    is_public=True,           # 公开标识
    owner_id=admin_id,        # 管理员ID
    primary_contract_type="买卖合同",
    transaction_nature="转移所有权",
    contract_object="货物",
    # ... 其他V2特征
)
```

**ChromaDB索引**：
```python
# 存储在公共集合
collection_name = "contract_templates_public"
vector_store.add_template(
    template_id=template.id,
    is_public=True,
    user_id=None  # 公共集合不需要user_id
)
```

---

### 2. 二类模板：用户私有模板

**标识**：`is_public = False`

**权限特征**：
- **上传权限**：所有用户可上传
- **可见范围**：仅上传者可见
- **模糊查询**：✅ 仅上传者可查询
- **直接下载**：✅ 仅上传者可下载
- **合同生成**：❌ 不能作为AI改写依据
- **增删改查**：✅ 上传者可管理自己的模板

**使用场景**：
- 用户个人的合同草稿
- 企业内部定制模板
- 不适合公开的敏感合同
- 个人参考使用的合同模板

**数据库存储**：
```python
ContractTemplate(
    is_public=False,          # 私有标识
    owner_id=user_id,         # 普通用户ID
    primary_contract_type="劳动合同",
    # ... 其他字段
)
```

**ChromaDB索引**：
```python
# 存储在用户私有集合
collection_name = f"contract_templates_user_{user_id}"
vector_store.add_template(
    template_id=template.id,
    is_public=False,
    user_id=user_id  # 私有集合需要user_id
)
```

---

## 二、权限矩阵

| 操作 | 公开模板 | 私有模板 |
|------|---------|---------|
| **上传** | 仅管理员 | 所有用户 |
| **查看** | 所有用户 | 仅所有者 |
| **下载** | 所有用户 | 仅所有者 |
| **编辑** | 仅管理员 | 所有者+管理员 |
| **删除** | 仅管理员 | 所有者+管理员 |
| **模糊查询** | 所有用户 | 仅所有者 |
| **合同生成** | ✅ 可用 | ❌ 不可用 |

---

## 三、工作流程

### 流程1：模糊查询模板

```
用户输入查询文本
    ↓
TemplateRetriever.retrieve(query, user_id)
    ↓
ChromaDB 向量检索 + BGE-Rerank 重排序
    ↓
权限过滤 _filter_by_permission()
    ├─ is_public=True → 所有用户可见
    └─ is_public=False AND owner_id=user_id → 仅所有者可见
    ↓
返回匹配结果（公开模板 + 用户私有模板）
```

**代码实现**：
```python
# backend/app/services/contract_generation/rag/template_retriever.py:376-408
def _filter_by_permission(self, templates, user_id):
    filtered = []
    for template in templates:
        if template.is_public:
            # 公开模板，所有人可见
            filtered.append(template)
        elif template.owner_id == user_id:
            # 用户的私有模板
            filtered.append(template)
        # else: 其他用户的私有模板，不可见
    return filtered
```

---

### 流程2：合同生成

```
用户输入需求
    ↓
需求分析（提取V2特征）
    ↓
结构化模板匹配 match_template(user_id=None)
    ↓
PostgreSQL 精确过滤
    ├─ WHERE is_public = TRUE  ← 仅公开模板
    ├─ AND primary_contract_type = ?
    ├─ AND transaction_nature = ?
    └─ AND contract_object = ?
    ↓
加载模板文件
    ↓
AI 改写生成合同
    ↓
返回生成的合同
```

**代码实现**：
```python
# backend/app/services/contract_generation/workflow.py:253-278
async def match_template(state):
    """
    【第二层】结构化模板匹配

    重要：合同生成仅使用管理员公开模板 (is_public=True)
    用户私有模板不参与AI合同生成，仅用于个人查询和下载
    """
    matcher = get_structural_matcher(db)

    # user_id=None 确保只匹配公开模板
    match_result = matcher.match(
        state["analysis_result"],
        user_id=None  # None = 仅匹配公开模板
    )
```

**SQL查询**：
```python
# backend/app/services/contract_generation/structural/__init__.py:93-117
query = self.db.query(ContractTemplate).filter(
    ContractTemplate.status == "active",
    ContractTemplate.primary_contract_type == primary_type,
    ContractTemplate.is_public.is_(True)  # 仅公开模板
)

# user_id=None 时，不包含用户私有模板
candidates = query.all()
```

---

### 流程3：模板管理

#### 管理员操作

```
管理员后台
    ├─ 上传公开模板
    │   ├─ 设置 is_public=True
    │   └─ owner_id=admin_id
    ├─ 编辑任何模板
    ├─ 删除任何模板
    └─ 查看所有模板（公开+私有）
```

**权限验证**：
```python
# backend/app/api/v1/endpoints/contract_templates.py:114-119
# 上传公开模板
if is_public and not current_user.is_admin:
    raise HTTPException(
        status_code=403,
        detail="只有管理员可以上传公开模板"
    )
```

#### 普通用户操作

```
普通用户界面
    ├─ 上传私有模板
    │   ├─ 设置 is_public=False
    │   └─ owner_id=current_user.id
    ├─ 管理自己的模板
    │   ├─ 编辑：仅自己的私有模板
    │   └─ 删除：仅自己的私有模板
    └─ 查询模板
        ├─ 公开模板（只读）
        └─ 自己的私有模板（完全控制）
```

**权限验证**：
```python
# backend/app/api/v1/endpoints/contract_templates.py:597-605
# 删除模板
if template.is_public:
    # 公开模板仅管理员可删除
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以删除公开模板")
else:
    # 私有模板：所有者或管理员可删除
    if template.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权删除此模板")
```

---

## 四、数据库设计

### ContractTemplate 表关键字段

```sql
CREATE TABLE contract_templates (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),

    -- 权限控制字段
    is_public BOOLEAN DEFAULT FALSE,
    owner_id INTEGER REFERENCES users(id),

    -- V2 四维法律特征
    transaction_nature VARCHAR(100),
    contract_object VARCHAR(100),
    complexity VARCHAR(50),
    stance VARCHAR(50),

    -- 结构锚点字段
    primary_contract_type VARCHAR(100),
    delivery_model VARCHAR(50),
    payment_model VARCHAR(50),
    risk_level VARCHAR(20),
    is_recommended BOOLEAN DEFAULT FALSE,

    -- 其他字段...
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 索引
CREATE INDEX idx_is_public ON contract_templates(is_public);
CREATE INDEX idx_owner_id ON contract_templates(owner_id);
CREATE INDEX idx_primary_type ON contract_templates(primary_contract_type);
CREATE INDEX idx_transaction_nature ON contract_templates(transaction_nature);
```

---

## 五、API端点权限

### 1. 上传模板

```
POST /api/v1/contract/upload

权限验证：
- is_public=True → 仅管理员
- is_public=False → 所有用户
```

### 2. 查询模板

```
GET /api/v1/contract/?scope={public|private|all}

权限规则：
- scope=public → 返回所有公开模板
- scope=private → 返回当前用户的私有模板
- scope=all → 返回公开模板 + 当前用户的私有模板
```

### 3. 更新模板

```
PUT /api/v1/contract/{template_id}

权限规则：
- is_public=True → 仅管理员可编辑
- is_public=False → 所有者或管理员可编辑
```

### 4. 删除模板

```
DELETE /api/v1/contract/{template_id}

权限规则：
- is_public=True → 仅管理员可删除
- is_public=False → 所有者或管理员可删除
```

### 5. V2特征更新

```
PUT /api/v1/contract/{template_id}/v2-features

权限：仅管理员可更新V2法律特征
```

---

## 六、前端界面

### 1. 模板列表显示

```
┌─────────────────────────────────────────────┐
│ 名称   │ 类型 │ V2特征 │ 权限 │ 操作       │
├─────────────────────────────────────────────┤
│ 买卖合 │买卖合│ [标签] │🟢公开│ [V2] [删除]│
│ 同模板 │ 同   │        │可用于│           │
│        │      │        │AI生成│           │
├─────────────────────────────────────────────┤
│ 劳动合 │劳动合│ [标签] │🟠私有│ [V2] [删除]│
│ 同草稿 │ 同   │        │仅个人│           │
│        │      │        │使用  │           │
└─────────────────────────────────────────────┘
```

### 2. 上传表单权限设置

```tsx
<Form.Item
  name="is_public"
  label="权限设置"
  tooltip="公开模板可供所有用户查询和AI生成使用，仅管理员可上传"
>
  <Select disabled={!currentUser?.is_admin}>
    <Option value={false}>
      <Tag color="orange">私有</Tag> 仅自己可见
    </Option>
    <Option value={true}>
      <Tag color="green">公开</Tag> 所有用户可见 + 可用于AI生成
    </Option>
  </Select>
</Form.Item>
```

**UI逻辑**：
- 管理员：可选择"公开"或"私有"
- 普通用户：只能选择"私有"，"公开"选项禁用

---

## 七、安全考虑

### 1. 防止权限提升

```python
# API层验证
if is_public and not current_user.is_admin:
    raise HTTPException(status_code=403)

# 数据库层验证
query = query.filter(
    (ContractTemplate.is_public.is_(True)) |
    (ContractTemplate.owner_id == current_user.id)
)
```

### 2. 合同生成隔离

```python
# 合同生成强制使用 user_id=None
match_result = matcher.match(
    state["analysis_result"],
    user_id=None  # 确保不包含私有模板
)
```

### 3. 向量索引隔离

```python
# ChromaDB 分集合存储
public_collection = "contract_templates_public"
private_collection = f"contract_templates_user_{user_id}"

# 检索时也分集合
results = vector_store.search_multi_collection(
    query=query,
    include_public=True,
    include_private=(user_id is not None)
)
```

---

## 八、使用建议

### 对于管理员

1. **公开模板选择**：
   - 只上传标准化、高质量的合同模板
   - 确保V2四维法律特征完整
   - 设置适当的推荐级别和风险等级

2. **质量控制**：
   - 定期审查公开模板的V2特征完整性
   - 监控公开模板的下载量和评分
   - 及时更新或删除过时的模板

### 对于普通用户

1. **私有模板使用**：
   - 用于保存个人合同草稿
   - 存储企业定制模板
   - 作为个人参考资料

2. **查询策略**：
   - 优先使用公开模板进行AI生成
   - 私有模板仅作个人参考
   - 可以下载公开模板后修改为私有版本

---

## 九、总结

**核心原则**：
- ✅ 公开模板：全局资源，用于AI生成和所有用户查询
- ✅ 私有模板：个人资源，仅用于个人查询和下载，不参与AI生成
- ✅ 权限隔离：数据库、API、ChromaDB三层权限控制
- ✅ 安全第一：防止权限提升和数据泄露

**架构优势**：
1. **明确的使用边界**：公开模板用于AI生成，私有模板用于个人参考
2. **细粒度权限控制**：上传、查看、编辑、删除分级管理
3. **性能优化**：ChromaDB分集合存储，检索效率高
4. **可扩展性**：易于扩展新的权限类型和功能

---

**文档版本**：v1.0
**更新日期**：2025-01-09
**维护者**：Legal Document Assistant Team
