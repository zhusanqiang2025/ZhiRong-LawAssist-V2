import React, { useState, useEffect } from 'react';
import { Layout, Menu, Button, Typography, message } from 'antd';
import {
  DashboardOutlined,
  FileTextOutlined,
  BranchesOutlined,
  AppstoreOutlined,
  ArrowLeftOutlined,
  DiffOutlined,
  FileProtectOutlined,
  ThunderboltOutlined,
  MonitorOutlined,
  BankOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

// 引入拆分后的组件
import CategoryManager from './admin/views/CategoryManager';
import KnowledgeGraphManager from './admin/views/KnowledgeGraphManager';
import TemplateManager from './admin/views/TemplateManager';
import ReviewRulesManager from './admin/views/ReviewRulesManager';
import RiskRulePackagesManager from './admin/views/RiskRulePackagesManager';
import LitigationRulePackagesManager from './admin/views/LitigationRulePackagesManager';
import CeleryMonitor from './admin/views/CeleryMonitor';
import KnowledgeBaseConfigPage from './KnowledgeBaseConfigPage';
// 假设 DashboardView 你不想拆分，可以保留在这里，或者也拆出去
// import DashboardView from './admin/views/DashboardView'; 

const { Header, Content, Sider } = Layout;
const { Title } = Typography;

// (简单保留 Dashboard 代码，如果太长建议也拆分)
const DashboardView = () => <div>📊 仪表盘开发中...</div>;

const AdminPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [selectedKey, setSelectedKey] = useState('dashboard');

  useEffect(() => {
    if (user && !user.is_admin) {
      message.error('无权访问');
      navigate('/');
    }
  }, [user, navigate]);

  const renderContent = () => {
    switch (selectedKey) {
      case 'dashboard': return <DashboardView />;
      case 'categories': return <CategoryManager />; // ✨ 合同分类管理
      case 'knowledge-graph': return <KnowledgeGraphManager />; // ✨ 知识图谱管理
      case 'templates': return <TemplateManager />; // ✨ 升级的模板管理
      case 'review-rules': return <ReviewRulesManager />; // ✨ 审查规则管理
      case 'risk-rule-packages': return <RiskRulePackagesManager />; // ✨ 风险评估规则包管理
      case 'litigation-rule-packages': return <LitigationRulePackagesManager />; // ✨ 案件分析规则包管理
      case 'celery-monitor': return <CeleryMonitor />; // ✨ Celery 任务队列监控
      case 'knowledge-base': return <KnowledgeBaseConfigPage />; // ✨ 知识库配置
      default: return <DashboardView />;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', background: '#001529', padding: '0 24px' }}>
        <Button type="text" icon={<ArrowLeftOutlined />} style={{ color: '#fff', marginRight: 16 }} onClick={() => navigate('/')}>
           返回前台
        </Button>
        <Title level={4} style={{ color: '#fff', margin: 0 }}>系统管理后台 (V3)</Title>
      </Header>
      <Layout>
        <Sider width={220} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            onClick={(e) => setSelectedKey(e.key)}
            style={{ height: '100%', borderRight: 0 }}
            items={[
              { key: 'dashboard', icon: <DashboardOutlined />, label: '数据仪表盘' },
              { key: 'categories', icon: <AppstoreOutlined />, label: '合同分类管理' },
              { key: 'knowledge-graph', icon: <BranchesOutlined />, label: '知识图谱管理' },
              { key: 'templates', icon: <FileTextOutlined />, label: '模板管理' },
              { key: 'review-rules', icon: <DiffOutlined />, label: '审查规则管理' },
              { key: 'risk-rule-packages', icon: <FileProtectOutlined />, label: '风险评估规则包' },
              { key: 'litigation-rule-packages', icon: <BankOutlined />, label: '案件分析规则包' },
              { key: 'celery-monitor', icon: <MonitorOutlined />, label: '任务队列监控' },
              { key: 'knowledge-base', icon: <DatabaseOutlined />, label: '知识库配置' },
            ]}
          />
        </Sider>
        <Layout style={{ padding: '24px' }}>
          <Content style={{ margin: 0, minHeight: 280 }}>
            {renderContent()}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default AdminPage;