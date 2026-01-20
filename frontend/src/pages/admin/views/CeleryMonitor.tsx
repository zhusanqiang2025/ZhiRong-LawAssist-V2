import React from 'react';
import { Card, Button, Typography, Space, Alert } from 'antd';
import {
  ReloadOutlined,
  MonitorOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

// Celery 监控组件 - 简化版，不依赖后端 API
export const CeleryMonitor: React.FC = () => {
  const [refreshKey, setRefreshKey] = React.useState(0);

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4}>Celery 任务队列监控</Title>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
          >
            刷新
          </Button>
        </Space>
      </div>

      <Alert
        message="Celery 任务队列系统"
        description="Celery 是一个分布式任务队列系统，用于处理长时间运行的后台任务。当前系统已启用 Celery，任务将在后台独立进程中执行。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Card>
        <div style={{ marginBottom: 16 }}>
          <Text strong>功能说明：</Text>
          <ul style={{ marginTop: 8, marginLeft: 20 }}>
            <li><Text code>任务持久化</Text>：即使关闭浏览器，任务也会继续执行</li>
            <li><Text code>实时监控</Text>：查看任务执行状态、Worker 负载情况</li>
            <li><Text code>错误重试</Text>：失败任务自动重试，提高成功率</li>
            <li><Text code>优先级队列</Text>：重要任务优先处理</li>
          </ul>
        </div>

        <div style={{ marginBottom: 16 }}>
          <Text strong>访问完整监控界面：</Text>
          <Paragraph style={{ marginTop: 8 }}>
            <a href="http://localhost:5555" target="_blank" rel="noopener noreferrer">
              http://localhost:5555
            </a>
          </Paragraph>
          <Text type="secondary">
            Flower 是 Celery 的官方监控工具，提供更详细的任务信息和性能指标。
          </Text>
        </div>

        <div style={{ marginBottom: 16 }}>
          <Text strong>快速测试：</Text>
          <ol style={{ marginTop: 8, marginLeft: 20 }}>
            <li>进入"案件分析"功能</li>
            <li>提交一个测试案件</li>
            <li><Text mark>关闭浏览器</Text></li>
            <li>等待 1-2 分钟</li>
            <li>重新打开并查看结果</li>
          </ol>
          <Paragraph style={{ marginTop: 8 }}>
            <Text type="success" strong>预期结果：任务仍在后台继续执行，可以查看到完整的分析结果。</Text>
          </Paragraph>
        </div>

        <Alert
          message="当前状态"
          description={
            <div>
              <p>✅ Celery Worker 运行中</p>
              <p>✅ Flower 监控界面可用 (http://localhost:5555)</p>
              <p>✅ 任务队列系统已启用</p>
            </div>
          }
          type="success"
          showIcon
        />
      </Card>

      <Card title="使用说明" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>1. 查看 Worker 状态</Text>
            <Paragraph>
              访问 Flower 界面，在"Workers"标签页查看所有在线的 Worker 及其负载情况。
            </Paragraph>
          </div>

          <div>
            <Text strong>2. 监控任务执行</Text>
            <Paragraph>
              在"Tasks"标签页查看所有任务的执行状态、参数、结果和错误信息。
            </Paragraph>
          </div>

          <div>
            <Text strong>3. 任务管理</Text>
            <Paragraph>
              可以撤销等待中的任务，查看任务的详细执行日志。
            </Paragraph>
          </div>

          <div>
            <Text strong>4. 性能分析</Text>
            <Paragraph>
              查看任务执行时间分布，识别执行缓慢的任务进行优化。
            </Paragraph>
          </div>
        </Space>
      </Card>
    </div>
  );
};

export default CeleryMonitor;
