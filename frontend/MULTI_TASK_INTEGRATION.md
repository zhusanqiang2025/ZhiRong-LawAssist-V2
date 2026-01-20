# 风险评估多任务功能集成指南

## 概述

本指南说明如何在现有的 `RiskAnalysisPageV2` 中集成多任务支持功能。

## 快速开始

### 方式 1：使用包装组件（推荐）

最简单的方式是使用 `RiskAnalysisMultiTaskWrapper` 包装现有的页面内容：

```tsx
// frontend/src/pages/RiskAnalysisPageV2.tsx

import RiskAnalysisMultiTaskWrapper from '../components/RiskAnalysisMultiTaskWrapper';

const RiskAnalysisPageV2: React.FC = () => {
  // ... 原有的状态和逻辑 ...

  return (
    <Layout>
      <EnhancedModuleNavBar currentModuleKey="risk-analysis" />

      <Content style={{ padding: '24px' }}>
        {/* 使用多任务包装组件 */}
        <RiskAnalysisMultiTaskWrapper
          currentTaskId={analysisState.sessionId}
          onSwitchTask={(sessionId) => {
            // 处理任务切换
            console.log('切换到任务:', sessionId);
            // 重新加载该任务的状态
            loadTaskStatus(sessionId);
          }}
          showTaskList={true}
        >
          {/* 原有的页面内容 */}
          {currentStep === 0 && renderInputPage()}
          {currentStep === 1 && renderProgressPage()}
          {currentStep === 2 && renderResultsPage()}
        </RiskAnalysisMultiTaskWrapper>
      </Content>
    </Layout>
  );
};
```

### 方式 2：手动集成（高级）

如果需要更细粒度的控制，可以手动集成各个组件：

```tsx
import { useRiskAnalysisTasks } from '../hooks/useRiskAnalysisTasks';
import TaskStatsBar from '../components/TaskStatsBar';
import RiskAnalysisTaskList from '../components/RiskAnalysisTaskList';

const RiskAnalysisPageV2: React.FC = () => {
  const {
    tasks,
    activeTaskId,
    createTask,
    switchTask,
    removeTask,
    refreshTaskList,
    canCreateNew,
    getInProgressCount,
    getCompletedCount
  } = useRiskAnalysisTasks();

  return (
    <Layout>
      <Content>
        {/* 任务统计栏 */}
        <TaskStatsBar
          inProgressCount={getInProgressCount()}
          completedCount={getCompletedCount()}
          onRefresh={refreshTaskList}
        />

        <Row gutter={16}>
          {/* 主内容区 */}
          <Col span={14}>
            {/* 原有内容 */}
          </Col>

          {/* 任务列表 */}
          <Col span={10}>
            <RiskAnalysisTaskList
              tasks={Array.from(tasks.values())}
              activeTaskId={activeTaskId}
              onTaskClick={switchTask}
              onTaskDelete={removeTask}
            />
          </Col>
        </Row>
      </Content>
    </Layout>
  );
};
```

## API 参考

### RiskAnalysisMultiTaskWrapper

| 属性 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `children` | `ReactNode` | - | 主内容区（原有的页面内容） |
| `currentTaskId` | `string \| null` | `null` | 当前任务 ID |
| `onCreateTask` | `(sessionId: string) => void` | - | 任务创建回调 |
| `onSwitchTask` | `(sessionId: string) => void` | - | 任务切换回调 |
| `showTaskList` | `boolean` | `true` | 是否显示任务列表 |
| `drawerMode` | `boolean` | `false` | 是否使用抽屉模式 |

### useRiskAnalysisTasks Hook

```typescript
const {
  // 状态
  tasks,                    // Map<string, AnalysisState> - 所有任务
  activeTaskId,             // string | null - 当前活动任务 ID
  isLoading,                // boolean - 是否正在加载

  // 操作方法
  createTask,               // (params) => Promise<string | null> - 创建新任务
  switchTask,               // (sessionId) => void - 切换活动任务
  removeTask,               // (sessionId) => void - 删除任务
  refreshTaskList,          // () => Promise<void> - 刷新任务列表

  // 工具方法
  canCreateNew,             // () => boolean - 是否可以创建新任务
  getInProgressCount,       // () => number - 获取进行中任务数
  getCompletedCount,        // () => number - 获取已完成任务数
  getTaskById,              // (sessionId) => AnalysisState | undefined - 根据 ID 获取任务
} = useRiskAnalysisTasks();
```

### createTask 参数

```typescript
interface CreateTaskParams {
  uploadId?: string;        // 上传文件 ID
  packageId?: string;       // 规则包 ID
  userInput: string;        // 用户输入
}
```

## 使用场景

### 场景 1：创建新任务

```tsx
const handleStartAnalysis = async () => {
  const sessionId = await createTask({
    uploadId: uploadId,
    packageId: selectedPackageIds[0],
    userInput: userInput
  });

  if (sessionId) {
    console.log('任务已创建:', sessionId);
    // 任务会自动成为活动任务
  } else {
    console.log('创建任务失败');
  }
};
```

### 场景 2：切换任务

```tsx
const handleTaskSwitch = (sessionId: string) => {
  switchTask(sessionId);

  // 重新加载该任务的状态
  const task = getTaskById(sessionId);
  if (task) {
    setAnalysisState({
      ...analysisState,
      sessionId: task.sessionId,
      status: task.status,
      progress: task.progress,
      // ... 其他状态
    });
  }
};
```

### 场景 3：删除任务

```tsx
const handleTaskDelete = (sessionId: string) => {
  removeTask(sessionId);

  // 如果删除的是当前任务，重置状态
  if (analysisState.sessionId === sessionId) {
    setAnalysisState({
      status: 'idle',
      sessionId: '',
      progress: 0,
      message: '',
      nodeProgress: {
        documentPreorganization: 'pending',
        multiModelAnalysis: 'pending',
        reportGeneration: 'pending',
      },
    });
  }
};
```

## 注意事项

1. **并发限制**：默认最多 5 个并发任务，超过时会提示用户等待
2. **任务持久化**：任务会自动保存到 localStorage，刷新页面后自动恢复
3. **WebSocket 连接**：每个任务都有独立的 WebSocket 连接，自动重连
4. **内存管理**：组件卸载时会自动断开所有 WebSocket 连接
5. **移动端适配**：在移动端，任务列表会显示为抽屉模式

## 故障排除

### 问题 1：任务没有恢复

**原因**：localStorage 中的任务数据已过期（24 小时）

**解决**：手动刷新任务列表或创建新任务

### 问题 2：WebSocket 连接失败

**原因**：后端服务未启动或网络问题

**解决**：检查后端服务状态，确保 WebSocket 端点可访问

### 问题 3：任务状态不同步

**原因**：前端状态与后端状态不一致

**解决**：调用 `refreshTaskList()` 从后端重新获取任务状态

## 下一步

- 实现任务间的数据共享
- 添加任务优先级排序
- 实现任务批量操作
- 添加任务搜索和筛选功能
