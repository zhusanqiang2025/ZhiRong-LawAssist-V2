# 前端页面更新指南

## 问题描述
管理后台的"任务队列监控"菜单项已添加，但浏览器可能缓存了旧版本的页面。

## 解决方案

### 方法 1：强制刷新浏览器（推荐）

1. **打开管理后台页面** (http://localhost:3000/admin)
2. **强制刷新**：
   - Windows: `Ctrl + Shift + R` 或 `Ctrl + F5`
   - Mac: `Cmd + Shift + R`
3. 如果还是看不到，尝试方法 2

### 方法 2：清除浏览器缓存

#### Chrome/Edge
1. 打开开发者工具 (`F12`)
2. 右键点击刷新按钮
3. 选择"清空缓存并硬性重新加载"

#### Firefox
1. 打开开发者工具 (`F12`)
2. 按住 `Shift` 点击刷新按钮
3. 选择"清空缓存"

### 方法 3：无痕模式测试

1. 打开无痕/隐私浏览窗口
2. 访问 http://localhost:3000/admin
3. 检查是否能看到"任务队列监控"菜单项

### 方法 4：重启前端服务

如果以上方法都不行，重启前端服务：

```bash
cd "e:\legal_document_assistant v3"
docker-compose restart frontend
```

等待 5-10 秒后，使用方法 1 强制刷新。

## 验证步骤

1. 登录管理员账户
2. 进入系统管理后台
3. 查看左侧菜单，应该包含：
   - 数据仪表盘
   - 合同分类管理
   - 知识图谱管理
   - 模板管理
   - 审查规则管理
   - 风险评估规则包
   - **任务队列监控** ← 新增的菜单项

4. 点击"任务队列监控"，应该看到：
   - Celery 任务队列监控标题
   - 系统说明（蓝色提示框）
   - Flower 链接 (http://localhost:5555)
   - 快速测试说明
   - 当前状态（绿色提示框）

## 技术说明

前端容器已成功重新构建并部署（时间戳：2026-01-14 06:25），新代码已经生效。

文件位置：
- 组件：[frontend/src/pages/admin/views/CeleryMonitor.tsx](frontend/src/pages/admin/views/CeleryMonitor.tsx)
- 页面：[frontend/src/pages/AdminPage.tsx](frontend/src/pages/AdminPage.tsx) (第 23、53、80 行)

菜单配置（第 80 行）：
```tsx
{ key: 'celery-monitor', icon: <MonitorOutlined />, label: '任务队列监控' }
```

## 如果问题仍然存在

请执行以下命令并提供输出：

```bash
# 检查前端容器状态
docker ps | grep frontend

# 查看前端日志
docker logs legal_assistant_v3_frontend --tail 20

# 检查文件时间戳
docker exec legal_assistant_v3_frontend sh -c "ls -la /usr/share/nginx/html/"
```
