import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout, Menu, Typography, Input, Avatar, Badge, Dropdown, 
  Space, Button, Row, Col, Card, theme, ConfigProvider, Popover, Tag
} from 'antd';
import type { MenuProps } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  SearchOutlined, BellOutlined,
  LogoutOutlined, UserOutlined, SettingOutlined,
  AppstoreOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
  ArrowRightOutlined, RobotOutlined,
  MessageOutlined, SafetyCertificateOutlined, FileSearchOutlined,
  FileProtectOutlined, FileTextOutlined, CalculatorOutlined,
  BuildOutlined, ReadOutlined, SnippetsOutlined, FormOutlined,
  ThunderboltFilled
} from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';
import api from '../api';
import SearchResults from '../components/SearchResults';
import { SearchResult } from '../types/search';
import './SceneSelectionPage.css';

const { Header, Sider, Content } = Layout;
const { Title, Text, Paragraph } = Typography;
const { useToken } = theme;

// --- 定制化法律科技 SVG 图标组件 ---
const LegalIcons = {
  Consultation: () => (
    <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
      <rect x="4" y="4" width="40" height="40" rx="12" fill="#e6f7ff"/>
      <path d="M16 24H32M16 30H26M16 18H28" stroke="#1890ff" strokeWidth="3" strokeLinecap="round"/>
      <path d="M34 14V34L28 28" stroke="#1890ff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Risk: () => (
    <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
      <rect x="4" y="4" width="40" height="40" rx="12" fill="#fff1f0"/>
      <path d="M24 10L12 16V24C12 31.5 17.5 38 24 40C30.5 38 36 31.5 36 24V16L24 10Z" stroke="#f5222d" strokeWidth="3" strokeLinejoin="round"/>
      <path d="M24 18V25" stroke="#f5222d" strokeWidth="3" strokeLinecap="round"/>
    </svg>
  ),
  Contract: () => (
    <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
      <rect x="4" y="4" width="40" height="40" rx="12" fill="#f6ffed"/>
      <path d="M30 14H18C16.8954 14 16 14.8954 16 16V32C16 33.1046 16.8954 34 18 34H30C31.1046 34 32 33.1046 32 32V16C32 14.8954 31.1046 14 30 14Z" stroke="#52c41a" strokeWidth="3"/>
      <path d="M22 22L24 24L28 20" stroke="#52c41a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Tool: () => (
    <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
      <rect x="4" y="4" width="40" height="40" rx="12" fill="#f9f0ff"/>
      <path d="M16 16H22V22H16V16Z" stroke="#722ed1" strokeWidth="2"/>
      <path d="M26 16H32V22H26V16Z" stroke="#722ed1" strokeWidth="2"/>
      <path d="M16 26H22V32H16V26Z" stroke="#722ed1" strokeWidth="2"/>
      <rect x="12" y="12" width="24" height="24" rx="2" stroke="#722ed1" strokeWidth="3"/>
    </svg>
  )
};

interface SceneItem {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  category: string;
  route?: string;
  hasBackend?: boolean;
}

