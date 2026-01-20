// frontend/src/components/ReportResultsDisplay.tsx
import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Typography,
  Space,
  Tag,
  Alert,
  Divider,
  Collapse,
  Statistic,
  Timeline,
  Button,
  Tooltip,
  Progress,
  Tabs
} from 'antd';
import {
  FileTextOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  BulbOutlined,
  ThunderboltOutlined,
  DownloadOutlined,
  EyeOutlined
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';

const { Text, Paragraph, Title } = Typography;
const { Panel } = Collapse;
const { TabPane } = Tabs;

// 风险项
export interface RiskItem {
  risk_id: string;
  risk_title: string;
  risk_level: 'high' | 'medium' | 'low';
  description: string;
  sources?: string[]; // 哪些模型发现此风险
  confidence: number;
  details?: string;
  suggestions?: string;  // ✅ 新增：应对策略/建议
}

// 应对策略
export interface Strategy {
  strategy_id: string;
  title: string;
  description: string;
  priority: 'immediate' | 'short' | 'long';
  actions: string[];
}

// 风险分布
export interface RiskDistribution {
  high: number;
  medium: number;
  low: number;
}

// 风险分析报告
export interface RiskAnalysisReport {
  executive_summary: string;
  risk_items: RiskItem[];
  risk_distribution: RiskDistribution;
  strategies: Strategy[];
  recommendations: string[];
  analysis_metadata?: {
    package_used?: string;
    models_used?: string[];
    selected_model?: string;
    analysis_duration?: number;
    document_count?: number;
  };
}

interface ReportResultsDisplayProps {
  report: RiskAnalysisReport;
  showMetadata?: boolean;
  onDownload?: () => void;
}

const ReportResultsDisplay: React.FC<ReportResultsDisplayProps> = ({
  report,
  showMetadata = true,
  onDownload
}) => {
  const [expandedRisks, setExpandedRisks] = useState<string[]>([]);

  // 获取风险等级配置
  const getRiskConfig = (level: 'high' | 'medium' | 'low') => {
    const configs = {
      high: { color: 'error', icon: <CloseCircleOutlined />, label: '高风险', progressColor: '#ff4d4f' },
      medium: { color: 'warning', icon: <WarningOutlined />, label: '中风险', progressColor: '#faad14' },
      low: { color: 'success', icon: <CheckCircleOutlined />, label: '低风险', progressColor: '#52c41a' }
    };
    return configs[level];
  };

  // 获取策略优先级配置
  const getPriorityConfig = (priority: 'immediate' | 'short' | 'long') => {
    const configs = {
      immediate: { color: 'red', label: '立即执行', icon: <ThunderboltOutlined /> },
      short: { color: 'orange', label: '短期', icon: <BulbOutlined /> },
      long: { color: 'blue', label: '长期', icon: <InfoCircleOutlined /> }
    };
    return configs[priority];
  };

  // 计算总体风险分数
  const calculateRiskScore = () => {
    const weights = { high: 10, medium: 5, low: 1 };
    const totalScore =
      report.risk_distribution.high * weights.high +
      report.risk_distribution.medium * weights.medium +
      report.risk_distribution.low * weights.low;

    const totalRisks =
      report.risk_distribution.high +
      report.risk_distribution.medium +
      report.risk_distribution.low;

    if (totalRisks === 0) return 0;

    const avgScore = totalScore / totalRisks;
    return Math.round((avgScore / 10) * 100);
  };

  // 渲染风险分布图表
  const renderRiskDistribution = () => {
    const total =
      report.risk_distribution.high +
      report.risk_distribution.medium +
      report.risk_distribution.low;

    if (total === 0) {
      return <Alert message="未发现风险" type="success" showIcon />;
    }

    const highPercent = (report.risk_distribution.high / total) * 100;
    const mediumPercent = (report.risk_distribution.medium / total) * 100;
    const lowPercent = (report.risk_distribution.low / total) * 100;

    return (
      <Row gutter={16}>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title={<Text type="danger">高风险</Text>}
              value={report.risk_distribution.high}
              suffix={`/ ${total}`}
              valueStyle={{ color: '#cf1322' }}
            />
            <Progress
              percent={highPercent}
              strokeColor="#ff4d4f"
              showInfo={false}
              size="small"
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title={<Text type="warning">中风险</Text>}
              value={report.risk_distribution.medium}
              suffix={`/ ${total}`}
              valueStyle={{ color: '#fa8c16' }}
            />
            <Progress
              percent={mediumPercent}
              strokeColor="#faad14"
              showInfo={false}
              size="small"
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title={<Text type="success">低风险</Text>}
              value={report.risk_distribution.low}
              suffix={`/ ${total}`}
              valueStyle={{ color: '#52c41a' }}
            />
            <Progress
              percent={lowPercent}
              strokeColor="#52c41a"
              showInfo={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    );
  };

  // 渲染风险项列表
  const renderRiskItems = () => {
    if (report.risk_items.length === 0) {
      return <Alert message="未发现风险项" type="success" showIcon />;
    }

    return (
      <Collapse
        activeKey={expandedRisks}
        onChange={(keys) => setExpandedRisks(keys as string[])}
        accordion
      >
        {report.risk_items.map((risk) => {
          const config = getRiskConfig(risk.risk_level);

          return (
            <Panel
              header={
                <Space>
                  {config.icon}
                  <Text strong>{risk.risk_title}</Text>
                  <Tag color={config.color}>{config.label}</Tag>
                  <Tag>置信度: {(risk.confidence * 100).toFixed(0)}%</Tag>
                  {risk.sources && risk.sources.length > 0 && (
                    <Tooltip title={`发现模型: ${risk.sources.join(', ')}`}>
                      <Tag color="blue">{risk.sources.length} 个模型</Tag>
                    </Tooltip>
                  )}
                </Space>
              }
              key={risk.risk_id}
              extra={
                <Button
                  type="text"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                  }}
                >
                  详情
                </Button>
              }
            >
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <div>
                  <Text strong>风险描述：</Text>
                  <Paragraph>{risk.description}</Paragraph>
                </div>

                {risk.details && (
                  <div>
                    <Text strong>详细说明：</Text>
                    <Paragraph>{risk.details}</Paragraph>
                  </div>
                )}

                {/* ✅ 新增：显示应对策略/建议 */}
                {risk.suggestions && (
                  <div>
                    <Text strong>应对策略/建议：</Text>
                    <Paragraph>{risk.suggestions}</Paragraph>
                  </div>
                )}

                <div>
                  <Space>
                    <Text type="secondary">置信度：</Text>
                    <Progress
                      percent={risk.confidence * 100}
                      size="small"
                      strokeColor={config.progressColor}
                      style={{ width: 100 }}
                    />
                  </Space>
                </div>
              </Space>
            </Panel>
          );
        })}
      </Collapse>
    );
  };

  // 渲染应对策略
  const renderStrategies = () => {
    if (report.strategies.length === 0) {
      return <Alert message="暂无应对策略" type="info" showIcon />;
    }

    return (
      <Timeline mode="left">
        {report.strategies.map((strategy) => {
          const priorityConfig = getPriorityConfig(strategy.priority);

          return (
            <Timeline.Item
              key={strategy.strategy_id}
              color={priorityConfig.color}
              dot={priorityConfig.icon}
            >
              <Card size="small" style={{ marginBottom: 8 }}>
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Space>
                    <Tag color={priorityConfig.color}>{priorityConfig.label}</Tag>
                    <Text strong>{strategy.title}</Text>
                  </Space>

                  <Paragraph>{strategy.description}</Paragraph>

                  {strategy.actions.length > 0 && (
                    <div>
                      <Text strong>具体行动：</Text>
                      <ul style={{ marginTop: 8, paddingLeft: 16 }}>
                        {strategy.actions.map((action, idx) => (
                          <li key={idx}>
                            <Text>{action}</Text>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Space>
              </Card>
            </Timeline.Item>
          );
        })}
      </Timeline>
    );
  };

  // 渲染建议
  const renderRecommendations = () => {
    if (report.recommendations.length === 0) {
      return <Alert message="暂无建议" type="info" showIcon />;
    }

    return (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {report.recommendations.map((rec, idx) => (
          <Alert
            key={idx}
            message={
              <Space>
                <Tag color="blue">{idx + 1}</Tag>
                <Text>{rec}</Text>
              </Space>
            }
            type="info"
            showIcon
            icon={<BulbOutlined />}
          />
        ))}
      </Space>
    );
  };

  // 渲染元数据
  const renderMetadata = () => {
    if (!showMetadata || !report.analysis_metadata) return null;

    const metadata = report.analysis_metadata;

    return (
      <Card size="small" style={{ background: '#f5f5f5' }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space split={<Divider type="vertical" />}>
            {metadata.package_used && (
              <Text>规则包：<Tag>{metadata.package_used}</Tag></Text>
            )}
            {metadata.models_used && (
              <Text>
                模型：
                {metadata.models_used.map(m => (
                  <Tag key={m} color="blue">{m}</Tag>
                ))}
              </Text>
            )}
            {metadata.selected_model && (
              <Text>
                最终选择：<Tag color="gold">{metadata.selected_model}</Tag>
              </Text>
            )}
            {metadata.analysis_duration && (
              <Text>
                耗时：<Tag>{(metadata.analysis_duration / 1000).toFixed(2)}s</Tag>
              </Text>
            )}
            {metadata.document_count && (
              <Text>
                文档数：<Tag>{metadata.document_count}</Tag>
              </Text>
            )}
          </Space>
        </Space>
      </Card>
    );
  };

  const riskScore = calculateRiskScore();

  return (
    <div>
      {/* 头部：执行摘要和总体风险分数 */}
      <Card
        title={
          <Space>
            <FileTextOutlined />
            <Title level={4} style={{ margin: 0 }}>风险评估报告</Title>
          </Space>
        }
        extra={
          onDownload && (
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={onDownload}
            >
              下载报告
            </Button>
          )
        }
        style={{ marginBottom: 16 }}
      >
        {/* 元数据 */}
        {renderMetadata()}

        <Divider />

        {/* 总体风险分数 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="总体风险分数"
                value={riskScore}
                suffix="/ 100"
                valueStyle={{
                  color: riskScore >= 70 ? '#cf1322' : riskScore >= 40 ? '#fa8c16' : '#52c41a'
                }}
              />
            </Card>
          </Col>
          <Col span={18}>
            <div>
              <Text strong>执行摘要：</Text>
              <Paragraph>{report.executive_summary}</Paragraph>
            </div>
          </Col>
        </Row>

        {/* 风险分布 */}
        <div>
          <Title level={5}>风险分布</Title>
          {renderRiskDistribution()}
        </div>
      </Card>

      {/* 详细内容 */}
      <Card>
        <Tabs defaultActiveKey="risks">
          <TabPane
            tab={
              <Space>
                <WarningOutlined />
                风险项 ({report.risk_items.length})
              </Space>
            }
            key="risks"
          >
            {renderRiskItems()}
          </TabPane>

          <TabPane
            tab={
              <Space>
                <ThunderboltOutlined />
                应对策略 ({report.strategies.length})
              </Space>
            }
            key="strategies"
          >
            {renderStrategies()}
          </TabPane>

          <TabPane
            tab={
              <Space>
                <BulbOutlined />
                建议 ({report.recommendations.length})
              </Space>
            }
            key="recommendations"
          >
            {renderRecommendations()}
          </TabPane>

          <TabPane
            tab={
              <Space>
                <FileTextOutlined />
                完整报告
              </Space>
            }
            key="full"
          >
            <div style={{ padding: 16, background: '#f5f5f5', borderRadius: 4 }}>
              <ReactMarkdown>{report.executive_summary}</ReactMarkdown>
            </div>
          </TabPane>
        </Tabs>
      </Card>
    </div>
  );
};

export default ReportResultsDisplay;
