# 合同生成模块 - 数据库迁移执行指南

## Stage 2 (P1): 数据持久化集成 - 迁移步骤

本文档说明如何执行数据库迁移和验证集成功能。

---

## 前置条件

1. **数据库运行中**
   ```bash
   # 检查 PostgreSQL 是否运行
   # Windows: 打开服务管理器查看 PostgreSQL 服务状态
   # 或使用命令:
   pg_isready -h localhost -p 5432
   ```

2. **环境变量配置**
   - 检查 `.env` 文件中的数据库连接配置
   - 确保 `DATABASE_URL` 正确配置

3. **Python 虚拟环境**
   - 激活虚拟环境
   - 安装所有依赖

---

## 步骤 1: 执行数据库迁移

### 1.1 检查当前迁移状态

```bash
cd backend
alembic current
```

**预期输出**:
```
Current revision(s): 20260116_add_evaluation_stance
```

### 1.2 查看待执行的迁移

```bash
alembic history
```

**预期输出** (最后几行):
```
...
<Rev> 20260116_add_evaluation_stance (current)
<Rev> 20260117_add_contract_generation_indexes (head)
```

### 1.3 执行迁移

```bash
alembic upgrade head
```

**预期输出**:
```
Running upgrade 20260116_add_evaluation_stance -> 20260117_add_contract_generation_indexes
```

### 1.4 验证迁移成功

```bash
alembic current
```

**预期输出**:
```
Current revision(s): 20260117_add_contract_generation_indexes
```

---

## 步骤 2: 验证索引创建

### 2.1 连接到数据库

```bash
psql -h localhost -U your_username -d your_database
```

### 2.2 查询创建的索引

```sql
-- 查询 tasks 表的所有索引
SELECT
    indexname,
    indexdef
FROM
    pg_indexes
WHERE
    tablename = 'tasks'
    AND (
        indexname LIKE '%contract_generation%'
        OR indexname LIKE '%owner_type_created%'
        OR indexname LIKE '%params_planning_mode%'
    )
ORDER BY
    indexname;
```

**预期结果**:
- `ix_tasks_owner_type_created` - 复合索引
- `ix_tasks_params_planning_mode` - 表达式索引
- `ix_tasks_contract_gen_status` - 部分索引

### 2.3 验证索引详情

```sql
-- 查看复合索引定义
\d+ tasks

-- 或使用 pg_indexes 视图查看具体定义
SELECT indexname, indexdef FROM pg_indexes WHERE indexname = 'ix_tasks_owner_type_created';
```

---

## 步骤 3: 运行集成测试

### 3.1 确保有测试用户

在执行测试前，确保数据库中存在 ID 为 1 的用户，或修改测试脚本使用实际的用户 ID。

```sql
-- 查询现有用户
SELECT id, username FROM users LIMIT 5;
```

### 3.2 运行测试脚本

```bash
cd backend
python tests/test_contract_generation_db_integration.py
```

**预期输出**:
```
============================================================
合同生成模块 - 数据库集成测试
============================================================

测试 1: 验证数据库索引
------------------------------------------------------------
✅ 索引 ix_tasks_owner_type_created 已创建
✅ 索引 ix_tasks_params_planning_mode 已创建
✅ 索引 ix_tasks_contract_gen_status 已创建

测试 2: CRUD 操作功能
------------------------------------------------------------
2.1 创建合同生成任务
✅ 创建合同生成任务
   任务 ID: xxx-xxx-xxx
   任务类型: contract_generation
   规划模式: multi_model

2.2 获取合同生成任务列表
✅ 获取任务列表 (找到 1 个任务)

2.3 更新任务进度
✅ 更新任务进度

2.4 保存融合报告
✅ 保存融合报告

2.5 更新任务结果
✅ 更新任务结果

2.6 按状态筛选
✅ 按状态筛选 (找到 1 个已完成任务)
✅ 清理测试数据

...

============================================================
🎉 所有测试通过！
============================================================
```

---

## 步骤 4: API 端点测试

### 4.1 启动后端服务

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 测试历史任务端点

#### 4.2.1 获取任务列表

