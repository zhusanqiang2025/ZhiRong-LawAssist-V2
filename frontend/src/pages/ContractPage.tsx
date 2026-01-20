// frontend/src/pages/ContractPage.tsx (清洁版 v3.1)
import React, { useState, useEffect, useRef } from 'react';
import {
  Button,
  Card,
  Layout,
  Typography,
  message,
  Space,
  Tabs,
  Tag,
  Input,
  Select,
  Rate,
  Pagination,
  List,
  Tooltip,
  Modal,
  Form,
  Upload,
  Switch,
  Row,
  Col,
  Alert,
  Spin,
  Table
} from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  FileTextOutlined,
  SearchOutlined,
  EyeOutlined,
  CloudUploadOutlined,
  InboxOutlined,
  EditOutlined,
  AppstoreOutlined,
  BarsOutlined,
  UnorderedListOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import api from '../api';
import { contractTemplateApi, ContractTemplate, TemplateInfo } from '../api/contractTemplates';
import { useSessionPersistence } from '../hooks/useSessionPersistence';
import './ContractPage.css';

const { Header, Content } = Layout;
const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { Search } = Input;
const { Option } = Select;
const { Dragger } = Upload;

// 定义本地接口类型（扩展 ContractTemplate）
interface CategoryInfo {
    category: string;
    count: number;
}

