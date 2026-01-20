// frontend/src/pages/KnowledgeBaseTestPage.tsx
/**
 * 知识库功能测试页面
 *
 * 用于测试知识库 API 和功能
 */

import React, { useState, useEffect } from 'react';
import { Card, Input, Button, Typography, List, Tag, Space, message, Spin, Alert } from 'antd';
import { SearchOutlined, DatabaseOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import knowledgeBaseApi from '../api/knowledgeBase';
import type { SearchResult, KnowledgeItem } from '../api/knowledgeBase';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const KnowledgeBaseTestPage: React.FC = () => {
  const navigate = useNavigate();

  // ============ 状态管理 ============
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [healthInfo, setHealthInfo] = useState<any>(null);

  // ============ 数据加载 ============
  useEffect(() => {
    loadHealthInfo();
  }, []);

  const loadHealthInfo = async () => {
    try {
      const response = await knowledgeBaseApi.healthCheck();
      setHealthInfo(response.data.data);
    } catch (error: any) {
      console.error('加载健康状态失败:', error);
    }
  };

  // ============ 事件处理 ============
  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      message.warning('请输入搜索内容');
      return;
    }

    setSearching(true);
    try {
      const response = await knowledgeBaseApi.search({
        query: searchQuery,
        limit: 5,
      });

      setSearchResult(response.data.data);
      message.success(`找到 ${response.data.data.total} 条结果`);
    } catch (error: any) {
      message.error(`搜索失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSearching(false);
    }
  };

  // ============ 渲染辅助 ============
  const renderHealthStatus = () => {
    if (!healthInfo) {
      return <Spin tip="加载中..." />;
    }

    return (
      <Card title="系统状态" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>知识源总数：</Text>
            <Tag color="blue" style={{ marginLeft: 8 }}>
              {healthInfo.total_stores}
            </Tag>
          </div>
          <div>
            <Text strong>可用知识源：</Text>
            <Tag color="green" style={{ marginLeft: 8 }}>
              {healthInfo.available_stores}
            </Tag>
          </div>
          <div>
            <Text strong>知识源列表：</Text>
          </div>
          <List
            size="small"
            dataSource={healthInfo.stores}
            renderItem={(store: any) => (
              <List.Item>
                <Space>
                  <DatabaseOutlined />
                  <Text>{store.name}</Text>
                  {store.available ? (
                    <Tag color="success">可用</Tag>
                  ) : (
                    <Tag color="error">不可用</Tag>
                  )}
                  <Text type="secondary">优先级: {store.priority}</Text>
                </Space>
              </List.Item>
            )}
          />
        </Space>
      </Card>
    );
  };

  const renderSearchResults = () => {
    if (!searchResult) {
      return (
        <Alert
          message="请输入关键词搜索知识库"
          description="例如：违约责任、劳动合同、公司破产等"
          type="info"
          showIcon
        />
      );
    }

    if (searchResult.total === 0) {
      return (
        <Alert
          message="未找到相关结果"
          description="请尝试其他关键词"
          type="warning"
          showIcon
        />
      );
    }

    return (
      <List
        header={<div>找到 {searchResult.total} 条结果</div>}
        dataSource={searchResult.items}
        renderItem={(item: KnowledgeItem, index: number) => (
          <List.Item key={item.id}>
            <Card size="small" style={{ width: '100%' }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text strong>{index + 1}. {item.title}</Text>
                  <Tag color="blue" style={{ marginLeft: 8 }}>
                    相关性: {(item.relevance_score * 100).toFixed(0)}%
                  </Tag>
                </div>
                <div>
                  <Text type="secondary">来源：{item.source}</Text>
                </div>
                <Paragraph
                  ellipsis={{ rows: 3 }}
                  style={{ marginTop: 8, marginBottom: 0 }}
                >
                  {item.content}
                </Paragraph>
              </Space>
            </Card>
          </List.Item>
        )}
      />
    );
  };

  // ============ 主渲染 ============
  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <Button
        type="text"
        onClick={() => navigate('/admin')}
        style={{ marginBottom: 16 }}
      >
        ← 返回管理后台
      </Button>

      <Title level={2}>知识库功能测试</Title>
      <Paragraph type="secondary">
        测试知识库搜索功能和系统状态
      </Paragraph>

      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* 系统状态 */}
        {renderHealthStatus()}

        {/* 搜索区域 */}
        <Card title="搜索知识库">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Input.Search
              placeholder="输入关键词，例如：违约责任、劳动合同、公司破产"
              enterButton={<Button type="primary" icon={<SearchOutlined />}>搜索</Button>}
              size="large"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onSearch={handleSearch}
              loading={searching}
            />

            {searchResult && searchResult.search_intent && (
              <Alert
                message="搜索意图识别"
                description={
                  <Space direction="vertical" size="small">
                    <div>
                      <Text type="secondary">原始查询：</Text>
                      <Text code>{searchResult.search_intent.original_query}</Text>
                    </div>
                    <div>
                      <Text type="secondary">优化查询：</Text>
                      <Text code>{searchResult.search_intent.optimized_query}</Text>
                    </div>
                    <div>
                      <Text type="secondary">目标领域：</Text>
                      {searchResult.search_intent.target_domains.map((domain: string) => (
                        <Tag key={domain} color="purple">
                          {domain}
                        </Tag>
                      ))}
                    </div>
                  </Space>
                }
                type="info"
                style={{ marginTop: 16 }}
              />
            )}
          </Space>
        </Card>

        {/* 搜索结果 */}
        {renderSearchResults()}
      </Space>
    </div>
  );
};

export default KnowledgeBaseTestPage;
