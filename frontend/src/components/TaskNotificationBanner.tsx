// frontend/src/components/TaskNotificationBanner.tsx
import React, { useState, useEffect } from 'react';
import { Alert, Button, Space, Typography, message } from 'antd';
import { CheckCircleOutlined, EyeOutlined, CloseOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import api from '../api';

const { Text } = Typography;

interface TaskItem {
  id: string;
  title: string;
  status: string;
  progress: number;
  time: string;
}

const TaskNotificationBanner: React.FC = () => {
  const [unviewedTasks, setUnviewedTasks] = useState<TaskItem[]>([]);
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // 检查未查看任务
  const checkUnviewedTasks = async () => {
    try {
      setLoading(true);
      const response = await api.getUnviewedTasks();
      if (response.data && response.data.length > 0) {
        setUnviewedTasks(response.data);
        setVisible(true);
      } else {
        setVisible(false);
      }
    } catch (error) {
      console.error('检查未查看任务失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // 页面加载时检查
    checkUnviewedTasks();

    // 每60秒检查一次
    const interval = setInterval(checkUnviewedTasks, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleViewTask = (taskId: string) => {
    navigate(`/result/${taskId}`);
  };

  const handleDismiss = async () => {
    // 标记所有任务为已查看
    try {
      await Promise.all(
        unviewedTasks.map(task => api.markTaskAsViewed(task.id))
      );
      setVisible(false);
      setUnviewedTasks([]);
      message.success('已标记所有任务为已查看');
    } catch (error) {
      console.error('标记任务失败:', error);
      message.error('标记任务失败，请重试');
    }
  };

  if (!visible || unviewedTasks.length === 0) {
    return null;
  }

  return (
    <Alert
      message="任务完成提醒"
      description={
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Text>
            您有 <Text strong>{unviewedTasks.length}</Text> 个任务已完成，请查看结果：
          </Text>
          <Space wrap>
            {unviewedTasks.slice(0, 3).map(task => (
              <Button
                key={task.id}
                type="link"
                icon={<EyeOutlined />}
                onClick={() => handleViewTask(task.id)}
                style={{ padding: 0, height: 'auto' }}
              >
                {task.title}
              </Button>
            ))}
            {unviewedTasks.length > 3 && (
              <Text type="secondary">及其他 {unviewedTasks.length - 3} 个任务</Text>
            )}
          </Space>
        </Space>
      }
      type="success"
      icon={<CheckCircleOutlined />}
      closable
      closeText={<CloseOutlined />}
      onClose={handleDismiss}
      showIcon
      style={{ marginBottom: 24 }}
    />
  );
};

export default TaskNotificationBanner;
