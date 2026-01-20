// frontend/src/components/TaskStatsBar.tsx
/**
 * 任务统计栏组件
 *
 * 显示任务统计信息和操作按钮
 */

import React from 'react';
import { Card, Space, Typography, Button, Statistic, Row, Col } from 'antd';
import { ReloadOutlined, SyncOutlined } from '@ant-design/icons';

const { Text } = Typography;

export interface TaskStatsBarProps {
  inProgressCount: number;
  completedCount: number;
  onRefresh?: () => void;
  isLoading?: boolean;
  maxConcurrent?: number;
}

const TaskStatsBar: React.FC<TaskStatsBarProps> = ({
  inProgressCount,
  completedCount,
  onRefresh,
  isLoading = false,
  maxConcurrent = 5
}) => {
  const totalCount = inProgressCount + completedCount;

  return (
    <Card
      size="small"
      style={{ marginBottom: 16 }}
      bodyStyle={{ padding: '12px 16px' }}
    >
      <Row align="middle" justify="space-between" gutter={16}>
        <Col>
          <Space size="large">
            <Statistic
              title="进行中"
              value={inProgressCount}
              suffix={`/ ${maxConcurrent}`}
              valueStyle={{ fontSize: 18, color: inProgressCount >= maxConcurrent ? '#ff4d4f' : '#1890ff' }}
              prefix={<SyncOutlined spin={inProgressCount > 0} />}
            />

            <Statistic
              title="已完成"
              value={completedCount}
              valueStyle={{ fontSize: 18, color: '#52c41a' }}
            />

            {totalCount > 0 && (
              <Text type="secondary">
                共 {totalCount} 个任务
              </Text>
            )}
          </Space>
        </Col>

        <Col>
          {onRefresh && (
            <Button
              icon={<ReloadOutlined />}
              onClick={onRefresh}
              loading={isLoading}
              size="small"
            >
              刷新
            </Button>
          )}
        </Col>
      </Row>
    </Card>
  );
};

export default TaskStatsBar;
