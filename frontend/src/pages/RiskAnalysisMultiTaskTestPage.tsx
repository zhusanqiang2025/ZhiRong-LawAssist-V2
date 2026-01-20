// frontend/src/pages/RiskAnalysisMultiTaskTestPage.tsx
/**
 * 风险评估多任务功能测试页面
 *
 * 用于测试和演示多任务支持功能
 */

import React, { useState } from 'react';
import { Layout, Card, Button, Input, Space, Typography, Divider, message } from 'antd';
import { RocketOutlined, PlusOutlined } from '@ant-design/icons';
import RiskAnalysisMultiTaskWrapper from '../components/RiskAnalysisMultiTaskWrapper';
import { useRiskAnalysisTasks } from '../hooks/useRiskAnalysisTasks';

const { Content } = Layout;
const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

const RiskAnalysisMultiTaskTestPage: React.FC = () => {
  const [userInput, setUserInput] = useState('');
  const [selectedPackageId, setSelectedPackageId] = useState('');

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

  // 创建测试任务
  const handleCreateTask = async () => {
    if (!userInput.trim()) {
      message.warning('请输入用户需求');
      return;
    }

    const sessionId = await createTask({
      userInput: userInput,
      packageId: selectedPackageId || undefined
    });

    if (sessionId) {
      message.success(`任务已创建: ${sessionId}`);
      setUserInput('');
    } else {
      message.error('创建任务失败');
    }
  };

  // 模拟任务列表
  const mockTasks = [
    {
      sessionId: 'mock-1',
      status: 'analyzing' as const,
      progress: 65,
      message: '正在分析文档...',
      nodeProgress: {
        documentPreorganization: 'completed' as const,
        multiModelAnalysis: 'processing' as const,
        reportGeneration: 'pending' as const,
      },
      createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
      userInput: '测试任务 1：房屋买卖合同风险评估'
    },
    {
      sessionId: 'mock-2',
      status: 'completed' as const,
      progress: 100,
      message: '分析已完成',
      nodeProgress: {
        documentPreorganization: 'completed' as const,
        multiModelAnalysis: 'completed' as const,
        reportGeneration: 'completed' as const,
      },
      createdAt: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      userInput: '测试任务 2：劳动合同风险评估'
    },
    {
      sessionId: 'mock-3',
      status: 'pending' as const,
      progress: 0,
      message: '等待开始...',
      nodeProgress: {
        documentPreorganization: 'pending' as const,
        multiModelAnalysis: 'pending' as const,
        reportGeneration: 'pending' as const,
      },
      createdAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
      userInput: '测试任务 3：投资协议风险评估'
    }
  ];

  // 合并真实任务和模拟任务
  const allTasks = React.useMemo(() => {
    const realTasks = Array.from(tasks.values());
    return [...realTasks, ...mockTasks];
  }, [tasks]);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Content style={{ padding: '24px' }}>
        <div style={{ maxWidth: 1400, margin: '0 auto' }}>
          <Title level={2}>
            <RocketOutlined /> 风险评估多任务功能测试
          </Title>

          <Paragraph>
            此页面用于测试和演示多任务支持功能，包括任务创建、切换、删除、持久化等。
          </Paragraph>

          <Divider />

          {/* 测试控制面板 */}
          <Card title="测试控制面板" style={{ marginBottom: 24 }}>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              <div>
                <Text strong>创建新任务</Text>
                <div style={{ marginTop: 8 }}>
                  <TextArea
                    rows={4}
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    placeholder="输入用户需求（例如：房屋买卖合同风险评估）"
                  />
                </div>
              </div>

              <Space>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={handleCreateTask}
                  disabled={!canCreateNew()}
                >
                  创建任务
                </Button>

                <Button
                  onClick={refreshTaskList}
                >
                  刷新任务列表
                </Button>

                <Button
                  onClick={() => {
                    if (activeTaskId) {
                      switchTask(activeTaskId);
                      message.info(`已切换到任务: ${activeTaskId}`);
                    }
                  }}
                  disabled={!activeTaskId}
                >
                  切换活动任务
                </Button>
              </Space>

              <div>
                <Text type="secondary">
                  进行中: {getInProgressCount()} | 已完成: {getCompletedCount()} | 总计: {tasks.size}
                </Text>
              </div>
            </Space>
          </Card>

          {/* 使用多任务包装组件 */}
          <RiskAnalysisMultiTaskWrapper
            currentTaskId={activeTaskId}
            onSwitchTask={(sessionId) => {
              console.log('切换到任务:', sessionId);
              switchTask(sessionId);
            }}
            showTaskList={true}
          >
            {/* 主内容区 */}
            <Card>
              <Title level={3}>主内容区</Title>
              <Paragraph>
                这是主内容区，显示当前活动任务的详细信息。
              </Paragraph>

              {activeTaskId ? (
                <div>
                  <Text strong>当前活动任务: </Text>
                  <Text code>{activeTaskId}</Text>

                  <Divider />

                  <div>
                    <Text strong>任务列表（含模拟数据）:</Text>
                    <div style={{ marginTop: 16 }}>
                      {allTasks.map(task => (
                        <Card
                          key={task.sessionId}
                          size="small"
                          style={{
                            marginBottom: 8,
                            border: task.sessionId === activeTaskId
                              ? '2px solid #1890ff'
                              : '1px solid #f0f0f0'
                          }}
                        >
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <Space>
                              <Text strong>{task.userInput || '未命名任务'}</Text>
                              <Text type="secondary">({task.sessionId})</Text>
                            </Space>
                            <Text type="secondary">
                              状态: {task.status} | 进度: {task.progress}%
                            </Text>
                          </Space>
                        </Card>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <Text type="secondary">没有活动任务，请创建或选择一个任务</Text>
              )}
            </Card>
          </RiskAnalysisMultiTaskWrapper>
        </div>
      </Content>
    </Layout>
  );
};

export default RiskAnalysisMultiTaskTestPage;
