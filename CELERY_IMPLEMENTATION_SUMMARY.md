# Celery任务队列系统实施总结

## 实施日期
2026-01-14

## 实施阶段
✅ **阶段1：准备阶段（不破坏现有功能）** - 已完成

---

## 已完成的工作

### 1. 依赖安装
**文件**: [backend/requirements.txt](backend/requirements.txt:106-109)

添加了以下Celery相关依赖：
- `celery==5.3.4` - Celery任务队列核心库
- `celery-progress==0.3.1` - 进度追踪库
- `flower==2.0.1` - Celery监控工具

### 2. Celery应用配置
**文件**: [backend/app/tasks/celery_app.py](backend/app/tasks/celery_app.py) (新建)

创建了Celery应用配置，包括：
- Redis作为Broker和Result Backend
- 三个优先级队列（high_priority, medium_priority, low_priority）
- 任务路由配置
- 超时和重试配置
- Worker配置（并发数、任务数限制等）
- 时区配置（Asia/Shanghai）

### 3. 任务基类
**文件**: [backend/app/tasks/base_task.py](backend/app/tasks/base_task.py) (新建)

实现了两个任务基类：
- `DatabaseTask`: 提供数据库持久化、任务成功/失败钩子
- `WebSocketProgressTask`: 继承DatabaseTask，额外提供WebSocket进度推送

### 4. 进度追踪工具
**文件**: [backend/app/tasks/progress.py](backend/app/tasks/progress.py) (新建)

实现了进度追踪功能：
- `update_progress()`: 更新任务进度到数据库和WebSocket
- `send_task_notification()`: 发送任务通知
- `ProgressTracker`: 进度追踪器类

### 5. Docker配置
**文件**: [docker-compose.yml](docker-compose.yml:37-183)

添加了以下Celery服务：
- `celery-worker-high`: 高优先级Worker（合同生成、文书起草）
- `celery-worker-medium`: 中优先级Worker（案件分析、风险评估）
- `celery-worker-low`: 低优先级Worker（合同审查、批量处理）
- `celery-beat`: 定时任务调度器
- `celery-flower`: 监控工具（端口5555）

### 6. 数据库扩展
**文件**: [backend/app/models/task.py](backend/app/models/task.py:61-82)

扩展了Task模型，添加Celery集成字段：
- `celery_task_id`: Celery任务ID
- `worker_name`: Worker名称
- `queue_name`: 队列名称
- `task_type`: 任务类型
- `last_retry_at`: 最后重试时间
- `task_params`: 任务参数（JSON）
- `result_data`: 结果数据（JSON）

### 7. 案件分析任务迁移
**文件**: [backend/app/tasks/litigation_analysis_tasks.py](backend/app/tasks/litigation_analysis_tasks.py:26-187)

将案件分析任务改造为Celery任务：
- 使用`@celery_app.task`装饰器
- 继承`DatabaseTask`基类
- 添加进度追踪
- 添加自动重试机制（最多3次，间隔60秒）
- 保留旧版本函数以兼容

### 8. 任务管理API
**文件**: [backend/app/api/v1/endpoints/tasks.py](backend/app/api/v1/endpoints/tasks.py:17-279)

添加了统一任务管理接口：
- `POST /api/v1/tasks/create`: 创建任务
- `GET /api/v1/tasks/{task_id}/status`: 获取任务状态
- `POST /api/v1/tasks/{task_id}/cancel`: 取消任务
- `GET /api/v1/tasks/{task_id}/result`: 获取任务结果

### 9. 前端WebSocket管理器
**文件**: [frontend/src/utils/WebSocketManager.ts](frontend/src/utils/WebSocketManager.ts) (新建)

实现了前端WebSocket管理器：
- 自动连接管理
- 断线自动重连（最多5次）
- 降级轮询机制
- 事件处理系统

### 10. 环境变量配置
**文件**: [.env](.env:85-95)

添加了Celery配置环境变量：
- `CELERY_BROKER_URL`: Redis Broker地址
- `CELERY_RESULT_BACKEND`: Redis结果后端地址
- `CELERY_TASK_TRACK_STARTED`: 启用任务追踪
- `CELERY_TASK_TIME_LIMIT`: 任务硬超时
- `CELERY_TASK_SOFT_TIME_LIMIT`: 任务软超时

---