```bash
# 需要先登录获取 token
curl -X GET "http://localhost:8000/api/contract-generation/tasks?skip=0&limit=20" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**预期响应**:
```json
{
  "tasks": [
    {
      "id": "task-id-1",
      "status": "completed",
      "progress": 100.0,
      "created_at": "2026-01-17T10:30:00",
      "planning_mode": "multi_model",
      "user_input": "用户需求描述",
      "has_synthesis_report": true,
      "error_message": null
    }
  ],
  "total": 1
}
```

#### 4.2.2 获取任务详情

```bash
curl -X GET "http://localhost:8000/api/contract-generation/tasks/TASK_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**预期响应**:
```json
{
  "id": "task-id-1",
  "status": "completed",
  "progress": 100.0,
  "current_node": "completed",
  "node_progress": {...},
  "workflow_steps": [...],
  "created_at": "2026-01-17T10:30:00",
  "task_params": {
    "user_input": "用户需求描述",
    "planning_mode": "multi_model",
    "uploaded_files": []
  },
  "result_data": {
    "multi_model_synthesis_report": {...},
    "generated_contracts": [...]
  }
}
```

### 4.3 测试合同生成端点（带任务记录）

```bash
curl -X POST "http://localhost:8000/api/contract-generation/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "user_input=生成一份买卖合同" \
  -F "planning_mode=multi_model"
```

**验证**:
1. 检查返回的响应中是否包含 `task_id`
2. 查询数据库确认任务记录已创建
3. 检查任务进度更新

---

## 步骤 5: Celery 任务集成测试

### 5.1 启动 Celery Worker

```bash
cd backend
celery -A app.tasks.celery_app worker -l info -Q high_priority
```

### 5.2 提交异步任务

通过 API 提交合同生成任务（确保 `CELERY_ENABLED=true`）。

### 5.3 监控任务执行

```bash
# 使用 Flower 监控
celery -A app.tasks.celery_app flower
```

访问 http://localhost:5555 查看任务状态。

### 5.4 验证数据库记录

检查数据库中的任务记录是否正确更新：
- `status` 从 `pending` → `running` → `completed`
- `progress` 从 0 → 10 → 30 → 100
- `result_data` 包含融合报告和生成结果

```sql
SELECT
    id,
    status,
    progress,
    task_params->>'planning_mode' as planning_mode,
    result_data->'multi_model_synthesis_report'->>'fusion_summary' as fusion_summary
FROM tasks
WHERE task_type = 'contract_generation'
ORDER BY created_at DESC
LIMIT 5;
```

---

## 常见问题排查

### 问题 1: 迁移失败 - 数据库连接错误

**错误信息**:
```
sqlalchemy.exc.OperationalError: could not translate host name "db" to address
```

**解决方案**:
- 检查 `.env` 文件中的 `DATABASE_URL`
- 确保数据库正在运行
- 确保网络连接正常

### 问题 2: 索引创建失败 - 不支持表达式索引

**错误信息**:
```
syntax error near or at "->>"
```

**解决方案**:
- 迁移脚本已包含降级逻辑
- 如果数据库不支持表达式索引，会自动创建普通索引
- 这不会影响核心功能

### 问题 3: 测试失败 - 用户不存在

**错误信息**:
```
sqlalchemy.exc.IntegrityError: FOREIGN KEY constraint failed
```

**解决方案**:
- 修改测试脚本中的 `owner_id` 为实际存在的用户 ID
- 或在测试前创建测试用户

### 问题 4: Celery 任务未创建数据库记录

**可能原因**:
1. `owner_id` 未传递到 Celery 任务
2. 数据库会话未正确关闭
3. 异常未被正确捕获

**解决方案**:
- 检查 API 层是否正确传递 `owner_id`
- 检查 Celery 任务的 `finally` 块是否执行
- 查看 Celery worker 日志

---

## 回滚步骤

如果需要回滚迁移：

```bash
alembic downgrade -1
```

或回滚到特定版本：

```bash
alembic downgrade 20260116_add_evaluation_stance
```

---

## 验收标准

迁移和测试成功应满足以下标准：

1. ✅ 所有三个索引已创建
2. ✅ 集成测试全部通过
3. ✅ API 端点正常响应
4. ✅ Celery 任务正确创建和更新数据库记录
5. ✅ 融合报告正确保存到 `result_data` 字段
6. ✅ 任务进度正确更新（10% → 30% → 100%）

---

## 下一步

完成 Stage 2 后，可以继续：

1. **Stage 3 (P2)**: 优化和监控
   - 增强配置验证
   - 添加监控指标
   - 性能优化

2. **前端适配**: 创建历史任务管理页面
   - 展示任务列表
   - 查看任务详情
   - 恢复暂停的任务

3. **端到端测试**: 完整的用户流程测试
   - 单模型规划流程
   - 多模型规划流程
   - 错误处理和重试

---

## 联系和支持

如有问题，请查看：
- 项目文档: `📄 合同生成模块产品开发文档 (V2.0 - 完整版).md`
- 升级计划: `C:\Users\44314\.claude\plans\expressive-swimming-panda.md`
- 代码注释: 各模块文件中的详细注释
