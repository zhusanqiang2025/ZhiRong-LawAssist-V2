import React from 'react';
import { Button, Dropdown } from 'antd';
import {
  ArrowLeftOutlined,
  UserOutlined,
  AppstoreOutlined,
  FileProtectOutlined,
  DiffOutlined,
  BankOutlined,
  FileTextOutlined,
  CalculatorOutlined,
  SafetyOutlined,
  EditOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { MenuProps } from 'antd';

// 模块配置
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

interface ModuleNavBarProps {
  currentModuleKey: string;
  title?: string;
  icon?: React.ReactNode;
  onBack?: () => void;
  backTo?: string;
  showQuickNav?: boolean;
  style?: React.CSSProperties;
}

const ModuleNavBar: React.FC<ModuleNavBarProps> = ({
  currentModuleKey,
  title,
  icon,
  onBack,
  backTo = '/',
  showQuickNav = true,
  style
}) => {
  const navigate = useNavigate();
  const config = MODULE_CONFIGS[currentModuleKey];
  const displayTitle = title || config?.title || '';
  const displayIcon = icon || config?.icon;

  const quickNavItems: MenuProps['items'] = [
    // 第一行：咨询类
    { type: 'divider' },
    {
      key: 'consultation',
      label: '智能咨询',
      icon: <UserOutlined />,
      onClick: () => navigate('/consultation')
    },
    {
      key: 'risk-analysis',
      label: '风险评估',
      icon: <SafetyOutlined />,
      disabled: currentModuleKey === 'risk-analysis',
      onClick: () => navigate('/risk-analysis')
    },
    {
      key: 'case-analysis',
      label: '案件分析',
      icon: <BankOutlined />,
      disabled: currentModuleKey === 'case-analysis',
      onClick: () => navigate('/litigation-analysis')
    },
    // 第二行：合同类
    { type: 'divider' },
    {
      key: 'contract-generation',
      label: '合同生成',
      icon: <FileProtectOutlined />,
      disabled: currentModuleKey === 'contract-generation',
      onClick: () => navigate('/contract/generate')
    },
    {
      key: 'contract-review',
      label: '合同审查',
      icon: <DiffOutlined />,
      disabled: currentModuleKey === 'contract-review',
      onClick: () => navigate('/contract/review')
    },
    {
      key: 'template-search',
      label: '模板查询',
      icon: <AppstoreOutlined />,
      disabled: currentModuleKey === 'template-search',
      onClick: () => navigate('/contract')
    },
    // 第三行：工具类
    { type: 'divider' },
    {
      key: 'document-processing',
      label: '文档处理',
      icon: <EditOutlined />,
      disabled: currentModuleKey === 'document-processing',
      onClick: () => navigate('/document-processing')
    },
    {
      key: 'document-drafting',
      label: '文书起草',
      icon: <FileTextOutlined />,
      disabled: currentModuleKey === 'document-drafting',
      onClick: () => navigate('/document-drafting')
    },
    {
      key: 'cost-calculation',
      label: '费用测算',
      icon: <CalculatorOutlined />,
      disabled: currentModuleKey === 'cost-calculation',
      onClick: () => navigate('/cost-calculation')
    },
  ];

  const handleBack = () => {
    if (onBack) onBack();
    else navigate(backTo);
  };

  return (
    <div style={{
      height: '56px',
      flexShrink: 0,
      background: '#fff',
      borderBottom: '1px solid #e8e8e8',
      display: 'flex',
      alignItems: 'center',
      padding: '0 24px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      zIndex: 100,
      ...style
    }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={handleBack}
        style={{ marginRight: '24px' }}
      >
        返回主页
      </Button>
      <div style={{
        fontSize: '18px',
        fontWeight: 600,
        color: '#262626',
        marginRight: '32px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flex: 1
      }}>
        {React.cloneElement(displayIcon as React.ReactElement, {
          style: { color: '#1890ff' }
        })}
        {displayTitle}
      </div>
      {showQuickNav && (
        <Dropdown menu={{ items: quickNavItems }} trigger={['click']} placement="bottomLeft">
          <Button type="default">
            其他功能模块
          </Button>
        </Dropdown>
      )}
    </div>
  );
};

export default ModuleNavBar;
