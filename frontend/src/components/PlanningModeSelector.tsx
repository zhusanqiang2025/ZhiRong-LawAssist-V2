/**
 * 规划模式选择组件
 *
 * 当用户需求被识别为"合同规划"场景时，显示此组件让用户选择规划模式
 * - 多模型综合融合：使用多个AI模型从不同视角分析，综合融合生成最优方案
 * - 单模型快速生成：使用单个AI模型快速生成规划方案
 */

import React, { useState } from 'react';
import { Card, Radio, Button, Typography, Tag, Space, Alert } from 'antd';
import type { RadioChangeEvent } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  StarOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import type { PlanningModeOption } from '../types/planning';

const { Text, Paragraph } = Typography;

interface PlanningModeSelectorProps {
  options: {
    multi_model: PlanningModeOption;
    single_model: PlanningModeOption;
  };
  defaultChoice: string;
  onConfirm: (mode: 'multi_model' | 'single_model') => void;
  loading?: boolean;
}

const PlanningModeSelector: React.FC<PlanningModeSelectorProps> = ({
  options,
  defaultChoice,
  onConfirm,
  loading = false
}) => {
  const [selectedMode, setSelectedMode] = useState<'multi_model' | 'single_model'>(
    defaultChoice as 'multi_model' | 'single_model'
  );

  const currentOption = options[selectedMode];

  const handleModeChange = (e: RadioChangeEvent) => {
    setSelectedMode(e.target.value);
  };

  const handleConfirm = () => {
    onConfirm(selectedMode);
  };

  return (
    <div className="planning-mode-selector">
      <div className="selector-header">
        <Typography.Title level={3}>请选择规划模式</Typography.Title>
        <Paragraph type="secondary">
          系统已识别您的需求为"合同规划"场景，请选择您偏好的规划模式：
        </Paragraph>
      </div>

      <Radio.Group
        value={selectedMode}
        onChange={handleModeChange}
        className="mode-radio-group"
        disabled={loading}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* 多模型选项 */}
          <Radio
            value="multi_model"
            disabled={!options.multi_model.available || loading}
            className={selectedMode === 'multi_model' ? 'radio-card-selected' : ''}
          >
            <Card
              className={`mode-card ${selectedMode === 'multi_model' ? 'selected' : ''} ${options.multi_model.recommended ? 'recommended' : ''}`}
              hoverable
              onClick={() => {
                if (options.multi_model.available && !loading) {
                  setSelectedMode('multi_model');
                }
              }}
            >
              <div className="mode-card-header">
                <Space>
                  <StarOutlined className="recommend-icon" />
                  <Text strong>{options.multi_model.name}</Text>
                  {options.multi_model.recommended && (
                    <Tag color="gold">推荐</Tag>
                  )}
                  {options.multi_model.expected_quality === '高质量' && (
                    <Tag color="success">高质量</Tag>
                  )}
                </Space>
                {!options.multi_model.available && (
                  <Tag color="error">暂不可用</Tag>
                )}
              </div>

              <Paragraph className="mode-description">
                {options.multi_model.description}
              </Paragraph>

              <div className="mode-features">
                <Text type="secondary">特点：</Text>
                <ul>
                  {options.multi_model.features.map((feature, index) => (
                    <li key={index}>{feature}</li>
                  ))}
                </ul>
              </div>

              <div className="mode-info">
                <Space size="large">
                  <Text>
                    <ClockCircleOutlined /> 预计时间：{options.multi_model.processing_time}
                  </Text>
                  <Text>
                    <CheckCircleOutlined /> 质量预期：{options.multi_model.expected_quality}
                  </Text>
                </Space>
              </div>
            </Card>
          </Radio>

          {/* 单模型选项 */}
          <Radio
            value="single_model"
            disabled={!options.single_model.available || loading}
            className={selectedMode === 'single_model' ? 'radio-card-selected' : ''}
          >
            <Card
              className={`mode-card ${selectedMode === 'single_model' ? 'selected' : ''}`}
              hoverable
              onClick={() => {
                if (options.single_model.available && !loading) {
                  setSelectedMode('single_model');
                }
              }}
            >
              <div className="mode-card-header">
                <Space>
                  <ThunderboltOutlined />
                  <Text strong>{options.single_model.name}</Text>
                  {options.single_model.expected_quality === '标准质量' && (
                    <Tag color="blue">标准质量</Tag>
                  )}
                </Space>
              </div>

              <Paragraph className="mode-description">
                {options.single_model.description}
              </Paragraph>

              <div className="mode-features">
                <Text type="secondary">特点：</Text>
                <ul>
                  {options.single_model.features.map((feature, index) => (
                    <li key={index}>{feature}</li>
                  ))}
                </ul>
              </div>

              <div className="mode-info">
                <Space size="large">
                  <Text>
                    <ClockCircleOutlined /> 预计时间：{options.single_model.processing_time}
                  </Text>
                  <Text>
                    <CheckCircleOutlined /> 质量预期：{options.single_model.expected_quality}
                  </Text>
                </Space>
              </div>
            </Card>
          </Radio>
        </Space>
      </Radio.Group>

      {/* 当前选择说明 */}
      <Alert
        message={`您选择了：${currentOption.name}`}
        description={
          <div>
            <div>• {currentOption.description}</div>
            <div>• 预计耗时：{currentOption.processing_time}</div>
            <div>• 质量预期：{currentOption.expected_quality}</div>
          </div>
        }
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        style={{ marginTop: 16 }}
      />

      {/* 确认按钮 */}
      <Button
        type="primary"
        size="large"
        block
        onClick={handleConfirm}
        loading={loading}
        disabled={!currentOption.available}
        style={{ marginTop: 24 }}
      >
        确认选择并开始规划
      </Button>
    </div>
  );
};

export default PlanningModeSelector;
