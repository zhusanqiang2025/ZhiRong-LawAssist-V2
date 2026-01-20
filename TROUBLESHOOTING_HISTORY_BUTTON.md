# 历史任务按钮显示问题排查指南

## 问题描述
在风险评估页面顶部看不到"历史任务"按钮

## 已确认正常的部分
✅ 数据库迁移成功（3个新字段已添加）
✅ 后端服务运行中
✅ 前端开发服务器运行中
✅ 代码构建成功（无语法错误）
✅ 组件文件已创建
✅ 代码已正确集成到 RiskAnalysisPageV2.tsx

## 可能的原因和解决方案

### 1. 前端开发服务器未热重载

**解决方案**：重启前端开发服务器

```bash
# 停止当前的前端开发服务器（Ctrl+C）
# 然后重新启动
cd "e:\legal_document_assistant v3\frontend"
npm run dev
```

### 2. 浏览器缓存问题

**解决方案**：硬刷新浏览器
- Windows: `Ctrl + Shift + R` 或 `Ctrl + F5`
- Mac: `Cmd + Shift + R`

### 3. JavaScript 运行时错误

**解决方案**：检查浏览器控制台

1. 打开浏览器开发者工具（F12）
2. 查看 Console 标签页
3. 查找红色错误信息
4. 如果有错误，截图并提供给我

常见的错误可能是：
- 模块导入失败
- 组件未定义
- API 连接错误

### 4. 检查 Network 面板

**解决方案**：检查 API 请求

1. 打开开发者工具（F12）
2. 切换到 Network 标签页
3. 刷新页面
4. 查找 `/api/v1/risk-analysis-v2/sessions` 请求
5. 查看请求状态和响应

### 5. 组件渲染条件

**解决方案**：检查是否有条件渲染

在代码中，历史按钮是通过 `extra` prop 传递给 EnhancedModuleNavBar 的：

```tsx
<EnhancedModuleNavBar
  currentModuleKey="risk-analysis"
  title="风险评估"
  icon={<SafetyOutlined />}
  extra={
    <Space>
      <RiskAnalysisHistoryButton
        count={unreadCount}
        onClick={() => setHistoryVisible(true)}
      />
    </Space>
  }
/>
```

可能是 EnhancedModuleNavBar 组件没有正确显示 `extra` 内容。

## 快速验证方法

### 方法 1：在浏览器控制台直接测试

打开浏览器控制台（F12），输入：

```javascript
// 检查页面是否包含历史按钮文字
document.body.innerText.includes('历史任务')
```

如果返回 `true`，说明按钮在页面上但可能被隐藏。

### 方法 2：检查元素

1. 右键点击页面顶部导航栏
2. 选择"检查"或"检查元素"
3. 在 DOM 树中查找 "历史任务" 文本或 `RiskAnalysisHistoryButton` 组件

### 方法 3：临时添加调试代码

我可以帮您临时修改代码，添加 console.log 来调试：

```tsx
// 在 RiskAnalysisPageV2.tsx 中 EnhancedModuleNavBar 之前添加
console.log('unreadCount:', unreadCount);
console.log('historyVisible:', historyVisible);
console.log('Rendering history button with count:', unreadCount);
```

## 下一步

请尝试以下操作：

1. **首先尝试**：重启前端开发服务器
2. **然后尝试**：硬刷新浏览器（Ctrl+Shift+R）
3. **如果还不行**：打开浏览器控制台查看是否有错误
4. **告诉我**：
   - 控制台有什么错误信息？
   - Network 标签页中 `/api/v1/risk-analysis-v2/sessions` 请求的状态是什么？
   - 页面顶部导航栏长什么样（截图）？

## 替代方案：临时测试 API

如果按钮暂时看不到，您可以直接测试 API：

```bash
# 获取历史会话列表
curl http://localhost:8000/api/v1/risk-analysis-v2/sessions \
  -H "Authorization: Bearer YOUR_TOKEN"
```

或者直接在浏览器访问：
```
http://localhost:8000/docs
```

然后找到 `/api/v1/risk-analysis-v2/sessions` 端点进行测试。
