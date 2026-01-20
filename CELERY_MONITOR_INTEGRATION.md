# Celery 监控集成到管理后台

## 功能说明

Flower 监控页面已经成功集成到系统管理后台，提供以下功能：

### 1. **实时监控面板**
- **统计数据卡片**：
  - 活跃 Worker 数量
  - 总任务数
  - 成功任务数
  - 失败任务数

- **Worker 状态卡片**：
  - 每个 Worker 的在线状态
  - 并发数配置
  - 当前活跃任务数
  - 成功/失败任务统计
  - 负载进度条

- **任务列表**：
  - 最近 50 个任务的详细信息
  - 任务状态标签（等待中、执行中、成功、失败、重试中、已撤销）
  - 任务执行时间
  - 重试次数
  - 操作按钮（查看详情、撤销任务）

### 2. **任务管理功能**
- **查看任务详情**：查看任务的参数、结果、错误信息
- **撤销任务**：可以撤销等待中或执行中的任务
- **实时刷新**：每 5 秒自动刷新数据
- **手动刷新**：点击刷新按钮立即更新

### 3. **快速链接**
- 点击"打开 Flower 完整界面"按钮，可以跳转到原生的 Flower 监控界面（http://localhost:5555）

## 访问方式

### 通过管理后台访问

1. 登录系统（使用管理员账户）
2. 进入"系统管理后台"
3. 点击左侧菜单的"任务队列监控"

### 直接访问 Flower

在浏览器中打开：http://localhost:5555

## API 端点

后端提供了以下 API 端点供前端调用：

| 端点 | 方法 | 描述 | 权限 |
|------|------|------|------|
| `/api/v1/admin/celery/stats` | GET | 获取 Celery 统计数据 | 管理员 |
| `/api/v1/admin/celery/tasks/{task_id}` | GET | 获取任务详情 | 管理员 |
| `/api/v1/admin/celery/tasks/{task_id}/revoke` | POST | 撤销任务 | 管理员 |
| `/api/v1/admin/celery/workers/{worker_name}/shutdown` | POST | 关闭 Worker | 管理员 |
| `/api/v1/admin/celery/purge` | POST | 清空队列 | 管理员 |
| `/api/v1/admin/celery/configuration` | GET | 获取 Celery 配置 | 管理员 |

## 使用场景

### 1. **日常监控**
- 定期查看 Worker 状态，确保所有 Worker 正常运行
- 监控任务队列长度，及时发现任务堆积
- 查看任务成功率，识别问题任务

### 2. **故障排查**
- 查看失败任务的错误信息和堆栈跟踪
- 识别执行时间过长的任务
- 检查 Worker 是否过载

### 3. **性能优化**
- 分析任务执行时间分布
- 识别需要优化的慢任务
- 根据负载情况调整 Worker 数量

### 4. **任务管理**
- 撤销不需要的任务
- 清空积压的任务队列
- 重启有问题的 Worker

## 监控指标说明

### Worker 指标
- **并发数（Concurrency）**：Worker 可以同时执行的任务数
- **活跃任务数（Active Tasks）**：当前正在执行的任务数
- **负载进度条**：显示 Worker 的使用率
  - 绿色：正常负载
  - 红色：过载

### 任务指标
- **状态（State）**：
  - `PENDING`：等待执行
  - `STARTED`：正在执行
  - `SUCCESS`：执行成功
  - `FAILURE`：执行失败
  - `RETRY`：等待重试
  - `REVOKED`：已撤销

- **执行时间（Runtime）**：任务从开始到完成的时间（秒）

- **重试次数（Retries）**：任务已重试的次数

## 集成架构

```
┌─────────────────┐
│   管理员后台    │
│   (AdminPage)   │
└────────┬────────┘
         │
         │ HTTP API
         ▼
┌─────────────────┐
│ Celery Monitor  │
│     API         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Celery App    │
│  (inspect API)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Redis Broker   │
│  + Workers      │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   Flower UI     │
│   (端口 5555)   │
└─────────────────┘
```

## 前端组件

### 文件位置
- 组件：`frontend/src/pages/admin/views/CeleryMonitor.tsx`
- 页面：`frontend/src/pages/AdminPage.tsx`

### 组件功能
- **实时数据更新**：每 5 秒自动刷新
- **响应式布局**：适配不同屏幕尺寸
- **交互式操作**：支持任务撤销、详情查看
- **状态可视化**：使用颜色和图标直观显示状态

## 后端实现

### 文件位置
- API 端点：`backend/app/api/v1/endpoints/celery_monitor.py`
- 路由注册：`backend/app/api/v1/router.py`

### API 功能
- 使用 Celery 的 `inspect` API 获取 Worker 和任务信息
- 支持任务撤销、Worker 关闭等管理操作
- 提供统计数据供前端展示

## 扩展建议

### 1. **添加更多图表**
- 任务执行时间分布图
- 任务成功率趋势图
- Worker 负载历史曲线

### 2. **告警功能**
- 任务失败率超过阈值时告警
- Worker 离线告警
- 队列积压告警

### 3. **任务过滤和搜索**
- 按状态过滤任务
- 按时间范围筛选
- 按任务名称搜索

### 4. **批量操作**
- 批量撤销任务
- 批量重试失败任务
- 批量清理已完成任务

## 注意事项

1. **权限控制**：所有 Celery 监控 API 都需要管理员权限
2. **性能影响**：避免频繁刷新统计数据（建议至少间隔 5 秒）
3. **数据保留**：Redis 中的任务结果会过期，建议定期清理
4. **安全性**：Flower 界面不应暴露到公网，仅限内网访问

## 故障排查

### 问题：无法看到 Worker
- 检查 Worker 是否正在运行：`docker exec legal_assistant_v3_backend celery -A app.tasks.celery_app inspect active`
- 检查 Redis 连接：`docker exec legal_assistant_v3_redis redis-cli ping`

### 问题：任务不更新
- 重启 Worker：`docker exec legal_assistant_v3_backend pkill -f celery`
- 检查 Celery 配置：查看 `.env` 中的 `CELERY_BROKER_URL` 和 `CELERY_RESULT_BACKEND`

### 问题：Flower 无法访问
- 检查代理容器：`docker ps | grep flower-proxy`
- 重启代理：`docker restart flower-proxy`
- 检查端口占用：`netstat -an | grep 5555`
