// frontend/src/components/RiskAnalysisMultiTaskWrapper.tsx
/**
 * 风险评估多任务 UI 包装组件
 *
 * 为现有的 RiskAnalysisPageV2 添加多任务支持
 * 采用非侵入式设计，保持原有功能不变
 */

import React, { useEffect } from 'react';
import { Row, Col, Space, Button, Drawer, Typography } from 'antd';
import { UnorderedListOutlined, CloseOutlined } from '@ant-design/icons';
import { useRiskAnalysisTasks, AnalysisState } from '../hooks/useRiskAnalysisTasks';
import TaskStatsBar from './TaskStatsBar';
import RiskAnalysisTaskList from './RiskAnalysisTaskList';
import { getMaxConcurrentTasks } from '../utils/taskStorage';

const { Text } = Typography;

export interface RiskAnalysisMultiTaskWrapperProps {
  // 渲染主内容区（原有的输入表单、进度页面等）
  children: React.ReactNode;

  // 当前任务 ID（用于高亮显示）
  currentTaskId?: string | null;

  // 任务创建回调
  onCreateTask?: (sessionId: string) => void;

  // 任务切换回调
  onSwitchTask?: (sessionId: string) => void;

  // 是否显示任务列表（默认显示在右侧）
  showTaskList?: boolean;

  // 是否使用抽屉模式（移动端友好）
  drawerMode?: boolean;
}

const RiskAnalysisMultiTaskWrapper: React.FC<RiskAnalysisMultiTaskWrapperProps> = ({
  children,
  currentTaskId = null,
  onCreateTask,
  onSwitchTask,
  showTaskList = true,
  drawerMode = false
}) => {
  const {
    tasks,
    activeTaskId,
    isLoading,
    createTask,
    switchTask,
    removeTask,
    refreshTaskList,
    canCreateNew,
    getInProgressCount,
    getCompletedCount
  } = useRiskAnalysisTasks();

  const [taskListVisible, setTaskListVisible] = React.useState<boolean>(showTaskList);
  const [isMobile, setIsMobile] = React.useState<boolean>(false);

  // 检测是否为移动端
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);

    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 转换任务列表格式
  const taskList = React.useMemo(() => {
    return Array.from(tasks.values()).map(task => ({
      sessionId: task.sessionId,
      status: task.status,
      progress: task.progress,
      message: task.message,
      nodeProgress: task.nodeProgress,
      createdAt: task.createdAt,
      userInput: task.userInput
    }));
  }, [tasks]);

  // 处理任务切换
  const handleTaskClick = (sessionId: string) => {
    switchTask(sessionId);

    // 调用外部回调
    if (onSwitchTask) {
      onSwitchTask(sessionId);
    }

    // 移动端点击后关闭抽屉
    if (isMobile && drawerMode) {
      setTaskListVisible(false);
    }
  };

  // 处理任务删除
  const handleTaskDelete = (sessionId: string) => {
    removeTask(sessionId);

    // 如果删除的是当前任务，刷新页面
    if (currentTaskId === sessionId) {
      window.location.reload();
    }
  };

  // 任务列表侧边栏
  const renderTaskListSidebar = () => (
    <div style={{
      background: '#fff',
      padding: '16px',
      borderRadius: '8px',
      border: '1px solid #f0f0f0',
      height: 'fit-content',
      maxHeight: 'calc(100vh - 200px)',
      overflowY: 'auto'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16
      }}>
        <Text strong>任务列表</Text>
        {isMobile && (
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={() => setTaskListVisible(false)}
          />
        )}
      </div>

      <RiskAnalysisTaskList
        tasks={taskList}
        activeTaskId={currentTaskId || activeTaskId}
        onTaskClick={handleTaskClick}
        onTaskDelete={handleTaskDelete}
        loading={isLoading}
      />
    </div>
  );

  // 任务列表抽屉（移动端）
  const renderTaskListDrawer = () => (
    <Drawer
      title="任务列表"
      placement="right"
      onClose={() => setTaskListVisible(false)}
      open={taskListVisible}
      width={320}
    >
      <RiskAnalysisTaskList
        tasks={taskList}
        activeTaskId={currentTaskId || activeTaskId}
        onTaskClick={handleTaskClick}
        onTaskDelete={handleTaskDelete}
        loading={isLoading}
      />
    </Drawer>
  );

  return (
    <div style={{ width: '100%' }}>
      {/* 任务统计栏 */}
      <TaskStatsBar
        inProgressCount={getInProgressCount()}
        completedCount={getCompletedCount()}
        onRefresh={refreshTaskList}
        isLoading={isLoading}
        maxConcurrent={getMaxConcurrentTasks()}
      />

      {/* 主内容区 + 任务列表 */}
      <Row gutter={16}>
        {/* 主内容区 */}
        <Col xs={24} md={taskListVisible ? 14 : 24}>
          {children}
        </Col>

        {/* 任务列表侧边栏（桌面端） */}
        {!isMobile && taskListVisible && (
          <Col md={10}>
            {renderTaskListSidebar()}
          </Col>
        )}
      </Row>

      {/* 移动端：任务列表按钮 */}
      {isMobile && (
        <Button
          type="primary"
          icon={<UnorderedListOutlined />}
          onClick={() => setTaskListVisible(true)}
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 1000,
            borderRadius: '50%',
            width: 56,
            height: 56,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
          }}
        />
      )}

      {/* 任务列表抽屉（移动端） */}
      {isMobile && renderTaskListDrawer()}

      {/* 桌面端：任务列表抽屉（可选） */}
      {!isMobile && drawerMode && renderTaskListDrawer()}
    </div>
  );
};

export default RiskAnalysisMultiTaskWrapper;
