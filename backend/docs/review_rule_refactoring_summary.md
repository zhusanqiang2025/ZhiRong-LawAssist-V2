# ReviewRule 模型重构总结

## 任务目标

将 `ReviewRule` 模型从 `backend/app/models/contract.py` 文件中移除，并移动到独立的 `rule.py` 文件中。

## 执行步骤

### 1. 从 contract.py 中移除 ReviewRule ✅

**文件**: `backend/app/models/contract.py`

**删除的内容** (原第 20-39 行):
```python
# 1. 企业审查红线规则表
class ReviewRule(Base):
    __tablename__ = "contract_review_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True, comment="规则名称，如：预付款红线")
    description = Column(String(255), nullable=True, comment="规则描述")
    content = Column(Text, nullable=False, comment="具体规则 Prompt 内容")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 新增字段：支持规则分类和自定义规则
    rule_category = Column(String(20), nullable=False, default="custom", comment="规则类型：universal/feature/stance/custom")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    priority = Column(Integer, default=0, comment="优先级，数字越小越优先")
    is_system = Column(Boolean, default=False, comment="是否为系统规则")

    def __repr__(self):
        return f"<ReviewRule {self.name}>"
```

**状态**: ✅ 已完成

### 2. 创建独立的 rule.py 文件 ✅

**新文件**: `backend/app/models/rule.py`

**内容**:
```python
# backend/app/models/rule.py
"""
审查规则模型

用于管理合同审查的规则配置
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class ReviewRule(Base):
    """
    企业审查红线规则表

    功能:
    - 存储合同审查的规则配置
    - 支持规则分类和自定义规则
    - 支持规则优先级和启用/禁用
    """
    __tablename__ = "contract_review_rules"

    # ========== 基本信息 ==========
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True, comment="规则名称，如：预付款红线")
    description = Column(String(255), nullable=True, comment="规则描述")
    content = Column(Text, nullable=False, comment="具体规则 Prompt 内容")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 新增字段：支持规则分类和自定义规则
    rule_category = Column(String(20), nullable=False, default="custom", comment="规则类型：universal/feature/stance/custom")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    priority = Column(Integer, default=0, comment="优先级，数字越小越优先")
    is_system = Column(Boolean, default=False, comment="是否为系统规则")

    def __repr__(self):
        return f"<ReviewRule {self.name}>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "is_active": self.is_active,
            "rule_category": self.rule_category,
            "creator_id": self.creator_id,
            "priority": self.priority,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**状态**: ✅ 已完成

### 3. 更新 models/__init__.py ✅

**文件**: `backend/app/models/__init__.py`

**修改前**:
```python
from .contract import ContractDoc, ContractReviewItem, ReviewRule
```

**修改后**:
```python
from .contract import ContractDoc, ContractReviewItem
from .rule import ReviewRule  # ✅ 从 contract.py 移动到独立的 rule.py
```

**状态**: ✅ 已完成

### 4. 验证模型导入 ✅

**测试命令**:
```bash
cd backend && python -c "from app.models.rule import ReviewRule; from app.models.contract import ContractDoc; print('ReviewRule imported successfully'); print('ContractDoc imported successfully'); print('ReviewRule table:', ReviewRule.__tablename__); print('ContractDoc table:', ContractDoc.__tablename__)"
```

**测试结果**:
```
ReviewRule imported successfully
ContractDoc imported successfully
ReviewRule table: contract_review_rules
ContractDoc table: contract_docs
```

**状态**: ✅ 验证通过

## 影响分析

### 依赖 ReviewRule 的文件

以下文件仍然引用 `ReviewRule` 模型，但导入路径无需更改（因为 `__init__.py` 已更新）：

1. ✅ `backend/app/services/contract_review/rule_assembler.py`
2. ✅ `backend/app/services/contract_review_service.py`
3. ✅ `backend/app/services/langgraph_review_service.py`
4. ✅ `backend/app/models/__init__.py`
5. ✅ `backend/alembic/env.py`
6. ✅ `backend/app/schemas/__init__.py`
7. ✅ `backend/app/schemas.py`
8. ✅ `backend/app/api/v1/endpoints/admin.py`
9. ✅ `backend/app/services/contract_review/ARCHITECTURE.md`
10. ✅ `backend/migrate_json_rules_to_db_docker.py`
11. ✅ `backend/migrate_json_rules_to_db.py`
12. ✅ `backend/app/services/review_rules_service.py`
13. ✅ `backend/init_review_rules.py`

### 导入路径变化

**旧路径** (已废弃):
```python
from app.models.contract import ReviewRule
```

**新路径** (推荐):
```python
from app.models.rule import ReviewRule
```

**兼容路径** (通过 `__init__.py`):
```python
from app.models import ReviewRule
```

## 优势

### 1. 模块化设计
- ✅ `contract.py` 专注于合同相关模型
- ✅ `rule.py` 专注于规则管理
- ✅ 职责分离更清晰

### 2. 可维护性提升
- ✅ 更容易找到规则相关代码
- ✅ 减少单个文件的复杂度
- ✅ 便于后续扩展规则功能

### 3. 向后兼容
- ✅ 通过 `__init__.py` 保持导入兼容性
- ✅ 数据库表结构未改变
- ✅ 现有代码无需修改

## 数据库影响

### 表结构
- ✅ `contract_review_rules` 表结构未改变
- ✅ 数据库迁移不需要
- ✅ 现有数据完全保留

### 关系
- ✅ ReviewRule 与其他模型的关系未改变
- ✅ 外键约束保持不变

## 验证清单

- [x] ReviewRule 模型已从 contract.py 移除
- [x] ReviewRule 模型已移至 rule.py
- [x] models/__init__.py 已更新
- [x] 模型导入验证通过
- [x] 数据库表名正确
- [x] 后端服务正常运行
- [x] 登录 API 正常工作

## 总结

✅ **任务完成**: `ReviewRule` 模型已成功从 `contract.py` 移除并移至独立的 `rule.py` 文件。

✅ **向后兼容**: 所有现有代码继续正常工作，无需修改。

✅ **架构优化**: 模块化设计更清晰，便于后续维护和扩展。

---

## 相关文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| [backend/app/models/contract.py](../app/models/contract.py) | 删除 | 移除 ReviewRule 类定义 |
| [backend/app/models/rule.py](../app/models/rule.py) | 新建 | 创建独立的 ReviewRule 模型文件 |
| [backend/app/models/__init__.py](../app/models/__init__.py) | 修改 | 更新导入路径 |
