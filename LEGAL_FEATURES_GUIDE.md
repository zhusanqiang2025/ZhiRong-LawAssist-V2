# 法律特征库使用说明

## 📌 概述

您之前提出的核心问题是：**在这个分类体系下，系统是如何利用模板来生成合同的？是通过分类找合同，还是通过合同内容找合同？**

**答案：现在是双重检索机制。**

---

## 🔄 系统工作流程（优化后）

### 用户输入："我要买房子"

```
用户输入
   ↓
┌─────────────────────────────────────────────────┐
│          混合检索引擎（新增）                    │
├─────────────────────────────────────────────────┤
│  1️⃣ 分类关键词检索（快速）                       │
│     "买房子" → 匹配到 "房屋买卖" 分类            │
│     ↓                                           │
│     推荐分类：买卖合同 > 房屋买卖                │
│     V2特征：转移所有权 + 不动产                  │
├─────────────────────────────────────────────────┤
│  2️⃣ V2特征提取与反向检索（精准）                │
│     LLM分析："买房子" →                          │
│     - 交易性质：转移所有权                        │
│     - 标的：不动产                               │
│     - 复杂度：复杂                               │
│     ↓                                           │
│     反向匹配：房屋买卖（置信度95%）               │
├─────────────────────────────────────────────────┤
│  3️⃣ RAG向量检索（语义兜底）                      │
│     "买房子" 向量 → 在模板库中搜索                │
│     找到语义最相似的模板                         │
└─────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────┐
│           结果融合与排序                         │
├─────────────────────────────────────────────────┤
│  • 分类匹配：房屋买卖（权重+0.5）                 │
│  • 特征匹配：房屋买卖（权重+0.4）                 │
│  • 向量相似度：模板A 0.85, 模板B 0.78            │
├─────────────────────────────────────────────────┤
│  最终推荐：                                      │
│  1. 房屋买卖合同模板.docx                        │
│  2. 二手房买卖合同模板.docx                       │
│  3. 商品房购房合同模板.docx                       │
└─────────────────────────────────────────────────┘
   ↓
使用模板内容 + 用户信息 → 生成合同
```

---

## 🗂️ 分类-特征映射库

### 核心概念

**分类-特征映射**建立了合同分类与V2四维法律特征的对应关系：

| 合同分类 | 交易性质 | 标的 | 复杂度 | 立场 | 典型场景 |
|---------|---------|------|--------|------|---------|
| 买卖合同 > 货物买卖 | 转移所有权 | 货物 | 中等 | 平衡 | 普通商品交易 |
| 买卖合同 > 房屋买卖 | 转移所有权 | 不动产 | 复杂 | 平衡 | 房屋所有权转让 |
| 借款合同 | 融资借贷 | 资金 | 中等 | 甲方（出借人） | 民间借贷 |
| 劳动合同 | 劳动用工 | 劳动力 | 中等 | 平衡 | 建立劳动关系 |
| 租赁合同 > 房屋租赁 | 许可使用 | 不动产 | 中等 | 平衡 | 房屋出租 |

### 数据结构

```python
CategoryFeatureMapping:
  - category: "买卖合同"              # 一级分类
  - subcategory: "房屋买卖"           # 二级分类
  - v2_features:
      - transaction_nature: "转移所有权"
      - contract_object: "不动产"
      - complexity: "复杂"
      - stance: "平衡"
  - keywords: ["房子", "房产", "购房", "不动产"]
  - aliases: ["房屋买卖合同", "购房合同", "二手房合同"]
  - usage_scenario: "适用于房屋所有权转让..."
```

---

## 🛠️ API 接口

### 1. 获取所有分类-特征映射

```bash
GET /api/v1/legal-features/mappings
```

**响应示例：**
```json
[
  {
    "category": "买卖合同",
    "subcategory": "房屋买卖",
    "v2_features": {
      "transaction_nature": "转移所有权",
      "contract_object": "不动产",
      "complexity": "复杂",
      "stance": "平衡",
      "confidence": 1.0
    },
    "keywords": ["房子", "房产", "购房"],
    "aliases": ["房屋买卖合同", "购房合同"],
    "usage_scenario": "适用于房屋所有权转让..."
  }
]
```

### 2. 根据关键词搜索分类

```bash
POST /api/v1/legal-features/search-by-keywords
Content-Type: application/json

{
  "query": "房屋买卖"
}
```

**响应示例：**
```json
[
  {
    "category": "买卖合同",
    "subcategory": "房屋买卖",
    "v2_features": {...},
    "match_reason": "关键词完全匹配"
  }
]
```

### 3. 根据V2特征反向搜索分类

**场景**：LLM提取用户需求的特征后，反向推荐分类

```bash
POST /api/v1/legal-features/search-by-features
Content-Type: application/json

{
  "transaction_nature": "转移所有权",
  "contract_object": "不动产",
  "complexity": "复杂",
  "stance": "平衡"
}
```

**响应示例：**
```json
[
  {
    "category": "买卖合同",
    "subcategory": "房屋买卖",
    "v2_features": {...},
    "confidence": 0.95
  }
]
```

### 4. 获取所有一级分类

```bash
GET /api/v1/legal-features/categories
```

**响应：** ["买卖合同", "建设工程合同", "借款合同", ...]

### 5. 获取子分类列表

```bash
GET /api/v1/legal-features/categories/买卖合同/subcategories
```

**响应：** ["货物买卖", "设备买卖", "房屋买卖"]

---

## 💡 使用场景

### 场景1：前端分类选择器

```javascript
// 前端代码示例
const { data: categories } = await fetch('/api/v1/legal-features/categories').then(r => r.json());

// 渲染一级分类下拉框
<select>
  {categories.map(cat => (
    <option key={cat} value={cat}>{cat}</option>
  ))}
</select>
```

