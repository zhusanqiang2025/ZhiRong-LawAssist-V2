import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Statistic, Typography, Spin, Alert, Space,
  Progress, Tag, Button, Divider
} from 'antd';
import {
  UserOutlined,
  TeamOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  ReloadOutlined,
  DownloadOutlined
} from '@ant-design/icons';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import api from '../../../api';

const { Title } = Typography;

interface DashboardStats {
  users: {
    total: number;
    active: number;
    admins: number;
    online: number;
  };
  tasks: {
    total: number;
    pending: number;
    in_progress: number;
    completed: number;
    failed: number;
    created_today: number;
    by_type: Record<string, number>;
    trend_7days: Array<{ date: string; count: number }>;
  };
  templates: {
    total: number;
    total_downloads: number;
  };
  timestamp: string;
}

// 图表颜色配置
const COLORS = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2'];

export const DashboardView: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setError(null);
    try {
      const response = await api.getSystemStats();
      setStats(response.data);
    } catch (err: any) {
      setError(err.message || '加载统计数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    // 每30秒自动刷新
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
        <p style={{ marginTop: 16 }}>加载统计数据...</p>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <Alert
        message="加载失败"
        description={error}
        type="error"
        showIcon
        action={
          <Button size="small" onClick={fetchStats}>
            重试
          </Button>
        }
      />
    );
  }

  if (!stats) return null;

  const taskCompletionRate = stats.tasks.total > 0
    ? Math.round((stats.tasks.completed / stats.tasks.total) * 100)
    : 0;

  // 任务类型饼图数据
  const taskTypeData = Object.entries(stats.tasks.by_type || {}).map(([type, count], index) => ({
    name: type || '未分类',
    value: count,
    color: COLORS[index % COLORS.length]
  }));

  // 7天趋势数据（格式化日期）
  const trendData = stats.tasks.trend_7days?.map(item => ({
    ...item,
    date: new Date(item.date).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  })) || [];

  return (
    <div>
      {/* 标题栏 */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>系统数据仪表盘</Title>
        <Button
          icon={<ReloadOutlined />}
          onClick={fetchStats}
          loading={loading}
        >
          刷新
        </Button>
      </div>

      {/* 用户统计卡片 */}
      <Card title={<><UserOutlined /> 用户统计</>} style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title="总用户数"
              value={stats.users.total}
              prefix={<UserOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title="活跃用户"
              value={stats.users.active}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title="在线用户"
              value={stats.users.online}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title="管理员"
              value={stats.users.admins}
              valueStyle={{ color: '#722ed1' }}
            />
          </Col>
        </Row>
      </Card>

      {/* 任务统计卡片 */}
      <Card title={<><FileTextOutlined /> 任务统计</>} style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={8} md={4}>
            <Statistic
              title="总任务"
              value={stats.tasks.total}
              valueStyle={{ fontSize: 24 }}
            />
          </Col>
          <Col xs={12} sm={8} md={4}>
            <Statistic
              title="已完成"
              value={stats.tasks.completed}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a', fontSize: 24 }}
            />
          </Col>
          <Col xs={12} sm={8} md={4}>
            <Statistic
              title="进行中"
              value={stats.tasks.in_progress}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#1890ff', fontSize: 24 }}
            />
          </Col>
          <Col xs={12} sm={8} md={4}>
            <Statistic
              title="待处理"
              value={stats.tasks.pending}
              valueStyle={{ color: '#faad14', fontSize: 24 }}
            />
          </Col>
          <Col xs={12} sm={8} md={4}>
            <Statistic
              title="失败"
              value={stats.tasks.failed}
              prefix={<ExclamationCircleOutlined />}
              valueStyle={{ color: '#f5222d', fontSize: 24 }}
            />
          </Col>
          <Col xs={12} sm={8} md={4}>
            <Statistic
              title="今日新增"
              value={stats.tasks.created_today}
              valueStyle={{ color: '#13c2c2', fontSize: 24 }}
            />
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          {/* 任务完成率 */}
          <Col xs={24} md={12}>
            <div style={{ textAlign: 'center' }}>
              <Progress
                type="circle"
                percent={taskCompletionRate}
                status={taskCompletionRate >= 80 ? 'success' : 'normal'}
                width={120}
              />
              <div style={{ marginTop: 12 }}>
                <Space>
                  <Tag color="green">已完成: {stats.tasks.completed}</Tag>
                  <Tag color="blue">进行中: {stats.tasks.in_progress}</Tag>
                  <Tag color="orange">待处理: {stats.tasks.pending}</Tag>
                </Space>
              </div>
            </div>
          </Col>

          {/* 模板统计 */}
          <Col xs={24} md={12}>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="模板总数"
                  value={stats.templates.total}
                  prefix={<FileTextOutlined />}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="下载总量"
                  value={stats.templates.total_downloads}
                  prefix={<DownloadOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
            </Row>
          </Col>
        </Row>
      </Card>

      {/* 图表区域 */}
      <Row gutter={[16, 16]}>
        {/* 7天任务趋势图 */}
        <Col xs={24} lg={14}>
          <Card title="近7天任务趋势" extra={<Tag color="blue">任务创建量</Tag>}>
            {trendData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#1890ff"
                    strokeWidth={2}
                    name="任务数"
                    dot={{ fill: '#1890ff', r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                暂无趋势数据
              </div>
            )}
          </Card>
        </Col>

        {/* 任务类型分布 */}
        <Col xs={24} lg={10}>
          <Card title="任务类型分布">
            {taskTypeData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={taskTypeData}
                    cx="50%"
                    cy="50%"
                    labelLine={true}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    dataKey="value"
                  >
                    {taskTypeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                暂无分类数据
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 任务状态柱状图 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card title="任务状态分布">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={[
                { name: '已完成', value: stats.tasks.completed, color: '#52c41a' },
                { name: '进行中', value: stats.tasks.in_progress, color: '#1890ff' },
                { name: '待处理', value: stats.tasks.pending, color: '#faad14' },
                { name: '失败', value: stats.tasks.failed, color: '#f5222d' }
              ]}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#1890ff">
                  {[{ color: '#52c41a' }, { color: '#1890ff' }, { color: '#faad14' }, { color: '#f5222d' }].map((c, i) => (
                    <Cell key={`cell-${i}`} fill={c.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* 最后更新时间 */}
      <div style={{ textAlign: 'center', color: '#999', fontSize: 12, marginTop: 24, marginBottom: 8 }}>
        最后更新: {new Date(stats.timestamp).toLocaleString('zh-CN')} · 每30秒自动刷新
      </div>
    </div>
  );
};

export default DashboardView;