## 系统架构

```
┌─────────────────┐
│   FastAPI       │
│   主进程         │
│  (接收请求)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Redis Broker  │◄──────────────┐
│   (消息队列)     │               │
└────────┬────────┘               │
         │                         │
         ▼                         │
┌─────────────────┐               │
│  Celery Worker  │               │
│  ┌───────────┐  │               │
│  │ Worker 1  │  │ (高优先级)     │
│  │ 合同生成   │  │               │
│  │ 文书起草   │  │               │
│  └───────────┘  │               │
│  ┌───────────┐  │               │
│  │ Worker 2  │  │ (中优先级)     │
│  │ 案件分析   │  │               │
│  │ 风险评估   │  │               │
│  └───────────┘  │               │
│  ┌───────────┐  │               │
│  │ Worker 3  │  │ (低优先级)     │
│  │ 合同审查   │  │               │
│  └───────────┘  │               │
└────────┬────────┘               │
         │                        │
         ▼                        │
┌─────────────────┐               │
│  PostgreSQL     │               │
│  (任务持久化)    │               │
└─────────────────┘               │
                                   │
┌──────────────────────────────────┘
│  WebSocket进度推送流程:
│  1. Worker更新进度到Redis
│  2. Progress监听器推送进度
│  3. 前端实时显示
└──────────────────────────────────┘
```

---

## 使用指南

### 开发环境启动

```bash
# 启动所有服务
docker-compose up -d

# 查看Worker日志
docker-compose logs -f celery-worker-medium

# 查看Flower监控
# 访问 http://localhost:5555
```

### 创建任务（Python）

```python
from app.tasks.litigation_analysis_tasks import litigation_analysis_task

# 异步执行任务
result = litigation_analysis_task.apply_async(
    args=["session_123", "用户需求", ["doc1.pdf", "doc2.pdf"]],
    priority=5,
    queue="medium_priority"
)

# 获取任务ID
task_id = result.id
```

### 创建任务（API）

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/create" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "litigation_analysis",
    "params": {
      "session_id": "session_123",
      "user_input": "用户需求",
      "document_paths": ["doc1.pdf", "doc2.pdf"]
    },
    "priority": 5
  }'
```

### 前端使用WebSocket

```typescript
import { TaskWebSocketManager } from '@/utils/WebSocketManager';

const wsManager = new TaskWebSocketManager();

// 连接WebSocket
wsManager.connect(taskId);

// 监听进度
wsManager.on('progress', (data) => {
  console.log('Progress:', data.progress);
  console.log('Current node:', data.current_node);
});

// 监听完成事件
wsManager.on('completed', (data) => {
  console.log('Task completed:', data);
});
```

---

## 下一步工作

### 阶段2：并行运行（新旧系统共存）

1. 将案件分析API端点适配为Celery版本
2. 添加功能开关控制使用哪种任务系统
3. 对比测试两种方案的性能
4. 修复发现的问题

### 阶段3：完全迁移

1. 将风险评估迁移到Celery
2. 将合同审查迁移到Celery
3. 移除旧的BackgroundTasks代码
4. 更新所有API端点

### 阶段4：扩展到其他模块

1. 合同生成模块迁移
2. 文书起草模块迁移
3. 性能优化和监控

---

## 监控和维护

### Flower监控
- 访问地址: http://localhost:5555
- 功能: 查看任务状态、Worker状态、执行时间等

### 日志查看
```bash
# 查看Worker日志
docker-compose logs -f celery-worker-medium

# 查看Beat日志
docker-compose logs -f celery-beat
```

### 常用命令
```bash
# 检查Worker状态
celery -A app.tasks.celery_app inspect active

# 查看已注册任务
celery -A app.tasks.celery_app inspect registered

# 查看Worker统计
celery -A app.tasks.celery_app inspect stats
```

---

## 注意事项

1. **数据库迁移**: 需要运行数据库迁移以添加新的Celery字段到tasks表
2. **Redis持久化**: Redis配置了AOF持久化，确保任务不会丢失
3. **Worker重启**: 每个Worker处理100个任务后会自动重启（防止内存泄漏）
4. **任务超时**: 默认硬超时1小时，软超时55分钟
5. **重试机制**: 任务失败后最多重试3次，每次间隔60秒

---

## 联系方式

如有问题，请联系开发团队。
