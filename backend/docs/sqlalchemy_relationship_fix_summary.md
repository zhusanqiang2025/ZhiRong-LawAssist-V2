# SQLAlchemy 关系映射错误修复总结

## 问题描述

### 错误信息
```
sqlalchemy.exc.InvalidRequestError: Could not determine join condition between parent/child tables on relationship ContractReviewTask.contract - there are multiple foreign key paths linking the tables. Specify the 'foreign_keys' argument, providing a list of those columns which should be counted as containing a foreign key reference to the parent table.
```

### 根本原因

在 `ContractDoc` 和 `ContractReviewTask` 两个模型之间存在**多个外键路径**：

1. **ContractDoc.current_review_task_id** → ContractReviewTask.id (多对一)
2. **ContractReviewTask.contract_id** → ContractDoc.id (多对一)

SQLAlchemy 无法自动确定 `ContractReviewTask.contract` 关系应该使用哪个外键。

---

## 已尝试的修复方案

### 方案 1：在 ContractDoc.review_tasks 中指定 foreign_keys ✅

**文件**: `backend/app/models/contract.py`

```python
review_tasks = relationship(
    "ContractReviewTask",
    foreign_keys="ContractReviewTask.contract_id",
    back_populates="contract",
    cascade="all, delete-orphan"
)
```

**状态**: ✅ 已实施

---

### 方案 2：在 ContractReviewTask.contract 中指定 foreign_keys ✅

**文件**: `backend/app/models/contract_review_task.py`

```python
contract = relationship(
    "ContractDoc",
    foreign_keys=[contract_id],
    back_populates="review_tasks"
)
```

**状态**: ✅ 已实施

---

### 方案 3：为 current_review_task_id 创建独立关系 ✅

**文件**: `backend/app/models/contract.py`

```python
# 关系：当前审查任务（多对一）
current_review_task = relationship(
    "ContractReviewTask",
    foreign_keys=[current_review_task_id],
    post_update=True
)

# 关系：审查任务历史（一对多）
review_tasks = relationship(
    "ContractReviewTask",
    foreign_keys="ContractReviewTask.contract_id",
    back_populates="contract",
    cascade="all, delete-orphan"
)
```

**状态**: ✅ 已实施

---

## 当前状态

### 代码修改
- ✅ [backend/app/models/contract.py](../app/models/contract.py) - 已添加 `current_review_task` 关系和明确的 `foreign_keys`
- ✅ [backend/app/models/contract_review_task.py](../app/models/contract_review_task.py) - 已添加 `foreign_keys` 参数

### 服务状态
- ⚠️ 后端服务已启动，但 SQLAlchemy 错误仍然存在
- ⚠️ 登录功能可能受影响

---

## 问题分析

### 为什么修复后仍然报错？

可能的原因：

1. **模块缓存问题**：Python 可能缓存了旧的模块定义
2. **循环导入问题**：模型之间存在循环引用
3. **关系配置冲突**：`back_populates` 和 `foreign_keys` 配置不一致
4. **Uvicorn 热重载限制**：某些更改需要完全重启服务

### 需要的下一步操作

1. **完全重启后端服务**（不是热重载）
   ```bash
   # 停止现有服务
   # Ctrl+C 或 kill 进程

   # 重新启动
   cd "e:\legal_document_assistant v3\backend"
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **清除 Python 缓存**
   ```bash
   cd "e:\legal_document_assistant v3\backend"
   find . -type d -name __pycache__ -exec rm -rf {} +
   find . -type f -name "*.pyc" -delete
   ```

3. **验证数据库连接**
   - 确保 Docker 容器正在运行
   - 检查 `db` 主机名是否可解析

---

## 完整的修复代码

### ContractDoc 模型

```python
class ContractDoc(Base):
    __tablename__ = "contract_docs"

    # ... 其他字段 ...

    current_review_task_id = Column(
        Integer,
        ForeignKey("contract_review_tasks.id"),
        nullable=True,
        comment="当前审查任务ID"
    )

    # 关系：当前审查任务（多对一）
    current_review_task = relationship(
        "ContractReviewTask",
        foreign_keys=[current_review_task_id],
        post_update=True
    )

    # 关系：审查任务历史（一对多）
    review_tasks = relationship(
        "ContractReviewTask",
        foreign_keys="ContractReviewTask.contract_id",
        back_populates="contract",
        cascade="all, delete-orphan"
    )
