/**
 * 合同规划结果展示组件
 *
 * 展示多模型或单模型生成的合同规划结果
 * 包括：合同列表、签署顺序、关联关系、风险提示等
 */

import React from 'react';
import { Card, Timeline, Tag, Space, Typography, Alert, Divider, Steps } from 'antd';
import {
  FileTextOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  LinkOutlined,
  RocketOutlined
} from '@ant-design/icons';
import type { PlannedContract, ContractPlanningResult } from '../types/planning';

const { Text, Paragraph, Title } = Typography;

interface PlanningResultDisplayProps {
  result: ContractPlanningResult;
  onContinue?: () => void;
}

const PlanningResultDisplay: React.FC<PlanningResultDisplayProps> = ({ result, onContinue }) => {
  const { analysis_result } = result;
  const { contracts, signing_order, relationships, risk_notes, overall_description, planning_mode } = analysis_result;

  // 获取模式标签颜色
  const getModeTagColor = () => {
    return planning_mode === 'multi_model' ? 'gold' : 'blue';
  };

  // 获取模式标签文本
  const getModeTagText = () => {
    return planning_mode === 'multi_model' ? '多模型综合融合' : '单模型快速生成';
  };

  return (
    <div className="planning-result-display">
      {/* 头部信息 */}
      <Card className="result-header">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <RocketOutlined style={{ fontSize: 24, color: '#1890ff' }} />
            <Title level={3} style={{ margin: 0 }}>
              合同规划完成
            </Title>
            <Tag color={getModeTagColor()}>{getModeTagText()}</Tag>
          </Space>

          <Paragraph type="secondary">
            {overall_description}
          </Paragraph>

          <Space>
            <Text strong>合同数量：</Text>
            <Text>{analysis_result.total_estimated_contracts} 份</Text>
          </Space>
        </Space>
      </Card>

      {/* 规划的合同列表 */}
      <Card title="规划合同清单" className="contracts-list">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {contracts.map((contract, index) => (
            <Card
              key={contract.id}
              size="small"
              className="contract-item"
              hoverable
            >
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space>
                  <Tag color="blue">{index + 1}</Tag>
                  <Text strong>{contract.title}</Text>
                  <Tag>{contract.contract_type}</Tag>
                  <Tag color="geekblue">优先级：{contract.priority}</Tag>
                </Space>
                <Paragraph type="secondary" style={{ margin: 0 }}>
                  {contract.purpose}
                </Paragraph>
              </Space>
            </Card>
          ))}
        </Space>
      </Card>

      {/* 签署顺序 */}
      <Card title="建议签署顺序" className="signing-order">
        <Steps
          direction="vertical"
          current={-1}
          items={signing_order.map((contractId, index) => {
            const contract = contracts.find(c => c.id === contractId);
            return {
              title: contract?.title || contractId,
              description: contract?.purpose || '',
              icon: <FileTextOutlined />,
              status: 'finish'
            };
          })}
        />
      </Card>

      {/* 合同关联关系 */}
      {Object.keys(relationships).length > 0 && (
        <Card title="合同关联关系" className="relationships">
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {Object.entries(relationships).map(([contractId, relations]) => {
              const contract = contracts.find(c => c.id === contractId);
              return (
                <div key={contractId}>
                  <Space>
                    <LinkOutlined />
                    <Text strong>{contract?.title || contractId}</Text>
                  </Space>
                  <div style={{ marginLeft: 24, marginTop: 8 }}>
                    {relations.map((relation, idx) => (
                      <div key={idx} style={{ color: '#666' }}>
                        • {relation}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </Space>
        </Card>
      )}

      {/* 风险提示 */}
      {risk_notes.length > 0 && (
        <Card>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space>
              <WarningOutlined style={{ color: '#faad14' }} />
              <Text strong>风险提示</Text>
            </Space>
            <Alert
              message="请特别注意以下风险点"
              description={
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {risk_notes.map((note, index) => (
                    <li key={index}>{note}</li>
                  ))}
                </ul>
              }
              type="warning"
              showIcon
            />
          </Space>
        </Card>
      )}

      {/* 操作提示 */}
      <Alert
        message="下一步操作"
        description="您可以查看规划结果，确认后可以继续生成具体合同内容，或调整需求重新规划。"
        type="info"
        showIcon
        style={{ marginTop: 16 }}
      />
    </div>
  );
};

export default PlanningResultDisplay;
