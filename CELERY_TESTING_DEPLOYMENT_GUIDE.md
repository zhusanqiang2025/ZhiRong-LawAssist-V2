# Celery任务队列系统 - 测试与部署指南

## 部署前准备

### 1. 环境变量配置

在 `.env` 文件中设置以下环境变量：

```bash
# ==================== Celery 任务队列配置 ====================
# 功能开关：是否启用 Celery 任务队列系统
CELERY_ENABLED=false  # 默认关闭，测试时设为 true

# Celery Broker URL (Redis)
CELERY_BROKER_URL=redis://redis:6379/0

# Celery Result Backend (Redis)
CELERY_RESULT_BACKEND=redis://redis:6379/0

# 任务追踪启用
CELERY_TASK_TRACK_STARTED=true

# 任务硬超时（秒）
CELERY_TASK_TIME_LIMIT=3600

# 任务软超时（秒）
CELERY_TASK_SOFT_TIME_LIMIT=3300
```

### 2. 数据库迁移

运行以下命令执行数据库迁移：

```bash
# 进入后端目录
cd backend

# 查看待执行的迁移
alembic current

# 执行迁移
alembic upgrade head

# 验证迁移成功
alembic history
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看特定服务日志
docker-compose logs -f celery-worker-medium
docker-compose logs -f backend
```

---

## 测试流程

### 阶段1：不启用Celery（旧系统）

**目标**：验证旧系统仍能正常工作

#### 步骤

1. **确认环境变量**：
   ```bash
   # 确保 .env 中 CELERY_ENABLED=false
   grep CELERY_ENABLED .env
   ```

2. **重启服务**：
   ```bash
   docker-compose restart backend
   ```

3. **测试案件分析**：
   ```bash
   # 使用 Postman/curl 测试
   curl -X POST "http://localhost:8000/api/v1/litigation-analysis/start" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "package_id": "contract_dispute_default",
       "case_type": "contract_performance",
       "case_position": "plaintiff",
       "user_input": "测试案件分析",
       "document_ids": []
     }'
   ```

4. **验证响应**：
   ```json
   {
     "session_id": "...",
     "status": "pending",
     "task_system": "background_tasks",
     "message": "案件分析已启动"
   }
   ```

5. **查看后端日志**：
   ```bash
   docker-compose logs -f backend | grep "案件分析"
   ```

#### 预期结果

- ✅ 响应中 `task_system` 为 `background_tasks`
- ✅ 任务正常执行
- ✅ 分析能够完成

---

### 阶段2：启用Celery（新系统）

**目标**：验证Celery系统正常工作

#### 步骤

1. **修改环境变量**：
   ```bash
   # 编辑 .env
   nano .env
   # 设置 CELERY_ENABLED=true
   ```

2. **重启服务**：
   ```bash
   docker-compose restart backend celery-worker-medium celery-beat
   ```

3. **验证Worker状态**：
   ```bash
   # 进入Worker容器
   docker exec -it legal_assistant_v3_celery_worker_medium bash

   # 检查Celery状态
   celery -A app.tasks.celery_app inspect active

   # 查看已注册任务
   celery -A app.tasks.celery_app inspect registered
   ```

4. **测试案件分析**：
   ```bash
   curl -X POST "http://localhost:8000/api/v1/litigation-analysis/start" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "package_id": "contract_dispute_default",
       "case_type": "contract_performance",
       "case_position": "plaintiff",
       "user_input": "测试Celery任务",
       "document_ids": []
     }'
   ```

5. **验证响应**：
   ```json
   {
     "session_id": "...",
     "status": "pending",
     "celery_task_id": "xxx-xxx-xxx",
     "task_system": "celery",
     "message": "案件分析已启动 (Celery)"
   }
   ```

6. **查看Worker日志**：
   ```bash
   docker-compose logs -f celery-worker-medium
   ```

   预期看到类似输出：
   ```
   [2025-01-14 10:00:00,123: INFO/MainProcess] Task tasks.litigation_analysis[xxx] received
   [2025-01-14 10:00:05,456: INFO/MainProcess] [xxx] 案件分析任务开始
   [2025-01-14 10:05:30,789: INFO/MainProcess] [xxx] 案件分析完成
   ```

7. **查看Flower监控**：
   - 访问：http://localhost:5555
   - 查看任务执行状态
   - 查看Worker状态
   - 查看任务队列情况

#### 预期结果

- ✅ 响应中包含 `celery_task_id`
- ✅ 响应中 `task_system` 为 `celery`
- ✅ Worker日志显示任务接收和完成
- ✅ Flower监控中显示任务状态
- ✅ 分析结果正确保存

---

### 阶段3：容错测试

**目标**：验证系统容错能力

#### 测试1：Worker重启场景

1. **启动任务**：
   ```bash
   # 启动一个长时间运行的任务
   curl -X POST "http://localhost:8000/api/v1/litigation-analysis/start" ...
   ```

2. **在任务执行中重启Worker**：
   ```bash
   docker-compose restart celery-worker-medium
   ```

3. **验证**：
   - ✅ 任务应被重新执行（取决于配置）
   - ✅ 其他任务不受影响
   - ✅ 没有任务丢失

#### 测试2：Redis断开场景

