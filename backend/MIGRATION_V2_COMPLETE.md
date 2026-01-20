# Legal Transaction Logic V2 - 数据库升级完成

## ✅ 迁移成功

数据库已成功添加法律交易逻辑字段！

## 📊 新增字段

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `transaction_nature` | VARCHAR(50) | 交易实质（法律关系性质） | asset_transfer, service_delivery |
| `contract_object` | VARCHAR(50) | 核心标的（交易对象） | equity, ip, tangible_goods |
| `complexity` | VARCHAR(50) | 交易复杂度 | internal_simple, standard_commercial |
| `stance` | VARCHAR(20) | 合同立场 | buyer_friendly, seller_friendly, neutral |
| `metadata_info` | JSONB | 元数据（完整特征备份） | {"legal_features": {...}} |

## 🎯 当前状态

```
总模板数：744
待处理：744（transaction_nature IS NULL）
已处理：0
```

## 🚀 下一步操作

### 方式一：直接运行（批量处理）

```bash
cd backend
python scripts/enrich_templates_with_categories.py
```

**预期输出：**
```
🚀 启动 Data Governance 2.0 (Legal Logic Edition)...
📄 待治理模板数: 744

[1/744] 分析: 住宅房屋租赁合同 ... ✅ -> service_delivery
[2/744] 分析: 股权转让协议 ... ✅ -> asset_transfer
...
```

### 方式二：测试单个模板

在批量处理前，建议先测试：

```bash
cd backend

# 查询一个模板 ID
docker exec legal_assistant_v3_db psql -U admin -d legal_assistant_db -c \
  "SELECT id, name FROM contract_templates LIMIT 1;"

# 手动测试（修改脚本中的 template_id）
python scripts/enrich_templates_with_categories.py
```

## 📋 验证结果

### 1. 查看处理进度

```sql
-- 查看已处理的模板
SELECT COUNT(*) as processed
FROM contract_templates
WHERE transaction_nature IS NOT NULL;

-- 查看待处理的模板
SELECT COUNT(*) as pending
FROM contract_templates
WHERE transaction_nature IS NULL;
```

### 2. 查看分类统计

```sql
-- 使用内置的统计函数
SELECT * FROM get_transaction_nature_stats();
```

**预期输出：**
```
 transaction_nature | count | percentage
--------------------+-------+------------
 asset_transfer     |   150 |      20.00
 service_delivery   |   300 |      40.00
 ...
```

### 3. 查看详细数据

```sql
-- 使用新创建的视图
SELECT
    name,
    category,
    subcategory,
    transaction_nature,
    contract_object,
    complexity,
    stance
FROM v_contract_templates_legal_logic
WHERE transaction_nature IS NOT NULL
LIMIT 10;
```

### 4. 查看完整元数据

```sql
-- 查看 metadata_info 中的完整法律特征
SELECT
    name,
    transaction_nature,
    metadata_info->'legal_features' as legal_features
FROM contract_templates
WHERE transaction_nature IS NOT NULL
LIMIT 5;
```

## 🔍 新增的查询能力

### 按交易实质筛选

```sql
-- 找所有资产转移类合同
SELECT name, category, subcategory
FROM contract_templates
WHERE transaction_nature = 'asset_transfer'
  AND status = 'active';
```

### 按标的物筛选

```sql
-- 找所有股权相关合同
SELECT name, category
FROM contract_templates
WHERE contract_object = 'equity'
  AND status = 'active';
```

### 按复杂度筛选

```sql
-- 找所有简单合同（用于快速交易）
SELECT name, category
FROM contract_templates
WHERE complexity = 'internal_simple'
  AND status = 'active';
```

### 多维度组合查询

```sql
-- 找股权转移类的中立合同
SELECT name, category, subcategory
FROM contract_templates
WHERE transaction_nature = 'asset_transfer'
  AND contract_object = 'equity'
  AND stance = 'neutral'
  AND status = 'active';
```

## 🛠️ 故障排查

### 问题 1：脚本运行失败

**错误信息：**
```
❌ 数据库查询失败，请检查是否已添加 transaction_nature 等新字段！
```

**解决方案：**
```bash
# 重新执行迁移脚本
cd backend
docker exec -i legal_assistant_v3_db psql -U admin -d legal_assistant_db \
  < migrations/add_legal_transaction_fields.sql
```

### 问题 2：AI 分析失败

**错误信息：**
```
⚠️ AI 分析异常: API connection error
```

**解决方案：**
- 检查环境变量：`OPENAI_API_KEY`, `OPENAI_API_BASE`
- 检查网络连接
- 检查 API 配额

### 问题 3：JSON 解析失败

**错误信息：**
```
⚠️ AI 分析异常: Expecting value
```

**解决方案：**
- 这是 LLM 输出格式异常
- 脚本会自动重试
- 如果持续失败，检查 prompt 或调整 temperature

## 📊 预期处理时间

- **单模板分析**：约 2-5 秒（取决于 LLM 响应速度）
- **744 个模板**：约 25-60 分钟
- **API 限流保护**：内置 0.5 秒延迟

建议：在非高峰时段运行，或分批处理。

## 🎉 完成后验证

```sql
-- 1. 确认所有模板都已处理
SELECT COUNT(*) FROM contract_templates WHERE transaction_nature IS NULL;
-- 应该返回 0

-- 2. 查看分类分布
SELECT * FROM get_transaction_nature_stats();

-- 3. 查看样本数据
SELECT * FROM v_contract_templates_legal_logic LIMIT 10;
```

## 📚 相关文档

- **分类体系**：`categories.json`
- **脚本说明**：`scripts/README_TEMPLATE_ENRICHMENT.md`
- **原始迁移**：`migrations/add_legal_transaction_fields.sql`

## 🔄 回滚方案

如果需要回滚到 V1（不推荐）：

```sql
-- 删除新字段
ALTER TABLE contract_templates DROP COLUMN IF EXISTS transaction_nature;
ALTER TABLE contract_templates DROP COLUMN IF EXISTS contract_object;
ALTER TABLE contract_templates DROP COLUMN IF EXISTS complexity;

-- 恢复原有字段
UPDATE contract_templates SET delivery_model = NULL WHERE delivery_model IS NOT NULL;
```

**注意**：回滚会丢失所有 AI 分析的法律特征数据！
