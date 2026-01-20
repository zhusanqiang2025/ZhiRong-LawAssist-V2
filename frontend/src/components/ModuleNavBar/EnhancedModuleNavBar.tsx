// frontend/src/components/ModuleNavBar/EnhancedModuleNavBar.tsx
import React from 'react';
import { Button, Dropdown, Space } from 'antd';
import {
  ArrowLeftOutlined,
  HomeOutlined,
  UserOutlined,
  AppstoreOutlined,
  FileProtectOutlined,
  DiffOutlined,
  CalculatorOutlined,
  SafetyOutlined,
  EditOutlined,
  FileTextOutlined,
  BankOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { MenuProps } from 'antd';
import SessionTimer from './SessionTimer';
import UserInfoDisplay from './UserInfoDisplay';
import './EnhancedModuleNavBar.css';

const MODULE_CONFIGS: Record<string, { title: string; icon: React.ReactNode }> = {
  'consultation': { title: '智能咨询', icon: <UserOutlined /> },
  'risk-analysis': { title: '风险评估', icon: <SafetyOutlined /> },
  'case-analysis': { title: '案件分析', icon: <BankOutlined /> },
  'contract-generation': { title: '合同生成', icon: <FileProtectOutlined /> },
  'contract-review': { title: '合同审查', icon: <DiffOutlined /> },
  'template-search': { title: '模板查询', icon: <AppstoreOutlined /> },
  'document-processing': { title: '文档处理', icon: <EditOutlined /> },
  'document-drafting': { title: '文书起草', icon: <FileTextOutlined /> },
  'cost-calculation': { title: '费用测算', icon: <CalculatorOutlined /> },
};

interface EnhancedModuleNavBarProps {
  currentModuleKey: string;
  title?: string;
  icon?: React.ReactNode;
  onBack?: () => void;
  backTo?: string;
  showQuickNav?: boolean;
  showWorkbench?: boolean;
  showClock?: boolean;
  showUserInfo?: boolean;
  extra?: React.ReactNode;
  style?: React.CSSProperties;
}

const EnhancedModuleNavBar: React.FC<EnhancedModuleNavBarProps> = ({
  currentModuleKey,
  title,
  icon,
  onBack,
  backTo,
  showQuickNav = true,
  showWorkbench = true,
  showClock = false,
  showUserInfo = true,
  extra,
  style
}) => {
  const navigate = useNavigate();
  const config = MODULE_CONFIGS[currentModuleKey];
  const displayTitle = title || config?.title || '';
  const displayIcon = icon || config?.icon;

  const quickNavItems: MenuProps['items'] = [
    { type: 'divider' },
    { key: 'consultation', label: '智能咨询', icon: <UserOutlined />, onClick: () => navigate('/consultation') },
    { key: 'risk-analysis', label: '风险评估', icon: <SafetyOutlined />, disabled: currentModuleKey === 'risk-analysis', onClick: () => navigate('/risk-analysis') },
    { key: 'case-analysis', label: '案件分析', icon: <BankOutlined />, disabled: currentModuleKey === 'case-analysis', onClick: () => navigate('/litigation-analysis') },
    { type: 'divider' },
    { key: 'contract-generation', label: '合同生成', icon: <FileProtectOutlined />, disabled: currentModuleKey === 'contract-generation', onClick: () => navigate('/contract/generate') },
    { key: 'contract-review', label: '合同审查', icon: <DiffOutlined />, disabled: currentModuleKey === 'contract-review', onClick: () => navigate('/contract/review') },
    { key: 'template-search', label: '模板查询', icon: <AppstoreOutlined />, disabled: currentModuleKey === 'template-search', onClick: () => navigate('/contract') },
    { type: 'divider' },
    { key: 'document-processing', label: '文档处理', icon: <EditOutlined />, disabled: currentModuleKey === 'document-processing', onClick: () => navigate('/document-processing') },
    { key: 'document-drafting', label: '文书起草', icon: <FileTextOutlined />, disabled: currentModuleKey === 'document-drafting', onClick: () => navigate('/document-drafting') },
    { key: 'cost-calculation', label: '费用测算', icon: <CalculatorOutlined />, disabled: currentModuleKey === 'cost-calculation', onClick: () => navigate('/cost-calculation') },
  ];

  const handleBack = () => {
    if (onBack) onBack();
    else if (backTo) navigate(backTo);
    else navigate(-1);
  };

  const handleWorkbench = () => {
    navigate('/');
  };

  return (
    <div className="enhanced-module-navbar" style={style}>
      {/* 左侧区 */}
      <Space size="middle">
        {showWorkbench && (
          <Button type="text" icon={<HomeOutlined />} onClick={handleWorkbench}>
            工作台
          </Button>
        )}
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={handleBack}>
          返回
        </Button>
        <div className="navbar-title">
          {React.cloneElement(displayIcon as React.ReactElement, { style: { color: '#1890ff' } })}
          <span>{displayTitle}</span>
        </div>
      </Space>

      {/* 中间区：时钟 */}
      {showClock && <SessionTimer />}

      {/* 右侧区 */}
      <Space size="middle">
        {extra}
        {showQuickNav && (
          <Dropdown menu={{ items: quickNavItems }} trigger={['click']} placement="bottomLeft">
            <Button type="default">快捷导航</Button>
          </Dropdown>
        )}
        {showUserInfo && <UserInfoDisplay />}
      </Space>
    </div>
  );
};

export default EnhancedModuleNavBar;
