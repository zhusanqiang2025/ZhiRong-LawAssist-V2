# Celery 系统快速启动指南

## 当前状态

正在构建包含 Celery 依赖的后端 Docker 镜像...

## 构建完成后自动启动

构建完成后，以下服务将自动启动：

1. **backend** - FastAPI 后端服务 (端口 8000)
2. **celery-worker-medium** - Celery 任务处理器 (中优先级队列)
3. **celery-flower** - Celery 监控界面 (端口 5555)
4. **redis** - 消息队列和结果后端
5. **db** - PostgreSQL 数据库

## 启动步骤

### 1. 等待构建完成

构建正在进行中，请耐心等待。构建包含：
- 系统包：LibreOffice、Tesseract OCR、Graphviz 等
- Python 依赖：Celery 5.3.4、celery-progress 0.5、flower 2.0.1 等

### 2. 启动所有服务

```bash
# 构建完成后运行
docker-compose up -d
```

### 3. 验证服务状态

```bash
# 查看所有服务
docker-compose ps

# 预期看到以下服务都在运行:
# - legal_assistant_v3_backend
# - legal_assistant_v3_celery_worker_medium
# - legal_assistant_v3_celery_flower
# - legal_assistant_v3_redis
# - legal_assistant_v3_db
```

### 4. 访问监控界面

打开浏览器访问：
- **Flower 监控**: http://localhost:5555
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **前端界面**: http://localhost:3000

## 快速测试

### 方法 1: 使用 Python 测试脚本

```bash
# 1. 获取访问令牌 (登录)
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# 2. 运行测试脚本
python test_celery_system.py --token YOUR_TOKEN --compare
```

### 方法 2: 使用浏览器测试

1. 打开前端: http://localhost:3000
2. 登录 (admin / admin123)
3. 进入"案件分析"页面
4. 提交一个测试案件
5. 观察实时进度更新
6. **关键测试**: 关闭浏览器，等待几秒后重新打开
   - 旧系统: 任务可能中断
   - 新系统 (Celery): 任务继续执行，可以看到完整进度

### 方法 3: 使用 API 直接测试

```bash
# 1. 登录获取令牌
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' \
  | jq -r '.access_token')

# 2. 启动案件分析
curl -X POST "http://localhost:8000/api/v1/litigation-analysis/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "package_id": "contract_dispute_default",
    "case_type": "contract_performance",
    "case_position": "plaintiff",
    "user_input": "测试 Celery 系统",
    "document_ids": []
  }'

# 响应应包含:
# - "task_system": "celery"
# - "celery_task_id": "xxx-xxx-xxx"

# 3. 查看任务状态 (使用返回的 session_id)
curl -X GET "http://localhost:8000/api/v1/litigation-analysis/{session_id}/status" \
  -H "Authorization: Bearer $TOKEN"
```

## 验证 Celery 是否正常工作

### 1. 检查 Worker 日志

```bash
docker-compose logs -f celery-worker-medium

# 应该看到类似输出:
# [2025-01-14 xx:xx:xx,xxx: INFO/MainProcess] Connected to redis://redis:6379/0
# [2025-01-14 xx:xx:xx,xxx: INFO/MainProcess] celery@xxx ready.
# [2025-01-14 xx:xx:xx,xxx: INFO/MainProcess] Task tasks.litigation_analysis[xxx] received
```

### 2. 检查已注册任务

```bash
docker exec legal_assistant_v3_celery_worker_medium \
  celery -A app.tasks.celery_app inspect registered

# 应该看到:
# - tasks.litigation_analysis
# - tasks.health_check
```

### 3. 在 Flower 中查看

访问 http://localhost:5555，你应该看到：
- Worker 状态在线
- 任务队列信息
- 任务执行历史

## 关键差异对比

### 场景 1: 用户关闭浏览器

**旧系统 (BackgroundTasks)**:
- ❌ 任务可能中断
- ❌ 进度丢失
- ❌ 需要重新提交

**新系统 (Celery)**:
- ✅ 任务继续执行
- ✅ 进度保存在数据库
- ✅ 可以随时查看结果

### 场景 2: 后端服务重启

**旧系统**:
- ❌ 所有正在运行的任务丢失

**新系统**:
- ✅ 任务状态保留在 Redis 和 PostgreSQL
- ✅ Worker 重启后继续处理

### 场景 3: 并发任务

**旧系统**:
- ⚠️ 可能阻塞
- ⚠️ 性能下降

**新系统**:
- ✅ 队列处理
- ✅ 优先级控制
- ✅ 可扩展 Worker

## 环境变量

当前配置 ([.env](.env:91)):
- `CELERY_ENABLED=true` - 启用 Celery 系统
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `CELERY_RESULT_BACKEND=redis://redis:6379/0`

## 切换回旧系统

如果需要切换回旧系统进行对比：

1. 编辑 [.env](.env:91):
   ```
   CELERY_ENABLED=false
   ```

2. 重启后端:
   ```bash
   docker-compose restart backend
   ```

3. (可选) 停止 Celery 服务:
   ```bash
   docker-compose stop celery-worker-medium celery-flower
   ```

## 故障排查

### 问题: Worker 无法启动

```bash
# 检查 Redis 连接
docker exec legal_assistant_v3_redis redis-cli ping

# 检查 Worker 日志
docker-compose logs celery-worker-medium
```

### 问题: 任务不被执行

```bash
# 检查 Worker 是否注册了任务
docker exec legal_assistant_v3_celery_worker_medium \
  celery -A app.tasks.celery_app inspect registered

# 检查队列
docker exec legal_assistant_v3_celery_worker_medium \
  celery -A app.tasks.celery_app inspect active_queues
```

### 问题: Flower 无法访问

```bash
# 检查 Flower 容器状态
docker-compose ps celery-flower

# 重启 Flower
docker-compose restart celery-flower
```

## 下一步

- 阅读 [CELERY_USER_EXPERIENCE_COMPARISON.md](CELERY_USER_EXPERIENCE_COMPARISON.md) 了解详细对比
- 阅读 [CELERY_TESTING_DEPLOYMENT_GUIDE.md](CELERY_TESTING_DEPLOYMENT_GUIDE.md) 了解测试流程
- 阅读 [CELERY_FINAL_SUMMARY.md](CELERY_FINAL_SUMMARY.md) 了解完整实施总结

---

**注意**: 构建过程可能需要 5-10 分钟，具体取决于网络速度和机器性能。