```

### ContractReviewTask 模型

```python
class ContractReviewTask(Base):
    __tablename__ = "contract_review_tasks"

    # ... 其他字段 ...

    contract_id = Column(
        Integer,
        ForeignKey("contract_docs.id"),
        nullable=False,
        index=True
    )

    # 关系：所属合同（多对一）
    contract = relationship(
        "ContractDoc",
        foreign_keys=[contract_id],
        back_populates="review_tasks"
    )
```

---

## 验证步骤

### 1. 检查模型定义
```python
from app.models.contract import ContractDoc
from app.models.contract_review_task import ContractReviewTask

# 检查关系
print("ContractDoc.relationships:", ContractDoc.__mapper__.relationships.keys())
print("ContractReviewTask.relationships:", ContractReviewTask.__mapper__.relationships.keys())
```

### 2. 测试数据库连接
```python
from app.database import SessionLocal
from app.models.contract import ContractDoc

db = SessionLocal()
try:
    contracts = db.query(ContractDoc).limit(1).all()
    print(f"✅ 数据库连接成功，找到 {len(contracts)} 份合同")
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
finally:
    db.close()
```

### 3. 测试登录功能
在浏览器中访问 `http://localhost:3000` 并尝试登录

---

## 替代方案（如果问题仍然存在）

### 方案 A：移除 current_review_task_id 字段

如果 `current_review_task_id` 不是必需的，可以暂时移除它：

```python
# 在 ContractDoc 中注释掉
# current_review_task_id = Column(Integer, ForeignKey("contract_review_tasks.id"), nullable=True)
# current_review_task = relationship("ContractReviewTask", foreign_keys=[current_review_task_id])
```

### 方案 B：使用 primaryjoin 明确连接条件

```python
from sqlalchemy import and_

# 在 ContractDoc 中
review_tasks = relationship(
    "ContractReviewTask",
    primaryjoin=and_(
        ContractDoc.id == ContractReviewTask.contract_id
    ),
    foreign_keys=[ContractReviewTask.contract_id],
    back_populates="contract",
    cascade="all, delete-orphan"
)
```

### 方案 C：重命名关系以避免歧义

```python
# 在 ContractDoc 中
all_review_tasks = relationship(
    "ContractReviewTask",
    foreign_keys="ContractReviewTask.contract_id",
    back_populates="contract",
    cascade="all, delete-orphan"
)
```

---

## 总结

**已完成的工作**：
- ✅ 修复了 `ContractDoc.review_tasks` 关系，添加了 `foreign_keys` 参数
- ✅ 修复了 `ContractReviewTask.contract` 关系，添加了 `foreign_keys` 参数
- ✅ 为 `current_review_task_id` 创建了独立的关系
- ✅ 添加了详细的代码注释

**需要用户操作**：
- ⚠️ 完全重启后端服务（不是依赖热重载）
- ⚠️ 清除 Python 缓存
- ⚠️ 测试登录功能

**如果问题仍然存在**：
- 考虑使用替代方案 A（移除 `current_review_task_id`）
- 或者使用替代方案 B（使用 `primaryjoin`）

---

## 相关文件

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| [backend/app/models/contract.py](../app/models/contract.py) | 修改 | 添加 `current_review_task` 关系和明确的 `foreign_keys` |
| [backend/app/models/contract_review_task.py](../app/models/contract_review_task.py) | 修改 | 添加 `foreign_keys` 参数到 `contract` 关系 |
