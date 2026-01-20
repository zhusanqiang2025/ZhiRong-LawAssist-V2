// frontend/src/components/ModuleNavBar/UserInfoDisplay.tsx
import React from 'react';
import { Avatar, Dropdown, Space, Typography, Button } from 'antd';
import { UserOutlined, DownOutlined, SettingOutlined, LogoutOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';

const { Text } = Typography;

const UserInfoDisplay: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      label: '个人中心',
      icon: <UserOutlined />,
    },
    ...(user?.is_admin ? [{
      key: 'admin',
      label: '系统管理后台',
      icon: <SettingOutlined />,
      onClick: () => navigate('/admin')
    }] : []),
    {
      type: 'divider',
    },
    {
      key: 'logout',
      label: '退出登录',
      icon: <LogoutOutlined />,
      onClick: logout,
      danger: true,
    },
  ];

  return (
    <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
      <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '8px' }}>
        <Avatar style={{ backgroundColor: '#1890ff' }} icon={<UserOutlined />} />
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: '1.2' }}>
          <Text strong style={{ fontSize: '14px' }}>
            {user?.email ? user.email.split('@')[0] : '用户'}
          </Text>
          <Text type="secondary" style={{ fontSize: '10px' }}>
            {user?.is_admin ? '管理员' : '普通用户'}
          </Text>
        </div>
        <DownOutlined style={{ fontSize: '10px', color: '#bfbfbf' }} />
      </div>
    </Dropdown>
  );
};

export default UserInfoDisplay;
