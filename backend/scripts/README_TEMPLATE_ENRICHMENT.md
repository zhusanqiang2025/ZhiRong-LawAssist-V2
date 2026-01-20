# 模板智能分类与结构化参数提取脚本

## 功能说明

该脚本用于：
1. **读取** `templates_source` 目录下的 `.md` 合同文件
2. **AI 分析**：对照 `categories.json` 进行智能分类
3. **提取参数**：提取结构化参数（交付模型、付款模型、立场、风险等级等）
4. **更新数据库**：将分析结果更新到 `contract_templates` 表

## 前置条件

### 1. 环境要求
- Python 3.11+
- PostgreSQL 数据库
- DeepSeek API Key（或兼容的 OpenAI API）

### 2. 配置检查

确保以下环境变量已设置：

```bash
# 数据库连接
export DATABASE_URL="postgresql://postgres:password@localhost:5432/legal_docs"

# LLM API
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-chat"  # 可选，默认为 deepseek-chat
```

或者直接修改脚本中的配置常量。

## 使用方法

### 方式一：批量处理所有模板

处理所有未分类的模板（`delivery_model IS NULL`）：

```bash
cd backend
python scripts/enrich_templates_with_categories.py
```

**输出示例：**
```
============================================================
🚀 开始执行模板智能分类与结构化参数提取
============================================================

📋 加载分类体系...
   ✅ 分类体系加载成功

🔍 查询待处理的模板...
   📄 找到 150 个待处理模板

[1/150] 处理: 住宅房屋租赁合同
   🤖 AI 分析中... ✅
      → 民法典典型合同
      → 租赁合同
      → 住宅租赁合同
      💾 数据库已更新
```

### 方式二：测试单个模板

在批量处理前，可以先测试单个模板：

```bash
cd backend
python scripts/enrich_templates_with_categories.py --test "template-id-here"
```

**输出示例：**
```
🧪 测试模板 ID: 12345678-1234-1234-1234-123456789abc

🤖 AI 分析结果:
{
  "primary_category_id": "1",
  "primary_category_name": "民法典典型合同",
  "sub_type_name": "租赁合同",
  "sub_category_name": "住宅租赁合同",
  "contract_type": "租赁合同",
  "industry": "房地产",
  "delivery_model": "subscription",
  "payment_model": "installment",
  "stance": "neutral",
  "risk_level": "low"
}

💾 是否更新数据库？(y/n):
```

## 分类体系说明

### 十大主分类

1. **民法典典型合同** - 买卖、赠与、借款、租赁、承揽、建设工程、运输、技术、委托、物业、行纪中介
2. **非典型商事合同** - 股权投资、合伙联营、特许加盟、IP 商业化
3. **劳动与人力资源** - 标准劳动、灵活用工、附属协议
4. **行业特定合同** - 互联网软件、文娱传媒、供应链制造
5. **争议解决与法律程序** - 和解调解、债权债务
6. **婚姻家事与私人财富** - 婚姻家庭、财富传承
7. **公司治理与合规** - 公司组织文件、控制权投票
8. **政务与公共服务** - 政府采购、PPP、特许经营
9. **跨境与国际合同** - 国际贸易
10. **通用框架与兜底协议** - 意向框架、通用底座、单方声明

### 提取的结构化参数

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `delivery_model` | 交付模型 | turnkey, milestone, time_material, subscription, license, hybrid |
| `payment_model` | 付款模型 | lump_sum, installment, milestone_based, retainer, revenue_share, royalty, other |
| `stance` | 合同立场 | buyer_friendly, seller_friendly, neutral |
| `risk_level` | 风险等级 | high, mid, low |

## 数据库字段映射

脚本会更新以下数据库字段：

```sql
UPDATE contract_templates
SET
    -- 分类信息
    category = '一级分类名称',
    subcategory = '三级分类名称',

    -- 结构化参数
    primary_contract_type = '合同类型',
    delivery_model = '交付模型',      -- 映射到中文：单一交付/分期交付/持续交付/复合交付
    payment_model = '付款模型',        -- 映射到中文：一次性付款/分期付款/定期结算/混合模式
    industry_tags = '["行业标签"]',
    allowed_party_models = '["B2B", "B2C"]',
    risk_level = 'high/mid/low',

    -- 关键词
    keywords = '["一级分类", "二级分类", "三级分类", "行业"]',
    updated_at = NOW()
WHERE id = 'template-id';
```

## 错误处理

### 常见错误及解决方案

#### 1. 文件不存在
```
⚠️ 文件不存在: templates_source/xxx.md
```
**解决方案**：检查 `file_url` 字段是否正确，或文件是否已被移动/删除。

#### 2. AI 分析失败
```
⚠️ AI 分析失败: API connection error
```
**解决方案**：
- 检查 API Key 是否正确
- 检查网络连接
- 检查 API Base URL 是否可访问

#### 3. JSON 解析失败
```
⚠️ JSON 解析失败: Expecting value
```
**解决方案**：脚本会自动重试，如果持续失败，可能是 LLM 输出格式异常，可以调整 prompt。

## 日志与监控

### 实时进度
脚本会实时显示处理进度：
```
[1/150] 处理: 住宅房屋租赁合同
   🤖 AI 分析中... ✅
```

### 统计报告
处理完成后会输出统计：
```
============================================================
📊 处理完成统计
============================================================
   总计: 150 个模板
   ✅ 成功: 145 个
   ⚠️  跳过: 3 个
   ❌ 失败: 2 个
============================================================
```

## 后续步骤

### 1. 验证结果
检查数据库中更新的记录：

```sql
SELECT
    id,
    name,
    category,
    subcategory,
    primary_contract_type,
    delivery_model,
    payment_model,
    risk_level
FROM contract_templates
WHERE delivery_model IS NOT NULL
ORDER BY updated_at DESC
LIMIT 10;
```

### 2. 查看未处理的模板
```sql
SELECT COUNT(*)
FROM contract_templates
WHERE delivery_model IS NULL;
```

### 3. 重新处理失败的模板
如果某些模板处理失败，可以修复问题后重新运行脚本（只会处理 `delivery_model IS NULL` 的记录）。

## 注意事项

1. **API 限流**：脚本内置了 0.5 秒的延迟，避免触发 API 限流
2. **事务安全**：每次更新都是独立事务，单个失败不会影响其他记录
3. **可恢复性**：可以随时中断和重新运行，已处理的模板会被跳过
4. **测试先行**：建议先使用 `--test` 参数测试几个样本，确认结果符合预期后再批量处理

## 自定义配置

如需修改分类体系或映射规则，编辑以下文件：

- **分类体系**：`categories.json`
- **映射规则**：脚本中的 `update_template_in_db()` 函数

## 技术支持

如遇问题，请检查：
1. Python 环境：`python --version`
2. 依赖包：`pip install langchain-openai sqlalchemy`
3. 数据库连接：`psql -h localhost -U postgres -d legal_docs`
4. API 连接：`curl -X POST $OPENAI_API_BASE`
