// frontend/src/components/TemplateSelector.tsx
import React, { useState, useEffect } from 'react';
import { Card, Select, Button, Tag, Spin, Alert, Space, Typography, Empty, Radio, Row, Col, Tooltip } from 'antd';
import { SearchOutlined, AppstoreOutlined, BarsOutlined, StarOutlined, DownloadOutlined } from '@ant-design/icons';
import { contractTemplateApi, ContractTemplate } from '../api/contractTemplates';

const { Option } = Select;
const { Text, Title } = Typography;

interface TemplateSelectorProps {
  onSelectTemplate?: (template: ContractTemplate) => void;
  selectedTemplateId?: string;
  showUserTemplates?: boolean; // 是否显示用户自己的模版
}

type ViewMode = 'card' | 'list';

const TemplateSelector: React.FC<TemplateSelectorProps> = ({
  onSelectTemplate,
  selectedTemplateId,
  showUserTemplates = true
}) => {
  const [categories, setCategories] = useState<any[]>([]);
  const [publicTemplates, setPublicTemplates] = useState<ContractTemplate[]>([]);
  const [userTemplates, setUserTemplates] = useState<ContractTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [viewMode, setViewMode] = useState<ViewMode>('card'); // 新增：视图模式状态

  // 加载分类和模版数据
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError('');

    try {
      // 并行加载分类、公有模版和用户模版
      const [categoriesRes, publicRes, userRes] = await Promise.all([
        contractTemplateApi.getCategoryTree(true),
        contractTemplateApi.getTemplates({ scope: 'public', page_size: 100 }),
        showUserTemplates ? contractTemplateApi.getTemplates({ scope: 'my', page_size: 100 }) : Promise.resolve({ templates: [] })
      ]);

      setCategories(categoriesRes);
      setPublicTemplates(publicRes.templates);
      setUserTemplates(userRes.templates);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || '加载模版数据失败';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // 处理分类选择
  const handleCategoryChange = (value: string) => {
    setSelectedCategory(value);
  };

  // 处理模版选择
  const handleTemplateSelect = (templateId: string) => {
    const template = [...publicTemplates, ...userTemplates].find(t => t.id === templateId);
    if (template && onSelectTemplate) {
      onSelectTemplate(template);
    }
  };

  // 根据分类过滤模版
  const getFilteredTemplates = (templates: ContractTemplate[]) => {
    if (!selectedCategory) return templates;
    return templates.filter(template => template.category === selectedCategory);
  };

  // 新增：渲染卡片视图
  const renderCardView = (templates: ContractTemplate[], title: string) => {
    if (templates.length === 0) return null;

    return (
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 12 }}>{title} ({templates.length})</Title>
        <Row gutter={[16, 16]}>
          {templates.map((template) => (
            <Col key={template.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                onClick={() => handleTemplateSelect(template.id)}
                style={{
                  height: '100%',
                  border: selectedTemplateId === template.id ? '2px solid #1890ff' : '1px solid #d9d9d9',
                  position: 'relative'
                }}
                bodyStyle={{ padding: 16 }}
              >
                <div style={{ marginBottom: 8 }}>
                  <Tooltip title={template.name}>
                    <Text strong ellipsis style={{ fontSize: 14 }}>{template.name}</Text>
                  </Tooltip>
                </div>

                <div style={{ marginBottom: 8 }}>
                  <Tag color="blue" style={{ fontSize: 11 }}>{template.category}</Tag>
                  {template.subcategory && (
                    <Tag color="cyan" style={{ fontSize: 11 }}>{template.subcategory}</Tag>
                  )}
                  <Tag color={template.is_public ? 'green' : 'orange'} style={{ fontSize: 11 }}>
                    {template.is_public ? '公有' : '私有'}
                  </Tag>
                </div>

                {template.description && (
                  <Tooltip title={template.description}>
                    <Text
                      type="secondary"
                      ellipsis
                      style={{ fontSize: 12, display: 'block', marginBottom: 8, height: 36 }}
                    >
                      {template.description}
                    </Text>
                  </Tooltip>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                  <Space size={4}>
                    {template.rating > 0 && (
                      <Tag color="gold" style={{ fontSize: 11, margin: 0 }}>
                        <StarOutlined style={{ fontSize: 10 }} /> {template.rating.toFixed(1)}
                      </Tag>
                    )}
                    <Tag style={{ fontSize: 11, margin: 0 }}>
                      <DownloadOutlined style={{ fontSize: 10 }} /> {template.download_count}
                    </Tag>
                  </Space>
                  {selectedTemplateId === template.id && (
                    <Tag color="blue" style={{ fontSize: 11 }}>已选择</Tag>
                  )}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>
    );
  };

  // 新增：渲染列表视图
  const renderListView = (templates: ContractTemplate[], title: string) => {
    if (templates.length === 0) return null;

    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <Text strong style={{ fontSize: 13 }}>{title} ({templates.length})</Text>
        </div>
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          {templates.map((template) => (
            <Card
              key={template.id}
              size="small"
              hoverable
              onClick={() => handleTemplateSelect(template.id)}
              style={{
                border: selectedTemplateId === template.id ? '2px solid #1890ff' : '1px solid #d9d9d9'
              }}
              bodyStyle={{ padding: '12px 16px' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <Text strong ellipsis style={{ fontSize: 13 }}>{template.name}</Text>
                    <Tag color="blue" style={{ fontSize: 11, margin: 0, flexShrink: 0 }}>{template.category}</Tag>
                    {template.subcategory && (
                      <Tag color="cyan" style={{ fontSize: 11, margin: 0, flexShrink: 0 }}>{template.subcategory}</Tag>
                    )}
                    <Tag color={template.is_public ? 'green' : 'orange'} style={{ fontSize: 11, margin: 0, flexShrink: 0 }}>
                      {template.is_public ? '公有' : '私有'}
                    </Tag>
                    {selectedTemplateId === template.id && (
                      <Tag color="blue" style={{ fontSize: 11, margin: 0, flexShrink: 0 }}>已选择</Tag>
                    )}
                  </div>
                  {template.description && (
                    <Text type="secondary" ellipsis style={{ fontSize: 12, display: 'block' }}>
                      {template.description}
                    </Text>
                  )}
                </div>
                <Space size={12} style={{ flexShrink: 0, marginLeft: 16 }}>
                  {template.rating > 0 && (
                    <Tag color="gold" style={{ fontSize: 11, margin: 0 }}>
                      <StarOutlined style={{ fontSize: 10 }} /> {template.rating.toFixed(1)}
                    </Tag>
                  )}
                  <Tag style={{ fontSize: 11, margin: 0 }}>
                    <DownloadOutlined style={{ fontSize: 10 }} /> {template.download_count}
                  </Tag>
                </Space>
              </div>
            </Card>
          ))}
        </Space>
      </div>
    );
  };

  if (loading) {
    return (
      <Card title="选择合同模版" style={{ marginBottom: 16 }}>
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Spin size="large" tip="正在加载模版..." />
        </div>
      </Card>
    );
  }

  const filteredPublicTemplates = getFilteredTemplates(publicTemplates);
  const filteredUserTemplates = getFilteredTemplates(userTemplates);

  return (
    <Card title="选择合同模版" style={{ marginBottom: 16 }}>
      {error && (
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16 }}
          onClose={() => setError('')}
        />
      )}

      {/* 分类筛选和视图切换 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <Space>
          <Text strong>合同类型：</Text>
          <Select
            style={{ width: 200 }}
            placeholder="请选择合同类型"
            allowClear
            onChange={handleCategoryChange}
            value={selectedCategory}
          >
            {categories.map(category => (
              <Option key={category.id} value={category.name}>
                {category.name}
              </Option>
            ))}
          </Select>
          <Button
            icon={<SearchOutlined />}
            onClick={loadData}
          >
            刷新
          </Button>
        </Space>

        {/* 新增：视图切换按钮 */}
        <Radio.Group
          value={viewMode}
          onChange={(e) => setViewMode(e.target.value)}
          buttonStyle="solid"
        >
          <Radio.Button value="card"><AppstoreOutlined /> 卡片</Radio.Button>
          <Radio.Button value="list"><BarsOutlined /> 列表</Radio.Button>
        </Radio.Group>
      </div>

      {/* 统计信息 */}
      <div style={{ marginBottom: 16, fontSize: 12, color: '#666' }}>
        <Space>
          <span>公有模版: <Text strong>{filteredPublicTemplates.length}</Text> 个</span>
          {showUserTemplates && (
            <span>我的模版: <Text strong>{filteredUserTemplates.length}</Text> 个</span>
          )}
        </Space>
      </div>

      {/* 根据视图模式渲染 */}
      {viewMode === 'card' ? (
        <>
          {/* 卡片视图 */}
          {renderCardView(filteredPublicTemplates, '公有模版')}
          {showUserTemplates && renderCardView(filteredUserTemplates, '我的模版')}

          {/* 如果没有模版 */}
          {filteredPublicTemplates.length === 0 &&
           (!showUserTemplates || filteredUserTemplates.length === 0) && (
            <Empty
              description="暂无模版"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ marginTop: 16 }}
            />
          )}
        </>
      ) : (
        <>
          {/* 列表视图 */}
          {renderListView(filteredPublicTemplates, '公有模版')}
          {showUserTemplates && renderListView(filteredUserTemplates, '我的模版')}

          {/* 如果没有模版 */}
          {filteredPublicTemplates.length === 0 &&
           (!showUserTemplates || filteredUserTemplates.length === 0) && (
            <Empty
              description="暂无模版"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ marginTop: 16 }}
            />
          )}
        </>
      )}
    </Card>
  );
};

export default TemplateSelector;