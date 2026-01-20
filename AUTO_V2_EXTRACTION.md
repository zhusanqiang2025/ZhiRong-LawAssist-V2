# 合同模板V2法律特征自动提取功能

## 功能概述

系统现已集成自动V2法律特征提取功能，当您上传Word文档时，系统会自动分析文档内容并提取以下法律特征：

- **交易性质** (transaction_nature): 转移所有权、提供服务、许可使用等
- **合同标的** (contract_object): 货物、服务、IP、股权等
- **复杂程度** (complexity): 简单、中等、复杂
- **立场** (stance): 中立、甲方、乙方、平衡

## 工作流程

```
上传Word文档 → 保存原始文件 → 提取文本内容 → LLM分析提取V2特征 → 保存到数据库
```

### 1. 文档内容提取
使用现有的 `DocumentPreprocessor` 模块提取Word文档的纯文本内容。

**文件**: [backend/app/services/document_preprocessor.py](backend/app/services/document_preprocessor.py)

**功能**:
- 支持 `.docx`, `.doc`, `.pdf`, `.md`, `.txt` 格式
- 自动识别文档结构
- 提取纯文本内容供AI分析

### 2. V2特征智能提取
使用 `V2FeatureExtractor` 和LLM自动分析文档内容。

**文件**: [backend/app/services/template_feature_extractor.py](backend/app/services/template_feature_extractor.py)

**提取器**:
- 集成 `V2FeatureExtractor` (已有的V2特征提取器)
- 使用 ChatOpenAI (配置在 `settings.OPENAI_MODEL_NAME`)
- 返回标准化的V2枚举值

### 3. 上传接口
**文件**: [backend/app/api/v1/endpoints/contract_templates.py](backend/app/api/v1/endpoints/contract_templates.py#L121-L265)

**新增参数**:
- `auto_extract`: 是否启用自动提取（默认 `True`）

**逻辑**:
```python
# 如果启用自动提取且未手动提供完整V2特征
if auto_extract and not all([transaction_nature, contract_object, complexity, stance]):
    # 调用特征提取器
    feature_extractor = get_template_feature_extractor()
    extracted_features, extract_note = feature_extractor.extract_from_file(
        file_path=source_file_path,
        category_hint=category
    )

    # 使用自动提取的值填充空字段
    if not transaction_nature:
        transaction_nature = extracted_features.get("transaction_nature")
    # ... 其他字段
```

## V2特征分类体系

### 交易性质 (transaction_nature)
- `asset_transfer` - 转移所有权（买卖、赠与）
- `service_delivery` - 提供服务
- `authorization` - 许可使用（IP授权）
- `entity_creation` - 合作经营（合资、合作）
- `capital_finance` - 融资借贷
- `resource_sharing` - 资源共享
- `dispute_resolution` - 争议解决

### 合同标的 (contract_object)
- `tangible_goods` - 有形货物
- `human_labor` - 人力劳动
- `ip` - 知识产权
- `equity` - 股权
- `monetary_debt` - 资金债权
- `data_traffic` - 数据流量
- `credibility` - 信誉

### 复杂程度 (complexity)
- `internal_simple` - 内部简单
- `standard_commercial` - 标准商业
- `complex_strategic` - 复杂战略

### 立场 (stance)
- `buyer_friendly` - 买方倾向
- `seller_friendly` - 卖方倾向
- `neutral` - 中立平衡

## 使用方式

### 前端上传（默认启用自动提取）

在前端"模板管理"或"分类配置"页面上传模板时：

1. 选择Word文档
2. 填写模板名称
3. 选择分类（可选）
4. 点击上传

系统会自动提取V2特征，您也可以在"模板管理" → "V2特征"按钮中查看和编辑提取结果。

### API调用

```bash
curl -X POST "http://localhost:8000/api/v1/contract/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@contract.docx" \
  -F "name=借款合同模板" \
  -F "category=借款合同" \
  -F "is_public=true" \
  -F "auto_extract=true"
```

**响应示例**:
```json
{
  "id": "template-id",
  "name": "借款合同模板",
  "transaction_nature": "capital_finance",
  "contract_object": "monetary_debt",
  "complexity": "standard_commercial",
  "stance": "neutral",
  "metadata_info": {
    "auto_extracted": true,
    "extract_note": "特征提取成功"
  }
}
```

## 手动覆盖自动提取

如果您手动提供V2特征字段，系统将使用您的值而不是自动提取的值：

```bash
curl -X POST "http://localhost:8000/api/v1/contract/upload" \
  -F "file=@contract.docx" \
  -F "name=借款合同模板" \
  -F "transaction_nature=capital_finance" \  # 手动指定
  -F "contract_object=monetary_debt" \       # 手动指定
  -F "auto_extract=false"                    # 禁用自动提取
```

## 提取质量保证

### 默认值策略
如果自动提取失败，系统会使用安全的默认值：
- transaction_nature: `service_delivery`
- contract_object: `ip`
- complexity: `standard_commercial`
- stance: `neutral`

### 错误处理
- 提取失败不会阻断上传流程
- 错误信息会记录在 `metadata_info.extract_note` 中
- 管理员可在V2编辑器中手动修正

## 日志监控

### 后端日志
```bash
docker logs legal_assistant_v3_backend -f
```

**关键日志**:
```
[Upload] 开始自动提取V2法律特征...
[TemplateFeatureExtractor] Step 1: 提取文档文本内容...
[TemplateFeatureExtractor] Step 2: 使用LLM提取V2特征...
[TemplateFeatureExtractor] 特征提取完成: {...}
[Upload] V2特征自动提取完成: {...}
[Upload] 模板上传成功: template-id, 自动提取: True
```

## 配置要求

### 环境变量
确保以下配置正确设置：

```bash
# .env
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o-mini
```

### 依赖模块
- ✅ `DocumentPreprocessor` - 文档内容提取
- ✅ `V2FeatureExtractor` - V2特征提取
- ✅ `ChatOpenAI` - LLM调用

## 常见问题

### Q: 自动提取准确率如何？
A: 取决于文档质量和LLM模型能力。建议：
- 使用格式规范的Word文档
- 上传后检查并可在V2编辑器中手动修正

### Q: 可以关闭自动提取吗？
A: 可以。在上传时设置 `auto_extract=false`

### Q: 支持哪些文档格式？
A: 支持 `.docx`, `.doc`, `.pdf`, `.md`, `.txt`

### Q: 提取失败怎么办？
A: 系统会使用默认值，不会影响上传。您可以：
1. 查看后端日志了解失败原因
2. 在V2编辑器中手动编辑特征
3. 重新上传并检查文档格式

## 后续优化方向

1. **批量处理**: 为现有模板批量补充V2特征
2. **置信度评分**: 显示AI提取的置信度
3. **人工审核**: 提取低置信度时标记需人工审核
4. **持续学习**: 根据人工修正结果优化提示词

---

**更新时间**: 2026-01-09
**版本**: v3.0
