// frontend/src/components/ModuleNavBar/SessionTimer.tsx
import React, { useState, useEffect } from 'react';
import { Space, Typography } from 'antd';
import { FieldTimeOutlined } from '@ant-design/icons';
import { useSession } from '../../context/SessionContext';

const { Text } = Typography;

const SessionTimer: React.FC = () => {
  const { sessionStartTime } = useSession();
  const [elapsed, setElapsed] = useState<string>('00:00:00');

  useEffect(() => {
    if (!sessionStartTime) return;

    const timer = setInterval(() => {
      const now = Date.now();
      const seconds = Math.floor((now - sessionStartTime) / 1000);

      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = seconds % 60;

      setElapsed(
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
      );
    }, 1000);

    return () => clearInterval(timer);
  }, [sessionStartTime]);

  if (!sessionStartTime) return null;

  return (
    <Space style={{ marginRight: 16 }}>
      <FieldTimeOutlined style={{ color: '#1890ff' }} />
      <Text style={{ fontSize: 14, fontWeight: 500 }}>{elapsed}</Text>
    </Space>
  );
};

export default SessionTimer;