const SceneSelectionPage: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [greeting, setGreeting] = useState('你好');
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  
  // 状态管理
  const [searchVisible, setSearchVisible] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchFacets, setSearchFacets] = useState({ module: 0, task: 0, legal: 0 });
  
  // 动态 Placeholder 状态
  const [placeholderText, setPlaceholderText] = useState('全库搜索...');
  const placeholders = ['搜索 "房屋租赁合同"', '查询 "民间借贷纠纷案例"', '输入 "风险评估报告"', '搜索 "劳动法条文"'];

  useEffect(() => {
    // 问候语逻辑
    const hour = new Date().getHours();
    if (hour < 11) setGreeting('上午好');
    else if (hour < 13) setGreeting('中午好');
    else if (hour < 18) setGreeting('下午好');
    else setGreeting('晚上好');

    // 搜索框动态 Placeholder 逻辑
    let index = 0;
    const interval = setInterval(() => {
      index = (index + 1) % placeholders.length;
      setPlaceholderText(placeholders[index]);
    }, 4000); // 每4秒切换一次

    return () => clearInterval(interval);
  }, []);

  // 搜索逻辑
  const performSearch = useCallback(async (query: string) => {
    if (!query || query.length < 2) {
      setSearchResults([]); 
      return;
    }
    setSearchLoading(true);
    try {
      const response = await api.globalSearch({ query });
      setSearchResults(response.data.results);
      setSearchFacets(response.data.facets);
    } catch (error) {
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, []);

  let searchTimeout: NodeJS.Timeout;
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => { if(value.length>=2) performSearch(value) }, 300);
  };

  // ========== 核心模块配置 ==========
  const gridScenes: SceneItem[] = [
    // 咨询类
    { id: 'consultation', title: '智能咨询', description: '资深律师为您提供专业的法律咨询服务', icon: <LegalIcons.Consultation />, category: 'consultation', route: '/consultation', hasBackend: true },
    { id: 'risk-analysis', title: '风险评估', description: '深度分析法律文件，识别潜在风险点', icon: <LegalIcons.Risk />, category: 'consultation', route: '/risk-analysis', hasBackend: true },
    { id: 'case-analysis', title: '案件分析', description: '分析案件材料，制定诉讼策略', icon: <LegalIcons.Consultation />, category: 'consultation', route: '/litigation-analysis', hasBackend: true },
    // 合同类
    { id: 'contract-generation', title: '合同生成', description: '基于需求智能生成各类合同文书', icon: <LegalIcons.Contract />, category: 'contract', route: '/contract/generate', hasBackend: true },
    { id: 'contract-review', title: '合同审查', description: '专业审查合同条款，识别潜在风险', icon: <LegalIcons.Contract />, category: 'contract', route: '/contract/review', hasBackend: true },
    { id: 'template-search', title: '模板查询', description: '查找合适的法律文书模板', icon: <LegalIcons.Contract />, category: 'contract', route: '/contract', hasBackend: true },
    // 工具类
    { id: 'document-processing', title: '文档处理', description: '文档预处理、智能编辑、文件比对', icon: <LegalIcons.Tool />, category: 'tools', route: '/document-processing', hasBackend: true },
    { id: 'document-drafting', title: '文书起草', description: '起草各类司法文书和函件', icon: <LegalIcons.Tool />, category: 'tools', route: '/document-drafting', hasBackend: true },
    { id: 'cost-calculation', title: '费用测算', description: '计算诉讼费用、律师费等', icon: <LegalIcons.Tool />, category: 'tools', route: '/cost-calculation', hasBackend: true },
  ];

  const sceneCategories = [
    { id: 'consultation', name: '咨询业务', icon: <MessageOutlined style={{ color: '#1890ff' }} />, description: 'AI 驱动的专业法律咨询与风险分析' },
    { id: 'contract', name: '合同业务', icon: <FileProtectOutlined style={{ color: '#52c41a' }} />, description: '全生命周期合同管理与生成审查' },
    { id: 'tools', name: '效率工具', icon: <BuildOutlined style={{ color: '#722ed1' }} />, description: '提升法律工作效率的实用工具箱' }
  ];

  const handleSceneClick = (scene: SceneItem) => {
    if (scene.id === 'document-drafting') {
      navigate(scene.route || '/', { state: { from: 'judicial', docType: 'judicial_document' } });
    } else {
      navigate(scene.route || '/');
    }
  };

  // ========== 侧边栏菜单 (补全了模板查询和文书起草) ==========
  const navMenuItems: MenuProps['items'] = [
    { key: '/', label: '工作台', icon: <AppstoreOutlined /> },
    { type: 'group', label: '咨询业务', children: [
        { key: '/consultation', label: '智能咨询', icon: <MessageOutlined /> }, 
        { key: '/risk-analysis', label: '风险评估', icon: <SafetyCertificateOutlined /> },
        { key: '/litigation-analysis', label: '案件分析', icon: <FileSearchOutlined /> },
    ]},
    { type: 'group', label: '合同业务', children: [
        { key: '/contract/generate', label: '合同生成', icon: <FileProtectOutlined /> },
        { key: '/contract/review', label: '合同审查', icon: <ReadOutlined /> },
        { key: '/contract', label: '模板查询', icon: <SnippetsOutlined /> }, // ✅ 修正：已添加
    ]},
    { type: 'group', label: '效率工具', children: [
         { key: '/document-processing', label: '文档处理', icon: <FileTextOutlined /> },
         { key: '/document-drafting', label: '文书起草', icon: <FormOutlined /> }, // ✅ 修正：已添加
         { key: '/cost-calculation', label: '费用测算', icon: <CalculatorOutlined /> },
    ]},
    { key: '/guidance', label: '智能引导', icon: <RobotOutlined /> },
  ];

  const userMenuItems: MenuProps['items'] = [
    { key: 'profile', label: '个人中心 & 知识库', icon: <UserOutlined /> },
    ...(user?.is_admin ? [{ key: 'admin', label: '系统管理后台', icon: <SettingOutlined />, onClick: () => navigate('/admin') }] : []),
    { type: 'divider' },
    { key: 'logout', label: '退出登录', icon: <LogoutOutlined />, onClick: logout, danger: true },
  ];

  return (
    <ConfigProvider
      theme={{
        token: { colorPrimary: '#1890ff' },
        components: {
          Card: { borderRadiusLG: 12 },
          Input: { borderRadius: 6 }
        }
      }}
    >
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          trigger={null}
          collapsible
          collapsed={collapsed}
          width={240}
          className="custom-sidebar" // 用于 CSS 定制
          style={{ 
            background: '#001529', 
            boxShadow: '2px 0 8px rgba(0,0,0,0.15)',
            zIndex: 10
          }} 
        >
          <div style={{ 
            height: '64px', display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderBottom: '1px solid rgba(255,255,255,0.1)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#fff', fontSize: '18px', fontWeight: 'bold' }}>
              {!collapsed && (
                <>
                  <span className="logo-icon">⚖️</span>
                  <span>智融法助 2.0</span>
                </>
              )}
              {collapsed && <span style={{ fontSize: '24px' }}>⚖️</span>}
            </div>
          </div>

          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[location.pathname]}
            items={navMenuItems}
            onClick={({ key }) => navigate(key as string)}
            style={{ marginTop: '16px', background: 'transparent' }}
          />
        </Sider>

        <Layout style={{ background: '#f0f2f5' }}>
          <Header style={{ 
            padding: '0 24px', background: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            boxShadow: '0 1px 4px rgba(0,21,41,0.08)', zIndex: 9, position: 'sticky', top: 0
          }}>
            <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed(!collapsed)} />
            
            <Space size="large">
              <Popover content={<SearchResults query={searchQuery} results={searchResults} loading={searchLoading} facets={searchFacets} />} open={searchVisible} onOpenChange={setSearchVisible} placement="bottomRight" overlayClassName="search-popover">
                <Input 
                  prefix={<SearchOutlined style={{ color: 'rgba(0,0,0,0.45)' }} />} 
                  placeholder={placeholderText} // 动态 Placeholder
                  className="search-input-animated"
                  style={{ width: 280, transition: 'all 0.3s' }}
                  value={searchQuery} onChange={handleSearchChange} onFocus={() => searchQuery && setSearchVisible(true)}
                />
              </Popover>
              <Badge count={0} dot><BellOutlined className="bell-icon-hover" style={{ fontSize: '18px', cursor: 'pointer' }} /></Badge>
              <Dropdown menu={{ items: userMenuItems }}>
                <Space style={{ cursor: 'pointer' }}>
                  <Avatar style={{ backgroundColor: '#1890ff' }} icon={<UserOutlined />} />
                  <span style={{ color: 'rgba(0,0,0,0.85)' }}>{user?.email?.split('@')[0]}</span>
                </Space>
              </Dropdown>
            </Space>
          </Header>

          <Content style={{ padding: '24px', overflowY: 'auto' }}>
            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
              
              {/* Banner 区域 (带动态效果) */}
              <Card className="welcome-banner" bordered={false}>
                {/* 动态脉冲点 - 暗示 AI 在线 */}
                <div className="ai-status-pulse">
                  <span className="pulse-dot"></span>
                  <span className="status-text">AI 引擎在线</span>
                </div>

                <Row align="middle" justify="space-between" style={{ position: 'relative', zIndex: 1 }}>
                  <Col xs={24} md={16}>
                    <Title level={2} style={{ color: '#fff', marginBottom: '12px' }}>
                      {greeting}，{user?.email?.split('@')[0]}
                    </Title>
                    <Paragraph style={{ color: 'rgba(255,255,255,0.9)', fontSize: '16px', marginBottom: '24px', maxWidth: '600px', lineHeight: '1.8' }}>
                      欢迎使用智融法助 2.0。无论您是需要起草合同、评估风险还是分析案件，
                      我们的多模型 AI 专家团队已准备就绪，随时为您提供专业支持。
                    </Paragraph>
                    <Space>
                      <Button type="primary" size="large" icon={<RobotOutlined />} onClick={() => navigate('/guidance')} 
                        className="glass-button"
                      >
                        开始智能引导
                      </Button>
                      <Button size="large" icon={<ThunderboltFilled />} onClick={() => navigate('/contract/generate')}
                        className="glass-button-secondary"
                      >
                        快速起草
                      </Button>
                    </Space>
                  </Col>
                  <Col xs={0} md={8} style={{ textAlign: 'right', position: 'relative', height: '180px' }}>
                    <div className="banner-robot-icon floating-animation">
                      <RobotOutlined />
                    </div>
                  </Col>
                </Row>
              </Card>

              {/* 九宫格区域 (带瀑布流动画) */}
              <div className="waterfall-container">
                {sceneCategories.map((category, catIndex) => {
                  const categoryScenes = gridScenes.filter(s => s.category === category.id);
                  return (
                    <div key={category.id} className="category-section" style={{ animationDelay: `${catIndex * 0.1}s` }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
                        <span style={{ fontSize: '20px', marginRight: '8px', display: 'flex' }}>{category.icon}</span>
                        <Title level={4} style={{ margin: 0, color: '#262626' }}>{category.name}</Title>
                        <span style={{ margin: '0 12px', color: '#d9d9d9' }}>|</span>
                        <Text type="secondary">{category.description}</Text>
                      </div>
                      
                      <Row gutter={[20, 20]}>
                        {categoryScenes.map((scene, sceneIndex) => (
                          <Col xs={24} sm={12} md={8} key={scene.id}>
                            <Card
                              hoverable
                              className="scene-card"
                              onClick={() => handleSceneClick(scene)}
                              bordered={false}
                              style={{ animationDelay: `${(catIndex * 0.1) + (sceneIndex * 0.05)}s` }}
                            >
                              <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                                <div style={{ marginRight: '16px' }}>{scene.icon}</div>
                                <div>
                                  <Title level={5} style={{ margin: '0 0 8px 0', fontSize: '16px' }}>{scene.title}</Title>
                                  <Paragraph type="secondary" style={{ margin: 0, fontSize: '13px', lineHeight: '1.5' }}>
                                    {scene.description}
                                  </Paragraph>
                                </div>
                              </div>
                              <div className="card-hover-arrow">
                                <ArrowRightOutlined />
                              </div>
                            </Card>
                          </Col>
                        ))}
                      </Row>
                    </div>
                  );
                })}
              </div>

            </div>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
};

export default SceneSelectionPage;