# 合同法律特征知识图谱 - 使用指南

## 📌 概述

您提出的需求是：**将合同名称、法律特征、合同模板三者关联起来，形成完整的法律知识图谱。**

现在这个系统已经实现了！

---

## 🎯 核心概念

### 三元组知识图谱

```
┌─────────────────────────────────────────────────────────────┐
│                      合同法律特征知识图谱                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   合同名称 "不动产买卖合同"                                  │
│        │                                                    │
│        ├─→ 交易性质：转移所有权                               │
│        ├─→ 合同标的：不动产                                   │
│        ├─→ 复杂程度：复杂                                     │
│        ├─→ 立场：平衡                                         │
│        ├─→ 交易对价：有偿，双方协商                             │
│        └─→ 交易特征：占有转移+办理所有权转移登记实现交付              │
│                                                             │
│        ↓                                                    │
│   自动匹配最佳模板                                          │
│        ↓                                                    │
│   不动产买卖合同模板.docx                                    │
│        ↓                                                    │
│   生成最终合同                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 已实现的功能

### 1. 数据库扩展（已完成）

在 `contract_templates` 表中添加了两个新字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `transaction_consideration` | String(200) | 交易对价：有偿/无偿/混合，具体说明 |
| `transaction_characteristics` | Text | 交易特征：特殊的法律特征描述 |

### 2. 知识图谱配置（已完成）

创建了 `ContractKnowledgeGraph` 类，预配置了 **14 种常见合同类型** 的完整法律特征：

| 合同类型 | 交易性质 | 标的 | 交易对价 | 交易特征 |
|---------|---------|------|---------|---------|
| **不动产买卖合同** | 转移所有权 | 不动产 | 有偿，双方协商 | 占有转移+办理所有权转移登记实现交付 |
| **动产买卖合同** | 转移所有权 | 动产 | 有偿，双方协商 | 占有转移（部分特殊动产需办理转移登记） |
| **借款合同** | 融资借贷 | 资金 | 有偿，利息形式 | 资金转移+利息支付 |
| **房屋租赁合同** | 许可使用 | 不动产 | 有偿，租金形式 | 使用权转移+占有转移 |
| **建设工程合同** | 提供服务 | 工程 | 有偿，按工程进度付款 | 持续交付+分期验收 |
| **劳动合同** | 劳动用工 | 劳动力 | 有偿，工资形式 | 劳动服务+社会保障 |
| **技术开发合同** | 提供服务 | 智力成果 | 有偿，分期付款 | 智力成果创造+知识产权归属 |
| **技术转让合同** | 转移所有权 | 智力成果 | 有偿，技术转让费 | 知识产权转移+使用权许可 |
| **承揽合同** | 提供服务 | 动产 | 有偿，按工作成果付款 | 工作成果交付+验收 |
| **委托合同** | 提供服务 | 服务 | 有偿，佣金或服务费 | 代理行为+结果交付 |
| **合作协议** | 合作经营 | 股权 | 有偿，按投资比例 | 共同投资+共享收益+共担风险 |
| **保证合同** | 融资借贷 | 资金 | 无偿 | 信用增强+责任承担 |
| **赠与合同** | 转移所有权 | 动产 | 无偿 | 无偿转让+权利转移 |

### 3. API 接口（已完成）

创建了完整的知识图谱查询 API：

| 端点 | 功能 | 说明 |
|------|------|------|
| `GET /api/v1/knowledge-graph/contract-types` | 获取所有合同类型 | 返回所有合同类型及其法律特征 |
| `GET /api/v1/knowledge-graph/contract-types/{name}` | 获取指定合同类型的法律特征 | 返回完整的六维法律特征 |
| `POST /api/v1/knowledge-graph/search-by-keywords` | 关键词搜索合同类型 | 输入"房屋买卖"，返回"不动产买卖合同"的特征 |
| `GET /api/v1/knowledge-graph/categories/{category}/contract-types` | 按分类获取合同类型 | 获取某分类下的所有合同类型 |
| `GET /api/v1/knowledge-graph/legal-features/{name}` | 快速获取法律特征 | 用于自动填充表单 |

---

## 📖 使用示例

### 示例 1：用户选择合同类型

**场景**：管理员在上传模板时，选择"不动产买卖合同"

```javascript
// 1. 调用 API 获取法律特征
const response = await fetch('/api/v1/knowledge-graph/legal-features/不动产买卖合同');
const features = await response.json();