const ContractPage: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // ========== 会话持久化 ==========
  // 定义会话数据类型
  interface ContractPageSessionData {
    activeTab: string;
    selectedCategory: string | undefined;
    sortBy: string;
    currentPage: number;
    pageSize: number;
    viewMode: 'card' | 'list';
    searchQuery: string;
    hasSearched: boolean;
  }

  // 使用 ref 来追踪是否已经恢复过会话，避免重复恢复
  const hasRestoredRef = useRef(false);
  const isRestoringRef = useRef(false);

  const {
    hasSession,
    saveSession,
    clearSession,
    isLoading: isRestoringSession
  } = useSessionPersistence<ContractPageSessionData>('contract_page_session', {
    expirationTime: 2 * 60 * 60 * 1000, // 2小时
    autoRestore: false, // 禁用自动恢复，手动控制恢复时机
    onRestore: (sessionId, data) => {
      console.log('[合同模板页] 恢复会话:', data);
      isRestoringRef.current = true;

      setActiveTab(data.activeTab || 'query');
      setSelectedCategory(data.selectedCategory);
      setSortBy(data.sortBy || 'created_at');
      setCurrentPage(data.currentPage || 1);
      setPageSize(data.pageSize || 12);
      setViewMode(data.viewMode || 'card');
      if (data.searchQuery) {
        setHasSearched(data.hasSearched);
        if (data.hasSearched) {
          handleSearch(data.searchQuery);
        }
      }

      // 标记恢复完成（延迟到下一个事件循环，避免在状态更新期间触发）
      setTimeout(() => {
        hasRestoredRef.current = true;
        isRestoringRef.current = false;
      }, 0);
    }
  });

  // 保存会话状态
  const saveCurrentState = (searchQuery?: string) => {
    // 如果正在恢复会话，则不保存
    if (isRestoringRef.current) {
      console.log('[合同模板页] 正在恢复会话，跳过保存');
      return;
    }

    saveSession(Date.now().toString(), {
      activeTab,
      selectedCategory,
      sortBy,
      currentPage,
      pageSize,
      viewMode,
      searchQuery: searchQuery || '',
      hasSearched
    });
  };

  // ========== 状态管理 ==========
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<ContractTemplate[]>([]);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [totalTemplates, setTotalTemplates] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  
  // 筛选状态
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>();
  const [sortBy, setSortBy] = useState('created_at');
  // 移除未使用的 setSortOrder，保留 sortOrder 默认值
  const [sortOrder] = useState('desc'); 
  
  // 搜索状态
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<TemplateInfo[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  
  // Tab 状态
  const [activeTab, setActiveTab] = useState('query');

  // 视图模式状态
  const [viewMode, setViewMode] = useState<'card' | 'list'>('card');

  // 上传 Modal 状态
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadForm] = Form.useForm();

  // 预览 Modal 状态
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [previewData, setPreviewData] = useState<{
    name: string;
    content: string;
    file_type: string;
    preview_type?: string;
  } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // 初始化
  useEffect(() => {
    const params = (location.state as any) || {};
    if (params.action === 'generate') setActiveTab('generate');

    loadCategories();
  }, [location.state]); // 添加依赖

  // 手动控制会话恢复（仅在组件首次挂载时执行一次）
  useEffect(() => {
    // 如果已经恢复过，或者正在恢复，则跳过
    if (hasRestoredRef.current || isRestoringRef.current) {
      return;
    }

    // 检查是否有可恢复的会话
    if (hasSession) {
      console.log('[合同模板页] 检测到会话，准备恢复');
      isRestoringRef.current = true;

      // 获取存储的会话数据
      const storedData = localStorage.getItem('contract_page_session');
      if (storedData) {
        try {
          const session = JSON.parse(storedData);
          // 手动触发恢复
          const { onRestore } = (useSessionPersistence as any).restore?.cache?.get('contract_page_session') || {};
          if (session.data) {
            // 直接恢复状态而不触发消息
            setActiveTab(session.data.activeTab || 'query');
            setSelectedCategory(session.data.selectedCategory);
            setSortBy(session.data.sortBy || 'created_at');
            setCurrentPage(session.data.currentPage || 1);
            setPageSize(session.data.pageSize || 12);
            setViewMode(session.data.viewMode || 'card');
            if (session.data.searchQuery) {
              setHasSearched(session.data.hasSearched);
              if (session.data.hasSearched) {
                handleSearch(session.data.searchQuery);
              }
            }

            // 显示恢复消息（只显示一次）
            message.success('已恢复之前的浏览状态');

            // 标记恢复完成
            setTimeout(() => {
              hasRestoredRef.current = true;
              isRestoringRef.current = false;
            }, 100);
          }
        } catch (error) {
          console.error('[合同模板页] 恢复会话失败:', error);
          hasRestoredRef.current = true;
          isRestoringRef.current = false;
        }
      } else {
        hasRestoredRef.current = true;
      }
    } else {
      // 没有会话，直接标记完成
      hasRestoredRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 只在组件挂载时执行一次

  // 监听条件变化重新加载列表
  useEffect(() => {
    if (activeTab === 'query' || activeTab === 'my-templates') {
        loadTemplates();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage, pageSize, selectedCategory, sortBy, sortOrder, activeTab]);

  // 监听状态变化，自动保存会话
  useEffect(() => {
    // 只在恢复完成后才保存会话
    if (hasRestoredRef.current && !isRestoringRef.current && !isRestoringSession) {
      saveCurrentState();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedCategory, sortBy, currentPage, pageSize, viewMode, hasSearched]);
  // ========== 会话持久化结束 ==========

  const loadCategories = async () => {
    try {
      const res = await contractTemplateApi.getCategoryTree(true);
      // 将分类树转换为 CategoryInfo 格式
      const categoryMap = new Map<string, number>();
      res.forEach((cat: any) => {
        if (cat.name) {
          categoryMap.set(cat.name, (categoryMap.get(cat.name) || 0) + 1);
        }
      });
      const categoryInfo: CategoryInfo[] = Array.from(categoryMap.entries()).map(([category, count]) => ({
        category,
        count
      }));
      setCategories(categoryInfo);
    } catch (error) {
      console.error('加载分类失败:', error);
    }
  };

  const loadTemplates = async () => {
    setLoading(true);
    try {
      // 根据 Tab 决定调用哪个 API
      const scope = activeTab === 'my-templates' ? 'my' : 'public';

      const params = {
        page: currentPage,
        page_size: pageSize,
        category: selectedCategory,
        sort_by: sortBy,
        sort_order: sortOrder,
        scope: scope as 'public' | 'my' | 'all'
      };

      const res = await contractTemplateApi.getTemplates(params);

      setTemplates(res.templates);
      setTotalTemplates(res.total_count);
    } catch (error) {
      console.error('加载模板失败:', error);
      message.error('加载列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (query: string) => {
    if (!query.trim()) {
      setHasSearched(false);
      setSearchResults([]);
      saveCurrentState('');
      return;
    }

    setSearchLoading(true);
    setHasSearched(true);

    try {
      const res = await contractTemplateApi.searchTemplates({
        query: query.trim()
      });

      setSearchResults(res.templates);
      saveCurrentState(query); // 保存搜索状态

      if (res.templates.length === 0) {
        message.info('未找到相关模板');
      }
    } catch (error) {
      console.error('搜索失败:', error);
      message.error('搜索服务暂时不可用');
    } finally {
      setSearchLoading(false);
    }
  };

  // 通用下载处理函数（支持 ContractTemplate 和 TemplateInfo）
  const handleDownload = async (template: { id: string; name: string }) => {
    try {
      await contractTemplateApi.downloadTemplate(template.id);
      message.success(`开始下载: ${template.name}`);
    } catch (error) {
      console.error('下载失败:', error);
      message.error('下载失败');
    }
  };

  // 通用预览处理函数（支持 ContractTemplate 和 TemplateInfo）
  const handlePreview = async (template: { id: string; name: string }) => {
    setPreviewLoading(true);
    setIsPreviewModalOpen(true);
    setPreviewData(null);

    try {
      const data = await contractTemplateApi.getTemplatePreview(template.id);
      setPreviewData({
        name: template.name,
        content: data.content,
        file_type: data.file_type
      });
    } catch (error: any) {
      console.error('预览失败:', error);
      if (error.response?.data?.detail) {
        setPreviewData({
          name: template.name,
          content: error.response.data.detail,
          file_type: 'unknown'
        });
      } else {
        message.error('预览失败');
        setIsPreviewModalOpen(false);
      }
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleRate = async (templateId: string, rating: number) => {
    try {
      await contractTemplateApi.rateTemplate(templateId, rating);
      message.success('评分成功');
      loadTemplates();
    } catch (error) {
      message.error('评分失败');
    }
  };

  // 处理上传提交
  const handleUploadSubmit = async () => {
    try {
        const values = await uploadForm.validateFields();
        setUploading(true);

        const formData = new FormData();
        formData.append('name', values.name);
        formData.append('category', values.category);
        formData.append('description', values.description || '');
        formData.append('is_public', values.is_public ? 'true' : 'false');
        
        if (values.keywords) {
            formData.append('keywords', values.keywords.join(','));
        }
        
        if (values.file && values.file.length > 0) {
            formData.append('file', values.file[0].originFileObj);
        }

        await api.uploadTemplate(formData);
        
        message.success('上传成功！');
        setIsUploadModalOpen(false);
        uploadForm.resetFields();

        // 如果当前不在我的模板页，切换过去查看
        if (activeTab !== 'my-templates') {
            setActiveTab('my-templates');
        } else {
            loadTemplates();
        }

    } catch (error) {
        console.error(error);
        message.error('上传失败');
    } finally {
        setUploading(false);
    }
  };

  // 渲染单个卡片
  const renderTemplateCard = (template: ContractTemplate) => {
    const isAdmin = user?.is_admin || false;

    // 构建操作按钮
    const actions = [
      <Tooltip title="下载" key="download-tip">
        <DownloadOutlined key="download" onClick={() => handleDownload(template)} />
      </Tooltip>,
      <Tooltip title="预览" key="view-tip">
        <EyeOutlined key="view" onClick={() => handlePreview(template)} />
      </Tooltip>
    ];

    // 仅管理员显示编辑按钮
    if (isAdmin) {
      actions.push(
        <Tooltip title="编辑" key="edit-tip">
          <EditOutlined key="edit" onClick={() => navigate(`/contract/${template.id}/edit`)} />
        </Tooltip>
      );
    }

    actions.push(
      <Rate
        key="rate"
        disabled={(template as any).rating_count > 0}
        defaultValue={template.rating}
        style={{ fontSize: 12 }}
        onChange={(val) => handleRate(template.id, val)}
      />
    );

    return (
      <Card
        key={template.id}
        hoverable
        className="template-card"
        cover={
          <div className="template-preview-placeholder" style={{ height: 160, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FileTextOutlined style={{ fontSize: 48, color: '#1890ff' }} />
          </div>
        }
        actions={actions}
      >
        <Card.Meta
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{template.name}</span>
              {template.is_public ? <Tag color="green">公开</Tag> : <Tag color="orange">私有</Tag>}
            </div>
          }
          description={
            <div>
              <Text type="secondary" style={{ fontSize: 12 }} ellipsis>{template.description || '暂无描述'}</Text>
              <div style={{ marginTop: 8 }}>
                <Tag color="blue">{template.category}</Tag>
                <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                   <DownloadOutlined /> {template.download_count}
                </span>
              </div>
            </div>
          }
        />
      </Card>
    );
  };

  // 渲染列表视图
  const renderListView = () => {
    const columns = [
      {
        title: '模板名称',
        dataIndex: 'name',
        key: 'name',
        width: '25%',
        render: (text: string, record: ContractTemplate) => (
          <Space>
            <Text strong ellipsis={{ tooltip: text }} style={{ maxWidth: 200 }}>
              {text}
            </Text>
            {record.is_public ? <Tag color="green">公开</Tag> : <Tag color="orange">私有</Tag>}
          </Space>
        ),
      },
      {
        title: '分类',
        dataIndex: 'category',
        key: 'category',
        width: '10%',
        render: (category: string) => <Tag color="blue">{category}</Tag>,
      },
      {
        title: '描述',
        dataIndex: 'description',
        key: 'description',
        width: '25%',
        render: (text: string) => (
          <Text type="secondary" ellipsis={{ tooltip: text || '暂无描述' }}>
            {text || '暂无描述'}
          </Text>
        ),
      },
      {
        title: '评分',
        dataIndex: 'rating',
        key: 'rating',
        width: '10%',
        render: (rating: number, record: ContractTemplate) => (
          <Space>
            <Rate disabled defaultValue={rating} style={{ fontSize: 12 }} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              ({(record as any).rating_count || 0})
            </Text>
          </Space>
        ),
      },
      {
        title: '下载次数',
        dataIndex: 'download_count',
        key: 'download_count',
        width: '10%',
        render: (count: number) => <Text><DownloadOutlined /> {count}</Text>,
      },
      {
        title: '操作',
        key: 'action',
        width: '20%',
        render: (_: any, record: ContractTemplate) => {
          const isAdmin = user?.is_admin || false;
          return (
            <Space size="small">
              <Tooltip title="下载">
                <Button
                  type="text"
                  icon={<DownloadOutlined />}
                  onClick={() => handleDownload(record)}
                />
              </Tooltip>
              <Tooltip title="预览">
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={() => handlePreview(record)}
                />
              </Tooltip>
              {isAdmin && (
                <Tooltip title="编辑">
                  <Button
                    type="text"
                    icon={<EditOutlined />}
                    onClick={() => navigate(`/contract/${record.id}/edit`)}
                  />
                </Tooltip>
              )}
            </Space>
          );
        },
      },
    ];

    return (
      <Table
        columns={columns}
        dataSource={templates}
        loading={loading}
        rowKey="id"
        pagination={false}
        size="middle"
      />
    );
  };

  // 渲染搜索结果卡片 (TemplateInfo 类型)
  const renderSearchResultCard = (template: TemplateInfo) => {
    const isAdmin = user?.is_admin || false;

    // 构建操作按钮
    const actions = [
      <Tooltip title="下载" key="download-tip">
        <DownloadOutlined key="download" onClick={() => handleDownload(template)} />
      </Tooltip>,
      <Tooltip title="预览" key="view-tip">
        <EyeOutlined key="view" onClick={() => handlePreview(template)} />
      </Tooltip>,
    ];

    // 仅管理员显示编辑按钮
    if (isAdmin) {
      actions.push(
        <Tooltip title="编辑" key="edit-tip">
          <EditOutlined key="edit" onClick={() => navigate(`/contract/${template.id}/edit`)} />
        </Tooltip>
      );
    }

    actions.push(
      <Tooltip title="匹配度" key="score">
        <span style={{ fontSize: 12, color: '#52c41a' }}>{(template.final_score * 100).toFixed(0)}%</span>
      </Tooltip>
    );

    return (
      <Card
        key={template.id}
        hoverable
        className="template-card"
        cover={
          <div className="template-preview-placeholder" style={{ height: 160, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FileTextOutlined style={{ fontSize: 48, color: '#1890ff' }} />
          </div>
        }
        actions={actions}
      >
        <Card.Meta
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{template.name}</span>
              <Tag color="purple">智能</Tag>
            </div>
          }
          description={
            <div>
              <Text type="secondary" style={{ fontSize: 12 }} ellipsis>{template.description || '暂无描述'}</Text>
              <div style={{ marginTop: 8 }}>
                <Tag color="blue">{template.category}</Tag>
                {template.subcategory && <Tag color="cyan">{template.subcategory}</Tag>}
                {template.match_reason && (
                  <div style={{ marginTop: 4, fontSize: 11, color: '#52c41a' }}>
                    {template.match_reason}
                  </div>
                )}
              </div>
            </div>
          }
        />
      </Card>
    );
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#f0f2f5' }}>
      {/* 统一导航栏 */}
      <ModuleNavBar
        currentModuleKey="template-search"
        extra={
          <Space>
            <Button
              type="primary"
              icon={<CloudUploadOutlined />}
              onClick={() => setIsUploadModalOpen(true)}
            >
              上传模板
            </Button>
            <Button onClick={logout}>退出</Button>
          </Space>
        }
      />

      {/* 原有内容区域 */}
      <div style={{ flex: 1, padding: '24px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
        {/* 会话恢复提示 */}
        {hasSession && !hasRestoredRef.current && (
          <Alert
            message="发现未完成的浏览会话"
            description="您上次浏览的模板状态已保存，是否恢复？"
            type="info"
            showIcon
            closable
            action={
              <Space>
                <Button
                  size="small"
                  onClick={() => {
                    clearSession();
                    hasRestoredRef.current = true;
                  }}
                >
                  忽略
                </Button>
                <Button
                  type="primary"
                  size="small"
                  onClick={() => {
                    // 手动触发恢复（通过重新执行恢复 effect）
                    hasRestoredRef.current = false;
                    // 这将触发上面的 effect 执行恢复逻辑
                  }}
                >
                  恢复会话
                </Button>
              </Space>
            }
            style={{ marginBottom: 16 }}
          />
        )}

        <Tabs activeKey={activeTab} onChange={setActiveTab} type="card">

          {/* Tab 1: 模板广场 */}
          <TabPane tab="模板广场" key="query">
            <div style={{ marginBottom: 24, background: '#fff', padding: 24, borderRadius: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <Search
                  placeholder="输入关键词，AI 智能匹配..."
                  enterButton={<SearchOutlined />}
                  size="large"
                  loading={searchLoading}
                  onSearch={handleSearch}
                  onChange={(e) => !e.target.value && setHasSearched(false)}
                  style={{ maxWidth: 600, marginBottom: 0 }}
                />
                <Space>
                  <Button
                    type={viewMode === 'card' ? 'primary' : 'default'}
                    icon={<AppstoreOutlined />}
                    onClick={() => setViewMode('card')}
                  >
                    卡片
                  </Button>
                  <Button
                    type={viewMode === 'list' ? 'primary' : 'default'}
                    icon={<UnorderedListOutlined />}
                    onClick={() => setViewMode('list')}
                  >
                    列表
                  </Button>
                </Space>
              </div>
              <Space wrap>
                <Select
                    placeholder="选择分类"
                    allowClear
                    onChange={(val) => { setSelectedCategory(val); setCurrentPage(1); }}
                    style={{ width: 150 }}
                >
                    {categories.map(c => (
                        <Option key={c.category} value={c.category}>{c.category} ({c.count})</Option>
                    ))}
                </Select>
                <Select
                    defaultValue="created_at"
                    onChange={(val) => setSortBy(val)}
                    style={{ width: 120 }}
                >
                    <Option value="created_at">最新上传</Option>
                    <Option value="download_count">下载最多</Option>
                    <Option value="rating">评分最高</Option>
                </Select>
              </Space>
            </div>

            {/* 搜索/列表结果 */}
            {hasSearched ? (
                <List
                    grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
                    dataSource={searchResults}
                    renderItem={renderSearchResultCard}
                />
            ) : (
                <>
                    {viewMode === 'card' ? (
                        <List
                            grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
                            dataSource={templates}
                            loading={loading}
                            renderItem={renderTemplateCard}
                        />
                    ) : (
                        renderListView()
                    )}
                    <div style={{ textAlign: 'center', marginTop: 24 }}>
                        <Pagination
                            current={currentPage}
                            total={totalTemplates}
                            pageSize={pageSize}
                            onChange={(p, s) => { setCurrentPage(p); if(s) setPageSize(s); }}
                        />
                    </div>
                </>
            )}
          </TabPane>

          {/* Tab 2: 智能生成 */}
          <TabPane tab="智能生成" key="generate">
            <div style={{ padding: '20px 0' }}>
              <Card
                hoverable
                onClick={() => navigate('/contract-generation')}
                style={{
                  textAlign: 'center',
                  padding: 40,
                  cursor: 'pointer',
                  transition: 'all 0.3s ease',
                  border: '2px solid #1890ff'
                }}
                styles={{ body: { padding: 40 } }}
              >
                <FileTextOutlined style={{
                  fontSize: 64,
                  color: '#1890ff',
                  marginBottom: 20,
                  display: 'block'
                }} />
                <Title level={3} style={{ color: '#1890ff', marginBottom: 12 }}>
                  智能合同生成
                </Title>
                <Paragraph type="secondary" style={{ fontSize: 16, marginBottom: 24 }}>
                  AI 驱动的智能合同生成工具，支持单一合同、合同变更、合同解除等多种场景
                </Paragraph>
                <Space direction="vertical" size="small" style={{ width: '100%', maxWidth: 400, margin: '0 auto' }}>
                  <div style={{ textAlign: 'left', background: '#f5f5f5', padding: '12px 16px', borderRadius: 8 }}>
                    <Text strong>✓ 智能需求分析</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>AI 自动理解您的合同需求</Text>
                  </div>
                  <div style={{ textAlign: 'left', background: '#f5f5f5', padding: '12px 16px', borderRadius: 8 }}>
                    <Text strong>✓ 多种合同类型</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>支持单一合同、合同变更、解除、规划等</Text>
                  </div>
                  <div style={{ textAlign: 'left', background: '#f5f5f5', padding: '12px 16px', borderRadius: 8 }}>
                    <Text strong>✓ 基于 RAG 模板库</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>从 450+ 专业合同模板中智能检索</Text>
                  </div>
                </Space>
                <Button
                  type="primary"
                  size="large"
                  icon={<FileTextOutlined />}
                  style={{ marginTop: 24 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate('/contract-generation');
                  }}
                >
                  开始生成合同
                </Button>
              </Card>
            </div>
          </TabPane>

          {/* Tab 3: 我的模板 */}
          <TabPane tab="我的模板" key="my-templates">
            <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text type="secondary">这里显示您上传的所有模板（包含公开和私有）。</Text>
              <Space>
                <Button
                  type={viewMode === 'card' ? 'primary' : 'default'}
                  icon={<AppstoreOutlined />}
                  onClick={() => setViewMode('card')}
                  size="small"
                >
                  卡片
                </Button>
                <Button
                  type={viewMode === 'list' ? 'primary' : 'default'}
                  icon={<UnorderedListOutlined />}
                  onClick={() => setViewMode('list')}
                  size="small"
                >
                  列表
                </Button>
              </Space>
            </div>
            {viewMode === 'card' ? (
              <List
                  grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
                  dataSource={templates}
                  loading={loading}
                  renderItem={renderTemplateCard}
              />
            ) : (
              renderListView()
            )}
          </TabPane>
        </Tabs>
      </div>

      {/* 上传 Modal */}
      <Modal
        title="上传合同模板"
        open={isUploadModalOpen}
        onCancel={() => setIsUploadModalOpen(false)}
        onOk={handleUploadSubmit}
        confirmLoading={uploading}
      >
        <Form form={uploadForm} layout="vertical">
            <Form.Item name="file" label="文件" rules={[{ required: true }]} valuePropName="fileList" getValueFromEvent={e => Array.isArray(e) ? e : e?.fileList}>
                <Dragger maxCount={1} accept=".docx,.doc,.pdf">
                    <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                    <p className="ant-upload-text">点击或拖拽文件到此处</p>
                </Dragger>
            </Form.Item>
            <Row gutter={16}>
                <Col span={12}>
                    <Form.Item name="name" label="名称" rules={[{ required: true }]}>
                        <Input />
                    </Form.Item>
                </Col>
                <Col span={12}>
                    <Form.Item name="category" label="分类" rules={[{ required: true }]}>
                        <Select>
                            <Option value="劳动人事">劳动人事</Option>
                            <Option value="房屋租赁">房屋租赁</Option>
                            <Option value="商务合作">商务合作</Option>
                            <Option value="其他">其他</Option>
                        </Select>
                    </Form.Item>
                </Col>
            </Row>
            <Form.Item name="keywords" label="关键词">
                <Select mode="tags" placeholder="输入关键词按回车" />
            </Form.Item>
            <Form.Item name="description" label="描述">
                <Input.TextArea rows={2} />
            </Form.Item>
            
            {/* 权限控制：只有管理员能看到公开开关 */}
            {user?.is_admin && (
                <Form.Item name="is_public" label="公开设置" valuePropName="checked">
                    <Switch checkedChildren="公开" unCheckedChildren="私有" />
                </Form.Item>
            )}
        </Form>
      </Modal>

      {/* 预览 Modal */}
      <Modal
        title={<Title level={4} style={{ margin: 0 }}>{previewData?.name || '模板预览'}</Title>}
        open={isPreviewModalOpen}
        onCancel={() => setIsPreviewModalOpen(false)}
        footer={[
          <Button key="close" onClick={() => setIsPreviewModalOpen(false)}>
            关闭
          </Button>
        ]}
        width={800}
        style={{ top: 20 }}
      >
        {previewLoading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" tip="加载预览内容..." />
          </div>
        ) : previewData ? (
          <div>
            <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
              <Text type="secondary">
                文件类型: {previewData.file_type?.toUpperCase()}
                {previewData.preview_type === 'unsupported' && ' (不支持在线预览)'}
              </Text>
            </Space>
            <div
              style={{
                background: '#f5f5f5',
                padding: '16px',
                borderRadius: '4px',
                maxHeight: '500px',
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontFamily: previewData.preview_type === 'error' ? 'inherit' : 'monospace',
                fontSize: '13px',
                lineHeight: '1.6'
              }}
            >
              {previewData.content}
            </div>
            {previewData.preview_type === 'unsupported' && (
              <Alert
                message="提示"
                description="此文件格式不支持在线预览，请点击下载按钮下载文件后使用相应软件打开。"
                type="info"
                showIcon
              />
            )}
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

export default ContractPage;