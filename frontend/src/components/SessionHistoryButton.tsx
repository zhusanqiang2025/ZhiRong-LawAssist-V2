// frontend/src/components/SessionHistoryButton.tsx
/**
 * 历史记录按钮组件
 *
 * 显示历史记录按钮和数量徽章
 */

import React from 'react';
import { Button, Badge } from 'antd';
import { HistoryOutlined } from '@ant-design/icons';

interface SessionHistoryButtonProps {
  count?: number;
  onClick?: () => void;
  loading?: boolean;
}

const SessionHistoryButton: React.FC<SessionHistoryButtonProps> = ({
  count = 0,
  onClick,
  loading = false
}) => {
  return (
    <Badge count={count} showZero offset={[-5, 5]}>
      <Button
        type="default"
        icon={<HistoryOutlined />}
        onClick={onClick}
        loading={loading}
      >
        历史记录
      </Button>
    </Badge>
  );
};

export default SessionHistoryButton;
