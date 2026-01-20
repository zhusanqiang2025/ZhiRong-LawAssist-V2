// frontend/src/components/RiskAnalysisHistorySidebar/index.tsx
/**
 * 风险分析历史任务侧边栏
 *
 * 功能：
 * - 显示未完成和已完成任务
 * - 支持点击恢复任务
 * - 显示任务状态徽章
 * - 支持删除任务
 * - 显示未读计数
 */

import React, { useState, useEffect } from 'react';
import { Drawer, List, Tag, Button, Space, Typography, Divider, Empty, Spin, message } from 'antd';
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  DeleteOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import { riskAnalysisHistoryManager, RiskAnalysisHistoryItem } from '../../utils/riskAnalysisHistoryManager';

const { Text } = Typography;

interface RiskAnalysisHistorySidebarProps {
  visible: boolean;
  onClose: () => void;
  onLoadSession: (sessionId: string) => void;
}

const RiskAnalysisHistorySidebar: React.FC<RiskAnalysisHistorySidebarProps> = ({
  visible,
  onClose,
  onLoadSession
}) => {
  const [loading, setLoading] = useState(false);
  const [incompleteTasks, setIncompleteTasks] = useState<RiskAnalysisHistoryItem[]>([]);
  const [completedTasks, setCompletedTasks] = useState<RiskAnalysisHistoryItem[]>([]);

  // 同步历史记录
  const syncHistory = async () => {
    setLoading(true);
    try {
      await riskAnalysisHistoryManager.syncHistoryList();
      setIncompleteTasks(await riskAnalysisHistoryManager.getIncompleteTasks());
      setCompletedTasks(await riskAnalysisHistoryManager.getCompletedTasks());
    } catch (error) {
      message.error('同步历史记录失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      syncHistory();
    }
  }, [visible]);

  // 获取状态配置
  const getStatusConfig = (status: string) => {
    const configs = {
      'pending': { icon: <ClockCircleOutlined />, color: 'default', text: '待处理' },
      'parsing': { icon: <LoadingOutlined />, color: 'processing', text: '解析中' },
      'analyzing': { icon: <LoadingOutlined />, color: 'processing', text: '分析中' },
      'completed': { icon: <CheckCircleOutlined />, color: 'success', text: '已完成' },
      'failed': { icon: <ClockCircleOutlined />, color: 'error', text: '失败' }
    };
    return configs[status] || { icon: <ClockCircleOutlined />, color: 'default', text: '未知' };
  };

  // 渲染任务项
  const renderTaskItem = (task: RiskAnalysisHistoryItem) => {
    const statusConfig = getStatusConfig(task.status);

    return (
      <List.Item
        key={task.session_id}
        style={{ cursor: 'pointer' }}
        onClick={() => handleLoadSession(task.session_id)}
        actions={[
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              handleDeleteSession(task.session_id);
            }}
          />
        ]}
      >
        <List.Item.Meta
          avatar={statusConfig.icon}
          title={
            <Space>
              <span>{task.title}</span>
              {task.is_unread && <Tag color="red">新</Tag>}
            </Space>
          }
          description={
            <Space direction="vertical" size={0}>
              <Tag color={statusConfig.color}>{statusConfig.text}</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {riskAnalysisHistoryManager.formatTimestamp(task.timestamp)}
              </Text>
            </Space>
          }
        />
      </List.Item>
    );
  };

  // 加载会话
  const handleLoadSession = async (sessionId: string) => {
    onLoadSession(sessionId);
    onClose();
  };

  // 删除会话
  const handleDeleteSession = async (sessionId: string) => {
    const success = await riskAnalysisHistoryManager.deleteSession(sessionId);
    if (success) {
      message.success('删除成功');
      syncHistory();
    } else {
      message.error('删除失败');
    }
  };

  return (
    <Drawer
      title={
        <Space>
          <span>历史任务</span>
          <Button
            type="text"
            icon={<ReloadOutlined />}
            onClick={syncHistory}
            size="small"
          >
            刷新
          </Button>
        </Space>
      }
      placement="right"
      width={400}
      open={visible}
      onClose={onClose}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px 0' }}>
          <Spin tip="加载中..." />
        </div>
      ) : (
        <>
          {/* 未完成任务 */}
          <Divider orientation="left">
            未完成任务 ({incompleteTasks.length})
          </Divider>
          {incompleteTasks.length > 0 ? (
            <List
              dataSource={incompleteTasks}
              renderItem={renderTaskItem}
            />
          ) : (
            <Empty description="暂无未完成任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}

          {/* 已完成任务 */}
          <Divider orientation="left">
            已完成任务
          </Divider>
          {completedTasks.length > 0 ? (
            <List
              dataSource={completedTasks.slice(0, 10)}
              renderItem={renderTaskItem}
            />
          ) : (
            <Empty description="暂无已完成任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </>
      )}
    </Drawer>
  );
};

export default RiskAnalysisHistorySidebar;
