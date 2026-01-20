// frontend/src/components/ContractHealthAssessment.tsx
import React, { useEffect, useState } from 'react';
import { Card, Alert, Progress, Row, Col, Tag, Statistic } from 'antd';
import {
  HeartOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import api from '../api';
import './ContractHealthAssessment.css';

// 健康度评估数据接口
interface HealthAssessment {
  score: number;
  level: string;
  summary: string;
  risk_distribution: {
    Critical: number;
    High: number;
    Medium: number;
    Low: number;
  };
  total_risks: number;
  recommendations: string[];
}

interface Props {
  contractId: number;
}

const ContractHealthAssessment: React.FC<Props> = ({ contractId }) => {
  const [assessment, setAssessment] = useState<HealthAssessment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAssessment();
  }, [contractId]);

  const fetchAssessment = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getHealthAssessment(contractId);
      setAssessment(res.data);
    } catch (err: any) {
      console.error('获取健康度评估失败', err);
      setError(err.response?.data?.detail || '获取健康度评估失败');
    } finally {
      setLoading(false);
    }
  };

  // 获取风险等级颜色
  const getLevelColor = (level: string) => {
    switch (level) {
      case '健康': return '#52c41a';
      case '良好': return '#1890ff';
      case '中等风险': return '#faad14';
      case '高风险': return '#ff4d4f';
      case '极高风险': return '#cf1322';
      default: return '#8c8c8c';
    }
  };

  // 获取风险等级图标
  const getLevelIcon = (level: string) => {
    switch (level) {
      case '健康':
      case '良好':
        return <CheckCircleOutlined />;
      case '中等风险':
        return <ExclamationCircleOutlined />;
      case '高风险':
      case '极高风险':
        return <WarningOutlined />;
      default:
        return null;
    }
  };

  // 获取 Alert 类型
  const getAlertType = (level: string): 'success' | 'info' | 'warning' | 'error' => {
    switch (level) {
      case '健康':
      case '良好':
        return 'success';
      case '中等风险':
        return 'warning';
      case '高风险':
      case '极高风险':
        return 'error';
      default:
        return 'info';
    }
  };

  if (loading) {
    return <Card loading />;
  }

  if (error) {
    return (
      <Card className="health-assessment-card" style={{ marginBottom: 20 }}>
        <Alert
          message="健康度评估加载失败"
          description={error}
          type="error"
          showIcon
        />
      </Card>
    );
  }

  if (!assessment) {
    return null;
  }

  return (
    <Card className="health-assessment-card" style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <HeartOutlined
          style={{
            fontSize: 24,
            color: getLevelColor(assessment.level)
          }}
        />
        <h2 style={{ margin: 0, fontSize: 18 }}>合同健康度综合评估</h2>
      </div>

      <Row gutter={24}>
        {/* 健康度评分 */}
        <Col span={8}>
          <div style={{ textAlign: 'center' }}>
            <Statistic
              title="健康度评分"
              value={assessment.score}
              suffix="/ 100"
              valueStyle={{
                color: getLevelColor(assessment.level),
                fontSize: 28
              }}
            />
            <Progress
              percent={assessment.score}
              strokeColor={getLevelColor(assessment.level)}
              showInfo={false}
              style={{ marginTop: 12 }}
              strokeWidth={12}
            />
          </div>
        </Col>

        {/* 风险等级 */}
        <Col span={8}>
          <div style={{ textAlign: 'center' }}>
            <Statistic
              title="风险等级"
              value={assessment.level}
              prefix={getLevelIcon(assessment.level)}
              valueStyle={{
                color: getLevelColor(assessment.level),
                fontSize: 18
              }}
            />
            <div style={{ marginTop: 12, color: '#8c8c8c', fontSize: 13 }}>
              共发现 {assessment.total_risks} 个风险点
            </div>
          </div>
        </Col>

        {/* 风险分布 */}
        <Col span={8}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 12 }}>风险分布</div>
            <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 6 }}>
              {assessment.risk_distribution.Critical > 0 && (
                <Tag color="red">
                  极严重: {assessment.risk_distribution.Critical}
                </Tag>
              )}
              {assessment.risk_distribution.High > 0 && (
                <Tag color="orange">
                  高风险: {assessment.risk_distribution.High}
                </Tag>
              )}
              {assessment.risk_distribution.Medium > 0 && (
                <Tag color="gold">
                  中等: {assessment.risk_distribution.Medium}
                </Tag>
              )}
              {assessment.risk_distribution.Low > 0 && (
                <Tag color="blue">
                  轻微: {assessment.risk_distribution.Low}
                </Tag>
              )}
              {assessment.total_risks === 0 && (
                <Tag color="green">无风险点</Tag>
              )}
            </div>
          </div>
        </Col>
      </Row>

      {/* 综合评估 */}
      <Alert
        message="综合评估"
        description={assessment.summary}
        type={getAlertType(assessment.level)}
        showIcon
        style={{ marginTop: 20 }}
      />

      {/* 改进建议 */}
      {assessment.recommendations && assessment.recommendations.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14 }}>
            改进建议：
          </div>
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            {assessment.recommendations.map((rec, idx) => (
              <li key={idx} style={{ marginBottom: 4 }}>{rec}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};

export default ContractHealthAssessment;
