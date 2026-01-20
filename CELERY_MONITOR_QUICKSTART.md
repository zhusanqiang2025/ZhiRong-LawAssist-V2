# Celery 监控快速开始指南

## 当前状态

✅ **已完成**：
- Celery 5.3.4 已安装并运行
- Celery Worker 正在处理任务
- Flower 监控运行在 http://localhost:5555
- 管理后台已集成 Celery 监控组件

## 立即体验

### 方式 1：通过管理后台（推荐）

1. **打开前端**
   ```
   http://localhost:3000
   ```

2. **登录管理员账户**
   - 邮箱：`test@example.com`
   - 密码：`Test123456`

3. **进入管理后台**
   - 点击页面上的"系统管理"或"管理后台"链接

4. **查看 Celery 监控**
   - 在左侧菜单点击"任务队列监控"
   - 您将看到：
     - Worker 状态卡片
     - 任务统计信息
     - 最近任务列表

### 方式 2：直接访问 Flower

1. **打开浏览器访问**
   ```
   http://localhost:5555
   ```

2. **查看信息**
   - **Dashboard**：总体统计信息
   - **Tasks**：任务列表和详情
   - **Workers**：Worker 状态
   - **Broker**：Redis 连接信息

## 测试 Celery 系统

### 步骤 1：提交一个测试任务

1. 在前端进入"案件分析"功能
2. 填写测试案件信息
3. 提交任务

### 步骤 2：在 Flower 中查看任务执行

1. 打开 http://localhost:5555
2. 点击"Tasks"标签
3. 您应该看到新提交的任务
4. 实时观察任务状态变化：
   - `PENDING`（等待中）
   - `STARTED`（执行中）
   - `SUCCESS`（成功）

### 步骤 3：测试任务持久化（关键测试）

1. 提交一个案件分析任务
2. **立即关闭浏览器**
3. 等待 1-2 分钟
4. 重新打开浏览器并登录
5. 查看任务结果

**预期结果**：
- ✅ 任务仍在后台继续执行
- ✅ 可以查看到完整的任务结果
- ✅ 任务状态正确更新

## 验证 Celery 正常工作

### 检查 Worker 状态

```bash
docker exec legal_assistant_v3_backend celery -A app.tasks.celery_app inspect active
```

**预期输出**：
```
-> worker-medium@0171a042e05d: OK
    * tasks.health_check
    * tasks.litigation_analysis
1 node online.
```

### 检查已注册的任务

```bash
docker exec legal_assistant_v3_backend celery -A app.tasks.celery_app inspect registered
```

### 查看 Worker 日志

```bash
docker exec legal_assistant_v3_backend tail -f /proc/$(pgrep -f "celery.*worker" | head -1)/fd/1 2>/dev/null
```

或者：

```bash
docker logs legal_assistant_v3_backend | grep celery
```

## 常见问题

### Q：看不到任何 Worker
**A**：
1. 检查 Worker 是否运行：
   ```bash
   docker exec legal_assistant_v3_backend ps aux | grep celery
   ```
2. 如果没有运行，启动 Worker：
   ```bash
   docker exec legal_assistant_v3_backend celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2 --queues=medium_priority,default -n worker-medium@%h &
   ```

### Q：Flower 页面无法访问
**A**：
1. 检查代理容器：
   ```bash
   docker ps | grep flower-proxy
   ```
2. 如果没有运行，启动代理：
   ```bash
   docker run -d --name flower-proxy --network legal_document_assistantv3_app-network -p 5555:5555 alpine sh -c "apk add --no-cache socat && socat TCP-LISTEN:5555,fork,reuseaddr TCP:legal_assistant_v3_backend:5555"
   ```

### Q：任务一直是 PENDING 状态
**A**：
1. 检查 Worker 是否在线
2. 检查队列名称是否匹配
3. 重启 Worker：
   ```bash
   docker exec legal_assistant_v3_backend pkill -f celery
   docker exec legal_assistant_v3_backend nohup celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2 --queues=medium_priority,default -n worker-medium@%h &
   ```

### Q：如何启用 Celery 系统？
**A**：
检查 `.env` 文件中的配置：
```bash
CELERY_ENABLED=true
```

如果为 `false`，改为 `true` 并重启后端：
```bash
docker-compose restart backend
```

## 下一步

1. **完善数据库**：导入规则包数据，让案件分析功能可用
2. **性能优化**：根据实际负载调整 Worker 数量和并发配置
3. **监控告警**：配置任务失败告警
4. **扩展功能**：添加更多任务类型（合同审查、风险评估等）

## 相关文档

- [CELERY_MONITOR_INTEGRATION.md](CELERY_MONITOR_INTEGRATION.md) - 详细集成文档
- [CELERY_USER_EXPERIENCE_COMPARISON.md](CELERY_USER_EXPERIENCE_COMPARISON.md) - 用户体验对比
- [CELERY_QUICK_START.md](CELERY_QUICK_START.md) - 快速启动指南
