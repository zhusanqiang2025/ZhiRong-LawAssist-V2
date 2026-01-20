// frontend/src/components/ConsultationHistorySidebar/index.tsx
/**
 * 智能咨询历史记录侧边栏
 *
 * 功能：
 * 1. 显示历史会话列表
 * 2. 点击历史记录加载会话
 * 3. 删除历史记录
 * 4. 新建会话
 */

import React, { useState, useEffect } from 'react';
import { List, Typography, Button, Popconfirm, Empty, Tooltip } from 'antd';
import {
  HistoryOutlined,
  DeleteOutlined,
  PlusOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import type { ConsultationHistoryItem } from '../../utils/consultationHistoryManager';
import { consultationHistoryManager } from '../../utils/consultationHistoryManager';
import './index.css';

const { Text } = Typography;

interface ConsultationHistorySidebarProps {
  visible: boolean;
  onClose: () => void;
  onLoadHistory: (id: string) => void;
  onNewChat: () => void;
}

const ConsultationHistorySidebar: React.FC<ConsultationHistorySidebarProps> = ({
  visible,
  onClose,
  onLoadHistory,
  onNewChat
}) => {
  const [historyList, setHistoryList] = useState<ConsultationHistoryItem[]>([]);

  // 加载历史记录列表
  const loadHistoryList = () => {
    const list = consultationHistoryManager.getHistoryList();
    setHistoryList(list);
  };

  // 组件挂载时加载历史记录
  useEffect(() => {
    if (visible) {
      loadHistoryList();
    }
  }, [visible]);

  // 删除历史记录
  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    consultationHistoryManager.deleteConsultation(id);
    loadHistoryList();
  };

  // 点击历史记录
  const handleClick = (id: string) => {
    onLoadHistory(id);
    onClose();
  };

  if (!visible) return null;

  return (
    <div className="consultation-history-sidebar">
      <div className="history-sidebar-header">
        <div className="history-sidebar-title">
          <HistoryOutlined style={{ marginRight: 8 }} />
          <Text strong>历史记录</Text>
        </div>
        <Button
          type="text"
          icon={<PlusOutlined />}
          onClick={onNewChat}
          size="small"
        >
          新建会话
        </Button>
      </div>

      <div className="history-sidebar-content">
        {historyList.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无历史记录"
            style={{ marginTop: 40 }}
          />
        ) : (
          <List
            dataSource={historyList}
            renderItem={(item) => (
              <List.Item
                className="history-item"
                onClick={() => handleClick(item.id)}
              >
                <div className="history-item-content">
                  <div className="history-item-title">
                    <Text ellipsis={{ tooltip: item.title }}>
                      {item.title}
                    </Text>
                  </div>
                  <div className="history-item-meta">
                    <ClockCircleOutlined style={{ fontSize: 12, marginRight: 4 }} />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {consultationHistoryManager.formatTimestamp(item.timestamp)}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                      {item.messageCount} 条消息
                    </Text>
                  </div>
                </div>
                <Popconfirm
                  title="确认删除此会话？"
                  onConfirm={(e) => handleDelete(item.id, e as any)}
                  okText="确认"
                  cancelText="取消"
                >
                  <Button
                    type="text"
                    icon={<DeleteOutlined />}
                    size="small"
                    danger
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </List.Item>
            )}
          />
        )}
      </div>

      {historyList.length > 0 && (
        <div className="history-sidebar-footer">
          <Popconfirm
            title="确认清空所有历史记录？"
            onConfirm={() => {
              consultationHistoryManager.clearAllHistory();
              loadHistoryList();
            }}
            okText="确认"
            cancelText="取消"
          >
            <Button type="text" danger size="small">
              清空历史
            </Button>
          </Popconfirm>
        </div>
      )}
    </div>
  );
};

export default ConsultationHistorySidebar;
