# 合同模板自动检查与修复工具使用指南

## 概述

系统提供了两个自动化工具来检查和修复合同模板的分类和V2法律特征问题：

1. **分类一致性检查工具** - `check_category_consistency.py`
2. **V2特征检查与修复工具** - `check_and_fix_templates.py`

## 工具1: 分类一致性检查

### 功能
- 检查 `category` 和 `primary_contract_type` 字段是否一致
- 检查V2特征值是否有效
- 自动修复分类不一致问题
- 标准化V2特征值（中文转英文）

### 使用方式

#### 1. 只检查不修复
```bash
docker exec legal_assistant_v3_backend python scripts/check_category_consistency.py
```

#### 2. 检查并修复分类不一致
```bash
docker exec legal_assistant_v3_backend python scripts/check_category_consistency.py --fix-category
```

#### 3. 标准化V2特征值
```bash
docker exec legal_assistant_v3_backend python scripts/check_category_consistency.py --normalize-v2
```

#### 4. 导出检查报告
```bash
docker exec legal_assistant_v3_backend python scripts/check_category_consistency.py --export --report-file my_report.json
```

#### 5. 组合使用
```bash
docker exec legal_assistant_v3_backend python scripts/check_category_consistency.py --fix-category --normalize-v2 --export
```

### 检查报告

工具会生成以下统计信息：
- 📊 总计: 模板总数
- ⚠️ 分类不一致: 数量
- ⚠️ 无效V2值: 数量
- ❌ 缺失V2特征: 数量
- 🔧 可自动修复: 数量

## 工具2: V2特征检查与修复

### 功能
- 检查所有模板的V2特征完整性
- 从Word文档自动提取缺失的V2特征
- 验证文件是否存在
- 批量修复V2特征缺失问题
- 生成详细的检查报告

### 使用方式

#### 1. 只检查不修复（预览）
```bash
docker exec legal_assistant_v3_backend python scripts/check_and_fix_templates.py --dry-run
```

#### 2. 检查并修复缺失的V2特征
```bash
docker exec legal_assistant_v3_backend python scripts/check_and_fix_templates.py --fix
```

#### 3. 检查并修复所有模板（包括已有V2特征的）
```bash
docker exec legal_assistant_v3_backend python scripts/check_and_fix_templates.py --fix --fix-all
```

#### 4. 检查单个模板
```bash
docker exec legal_assistant_v3_backend python scripts/check_and_fix_templates.py --template-id xxx --dry-run
```

#### 5. 导出报告
```bash
docker exec legal_assistant_v3_backend python scripts/check_and_fix_templates.py --dry-run --export
```

### 输出信息

对于每个模板，工具会显示：
- 模板名称和ID
- ✅ V2特征完整 或 ❌ 缺失的V2字段
- ✅ 文件存在 或 ❌ 文件缺失
- ⚠️ 无效的V2特征值（如果有）

## 常见使用场景

### 场景1: 日常维护检查
```bash
# 每周运行一次，检查分类一致性
docker exec legal_assistant_v3_backend python scripts/check_category_consistency.py
```

### 场景2: 批量上传后检查
```bash
# 上传新模板后，检查并修复所有问题
docker exec legal_assistant_v3_backend python scripts/check_category_consistency.py --fix-category --normalize-v2
docker exec legal_assistant_v3_backend python scripts/check_and_fix_templates.py --fix
```

### 场景3: 数据迁移后验证
```bash
# 数据迁移后，全面检查并导出报告
docker exec legal_assistant_v3_backend python scripts/check_category_consistency.py --export
docker exec legal_assistant_v3_backend python scripts/check_and_fix_templates.py --dry-run --export
```

### 场景4: 单个模板问题诊断
```bash
# 检查特定模板的问题
docker exec legal_assistant_v3_backend python scripts/check_and_fix_templates.py --template-id template_id_here
```

## 检查报告格式

报告以JSON格式导出，包含以下结构：

```json
{
  "generated_at": "2026-01-09T16:45:00",
  "summary": {
    "total": 93,
    "complete": 2,
    "incomplete": 91,
    "missing_v2": 0,
    "missing_file": 0,
    "fixed_count": 91
  },
  "issues": [
    {
      "template_id": "xxx",
      "template_name": "模板名称",
      "issues": [
        {
          "type": "missing_v2",
          "fields": ["transaction_nature", "contract_object"]
        }
      ]
    }
  ],
  "fixed": [
    {
      "template_id": "xxx",
      "template_name": "模板名称"
    }
  ]
}
```

## 注意事项

1. **备份数据**: 在运行修复命令前，建议先备份数据库
2. **预览模式**: 使用 `--dry-run` 参数可以先预览将要修复的内容
3. **文件要求**: V2特征自动提取需要Word文档文件存在
4. **API配置**: 确保已正确配置 OpenAI API（用于V2特征提取）

## 故障排查

### 问题1: 提取失败
```
❌ 修复失败: API connection error
```
**解决**: 检查 `.env` 文件中的 `OPENAI_API_KEY` 和 `OPENAI_API_BASE` 配置

### 问题2: 文件不存在
```
❌ 文件不存在，无法自动修复: /path/to/file.docx
```
**解决**: 检查模板的 `file_url` 字段，确保文件路径正确

### 问题3: 数据库锁定
```
sqlalchemy.exc.OperationalError: database is locked
```
**解决**: 等待其他操作完成，或者重启后端容器

## 执行日志示例

### 成功修复示例
```
================================================================================
修复分类不一致问题
================================================================================

修复: 非货币出资补充约定
  将 primary_contract_type 从 '股权类协议'
  改为 '非典型商事合同'
...
✅ 已修复 91 个模板的分类不一致问题
```

### V2特征提取示例
```
📊 开始自动提取V2特征...
✅ 提取完成:
   transaction_nature: capital_finance
   contract_object: monetary_debt
   complexity: standard_commercial
   stance: neutral
   说明: 特征提取成功
✅ 已保存到数据库
```

## 定期维护建议

1. **每日**: 无需操作
2. **每周**: 运行分类一致性检查
3. **每月**: 运行完整的V2特征检查
4. **每季度**: 导出完整报告并归档

---

**更新时间**: 2026-01-09
**版本**: v1.0