// 2. 返回的数据：
{
  "transaction_nature": "转移所有权",
  "contract_object": "不动产",
  "complexity": "复杂",
  "stance": "平衡",
  "consideration_type": "有偿",
  "consideration_detail": "双方协商",
  "transaction_characteristics": "占有转移+办理所有权转移登记实现交付",
  "usage_scenario": "适用于房屋、商铺等不动产所有权转让",
  "legal_basis": ["民法典第209条", "民法典第214条"]
}

// 3. 自动填充表单
form.setFieldsValue({
  transaction_nature: features.transaction_nature,
  contract_object: features.contract_object,
  complexity: features.complexity,
  stance: features.stance,
  transaction_consideration: features.consideration_type + "，" + features.consideration_detail,
  transaction_characteristics: features.transaction_characteristics
});
```

### 示例 2：用户输入关键词搜索

**场景**：用户在合同生成页面输入"我要买房子"

```javascript
// 1. 调用搜索 API
const response = await fetch('/api/v1/knowledge-graph/search-by-keywords?query=我要买房子');
const result = await response.json();

// 2. 返回的数据：
{
  "contract_types": [
    {
      "name": "不动产买卖合同",
      "aliases": ["房屋买卖合同", "房产买卖合同", "二手房买卖合同"],
      "category": "买卖合同",
      "subcategory": "不动产买卖",
      "legal_features": {
        "transaction_nature": "转移所有权",
        "contract_object": "不动产",
        "complexity": "复杂",
        "stance": "平衡",
        "consideration_type": "有偿",
        "consideration_detail": "双方协商",
        "transaction_characteristics": "占有转移+办理所有权转移登记实现交付"
      },
      "recommended_template_ids": ["template_001", "template_002"]
    }
  ],
  "total_count": 1
}

// 3. 显示推荐
// "系统为您推荐：不动产买卖合同"
// "法律特征：转移所有权 + 不动产 + 占有转移+办理所有权转移登记实现交付"
// "已为您匹配 2 个模板"
```

### 示例 3：完整的模板上传流程

```javascript
// 管理员上传模板的完整流程

// 1. 选择合同类型
const [contractType, setContractType] = useState('');

// 2. 监听合同类型选择，自动填充法律特征
useEffect(() => {
  if (contractType) {
    fetchLegalFeatures(contractType);
  }
}, [contractType]);

const fetchLegalFeatures = async (typeName: string) => {
  const response = await fetch(`/api/v1/knowledge-graph/legal-features/${typeName}`);
  const features = await response.json();

  // 自动填充所有字段
  uploadForm.setFieldsValue({
    // V2 四维特征
    transaction_nature: features.transaction_nature,
    contract_object: features.contract_object,
    complexity: features.complexity,
    stance: features.stance,

    // V2+ 扩展特征
    transaction_consideration: `${features.consideration_type}，${features.consideration_detail}`,
    transaction_characteristics: features.transaction_characteristics,

    // 分类信息
    category: features.category || '',
    subcategory: features.subcategory || '',

    // 使用场景
    usage_scenario: features.usage_scenario || ''
  });
};

// 3. 上传文件时，所有法律特征已经自动填充
const handleUpload = async () => {
  const values = uploadForm.getFieldsValue();
  const formData = new FormData();

  // 文件
  formData.append('file', file);

  // 基本信息
  formData.append('name', values.name);
  formData.append('category', values.category);
  formData.append('subcategory', values.subcategory);

  // V2 四维特征
  formData.append('transaction_nature', values.transaction_nature);
  formData.append('contract_object', values.contract_object);
  formData.append('complexity', values.complexity);
  formData.append('stance', values.stance);

  // V2+ 扩展特征
  formData.append('transaction_consideration', values.transaction_consideration);
  formData.append('transaction_characteristics', values.transaction_characteristics);

  // 提交
  await contractTemplateApi.uploadTemplate(formData);
};
```

---

## 🚀 下一步集成步骤

### 步骤 1：重启后端容器（应用数据库迁移）

```bash
# 重启后端以应用新的数据库字段
docker restart legal_assistant_v3_backend
```

### 步骤 2：测试知识图谱 API

```bash
# 测试获取所有合同类型
curl http://localhost:8000/api/v1/knowledge-graph/contract-types