### 场景2：智能分类推荐

```javascript
// 用户输入："我要买房子"
const userQuery = "我要买房子";

// 1. 关键词匹配（快速）
const keywordResults = await fetch('/api/v1/legal-features/search-by-keywords', {
  method: 'POST',
  body: JSON.stringify({ query: userQuery })
}).then(r => r.json());

// 返回：[{category: "买卖合同", subcategory: "房屋买卖"}]

// 2. 特征提取与反向匹配（精准，需要LLM）
const features = await extractV2Features(userQuery);
// 返回：{transaction_nature: "转移所有权", contract_object: "不动产"}

const featureResults = await fetch('/api/v1/legal-features/search-by-features', {
  method: 'POST',
  body: JSON.stringify(features)
}).then(r => r.json());

// 返回：[{category: "买卖合同", subcategory: "房屋买卖", confidence: 0.95}]
```

### 场景3：模板上传时的特征自动填充

```javascript
// 管理员上传"房屋买卖合同.docx"
// 系统自动：
const file = selectedFile;
const category = "买卖合同";
const subcategory = "房屋买卖";

// 从映射库获取对应的V2特征
const mapping = await fetch(`/api/v1/legal-features/mappings/${category}?subcategory=${subcategory}`)
  .then(r => r.json());

// 自动填充到表单
form.setFieldsValue({
  category: mapping.category,
  subcategory: mapping.subcategory,
  transaction_nature: mapping.v2_features.transaction_nature,
  contract_object: mapping.v2_features.contract_object,
  complexity: mapping.v2_features.complexity,
  stance: mapping.v2_features.stance
});
```

---

## 📝 扩展分类库

### 方法1：代码配置（推荐）

编辑 `backend/app/services/legal_features/category_feature_mapping.py`：

```python
self.add_mapping(CategoryFeatureMapping(
    category="您的合同分类",
    subcategory="子分类（可选）",
    v2_features=V2Features(
        transaction_nature=TransactionNature.ASSET_TRANSFER,
        contract_object=ContractObject.TANGIBLE_GOODS,
        complexity=Complexity.STANDARD,
        stance=Stance.BALANCED
    ),
    primary_contract_type="您的主合同类型",
    keywords=["关键词1", "关键词2"],
    aliases=["别名1", "别名2"],
    usage_scenario="使用场景说明"
))
```

### 方法2：数据库管理（未来）

可以创建管理界面，通过API动态增删改查。

---

## 🎯 回答您的核心问题

### Q1: 系统是通过分类找合同，还是通过内容找合同？

**A: 两者结合，双重检索。**

1. **快速路径（分类检索）**：
   - 用户输入关键词 → 匹配分类库 → 直接定位到对应分类的模板

2. **精准路径（特征检索）**：
   - LLM提取V2特征 → 反向匹配分类 → 找到最符合特征的模板

3. **兜底路径（RAG向量检索）**：
   - 向量化用户输入 → 在所有模板中搜索语义相似度最高的

### Q2: 分类体系和法律特征有什么关系？

**A: 映射关系。**

- **分类**：面向用户的标签（如"买卖合同"）
- **V2特征**：法律层面的本质特征（如"转移所有权" + "货物"）
- **映射库**：建立两者之间的桥梁

例如：
- 用户看到："买卖合同"（直观）
- 系统内部：`transaction_nature="转移所有权" + contract_object="货物"`（法律本质）
- 这种映射让系统既能理解用户意图，又能进行法律特征匹配

### Q3: 如何完善法律特征库？

**A: 三个步骤：**

1. **建立分类-特征映射**（已完成）
   - 在 `category_feature_mapping.py` 中定义每个分类对应的V2特征

2. **为现有模板补充特征**（需人工）
   - 登录管理后台
   - 为每个模板选择正确的分类和V2特征

3. **持续优化**（持续）
   - 收集用户反馈
   - 调整映射关系
   - 添加新的分类

---

## 🔧 下一步建议

1. **测试映射库**：
   ```bash
   curl -X GET http://localhost:8000/api/v1/legal-features/mappings
   ```

2. **测试关键词搜索**：
   ```bash
   curl -X POST http://localhost:8000/api/v1/legal-features/search-by-keywords \
     -H "Content-Type: application/json" \
     -d '{"query": "房屋买卖"}'
   ```

3. **在前端集成**：
   - 在合同生成页面添加分类选择器
   - 用户选择分类后，自动推荐对应模板

4. **完善映射库**：
   - 根据您的业务需求，添加更多分类
   - 为每个分类精细配置V2特征

---

## 📚 相关文件

| 文件 | 作用 |
|------|------|
| `category_feature_mapping.py` | 分类-特征映射配置 |
| `hybrid_template_retriever.py` | 混合检索引擎 |
| `legal_features_management.py` | API接口 |
| `contract_template.py` (模型) | V2特征存储字段 |

---

## 🎓 总结

**核心改进**：

✅ **之前**：仅通过RAG向量检索（基于内容语义）
✅ **现在**：分类检索 + 特征检索 + 向量检索（三重保障）

**优势**：

1. **更精准**：分类映射确保法律特征准确匹配
2. **更快速**：分类检索可以快速定位，避免全库向量搜索
3. **更智能**：V2特征提取能理解用户意图，而非仅仅匹配关键词
4. **可解释**：可以向用户解释"为什么推荐这个模板"

**您现在可以**：
- 通过分类快速找到对应模板
- 通过V2特征进行精准匹配
- 通过RAG向量检索进行兜底
- 三种方式结果融合，返回最优推荐
