// frontend/src/components/MultiModelComparison.tsx
import React, { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Progress,
  Tag,
  Typography,
  Space,
  Alert,
  Divider,
  Timeline,
  Button,
  Collapse,
  Statistic,
  Rate,
  Badge
} from 'antd';
import {
  CheckCircleOutlined,
  SyncOutlined,
  RobotOutlined,
  TrophyOutlined,
  ClockCircleOutlined,
  EyeOutlined
} from '@ant-design/icons';

const { Text, Paragraph, Title } = Typography;
const { Panel } = Collapse;

// 模型类型
export type ModelType = 'deepseek' | 'qwen' | 'chatgpt';

// 模型状态
export type ModelStatus = 'pending' | 'analyzing' | 'completed' | 'failed';

// 单个模型的分析结果
export interface ModelAnalysisResult {
  model: ModelType;
  status: ModelStatus;
  progress: number;
  startTime?: number;
  endTime?: number;
  duration?: number; // 毫秒
  result?: {
    risk_items: number;
    high_risks: number;
    medium_risks: number;
    low_risks: number;
    confidence: number;
    strategies: number;
    recommendations: number;
    summary: string;
  };
  error?: string;
}

// 多模型对比结果
export interface MultiModelComparisonResult {
  models: {
    deepseek: ModelAnalysisResult;
    qwen: ModelAnalysisResult;
    chatgpt: ModelAnalysisResult;
  };
  selected: ModelType | null;
  comparison: {
    fastest: ModelType;
    most_comprehensive: ModelType; // 风险点数量最多
    highest_confidence: ModelType; // 置信度最高
    consensus: number; // 一致性评分（0-100）
  };
}

interface MultiModelComparisonProps {
  data?: MultiModelComparisonResult;
  selectedResult?: ModelType;
  onSelectResult?: (model: ModelType) => void;
}

const MODEL_INFO: Record<ModelType, { name: string; color: string; icon: string }> = {
  deepseek: { name: 'DeepSeek', color: '#1890ff', icon: '🔬' },
  qwen: { name: 'Qwen', color: '#52c41a', icon: '🌟' },
  chatgpt: { name: 'ChatGPT', color: '#fa8c16', icon: '🤖' }
};

