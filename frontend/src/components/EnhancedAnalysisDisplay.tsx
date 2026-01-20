// frontend/src/components/EnhancedAnalysisDisplay.tsx
/**
 * 增强分析结果展示组件
 *
 * 展示后端 EnhancedDocumentAnalysisService 生成的数据：
 * - 交易全景（交易故事叙述、合同状态）
 * - 主体画像（各方的义务、权利、风险敞口）
 * - 时间线（关键事件的时间序列）
 * - 争议焦点（如有）
 * - 股权/投资架构图（如有）
 */

import React from 'react';
import { Card, Timeline, Tag, Descriptions, Space, Typography, Alert } from 'antd';
import {
  FileTextOutlined,
  UserOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';
import DiagramViewer from './DiagramViewer';

const { Text, Paragraph } = Typography;

interface PartyProfile {
  name: string;
  role: string;
  obligations: string[];
  rights: string[];
  risk_exposure: string;
}

interface TransactionTimeline {
  date: string;
  event: string;
  source_doc: string;
  type: string;
}

interface EnhancedAnalysisData {
  transaction_summary: string;
  contract_status: string;
  dispute_focus?: string;
  parties: PartyProfile[];
  timeline: TransactionTimeline[];
  doc_relationships?: any[];
  architecture_diagram?: any;  // 新增：架构图数据
}

interface Props {
  enhancedAnalysis: EnhancedAnalysisData;
}

const EnhancedAnalysisDisplay: React.FC<Props> = ({ enhancedAnalysis }) => {
  if (!enhancedAnalysis) {
    return null;
  }

  const getStatusColor = (status: string) => {
    const colorMap: Record<string, string> = {
      '磋商': 'blue',
      '履约': 'green',
      '违约': 'red',
      '终止': 'default'
    };
    return colorMap[status] || 'default';
  };

  const getTimelineColor = (type: string) => {
    const colorMap: Record<string, string> = {
      '签署': 'blue',
      '履行': 'green',
      '违约': 'red',
      '变更': 'orange'
    };
    return colorMap[type] || 'gray';
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* 1. 交易全景 */}
      {enhancedAnalysis.transaction_summary && (
        <Card
          title={
            <Space>
              <FileTextOutlined />
              <span>交易全景</span>
            </Space>
          }
        >
          <Paragraph>{enhancedAnalysis.transaction_summary}</Paragraph>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="合同状态">
              <Tag color={getStatusColor(enhancedAnalysis.contract_status)}>
                {enhancedAnalysis.contract_status}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {/* 2. 主体画像 */}
      {enhancedAnalysis.parties && enhancedAnalysis.parties.length > 0 && (
        <Card
          title={
            <Space>
              <UserOutlined />
              <span>主体画像</span>
            </Space>
          }
        >
          {enhancedAnalysis.parties.map((party, index) => (
            <Card
              key={index}
              type="inner"
              size="small"
              style={{ marginBottom: 16 }}
              title={
                <Space>
                  <Tag color="blue">{party.role}</Tag>
                  <Text strong>{party.name}</Text>
                </Space>
              }
            >
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="核心义务">
                  {party.obligations.map((obligation, i) => (
                    <Tag key={i} color="cyan" style={{ marginBottom: 4 }}>
                      {obligation}
                    </Tag>
                  ))}
                </Descriptions.Item>
                <Descriptions.Item label="核心权利">
                  {party.rights.map((right, i) => (
                    <Tag key={i} color="green" style={{ marginBottom: 4 }}>
                      {right}
                    </Tag>
                  ))}
                </Descriptions.Item>
                <Descriptions.Item label="风险敞口">
                  <Text type={party.risk_exposure.includes('高') ? 'danger' : 'secondary'}>
                    {party.risk_exposure}
                  </Text>
                </Descriptions.Item>
              </Descriptions>
            </Card>
          ))}
        </Card>
      )}

      {/* 3. 时间线 */}
      {enhancedAnalysis.timeline && enhancedAnalysis.timeline.length > 0 && (
        <Card
          title={
            <Space>
              <ClockCircleOutlined />
              <span>时间线</span>
            </Space>
          }
        >
          <Timeline>
            {enhancedAnalysis.timeline.map((item, index) => (
              <Timeline.Item
                key={index}
                color={getTimelineColor(item.type)}
                dot={<Tag color={getTimelineColor(item.type)}>{item.type}</Tag>}
              >
                <Space direction="vertical" size="small">
                  <Text strong>{item.date}</Text>
                  <Text>{item.event}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    来源: {item.source_doc}
                  </Text>
                </Space>
              </Timeline.Item>
            ))}
          </Timeline>
        </Card>
      )}

      {/* 4. 争议焦点 */}
      {enhancedAnalysis.dispute_focus && (
        <Alert
          message="争议焦点"
          description={enhancedAnalysis.dispute_focus}
          type="warning"
          showIcon
          icon={<WarningOutlined />}
        />
      )}

      {/* 5. 股权/投资架构图 */}
      {enhancedAnalysis.architecture_diagram && (
        <Card
          title={
            <Space>
              <ApartmentOutlined />
              <span>股权/投资架构图</span>
            </Space>
          }
        >
          <DiagramViewer
            diagramType={enhancedAnalysis.architecture_diagram.diagram_type}
            format={enhancedAnalysis.architecture_diagram.format}
            sourceCode={enhancedAnalysis.architecture_diagram.code}
          />
        </Card>
      )}
    </Space>
  );
};

export default EnhancedAnalysisDisplay;
