// frontend/src/components/RiskAnalysisHistoryButton/index.tsx
/**
 * 历史任务按钮
 *
 * 显示未完成任务数量的角标
 */

import React from 'react';
import { Badge, Button } from 'antd';
import { HistoryOutlined } from '@ant-design/icons';

interface RiskAnalysisHistoryButtonProps {
  count: number;
  onClick: () => void;
}

const RiskAnalysisHistoryButton: React.FC<RiskAnalysisHistoryButtonProps> = ({
  count,
  onClick
}) => {
  return (
    <Badge count={count} size="small" offset={[-5, 5]}>
      <Button
        type="text"
        icon={<HistoryOutlined />}
        onClick={onClick}
        style={{
          color: '#1890ff',  // 改为蓝色，提升对比度
          backgroundColor: 'rgba(24, 144, 255, 0.1)',
          border: '1px solid rgba(24, 144, 255, 0.3)',
          borderRadius: '4px',
          padding: '4px 12px',
          fontWeight: 500
        }}
      >
        历史任务
      </Button>
    </Badge>
  );
};

export default RiskAnalysisHistoryButton;
