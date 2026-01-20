// frontend/src/components/TaskListGroup.tsx
import React from 'react';
import { Card, Row, Col, Typography, Space, Progress, Tag, Empty, Button, Tooltip, Divider } from 'antd';
import { CheckCircleOutlined, SyncOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Text } = Typography;

interface TaskItem {
  id: string;
  title: string;
  status: string;
  progress: number;
  time: string;
  source?: string; // 'celery' | 'litigation_analysis' | 'risk_analysis'
}

interface TaskListGroupProps {
  tasks: TaskItem[];
  title: string;
  emptyText?: string;
  status: 'in_progress' | 'completed';
  // 新增：任务操作
  onTaskClick?: (taskId: string) => void;
  onTaskDelete?: (taskId: string) => void;
  // 新增：显示模式
  showActions?: boolean;
  compact?: boolean;  // 紧凑模式，用于嵌入页面
}

const TaskListGroup: React.FC<TaskListGroupProps> = ({
  tasks,
  title,
  emptyText = '暂无任务',
  status,
  onTaskClick,
  onTaskDelete,
  showActions = false,
  compact = false
}) => {
  const navigate = useNavigate();

  // 如果没有任务，不显示该分组
  if (tasks.length === 0) {
    return null;
  }

  const borderColor = status === 'in_progress' ? '#1890ff' : '#52c41a';
  const tagColor = status === 'in_progress' ? 'processing' : 'success';
  const tagText = status === 'in_progress' ? '进行中' : '已完成';

  // 渲染任务卡片
  const renderTaskCard = (task: TaskItem) => {
    // 点击任务卡片
    const handleCardClick = () => {
      if (onTaskClick) {
        onTaskClick(task.id);
      } else {
        navigate(`/result/${task.id}`);
      }
    };

    // 删除任务
    const handleDelete = (e: React.MouseEvent) => {
      e.stopPropagation();
      if (onTaskDelete) {
        onTaskDelete(task.id);
      }
    };

    return (
      <Col xs={24} sm={12} md={8} key={task.id}>
        <Card
          hoverable
          onClick={handleCardClick}
          style={{
            borderLeft: `4px solid ${borderColor}`,
            cursor: 'pointer',
            ...(compact ? { padding: '12px' } : {})
          }}
          bodyStyle={compact ? { padding: '12px' } : undefined}
        >
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <Space>
              <Text ellipsis style={{ flex: 1 }}>{task.title}</Text>
              <Tag color={tagColor}>{tagText}</Tag>
            </Space>
            {status === 'in_progress' && task.progress > 0 && (
              <Progress
                percent={task.progress}
                size="small"
                status="active"
              />
            )}
            <Text type="secondary" style={{ fontSize: 12 }}>
              {task.time}
            </Text>

            {/* 任务操作按钮 */}
            {showActions && (
              <>
                <Divider style={{ margin: '8px 0' }} />
                <Space split={<Divider type="vertical" />}>
                  <Tooltip title="查看详情">
                    <Button
                      type="text"
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={handleCardClick}
                    >
                      查看
                    </Button>
                  </Tooltip>
                  {onTaskDelete && (
                    <Tooltip title="删除任务">
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={handleDelete}
                      >
                        删除
                      </Button>
                    </Tooltip>
                  )}
                </Space>
              </>
            )}
          </Space>
        </Card>
      </Col>
    );
  };

  return (
    <div style={{ marginBottom: compact ? 16 : 24 }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        marginBottom: 12,
        gap: 8
      }}>
        {status === 'in_progress' ? <SyncOutlined spin /> : <CheckCircleOutlined />}
        <Text strong style={{ fontSize: compact ? 14 : 16 }}>
          {title} <Text type="secondary">({tasks.length})</Text>
        </Text>
      </div>
      <Row gutter={[16, 16]}>
        {tasks.map(renderTaskCard)}
      </Row>
    </div>
  );
};

export default TaskListGroup;
