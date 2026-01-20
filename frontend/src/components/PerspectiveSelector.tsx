// frontend/src/components/PerspectiveSelector.tsx
/**
 * 评估视角选择器组件
 *
 * 功能：
 * 1. 显示可用的评估视角（公司混同风险/合同条款风险/投资项目风险/税务风险/股权穿透风险等）
 * 2. 支持多选评估视角
 * 3. 拖拽调整优先级
 * 4. 自动加载对应的规则包
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Select,
  Tag,
  Space,
  Button,
  Typography,
  Divider,
  Alert,
  Tooltip,
  Row,
  Col
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  DragOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import type { DragEndEvent } from '@dnd-kit/core';
import { DndContext, closestCenter } from '@dnd-kit/core';
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { riskRulePackagesApi } from '../api/riskRulePackages';
import {
  EvaluationPerspective,
  EVALUATION_PERSPECTIVES,
  RulePackageCategory,
  RULE_PACKAGE_CATEGORIES
} from '../types/riskAnalysis';

const { Text, Paragraph } = Typography;
const { OptGroup, Option } = Select;

// 分类颜色映射
const CATEGORY_COLORS: Record<RulePackageCategory, string> = {
  equity_risk: '#722ed1',
  investment_risk: '#fa8c16',
  governance_risk: '#f5222d',
  contract_risk: '#1890ff',
  tax_risk: '#13c2c2'
};

// 分类图标映射
const CATEGORY_ICONS: Record<RulePackageCategory, string> = {
  equity_risk: '📊',
  investment_risk: '💰',
  governance_risk: '🏢',
  contract_risk: '📄',
  tax_risk: '💲'
};

interface PerspectiveSelectorProps {
  value?: EvaluationPerspective[];
  onChange?: (perspectives: EvaluationPerspective[]) => void;
  disabled?: boolean;
  maxSelections?: number;  // 最多选择数量，默认不限制
}

// 可排序项组件
interface SortableItemProps {
  perspective: EvaluationPerspective;
  onRemove: (id: string) => void;
  index: number;
}

const SortableItem: React.FC<SortableItemProps> = ({ perspective, onRemove, index }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: perspective.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="perspective-sortable-item"
    >
      <Card
        size="small"
        style={{
          marginBottom: '8px',
          borderLeft: `4px solid ${CATEGORY_COLORS[perspective.category]}`,
          cursor: 'grab'
        }}
      >
        <Row align="middle" gutter={12}>
          <Col>
            <div
              {...attributes}
              {...listeners}
              style={{ cursor: 'grab', padding: '4px' }}
            >
              <DragOutlined style={{ color: '#8c8c8c' }} />
            </div>
          </Col>
          <Col flex="auto">
            <Space direction="vertical" size={0}>
              <Space>
                <Text strong style={{ fontSize: '14px' }}>
                  {index + 1}. {perspective.name}
                </Text>
                <Tag color={CATEGORY_COLORS[perspective.category]} style={{ margin: 0 }}>
                  {CATEGORY_ICONS[perspective.category]} {RULE_PACKAGE_CATEGORIES.find(c => c.value === perspective.category)?.label}
                </Tag>
                <Tag color="blue">
                  <ThunderboltOutlined style={{ fontSize: '12px' }} /> 优先级: {perspective.priority}
                </Tag>
              </Space>
              {perspective.description && (
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  {perspective.description}
                </Text>
              )}
            </Space>
          </Col>
          <Col>
            <Button
              type="text"
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => onRemove(perspective.id)}
              disabled={false}
            />
          </Col>
        </Row>
      </Card>
    </div>
  );
};

const PerspectiveSelector: React.FC<PerspectiveSelectorProps> = ({
  value = [],
  onChange,
  disabled = false,
  maxSelections
}) => {
  const [availablePackages, setAvailablePackages] = useState<EvaluationPerspective[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载规则包列表
  useEffect(() => {
    loadRulePackages();
  }, []);

  const loadRulePackages = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await riskRulePackagesApi.listPackages();
      const packages = response.packages
        .filter(pkg => pkg.is_active)
        .map(pkg => ({
          id: pkg.package_id,
          name: pkg.package_name,
          category: pkg.package_category as RulePackageCategory,
          description: pkg.description,
          rule_count: pkg.rules?.length || 0,
          is_active: pkg.is_active
        }));
      setAvailablePackages(packages);
    } catch (err: any) {
      console.error('加载规则包失败:', err);
      setError('加载规则包失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 添加视角
  const handleAdd = (perspectiveId: string) => {
    const perspective = availablePackages.find(p => p.id === perspectiveId);
    if (!perspective) return;

    // 检查是否已选择
    if (value.some(p => p.id === perspectiveId)) {
      return;
    }

    // 检查数量限制
    if (maxSelections && value.length >= maxSelections) {
      return;
    }

    const newPerspective: EvaluationPerspective = {
      ...perspective,
      priority: value.length + 1  // 新添加的优先级最低
    };

    onChange?.([...value, newPerspective]);
  };

  // 移除视角
  const handleRemove = (id: string) => {
    const newSelected = value.filter(p => p.id !== id);
    // 重新计算优先级
    const updated = newSelected.map((p, idx) => ({
      ...p,
      priority: idx + 1
    }));
    onChange?.(updated);
  };

  // 拖拽结束
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = value.findIndex(p => p.id === active.id);
    const newIndex = value.findIndex(p => p.id === over.id);

    if (oldIndex === -1 || newIndex === -1) return;

    // 重新排序
    const newSelected = [...value];
    const [moved] = newSelected.splice(oldIndex, 1);
    newSelected.splice(newIndex, 0, moved);

    // 更新优先级
    const updated = newSelected.map((p, idx) => ({
      ...p,
      priority: idx + 1
    }));

    onChange?.(updated);
  };

  // 获取未选择的视角选项
  const getAvailableOptions = () => {
    const selectedIds = new Set(value.map(p => p.id));
    return availablePackages.filter(p => !selectedIds.has(p.id));
  };

  // 按分类分组选项
  const getGroupedOptions = () => {
    const options = getAvailableOptions();
    const grouped: Record<RulePackageCategory, typeof options> = {
      equity_risk: [],
      investment_risk: [],
      governance_risk: [],
      contract_risk: [],
      tax_risk: []
    };

    options.forEach(opt => {
      grouped[opt.category].push(opt);
    });

    return grouped;
  };

  const groupedOptions = getGroupedOptions();

  return (
    <div className="perspective-selector">
      {/* 已选择的视角 */}
      {value.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ marginBottom: '12px' }}>
            <Space>
              <Text strong>已选择的评估视角</Text>
              <Tag color="blue">{value.length}</Tag>
              <Tooltip title="拖拽可调整优先级，优先级数字越小越优先">
                <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
              </Tooltip>
            </Space>
          </div>

          <DndContext
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={value.map(p => p.id)}
              strategy={verticalListSortingStrategy}
            >
              {value.map((perspective, index) => (
                <SortableItem
                  key={perspective.id}
                  perspective={perspective}
                  onRemove={handleRemove}
                  index={index}
                />
              ))}
            </SortableContext>
          </DndContext>
        </div>
      )}

      <Divider style={{ margin: '16px 0' }} />

      {/* 添加视角选择器 */}
      <div>
        <Space style={{ marginBottom: '12px' }}>
          <Text strong>添加评估视角</Text>
          {maxSelections && (
            <Text type="secondary">
              (已选 {value.length}/{maxSelections})
            </Text>
          )}
        </Space>

        {error && (
          <Alert
            message={error}
            type="error"
            closable
            onClose={() => setError(null)}
            style={{ marginBottom: '12px' }}
          />
        )}

        <Select
          placeholder="请选择评估视角"
          style={{ width: '100%' }}
          loading={loading}
          disabled={disabled || (maxSelections !== undefined && value.length >= maxSelections)}
          onSelect={(val) => handleAdd(val)}
          value={null}
          showSearch
          optionFilterProp="children"
        >
          {RULE_PACKAGE_CATEGORIES.map(category => {
            const options = groupedOptions[category.value];
            if (options.length === 0) return null;

            return (
              <OptGroup key={category.value} label={`${category.label} (${options.length})`}>
                {options.map(opt => (
                  <Option key={opt.id} value={opt.id}>
                    <Space>
                      <span>{CATEGORY_ICONS[category.value]}</span>
                      <span>{opt.name}</span>
                      {opt.rule_count > 0 && (
                        <Tag style={{ fontSize: '11px', margin: 0 }}>
                          {opt.rule_count} 条规则
                        </Tag>
                      )}
                    </Space>
                  </Option>
                ))}
              </OptGroup>
            );
          })}
        </Select>

        {value.length > 0 && (
          <div style={{ marginTop: '12px' }}>
            <Alert
              message={
                <Space>
                  <CheckCircleOutlined />
                  <Text>
                    已选择 {value.length} 个评估视角，将按优先级依次应用规则包
                  </Text>
                </Space>
              }
              type="info"
              showIcon
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default PerspectiveSelector;