# 测试搜索
curl "http://localhost:8000/api/v1/knowledge-graph/search-by-keywords?query=房屋买卖"

# 测试获取特定合同类型的特征
curl http://localhost:8000/api/v1/knowledge-graph/legal-features/不动产买卖合同
```

### 步骤 3：前端集成

在模板管理页面上传表单中，添加合同类型选择器：

```typescript
// TemplateManager.tsx

// 1. 添加合同类型选择
<Form.Item label="合同类型" name="contract_type_name" rules={[{ required: true }]}>
  <Select
    placeholder="选择合同类型（将自动填充法律特征）"
    showSearch
    onChange={handleContractTypeChange}
  >
    {/* 从知识图谱 API 获取选项 */}
    {contractTypes.map(ct => (
      <Option key={ct.name} value={ct.name}>
        {ct.name}
      </Option>
    ))}
  </Select>
</Form.Item>

// 2. 处理合同类型选择
const handleContractTypeChange = async (contractTypeName: string) => {
  try {
    // 获取该合同类型的法律特征
    const response = await fetch(`/api/v1/knowledge-graph/legal-features/${contractTypeName}`);
    const features = await response.json();

    // 自动填充表单
    uploadForm.setFieldsValue({
      transaction_nature: features.transaction_nature,
      contract_object: features.contract_object,
      complexity: features.complexity,
      stance: features.stance,
      transaction_consideration: `${features.consideration_type}，${features.consideration_detail}`,
      transaction_characteristics: features.transaction_characteristics,
      category: features.category || '',
      subcategory: features.subcategory || '',
      description: features.usage_scenario || ''
    });

    message.success(`已自动填充"${contractTypeName}"的法律特征`);
  } catch (e) {
    message.error('获取法律特征失败，请手动填写');
  }
};
```

---

## 📝 扩展知识图谱

如果您想添加新的合同类型，只需编辑 `contract_knowledge_graph.py` 文件：

```python
# 在 _initialize_knowledge_graph 方法中添加

self._add_contract_type(ContractTypeDefinition(
    name="您的合同名称",
    aliases=["别名1", "别名2"],
    category="所属分类",
    subcategory="子分类",
    legal_features=ContractLegalFeatures(
        transaction_nature=TransactionNature.ASSET_TRANSFER,
        contract_object=ContractObject.TANGIBLE_GOODS,
        complexity=Complexity.STANDARD,
        stance=Stance.BALANCED,
        consideration_type=ConsiderationType.PAID,
        consideration_detail="双方协商",
        transaction_characteristics="您的交易特征描述",
        usage_scenario="使用场景说明",
        legal_basis=["法律依据1", "法律依据2"]
    )
))
```

---

## 🎯 总结

### ✅ 已完成

1. ✅ **数据库扩展**：添加 `transaction_consideration` 和 `transaction_characteristics` 字段
2. ✅ **知识图谱配置**：预配置 14 种常见合同类型的完整法律特征
3. ✅ **API 接口**：提供完整的查询和管理接口
4. ✅ **前端类型定义**：更新 TypeScript 类型以支持新字段

### 🔄 待完成

1. ⏳ **前端集成**：在模板上传页面添加合同类型选择器
2. ⏳ **自动填充**：选择合同类型后自动填充法律特征表单
3. ⏳ **测试验证**：完整测试从选择到上传的流程

### 💡 优势

- **智能化**：用户只需选择合同类型，系统自动填充所有法律特征
- **标准化**：所有同类型合同的法律特征保持一致
- **可追溯**：每个特征都有法律依据和使用场景说明
- **易维护**：知识图谱集中管理，修改即可全局生效

---

**现在您已经拥有了一个完整的"合同名称-法律特征-模板"三元组知识图谱系统！** 🎉