const MultiModelComparison: React.FC<MultiModelComparisonProps> = ({
  data,
  selectedResult,
  onSelectResult
}) => {
  const [expandedResults, setExpandedResults] = useState<ModelType[]>([]);

  // 获取整体进度
  const getOverallProgress = () => {
    if (!data) return 0;
    const models = Object.values(data.models);
    const totalProgress = models.reduce((sum, m) => sum + m.progress, 0);
    return Math.round(totalProgress / models.length);
  };

  // 获取整体状态
  const getOverallStatus = () => {
    if (!data) return 'pending';
    const models = Object.values(data.models);
    const allCompleted = models.every(m => m.status === 'completed' || m.status === 'failed');
    const anyAnalyzing = models.some(m => m.status === 'analyzing');

    if (allCompleted) return 'completed';
    if (anyAnalyzing) return 'analyzing';
    return 'pending';
  };

  // 格式化持续时间
  const formatDuration = (ms?: number) => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  // 渲染模型卡片
  const renderModelCard = (modelType: ModelType, modelData: ModelAnalysisResult) => {
    const info = MODEL_INFO[modelType];
    const isAnalyzing = modelData.status === 'analyzing';
    const isCompleted = modelData.status === 'completed';
    const isFailed = modelData.status === 'failed';
    const isSelected = selectedResult === modelType;
    const isBest = data?.comparison && (
      data.comparison.fastest === modelType ||
      data.comparison.most_comprehensive === modelType ||
      data.comparison.highest_confidence === modelType
    );

    return (
      <Badge.Ribbon
        key={modelType}
        text={
          isBest ? (
            <Space>
              <TrophyOutlined />
              最优
            </Space>
          ) : isSelected ? (
            <Space>
              <CheckCircleOutlined />
              已选中
            </Space>
          ) : undefined
        }
        color={isSelected ? 'gold' : isBest ? 'cyan' : undefined}
      >
        <Card
          style={{
            marginBottom: 16,
            border: isSelected ? '2px solid #faad14' : undefined,
            position: 'relative',
            overflow: 'hidden'
          }}
          extra={
            onSelectResult && isCompleted ? (
              <Button
                type={isSelected ? 'primary' : 'default'}
                size="small"
                icon={isSelected ? <CheckCircleOutlined /> : <EyeOutlined />}
                onClick={() => onSelectResult(modelType)}
              >
                {isSelected ? '已选' : '选择此结果'}
              </Button>
            ) : undefined
          }
        >
          {/* 状态图标 */}
          <div style={{
            position: 'absolute',
            top: 16,
            right: 16,
            opacity: 0.1,
            fontSize: 48
          }}>
            {info.icon}
          </div>

          {/* 标题和状态 */}
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space>
              <Text strong style={{ fontSize: 16 }}>
                {info.icon} {info.name}
              </Text>
              {isAnalyzing && <SyncOutlined spin style={{ color: info.color }} />}
              {isCompleted && <CheckCircleOutlined style={{ color: '#52c41a' }} />}
              {isFailed && <Text type="danger">✗</Text>}

              <Tag color={isCompleted ? 'success' : isAnalyzing ? 'processing' : isFailed ? 'error' : 'default'}>
                {modelData.status === 'pending' && '等待中'}
                {modelData.status === 'analyzing' && '分析中'}
                {modelData.status === 'completed' && '已完成'}
                {modelData.status === 'failed' && '失败'}
              </Tag>
            </Space>

            {/* 进度条 */}
            {isAnalyzing && (
              <Progress
                percent={modelData.progress}
                status="active"
                strokeColor={info.color}
              />
            )}

            {/* 完成后的统计信息 */}
            {isCompleted && modelData.result && (
              <>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic
                      title="总风险点"
                      value={modelData.result.risk_items}
                      valueStyle={{ fontSize: 18, color: '#cf1322' }}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="置信度"
                      value={modelData.result.confidence * 100}
                      suffix="%"
                      valueStyle={{ fontSize: 18, color: '#52c41a' }}
                      precision={1}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="用时"
                      value={formatDuration(modelData.duration)}
                      valueStyle={{ fontSize: 16 }}
                    />
                  </Col>
                </Row>

                {/* 风险分布 */}
                <div style={{ marginTop: 8 }}>
                  <Space split={<Divider type="vertical" />}>
                    <Text type="danger">
                      高风险：{modelData.result.high_risks}
                    </Text>
                    <Text type="warning">
                      中风险：{modelData.result.medium_risks}
                    </Text>
                    <Text type="success">
                      低风险：{modelData.result.low_risks}
                    </Text>
                  </Space>
                </div>

                {/* 策略和建议 */}
                <Space split={<Divider type="vertical" />}>
                  <Text>策略：{modelData.result.strategies}</Text>
                  <Text>建议：{modelData.result.recommendations}</Text>
                </Space>
              </>
            )}

            {/* 失败信息 */}
            {isFailed && modelData.error && (
              <Alert
                message="分析失败"
                description={modelData.error}
                type="error"
                showIcon
              />
            )}
          </Space>

          {/* 详细结果折叠 */}
          {isCompleted && modelData.result && (
            <Collapse
              ghost
              size="small"
              style={{ marginTop: 12 }}
              activeKey={expandedResults.includes(modelType) ? modelType : undefined}
              onChange={(keys) => {
                const newExpanded = expandedResults.includes(modelType)
                  ? expandedResults.filter(m => m !== modelType)
                  : [...expandedResults, modelType];
                setExpandedResults(newExpanded);
              }}
            >
              <Panel header={<Text type="secondary">查看详细结果</Text>} key={modelType}>
                <div>
                  <Text strong>摘要：</Text>
                  <Paragraph>{modelData.result.summary}</Paragraph>
                </div>
              </Panel>
            </Collapse>
          )}
        </Card>
      </Badge.Ribbon>
    );
  };

  // 渲染对比摘要
  const renderComparisonSummary = () => {
    if (!data || !data.comparison) return null;

    const { comparison, selected } = data;

    return (
      <Card title={<Title level={5}>🏆 对比结果</Title>} style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="最快完成"
                value={MODEL_INFO[comparison.fastest].name}
                valueStyle={{ fontSize: 14, color: MODEL_INFO[comparison.fastest].color }}
                prefix={<ClockCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="最全面"
                value={MODEL_INFO[comparison.most_comprehensive].name}
                valueStyle={{ fontSize: 14, color: MODEL_INFO[comparison.most_comprehensive].color }}
                prefix={<RobotOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="最高置信度"
                value={MODEL_INFO[comparison.highest_confidence].name}
                valueStyle={{ fontSize: 14, color: MODEL_INFO[comparison.highest_confidence].color }}
                prefix={<TrophyOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="模型一致性"
                value={comparison.consensus}
                suffix="%"
                valueStyle={{ fontSize: 14 }}
                precision={0}
              />
            </Card>
          </Col>
        </Row>

        {selected && (
          <Alert
            message={
              <Space>
                <Text>已选择</Text>
                <Tag color="blue">{MODEL_INFO[selected].name}</Tag>
                <Text>的分析结果作为最终输出</Text>
              </Space>
            }
            type="info"
            showIcon
            style={{ marginTop: 12 }}
          />
        )}
      </Card>
    );
  };

  const overallStatus = getOverallStatus();
  const overallProgress = getOverallProgress();

  return (
    <div>
      {/* 整体进度 */}
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <Text strong>多模型并行分析</Text>
            {overallStatus === 'analyzing' && <SyncOutlined spin />}
            {overallStatus === 'completed' && <CheckCircleOutlined style={{ color: '#52c41a' }} />}
            <Tag color={overallStatus === 'completed' ? 'success' : overallStatus === 'analyzing' ? 'processing' : 'default'}>
              {overallStatus === 'pending' && '等待中'}
              {overallStatus === 'analyzing' && '分析中'}
              {overallStatus === 'completed' && '已完成'}
            </Tag>
          </Space>

          {overallStatus === 'analyzing' && (
            <Progress percent={overallProgress} status="active" />
          )}
        </Space>
      </Card>

      {/* 对比摘要 */}
      {renderComparisonSummary()}

      {/* 模型卡片 */}
      {data && (
        <Row gutter={16}>
          <Col span={24}>
            {Object.entries(data.models).map(([modelType, modelData]) =>
              renderModelCard(modelType as ModelType, modelData)
            )}
          </Col>
        </Row>
      )}
    </div>
  );
};

export default MultiModelComparison;
