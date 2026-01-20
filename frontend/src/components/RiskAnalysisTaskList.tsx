// frontend/src/components/RiskAnalysisTaskList.tsx
/**
 * 风险评估任务列表组件
 *
 * 显示进行中和已完成的任务
 * 支持任务切换、删除等操作
 */

import React from 'react';
import {
  Card,
  List,
  Tag,
  Progress,
  Space,
  Button,
  Typography,
  Divider,
  Empty,
  Tooltip
} from 'antd';
import {
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  EyeOutlined,
  RocketOutlined
} from '@ant-design/icons';
import { AnalysisState } from '../hooks/useRiskAnalysisTasks';
import { formatRelativeTime } from '../utils/taskStorage';

const { Text, Paragraph } = Typography;

export interface RiskAnalysisTaskListProps {
  tasks: AnalysisState[];
  activeTaskId: string | null;
  onTaskClick?: (sessionId: string) => void;
  onTaskDelete?: (sessionId: string) => void;
  loading?: boolean;
}

const RiskAnalysisTaskList: React.FC<RiskAnalysisTaskListProps> = ({
  tasks,
  activeTaskId,
  onTaskClick,
  onTaskDelete,
  loading = false
}) => {
  // 分组任务
  const inProgressTasks = tasks.filter(
    task => task.status === 'analyzing' || task.status === 'pending'
  );
  const completedTasks = tasks.filter(task => task.status === 'completed');
  const failedTasks = tasks.filter(task => task.status === 'failed');

  // 渲染任务项
  const renderTaskItem = (task: AnalysisState) => {
    const isActive = task.sessionId === activeTaskId;
    const isInProgress = task.status === 'analyzing' || task.status === 'pending';

    // 确定状态标签
    let statusTag = (
      <Tag icon={<SyncOutlined spin />} color="processing">
        进行中
      </Tag>
    );
    if (task.status === 'completed') {
      statusTag = (
        <Tag icon={<CheckCircleOutlined />} color="success">
          已完成
        </Tag>
      );
    } else if (task.status === 'failed') {
      statusTag = (
        <Tag icon={<CloseCircleOutlined />} color="error">
          失败
        </Tag>
      );
    }

    // 任务标题
    const taskTitle = task.userInput || '风险评估任务';
    const truncatedTitle = taskTitle.length > 30
      ? taskTitle.substring(0, 27) + '...'
      : taskTitle;

    return (
      <List.Item
        key={task.sessionId}
        style={{
          padding: '12px',
          marginBottom: '8px',
          borderRadius: '6px',
          border: isActive ? '2px solid #1890ff' : '1px solid #f0f0f0',
          backgroundColor: isActive ? '#e6f7ff' : '#fff',
          cursor: 'pointer',
          transition: 'all 0.2s'
        }}
        onClick={() => onTaskClick && onTaskClick(task.sessionId)}
      >
        <List.Item.Meta
          avatar={
            isInProgress ? (
              <SyncOutlined spin style={{ fontSize: 24, color: '#1890ff' }} />
            ) : task.status === 'completed' ? (
              <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
            ) : (
              <CloseCircleOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
            )
          }
          title={
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space>
                <Text strong={isActive}>{truncatedTitle}</Text>
                {statusTag}
                {isActive && (
                  <Tag color="blue">当前</Tag>
                )}
              </Space>

              {isInProgress && task.progress > 0 && (
                <Progress
                  percent={Math.round(task.progress)}
                  size="small"
                  status={isActive ? 'active' : 'normal'}
                  showInfo={true}
                />
              )}

              {task.message && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {task.message}
                </Text>
              )}

              {task.createdAt && (
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {formatRelativeTime(task.createdAt)}
                </Text>
              )}
            </Space>
          }
          description={
            <Space split={<Divider type="vertical" />}>
              <Tooltip title="查看详情">
                <Button
                  type="text"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    onTaskClick && onTaskClick(task.sessionId);
                  }}
                >
                  查看
                </Button>
              </Tooltip>

              <Tooltip title="删除任务">
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    onTaskDelete && onTaskDelete(task.sessionId);
                  }}
                >
                  删除
                </Button>
              </Tooltip>
            </Space>
          }
        />
      </List.Item>
    );
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* 进行中的任务 */}
      {inProgressTasks.length > 0 && (
        <div>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            marginBottom: 12,
            gap: 8
          }}>
            <RocketOutlined style={{ color: '#1890ff' }} />
            <Text strong style={{ fontSize: 14 }}>
              进行中 ({inProgressTasks.length})
            </Text>
          </div>
          <List
            dataSource={inProgressTasks}
            renderItem={renderTaskItem}
            loading={loading}
            style={{ backgroundColor: '#fafafa', borderRadius: 8, padding: '8px' }}
          />
        </div>
      )}

      {/* 已完成的任务 */}
      {completedTasks.length > 0 && (
        <div>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            marginBottom: 12,
            gap: 8
          }}>
            <CheckCircleOutlined style={{ color: '#52c41a' }} />
            <Text strong style={{ fontSize: 14 }}>
              已完成 ({completedTasks.length})
            </Text>
          </div>
          <List
            dataSource={completedTasks}
            renderItem={renderTaskItem}
            loading={loading}
            style={{ backgroundColor: '#fafafa', borderRadius: 8, padding: '8px' }}
          />
        </div>
      )}

      {/* 失败的任务 */}
      {failedTasks.length > 0 && (
        <div>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            marginBottom: 12,
            gap: 8
          }}>
            <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
            <Text strong style={{ fontSize: 14 }}>
              失败 ({failedTasks.length})
            </Text>
          </div>
          <List
            dataSource={failedTasks}
            renderItem={renderTaskItem}
            loading={loading}
            style={{ backgroundColor: '#fafafa', borderRadius: 8, padding: '8px' }}
          />
        </div>
      )}

      {/* 空状态 */}
      {tasks.length === 0 && !loading && (
        <Empty
          description="暂无任务"
          style={{ padding: '40px 0' }}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}
    </Space>
  );
};

export default RiskAnalysisTaskList;
