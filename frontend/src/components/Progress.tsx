import React from 'react';
import { Progress, Steps, Card, Tag, Spin, Typography, Row, Col, Space } from 'antd';
import { CheckCircleOutlined, ClockCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { TaskProgress } from '../types/task';

const { Text } = Typography;
const { Step } = Steps;

interface OverallProgressProps {
    progress: number;
    status: string;
    currentNode?: string;
    estimatedTimeRemaining?: number;
}

export const OverallProgress: React.FC<OverallProgressProps> = ({
    progress,
    status,
    currentNode,
    estimatedTimeRemaining
}) => {
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'success';
            case 'processing': return 'active';
            case 'failed': return 'exception';
            default: return 'normal';
        }
    };

    return (
        <Card size="small" className="overall-progress-card">
            <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                    <Text strong>总体进度: </Text>
                    <Progress
                        percent={progress}
                        status={getStatusColor(status)}
                        strokeColor={{
                            '0%': '#108ee9',
                            '100%': '#87d068',
                        }}
                    />
                </div>
                {currentNode && (
                    <div>
                        <Text type="secondary">当前节点: </Text>
                        <Text>{currentNode}</Text>
                    </div>
                )}
                {estimatedTimeRemaining && (
                    <div>
                        <Text type="secondary">预计剩余时间: </Text>
                        <Text>{Math.round(estimatedTimeRemaining / 60)} 分钟</Text>
                    </div>
                )}
            </Space>
        </Card>
    );
};

interface ProgressTimelineProps {
    task: Partial<TaskProgress>;
    showTimeEstimates?: boolean;
    compact?: boolean;
}

export const ProgressTimeline: React.FC<ProgressTimelineProps> = ({
    task,
    showTimeEstimates = true,
    compact = false
}) => {
    const getStepStatus = (stepName: string, currentStep?: string) => {
        if (!currentStep) return 'wait';
        if (stepName === currentStep) return 'process';
        // 简单的步骤顺序判断
        const steps = ['分析', '起草', '审查', '完成'];
        const currentIndex = steps.indexOf(currentStep);
        const stepIndex = steps.indexOf(stepName);
        return stepIndex < currentIndex ? 'finish' : 'wait';
    };

    const getStepIcon = (status: string) => {
        switch (status) {
            case 'finish': return <CheckCircleOutlined />;
            case 'process': return <LoadingOutlined />;
            default: return <ClockCircleOutlined />;
        }
    };

    const workflowSteps = task.workflowSteps || [
        { name: '分析', status: 'pending' },
        { name: '起草', status: 'pending' },
        { name: '审查', status: 'pending' },
        { name: '完成', status: 'pending' }
    ];

    return (
        <Card size="small" title="处理流程" className="progress-timeline-card">
            <Steps
                direction="vertical"
                size={compact ? 'small' : 'default'}
                current={workflowSteps.findIndex(step => step.status === 'processing')}
            >
                {workflowSteps.map((step, index) => (
                    <Step
                        key={step.name}
                        title={step.name}
                        status={getStepStatus(step.name, task.currentNode)}
                        icon={getStepIcon(step.status)}
                        description={
                            <div>
                                {step.status === 'processing' && (
                                    <Text type="secondary">处理中...</Text>
                                )}
                                {step.status === 'completed' && (
                                    <Text type="secondary">已完成</Text>
                                )}
                                {showTimeEstimates && step.estimatedTime && (
                                    <div>
                                        <Text type="secondary" style={{ fontSize: '12px' }}>
                                            预计时间: {step.estimatedTime}分钟
                                        </Text>
                                    </div>
                                )}
                            </div>
                        }
                    />
                ))}
            </Steps>
        </Card>
    );
};

interface NodeProgressProps {
    nodeProgress?: Record<string, any>;
    currentNode?: string;
}

export const NodeProgress: React.FC<NodeProgressProps> = ({
    nodeProgress,
    currentNode
}) => {
    if (!nodeProgress || Object.keys(nodeProgress).length === 0) {
        return null;
    }

    return (
        <Card size="small" title="节点详情" className="node-progress-card">
            <Space direction="vertical" style={{ width: '100%' }}>
                {Object.entries(nodeProgress).map(([nodeName, data]: [string, any]) => (
                    <div
                        key={nodeName}
                        className={`node-item ${nodeName === currentNode ? 'current-node' : ''}`}
                    >
                        <Row justify="space-between" align="middle">
                            <Col>
                                <Text strong={nodeName === currentNode}>
                                    {nodeName}
                                </Text>
                            </Col>
                            <Col>
                                <Tag color={
                                    data.status === 'completed' ? 'green' :
                                    data.status === 'processing' ? 'blue' :
                                    data.status === 'failed' ? 'red' : 'default'
                                }>
                                    {data.status || 'pending'}
                                </Tag>
                            </Col>
                        </Row>
                        {data.progress !== undefined && (
                            <Progress
                                percent={data.progress}
                                size="small"
                                style={{ marginTop: '4px' }}
                            />
                        )}
                        {data.message && (
                            <Text type="secondary" style={{ fontSize: '12px' }}>
                                {data.message}
                            </Text>
                        )}
                    </div>
                ))}
            </Space>
        </Card>
    );
};