1. **停止Redis**：
   ```bash
   docker-compose stop redis
   ```

2. **尝试创建任务**：
   ```bash
   curl -X POST "http://localhost:8000/api/v1/litigation-analysis/start" ...
   ```

3. **验证**：
   - ✅ 应返回错误或降级到BackgroundTasks
   - ✅ 系统不会崩溃

4. **恢复Redis**：
   ```bash
   docker-compose start redis
   ```

5. **验证恢复**：
   - ✅ 新任务可以正常创建
   - ✅ Worker重新连接

#### 测试3：用户断开连接场景

1. **启动任务后立即关闭WebSocket**
2. **验证**：
   - ✅ 任务继续在后台执行
   - ✅ 结果保存到数据库
   - ✅ 用户可以重新连接查看结果

---

### 阶段4：性能测试

**目标**：验证系统性能和可扩展性

#### 测试1：并发任务

```bash
# 使用脚本并发创建多个任务
for i in {1..10}; do
  curl -X POST "http://localhost:8000/api/v1/litigation-analysis/start" \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"package_id\":\"contract_dispute_default\",\"case_type\":\"contract_performance\",\"case_position\":\"plaintiff\",\"user_input\":\"并发测试 $i\",\"document_ids\":[]}" &
done
wait
```

**验证**：
- ✅ 所有任务都被接受
- ✅ Worker正确处理并发
- ✅ 没有任务丢失
- ✅ Flower监控显示队列长度

#### 测试2：长时间运行任务

1. 创建一个包含大量文档的分析任务
2. 监控：
   - 内存使用情况
   - 任务进度更新
   - 超时处理

**验证**：
- ✅ 内存使用稳定（Worker会在100个任务后重启）
- ✅ 进度正常更新
- ✅ 超时机制正常工作

---

## 常见问题排查

### 问题1：Worker无法启动

**症状**：
```bash
docker-compose logs celery-worker-medium
# 显示连接错误
```

**解决方案**：
```bash
# 检查Redis是否运行
docker-compose ps redis

# 检查Redis连接
docker exec -it legal_assistant_v3_redis redis-cli ping

# 检查网络
docker network inspect legal_document_assistant_v3_app-network
```

### 问题2：任务不被执行

**症状**：
- 任务状态一直是 `PENDING`
- Flower中看不到任务

**解决方案**：
```bash
# 检查Worker是否注册了任务
docker exec -it legal_assistant_v3_celery_worker_medium celery -A app.tasks.celery_app inspect registered

# 检查队列配置
docker exec -it legal_assistant_v3_celery_worker_medium celery -A app.tasks.celery_app inspect active_queues

# 手动触发任务
docker exec -it legal_assistant_v3_celery_worker_medium celery -A app.tasks.celery_app call tasks.health_check
```

### 问题3：任务执行失败

**症状**：
- Worker日志显示异常
- 任务状态为 `FAILED`

**解决方案**：
```bash
# 查看详细错误
docker-compose logs celery-worker-medium | tail -100

# 检查数据库连接
docker exec -it legal_assistant_v3_backend python -c "from app.database import SessionLocal; print('DB OK')"

# 检查环境变量
docker exec -it legal_assistant_v3_celery_worker_medium env | grep CELERY
```

### 问题4：Flower无法访问

**症状**：
- http://localhost:5555 无法打开

**解决方案**：
```bash
# 检查Flower容器状态
docker-compose ps celery-flower

# 查看Flower日志
docker-compose logs celery-flower

# 重启Flower
docker-compose restart celery-flower
```

---

## 性能优化建议

### 1. Worker配置调优

根据服务器资源调整Worker并发数：

```yaml
# docker-compose.yml
celery-worker-medium:
  command: >
    celery -A app.tasks.celery_app worker
    --loglevel=info
    --concurrency=4  # 根据CPU核心数调整
    --queue=medium_priority,default
    -n worker-medium@%h
    --max-tasks-per-child=100
```

### 2. Redis持久化

确保Redis开启AOF持久化：

```yaml
redis:
  command: redis-server --appendonly yes
```

### 3. 监控告警

建议配置以下监控指标：
- Worker健康状态
- 任务队列长度
- 任务执行时间
- 任务失败率

---

## 部署检查清单

- [ ] 环境变量已配置（`.env`）
- [ ] 数据库迁移已执行
- [ ] 所有服务正常启动
- [ ] Worker注册了任务
- [ ] Flower监控可访问
- [ ] 旧系统测试通过（`CELERY_ENABLED=false`）
- [ ] 新系统测试通过（`CELERY_ENABLED=true`）
- [ ] 容错测试通过
- [ ] 性能测试通过
- [ ] 日志和监控已配置

---

## 回滚方案

如果新系统出现问题，可以快速回滚：

```bash
# 1. 关闭Celery功能
# 编辑 .env，设置 CELERY_ENABLED=false

# 2. 重启backend
docker-compose restart backend

# 3. （可选）停止Celery Workers
docker-compose stop celery-worker-high celery-worker-medium celery-worker-low celery-beat celery-flower

# 系统将使用旧的BackgroundTasks系统继续运行
```

---

## 联系方式

如有问题，请联系开发团队。
