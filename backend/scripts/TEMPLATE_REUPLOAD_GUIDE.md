# 模板重新上传与元数据恢复指南

## 背景

由于AI预处理生成的Markdown文件存在质量问题（编号缺失、内容不完整），需要删除现有文件并基于新的分类体系重新上传Word格式的合同模板。

## 问题

删除现有的Markdown文件后，每个文件中包含的业务元数据会丢失，这些元数据对AI精准匹配非常重要：

```yaml
---
original_filename: 4.软件维护和支持服务合同.docx
category: 非典型合同
type: 商业与项目类协议
scenario: 企业软件_维护支持
tags: ["技术服务", "软件维护", "企业合同"]
processed_by: deepseek
date: 2026-01-05
---
```

## 解决方案

使用提供的脚本工具，可以在重新上传Word文档后，自动恢复这些元数据。

## 操作步骤

### 第一步：提取现有元数据

在删除Markdown文件之前，先提取所有元数据：

```bash
docker exec legal_assistant_v3_backend sh -c "cd /app && python scripts/extract_metadata_from_markdown.py"
```

这将生成元数据映射表：`/app/storage/template_metadata_mapping.json`

### 第二步：备份（可选）

如果需要，可以先备份数据库：

```bash
docker exec legal_assistant_v3_backend sh -c "pg_dump -U admin legal_assistant_db > /backup/backup_$(date +%Y%m%d).sql"
```

### 第三步：删除现有模板（可选）

如果想要清空数据库和文件：

```bash
# 删除所有模板记录
docker exec legal_assistant_v3_backend sh -c "cd /app && python -c \"
from app.database import SessionLocal
from app.models.contract_template import ContractTemplate

db = SessionLocal()
count = db.query(ContractTemplate).count()
print(f'准备删除 {count} 个模板记录')
db.query(ContractTemplate).delete()
db.commit()
print('已删除所有模板记录')
db.close()
\""

# 删除Markdown文件
docker exec legal_assistant_v3_backend sh -c "rm -rf /app/storage/templates/markdown/*.md"
docker exec legal_assistant_v3_backend sh -c "rm -rf /app/storage/templates/source/*"
```

### 第四步：重新上传Word文档

通过前端管理界面上传Word格式的合同模板：
1. 进入"模板管理"页面
2. 选择对应的分类路径
3. 上传Word文件

### 第五步：恢复元数据

上传完成后，运行元数据恢复脚本：

```bash
docker exec legal_assistant_v3_backend sh -c "cd /app && python scripts/restore_metadata_to_templates.py"
```

脚本会自动：
1. 加载元数据映射表
2. 根据模板名称匹配元数据
3. 将元数据写入数据库的 `metadata_info` 字段
4. 保留原有的V2法律特征

### 第六步：重建向量索引

元数据恢复后，需要重新建立向量索引：

```bash
# 通过API触发重建（如果有相关接口）
# 或手动重建索引
```

## 注意事项

1. **元数据匹配**：脚本使用模板名称进行精确或模糊匹配，如果Word文件名与原来的不同，可能无法自动匹配

2. **手动补充**：对于无法自动匹配的模板，可以通过前端界面手动编辑V2特征

3. **备份重要**：在删除数据前，务必先提取元数据映射表

4. **测试验证**：建议先测试几个模板，验证元数据恢复是否正确

## 验证方法

检查元数据是否正确恢复：

```python
from app.database import SessionLocal
from app.models.contract_template import ContractTemplate

db = SessionLocal()
template = db.query(ContractTemplate).filter(ContractTemplate.name.like('%软件维护%')).first()

if template and template.metadata_info:
    print(f"模板: {template.name}")
    print(f"Scenario: {template.metadata_info.get('scenario')}")
    print(f"Tags: {template.metadata_info.get('tags')}")
    print(f"Type: {template.metadata_info.get('type')}")
