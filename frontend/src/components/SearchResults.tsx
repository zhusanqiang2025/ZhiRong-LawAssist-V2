// frontend/src/components/SearchResults.tsx
import React from 'react';
import { Tabs, List, Tag, Empty, Typography, Space, Spin } from 'antd';
import {
  AppstoreOutlined,
  HistoryOutlined,
  BookOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { SearchResult } from '../types/search';

const { Text } = Typography;

interface SearchResultsProps {
  query: string;
  results: SearchResult[];
  loading: boolean;
  facets: {
    module: number;
    task: number;
    legal: number;
  };
}

const SearchResults: React.FC<SearchResultsProps> = ({
  query,
  results,
  loading,
  facets
}) => {
  const navigate = useNavigate();

  // 按类型分组
  const moduleResults = results.filter(r => r.type === 'module');
  const taskResults = results.filter(r => r.type === 'task');
  const legalResults = results.filter(r => r.type === 'legal');

  const handleResultClick = (item: SearchResult) => {
    if (item.url) {
      navigate(item.url);
    }
  };

  const ResultGroup: React.FC<{
    title: string;
    icon: React.ReactNode;
    results: SearchResult[]
  }> = ({ title, icon, results }) => {
    if (results.length === 0) return null;

    return (
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ marginBottom: 8, display: 'block' }}>
          {icon} {title} ({results.length})
        </Text>
        <List
          size="small"
          dataSource={results}
          renderItem={item => (
            <List.Item
              key={item.id}
              style={{ cursor: 'pointer', padding: '8px 0' }}
              onClick={() => handleResultClick(item)}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Text ellipsis style={{ maxWidth: 200 }}>{item.title}</Text>
                    {item.category && <Tag color="blue" style={{ fontSize: 11 }}>{item.category}</Tag>}
                  </Space>
                }
                description={
                  <Text type="secondary" ellipsis style={{ fontSize: 12 }}>
                    {item.description}
                  </Text>
                }
              />
            </List.Item>
          )}
        />
      </div>
    );
  };

  const items = [
    {
      key: 'all',
      label: `全部 (${results.length})`,
      children: (
        <div style={{ maxHeight: '400px', overflowY: 'auto', minWidth: 450 }}>
          <ResultGroup
            title="功能模块"
            icon={<AppstoreOutlined />}
            results={moduleResults}
          />
          <ResultGroup
            title="历史任务"
            icon={<HistoryOutlined />}
            results={taskResults}
          />
          <ResultGroup
            title="法律知识"
            icon={<BookOutlined />}
            results={legalResults}
          />
        </div>
      )
    },
    {
      key: 'module',
      label: `功能模块 (${facets.module})`,
      children: (
        <div style={{ maxHeight: '400px', overflowY: 'auto', minWidth: 450 }}>
          <ResultGroup
            title="功能模块"
            icon={<AppstoreOutlined />}
            results={moduleResults}
          />
        </div>
      )
    },
    {
      key: 'task',
      label: `历史任务 (${facets.task})`,
      children: (
        <div style={{ maxHeight: '400px', overflowY: 'auto', minWidth: 450 }}>
          <ResultGroup
            title="历史任务"
            icon={<HistoryOutlined />}
            results={taskResults}
          />
        </div>
      )
    },
    {
      key: 'legal',
      label: `法律知识 (${facets.legal})`,
      children: (
        <div style={{ maxHeight: '400px', overflowY: 'auto', minWidth: 450 }}>
          <ResultGroup
            title="法律知识"
            icon={<BookOutlined />}
            results={legalResults}
          />
        </div>
      )
    }
  ];

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center', minWidth: 450 }}>
        <Spin tip="搜索中..." />
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div style={{ padding: 24, minWidth: 450 }}>
        <Empty description="未找到相关结果" />
      </div>
    );
  }

  return (
    <Tabs
      defaultActiveKey="all"
      items={items}
      size="small"
    />
  );
};

export default SearchResults;
