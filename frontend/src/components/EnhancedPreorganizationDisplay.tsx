// frontend/src/components/EnhancedPreorganizationDisplay.tsx
/**
 * 增强型预整理结果展示组件
 *
 * 展示：
 * 1. 文档列表及其详细信息
 * 2. 文档关系分析
 * 3. 主体诉求对比
 * 4. 合同信息与双方关系基础
 * 5. 争议识别结果
 */

import React from 'react';
import { Card, Descriptions, Tag, Space, Typography, Divider, Row, Col, Alert, Timeline } from 'antd';
import {
  FileTextOutlined,
  UserOutlined,
  LinkOutlined,
  FileSearchOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  ArrowRightOutlined,
  SwapRightOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

interface DocumentInfo {
  file_path: string;
  file_name: string;
  category: string;  // 标准分类枚举值
  confidence: number;  // 分类置信度
  summary: string;
  sender?: string;
  recipient?: string;
  sender_role?: string;  // 标准角色枚举值
  recipient_role?: string;
  date?: string;
  key_dates: string[];
  classification_reasoning?: string;  // 分类理由
  key_points?: string[];  // 关键要点
}

interface Relationship {
  doc1_name: string;
  doc2_name: string;
  relationship_type: string;
  temporal_order?: string;
  reasoning: string;
}

interface PartyDemand {
  party: string;
  role: string;
  demands: string[];
  legal_basis: string[];
  position: string;
}

interface ContractReference {
  contract_name?: string;
  contract_date?: string;
  contract_parties: string[];
  contract_status: string;
}

interface EnhancedAnalysisData {
  documents: DocumentInfo[];
  relationships: Relationship[];
  relationship_summary: string;
  party_demands: PartyDemand[];
  demand_summary: string;
  contract_references: ContractReference[];
  contract_stage: string;
  relationship_basis: string;
  has_dispute: boolean;
  dispute_summary?: string;
}

interface EnhancedPreorganizationDisplayProps {
  enhancedAnalysis: EnhancedAnalysisData;
}

const EnhancedPreorganizationDisplay: React.FC<EnhancedPreorganizationDisplayProps> = ({
  enhancedAnalysis
}) => {
  const {
    documents,
    relationships,
    relationship_summary,
    party_demands,
    demand_summary,
    contract_references,
    contract_stage,
    relationship_basis,
    has_dispute,
    dispute_summary
  } = enhancedAnalysis;

  // 获取关系类型标签颜色
  const getRelationshipTypeColor = (type: string) => {
    const colorMap: Record<string, string> = {
      '来往函件': 'blue',
      '补充协议': 'green',
      '修订协议': 'orange',
      '相关文件': 'cyan',
      '争议文件': 'red'
    };
    return colorMap[type] || 'default';
  };

  // 获取合同状态标签颜色
  const getContractStageColor = (stage: string) => {
    const colorMap: Record<string, string> = {
      '合作意向': 'blue',
      '已签署合同': 'green',
      '履行中': 'cyan',
      '违约争议': 'red',
      '终止合作': 'orange'
    };
    return colorMap[stage] || 'default';
  };

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>

        {/* ==================== 1. 文档列表 ==================== */}
        <Card
          title={
            <Space>
              <FileTextOutlined />
              <span>文档列表与内容摘要</span>
              <Tag color="blue">{documents.length} 个文档</Tag>
            </Space>
          }
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {documents.map((doc, index) => (
              <Card
                key={doc.file_path}
                type="inner"
                size="small"
                headStyle={{ background: '#fafafa' }}
                title={
                  <Space>
                    <Tag color="blue">#{index + 1}</Tag>
                    <Text strong>{doc.file_name}</Text>
                    <Tag color="geekblue">{doc.category}</Tag>
                    <Tag color={
                      doc.confidence >= 0.9 ? 'green' :
                      doc.confidence >= 0.7 ? 'blue' :
                      doc.confidence >= 0.5 ? 'orange' : 'red'
                    }>
                      置信度: {(doc.confidence * 100).toFixed(0)}%
                    </Tag>
                  </Space>
                }
              >
                <Descriptions column={2} size="small" bordered>
                  {doc.sender && (
                    <Descriptions.Item label="发函方/发件方">
                      <Space>
                        <UserOutlined />
                        {doc.sender}
                        {doc.sender_role && <Tag color="blue">{doc.sender_role}</Tag>}
                      </Space>
                    </Descriptions.Item>
                  )}
                  {doc.recipient && (
                    <Descriptions.Item label="收函方/收件方">
                      <Space>
                        <UserOutlined />
                        {doc.recipient}
                        {doc.recipient_role && <Tag color="cyan">{doc.recipient_role}</Tag>}
                      </Space>
                    </Descriptions.Item>
                  )}
                  {doc.date && (
                    <Descriptions.Item label="文档日期">
                      <Tag icon={<FileTextOutlined />} color="purple">{doc.date}</Tag>
                    </Descriptions.Item>
                  )}
                  {doc.key_dates && doc.key_dates.length > 0 && (
                    <Descriptions.Item label="关键日期" span={2}>
                      <Space wrap>
                        {doc.key_dates.map((date, i) => (
                          <Tag key={i} color="purple">{date}</Tag>
                        ))}
                      </Space>
                    </Descriptions.Item>
                  )}
                  {doc.classification_reasoning && (
                    <Descriptions.Item label="分类理由" span={2}>
                      <Text type="secondary">{doc.classification_reasoning}</Text>
                    </Descriptions.Item>
                  )}
                </Descriptions>
                <Divider orientation="left" plain>内容摘要</Divider>
                <Paragraph>{doc.summary}</Paragraph>
                {doc.key_points && doc.key_points.length > 0 && (
                  <>
                    <Divider orientation="left" plain>关键要点</Divider>
                    <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                      {doc.key_points.map((point, i) => (
                        <li key={i}>{point}</li>
                      ))}
                    </ul>
                  </>
                )}
              </Card>
            ))}
          </Space>
        </Card>

        {/* ==================== 2. 文档关系分析 ==================== */}
        {relationships.length > 0 && (
          <Card
            title={
              <Space>
                <LinkOutlined />
                <span>文档关系分析</span>
                <Tag color="cyan">{relationships.length} 个关系</Tag>
              </Space>
            }
          >
            <Alert
              message={relationship_summary}
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />

            <Timeline
              items={relationships.map((rel, index) => ({
                dot: rel.temporal_order ? <SwapRightOutlined /> : <LinkOutlined />,
                color: getRelationshipTypeColor(rel.relationship_type),
                children: (
                  <Card key={index} size="small" style={{ marginBottom: 8 }}>
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Space>
                        <Text strong>{rel.doc1_name}</Text>
                        {rel.temporal_order && (
                          <Space>
                            <ArrowRightOutlined />
                            <Text>{rel.temporal_order}</Text>
                            <ArrowRightOutlined />
                          </Space>
                        )}
                        {rel.temporal_order ? (
                          <Text strong>{rel.doc2_name}</Text>
                        ) : (
                          <>
                            <SwapRightOutlined />
                            <Text strong>{rel.doc2_name}</Text>
                          </>
                        )}
                        <Tag color={getRelationshipTypeColor(rel.relationship_type)}>
                          {rel.relationship_type}
                        </Tag>
                      </Space>
                      <Text type="secondary">{rel.reasoning}</Text>
                    </Space>
                  </Card>
                )
              }))}
            />
          </Card>
        )}

        {/* ==================== 3. 主体诉求对比 ==================== */}
        {party_demands.length > 0 && (
          <Card
            title={
              <Space>
                <UserOutlined />
                <span>主体诉求分析</span>
                <Tag color="orange">{party_demands.length} 个主体</Tag>
              </Space>
            }
          >
            <Alert
              message={demand_summary}
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />

            <Row gutter={[16, 16]}>
              {party_demands.map((demand, index) => (
                <Col key={index} xs={24} md={12}>
                  <Card
                    size="small"
                    title={
                      <Space>
                        <UserOutlined />
                        <Text strong>{demand.party}</Text>
                        <Tag color="blue">{demand.role}</Tag>
                      </Space>
                    }
                    headStyle={{ background: index % 2 === 0 ? '#e6f7ff' : '#fff7e6' }}
                  >
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <div>
                        <Text strong>立场：</Text>
                        <Paragraph>{demand.position}</Paragraph>
                      </div>

                      <div>
                        <Text strong>诉求：</Text>
                        <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                          {demand.demands.map((d, i) => (
                            <li key={i}>{d}</li>
                          ))}
                        </ul>
                      </div>

                      {demand.legal_basis && demand.legal_basis.length > 0 && (
                        <div>
                          <Text strong>法律依据：</Text>
                          <Space wrap style={{ marginTop: 8 }}>
                            {demand.legal_basis.map((basis, i) => (
                              <Tag key={i} color="green" icon={<CheckCircleOutlined />}>
                                {basis}
                              </Tag>
                            ))}
                          </Space>
                        </div>
                      )}
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        )}

        {/* ==================== 4. 合同信息与双方关系基础 ==================== */}
        <Card
          title={
            <Space>
              <FileSearchOutlined />
              <span>合同信息与双方关系基础</span>
            </Space>
          }
        >
          <Descriptions column={1} bordered size="middle">
            <Descriptions.Item label="双方关系基础">
              <Tag color="blue" style={{ fontSize: 14 }}>
                {relationship_basis}
              </Tag>
            </Descriptions.Item>

            <Descriptions.Item label="当前合作阶段">
              <Tag color={getContractStageColor(contract_stage)} style={{ fontSize: 14 }}>
                {contract_stage}
              </Tag>
            </Descriptions.Item>

            {contract_references && contract_references.length > 0 && (
              <Descriptions.Item label="相关合同/协议">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  {contract_references.map((ref, index) => (
                    <Card key={index} size="small">
                      <Descriptions column={2} size="small">
                        {ref.contract_name && (
                          <Descriptions.Item label="合同名称" span={2}>
                            <Text strong>{ref.contract_name}</Text>
                          </Descriptions.Item>
                        )}
                        {ref.contract_date && (
                          <Descriptions.Item label="签署日期">
                            {ref.contract_date}
                          </Descriptions.Item>
                        )}
                        <Descriptions.Item label="合同状态">
                          <Tag color={getContractStageColor(ref.contract_status)}>
                            {ref.contract_status}
                          </Tag>
                        </Descriptions.Item>
                        {ref.contract_parties && ref.contract_parties.length > 0 && (
                          <Descriptions.Item label="合同各方" span={2}>
                            <Space wrap>
                              {ref.contract_parties.map((party, i) => (
                                <Tag key={i} color="purple">{party}</Tag>
                              ))}
                            </Space>
                          </Descriptions.Item>
                        )}
                      </Descriptions>
                    </Card>
                  ))}
                </Space>
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>

        {/* ==================== 5. 争议识别 ==================== */}
        {has_dispute && dispute_summary && (
          <Alert
            message="识别到争议"
            description={
              <Space direction="vertical" size="small">
                <Text>{dispute_summary}</Text>
                <Text type="secondary">
                  建议在后续风险评估中重点关注争议点，评估各方的法律风险和应对策略。
                </Text>
              </Space>
            }
            type="warning"
            icon={<AlertOutlined />}
            closable
          />
        )}

        {!has_dispute && (
          <Alert
            message="未识别到明显争议"
            description="根据文档分析，各方诉求相对一致，暂未识别到明显争议。"
            type="success"
            icon={<CheckCircleOutlined />}
          />
        )}

      </Space>
    </div>
  );
};

export default EnhancedPreorganizationDisplay;
