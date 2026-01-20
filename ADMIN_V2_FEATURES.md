# 管理员后台 V2 法律特征管理

## 概述

系统已升级管理员后台的模板管理功能，现在支持对合同模板的 V2 四维法律特征进行完整的管理和编辑。

## 功能特性

### 1. V2 四维法律特征

每个合同模板现在包含以下 V2 法律特征：

- **交易性质 (transaction_nature)**: 交易的核心法律特征
  - 转移所有权（买卖合同）
  - 提供服务（服务合同、委托合同）
  - 许可使用（技术转让、特许经营）
  - 合作经营（合伙合同、联营合同）
  - 融资借贷（借款合同、融资租赁）
  - 劳动用工（劳动合同）

- **合同标的 (contract_object)**: 交易的具体对象
  - 货物（商品、设备）
  - 工程（建设工程）
  - ip（智力成果：软件、专利）
  - 服务（人力服务）
  - 股权（股权转让）
  - 资金（借款、投资）
  - human_labor（劳动力）
  - real_estate（房地产）

- **复杂程度 (complexity)**: 合同的法律和交易复杂度
  - simple（简单标准化合同）
  - standard_commercial（常规商业合同）
  - complex（复杂交易结构）

- **立场 (stance)**: 合同的起草立场
  - neutral（中立/双方平衡）
  - party_a（偏向甲方）
  - party_b（偏向乙方）
  - balanced（完全对等）

### 2. 结构锚点字段

- **主合同类型 (primary_contract_type)**: 主要合同分类
  - 买卖合同、建设工程合同、承揽合同、技术转让合同
  - 租赁合同、借款合同、劳动合同、委托合同
  - 服务合同、合伙合同、合作协议、保密协议、其他

- **次要合同类型 (secondary_types)**: 复合合同的次要类型

- **风险等级 (risk_level)**: low / mid / high

- **推荐模板 (is_recommended)**: 是否为高频使用的标准模板

## 使用方法

### 前端管理界面

1. **访问管理后台**
   - 使用管理员账户登录系统
   - 访问 `/admin` 路径进入管理后台

2. **进入模板管理**
   - 在左侧菜单选择「模版管理」
   - 可以查看所有模板及其 V2 特征

3. **编辑 V2 特征**
   - 在模板列表中找到需要编辑的模板
   - 点击「V2特征」按钮
   - 在弹出的编辑器中修改 V2 法律特征
   - 点击「保存」提交更改

4. **上传新模板**
   - 点击「上传模版」按钮
   - 填写基本信息（名称、分类、描述等）
   - 系统会自动提示填写 V2 特征

### API 接口

管理员可以通过以下 API 端点管理 V2 特征：

```bash
# 获取模板列表（包含 V2 特征）
GET /api/v1/contract/?scope=all

# 获取单个模板详情（包含 V2 特征）
GET /api/v1/contract/{template_id}

# 更新模板 V2 法律特征（仅管理员）
PUT /api/v1/contract/{template_id}/v2-features
Content-Type: application/json

{
  "primary_contract_type": "委托合同",
  "secondary_types": ["服务合同"],
  "transaction_nature": "提供服务",
  "contract_object": "ip",
  "complexity": "standard_commercial",
  "stance": "neutral",
  "risk_level": "mid",
  "is_recommended": true,
  "metadata_info": {}
}
```

## 测试脚本

运行测试脚本验证 V2 特征功能：

```bash
docker-compose exec backend python scripts/test_admin_v2_features.py
```

测试脚本会检查：
- 管理员用户是否存在
- 现有模板的 V2 特征完整性
- V2 特征分布统计
- API 端点可用性

## 数据库字段说明

### ContractTemplate 模型

```python
# V2 四维法律特征
transaction_nature = Column(String(100))  # 交易性质
contract_object = Column(String(100))     # 合同标的
complexity = Column(String(50))           # 复杂程度
stance = Column(String(50))               # 立场
metadata_info = Column(JSON)              # 扩展元数据

# 结构锚点字段
primary_contract_type = Column(String(100))  # 主合同类型
secondary_types = Column(JSON)                # 次要合同类型
risk_level = Column(String(20))               # 风险等级
is_recommended = Column(Boolean)              # 推荐模板
```

## 前端类型定义

### ContractTemplate 接口

```typescript
interface ContractTemplate {
  // ... 基础字段

  // V2 四维法律特征
  transaction_nature?: TransactionNature;
  contract_object?: ContractObject;
  complexity?: Complexity;
  stance?: Stance;

  // 结构锚点字段
  primary_contract_type: PrimaryContractType;
  secondary_types?: string[];
  risk_level?: 'low' | 'mid' | 'high';
  is_recommended?: boolean;
}
```

## 智能匹配原理

V2 特征用于合同生成时的智能模板匹配：

1. **用户输入分析** → 提取 V2 特征
2. **模板匹配** → 根据 V2 特征匹配最合适的模板
3. **结构差异分析** → 评估模板与需求的匹配度

示例：
- 用户输入："我需要一份软件开发合同"
- 系统提取：transaction_nature="提供服务", contract_object="ip"
- 匹配结果：软件委托开发合同（委托合同 + ip）

## 注意事项

1. **权限控制**
   - 只有管理员可以编辑 V2 法律特征
   - 普通用户只能查看 V2 特征

2. **数据完整性**
   - 建议为所有模板补充完整的 V2 特征
   - 缺失 V2 特征的模板可能无法被正确匹配

3. **特征选择建议**
   - 软件开发/委托开发：service_delivery + ip
   - 技术咨询/服务：service_delivery + human_labor
   - 借款合同：融资借贷 + 资金
   - 买卖合同：转移所有权 + 货物

## 文件清单

### 前端文件

- `frontend/src/api/contractTemplates.ts` - API 接口定义和类型
- `frontend/src/components/TemplateV2Editor.tsx` - V2 特征编辑器组件
- `frontend/src/pages/AdminPage.tsx` - 管理后台页面

### 后端文件

- `backend/app/api/v1/endpoints/contract_templates.py` - 模板管理 API
- `backend/app/models/contract_template.py` - 模板数据模型

### 测试脚本

- `backend/scripts/test_admin_v2_features.py` - V2 特征功能测试

## 更新日志

### v3.1 (2026-01-08)

- ✅ 添加 V2 四维法律特征到前端类型定义
- ✅ 创建 TemplateV2Editor 组件用于可视化编辑
- ✅ 更新 AdminPage 模板管理界面显示 V2 特征
- ✅ 添加后端 API 端点 `/api/v1/contract/{id}/v2-features`
- ✅ 更新 TemplateResponse 模型包含 V2 字段
- ✅ 创建测试脚本验证功能完整性
