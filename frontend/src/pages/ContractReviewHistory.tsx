// frontend/src/pages/ContractReviewHistory.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { Table, Tag, Button, Space, Popconfirm, message, Card, Tooltip, Badge } from 'antd';
import {
  EyeOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  DeleteOutlined,
  ReloadOutlined,
  ArrowLeftOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import './ContractReview.css';

interface ContractReviewTask {
  id: number;
  contract_id: number;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed';
  stance: string;
  use_langgraph: boolean;
  transaction_structures?: string[];
  result_summary?: {
    total_items: number;
    by_severity: Record<string, number>;
  };
  created_at: string;
  completed_at?: string;
  started_at?: string;
  error_message?: string;
}

const ContractReviewHistory: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<ContractReviewTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  // 获取任务列表
  const fetchTasks = async (page: number = 1, pageSize: number = 20) => {
    setLoading(true);
    try {
      const params: any = {
        skip: (page - 1) * pageSize,
        limit: pageSize
      };
      if (statusFilter) {
        params.status = statusFilter;
      }

      const response = await api.get('/contract/review-tasks', { params });
      setTasks(response.data);
      setPagination(prev => ({ ...prev, current: page, pageSize }));
    } catch (error: any) {
      console.error('获取任务列表失败', error);
      message.error(error.response?.data?.detail || '获取任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks(1, pagination.pageSize);
  }, [statusFilter]);

  // 刷新任务列表
  const handleRefresh = () => {
    fetchTasks(pagination.current, pagination.pageSize);
  };

  // 暂停任务
  const handlePause = async (taskId: number) => {
    try {
      await api.put(`/contract/review-tasks/${taskId}/pause`);
      message.success('任务已暂停');
      fetchTasks(pagination.current, pagination.pageSize);
    } catch (error: any) {
      console.error('暂停任务失败', error);
      message.error(error.response?.data?.detail || '暂停任务失败');
    }
  };

  // 恢复任务
  const handleResume = async (taskId: number) => {
    try {
      await api.put(`/contract/review-tasks/${taskId}/resume`);
      message.success('任务已恢复');
      fetchTasks(pagination.current, pagination.pageSize);
    } catch (error: any) {
      console.error('恢复任务失败', error);
      message.error(error.response?.data?.detail || '恢复任务失败');
    }
  };

  // 删除任务
  const handleDelete = async (taskId: number) => {
    try {
      await api.delete(`/contract/review-tasks/${taskId}`);
      message.success('任务已删除');
      fetchTasks(pagination.current, pagination.pageSize);
    } catch (error: any) {
      console.error('删除任务失败', error);
      message.error(error.response?.data?.detail || '删除任务失败');
    }
  };

  // 查看结果
  const handleViewResult = (taskId: number, contractId: number) => {
    // 导航到审查页面，并传递contractId
    navigate(`/contract/review?contract_id=${contractId}`);
  };

  // 状态标签渲染
  const renderStatusTag = (status: string) => {
    const statusMap = {
      pending: { color: 'default', text: '等待中', icon: <ClockCircleOutlined /> },
      running: { color: 'processing', text: '执行中', icon: <LoadingOutlined /> },
      paused: { color: 'warning', text: '已暂停', icon: <PauseCircleOutlined /> },
      completed: { color: 'success', text: '已完成', icon: <CheckCircleOutlined /> },
      failed: { color: 'error', text: '失败', icon: <CloseCircleOutlined /> }
    };
    const { color, text, icon } = statusMap[status] || { color: 'default', text: status, icon: null };
    return (
      <Tag color={color} icon={icon}>
        {text}
      </Tag>
    );
  };

  // 风险统计标签渲染
  const renderSeverityTags = (resultSummary: ContractReviewTask['result_summary']) => {
    if (!resultSummary) return '-';

    const severityMap = {
      Critical: { color: 'red', text: '严重' },
      High: { color: 'orange', text: '高' },
      Medium: { color: 'blue', text: '中' },
      Low: { color: 'default', text: '低' }
    };

    const tags = [];
    for (const [severity, count] of Object.entries(resultSummary.by_severity)) {
      if (count > 0 && severityMap[severity]) {
        tags.push(
          <Tag key={severity} color={severityMap[severity].color}>
            {severityMap[severity].text}: {count}
          </Tag>
        );
      }
    }

    return tags.length > 0 ? <Space size={4}>{tags}</Space> : '-';
  };

  // 表格列定义
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
      sorter: (a: ContractReviewTask, b: ContractReviewTask) => a.id - b.id
    },
    {
      title: '合同ID',
      dataIndex: 'contract_id',
      key: 'contract_id',
      width: 100
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => renderStatusTag(status),
      filters: [
        { text: '等待中', value: 'pending' },
        { text: '执行中', value: 'running' },
        { text: '已暂停', value: 'paused' },
        { text: '已完成', value: 'completed' },
        { text: '失败', value: 'failed' }
      ],
      onFilter: (value: any, record: ContractReviewTask) => record.status === value
    },
    {
      title: '立场',
      dataIndex: 'stance',
      key: 'stance',
      width: 80
    },
    {
      title: '系统',
      dataIndex: 'use_langgraph',
      key: 'use_langgraph',
      width: 100,
      render: (useLangGraph: boolean) => (
        <Tag color={useLangGraph ? 'blue' : 'green'}>
          {useLangGraph ? 'LangGraph' : '传统法'}
        </Tag>
      )
    },
    {
      title: '交易结构',
      dataIndex: 'transaction_structures',
      key: 'transaction_structures',
      width: 150,
      ellipsis: true,
      render: (structures: string[] | undefined) => {
        if (!structures || structures.length === 0) return '-';
        return (
          <Tooltip title={structures.join(', ')}>
            <span>{structures.join(', ')}</span>
          </Tooltip>
        );
      }
    },
    {
      title: '审查项数',
      key: 'item_count',
      width: 120,
      render: (_: any, record: ContractReviewTask) => {
        if (!record.result_summary) return '-';
        return (
          <Badge
            count={record.result_summary.total_items}
            showZero
            style={{ backgroundColor: '#52c41a' }}
          />
        );
      }
    },
    {
      title: '风险分布',
      key: 'severity_dist',
      width: 180,
      render: (_: any, record: ContractReviewTask) => renderSeverityTags(record.result_summary)
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
      sorter: (a: ContractReviewTask, b: ContractReviewTask) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    },
    {
      title: '完成时间',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 180,
      render: (date: string) => date ? new Date(date).toLocaleString('zh-CN') : '-'
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      fixed: 'right' as const,
      render: (_: any, record: ContractReviewTask) => (
        <Space size="small">
          {/* 查看结果 (仅已完成任务) */}
          {record.status === 'completed' && (
            <Tooltip title="查看审查结果">
              <Button
                type="link"
                icon={<EyeOutlined />}
                onClick={() => handleViewResult(record.id, record.contract_id)}
              >
                查看结果
              </Button>
            </Tooltip>
          )}

          {/* 暂停 (仅运行中任务) */}
          {record.status === 'running' && (
            <Popconfirm
              title="确定暂停此任务?"
              onConfirm={() => handlePause(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" icon={<PauseCircleOutlined />}>
                暂停
              </Button>
            </Popconfirm>
          )}

          {/* 恢复 (仅已暂停任务) */}
          {record.status === 'paused' && (
            <Popconfirm
              title="确定恢复此任务?"
              onConfirm={() => handleResume(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" icon={<PlayCircleOutlined />}>
                恢复
              </Button>
            </Popconfirm>
          )}

          {/* 重试 (仅失败任务) */}
          {record.status === 'failed' && (
            <Popconfirm
              title="确定重新执行此任务?"
              onConfirm={() => handleResume(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" icon={<ReloadOutlined />}>
                重试
              </Button>
            </Popconfirm>
          )}

          {/* 删除 (非运行中任务) */}
          {record.status !== 'running' && (
            <Popconfirm
              title="确定删除此任务?"
              description="删除后将无法恢复"
              onConfirm={() => handleDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button
                type="link"
                danger
                icon={<DeleteOutlined />}
              >
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      )
    }
  ];

  return (
    <div style={{ padding: '24px', minHeight: '100vh', background: '#f0f2f5' }}>
      {/* 统一导航栏 */}
      <div style={{ marginBottom: 24 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/contract/review')}
        >
          返回审查页面
        </Button>
      </div>

      <Card
        title={
          <span>
            <HistoryOutlined style={{ marginRight: 8 }} />
            合同审查任务历史
          </span>
        }
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={loading}
          >
            刷新
          </Button>
        }
      >
        {/* 统计信息 */}
        <div style={{ marginBottom: 16, display: 'flex', gap: 24 }}>
          <Space size="large">
            <div>
              <span style={{ color: '#666' }}>总任务数：</span>
              <strong>{tasks.length}</strong>
            </div>
            <div>
              <span style={{ color: '#666' }}>运行中：</span>
              <Badge count={tasks.filter(t => t.status === 'running').length} />
            </div>
            <div>
              <span style={{ color: '#666' }}>已完成：</span>
              <Badge count={tasks.filter(t => t.status === 'completed').length} style={{ backgroundColor: '#52c41a' }} />
            </div>
            <div>
              <span style={{ color: '#666' }}>失败：</span>
              <Badge count={tasks.filter(t => t.status === 'failed').length} style={{ backgroundColor: '#ff4d4f' }} />
            </div>
          </Space>
        </div>

        {/* 任务列表表格 */}
        <Table
          columns={columns}
          dataSource={tasks}
          loading={loading}
          rowKey="id"
          scroll={{ x: 1600 }}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条记录`,
            onChange: (page, pageSize) => {
              fetchTasks(page, pageSize);
            }
          }}
          rowClassName={(record) => {
            if (record.status === 'failed') return 'task-row-failed';
            if (record.status === 'completed') return 'task-row-completed';
            if (record.status === 'running') return 'task-row-running';
            return '';
          }}
        />
      </Card>

      <style>{`
        .task-row-running {
          background-color: #e6f7ff;
        }
        .task-row-completed {
          background-color: #f6ffed;
        }
        .task-row-failed {
          background-color: #fff1f0;
        }
      `}</style>
    </div>
  );
};

export default ContractReviewHistory;
