// frontend/src/components/ModuleKnowledgeToggle.tsx
/**
 * 模块级知识库开关组件
 *
 * 功能：
 * 1. 显示当前模块的知识库启用状态
 * 2. 允许用户切换知识库开关
 * 3. 允许用户选择启用的知识源
 * 4. 保存用户偏好设置
 */

import React, { useState, useEffect } from 'react';
import { Card, Switch, Select, Button, Space, Typography, message, Tooltip } from 'antd';
import {
  DatabaseOutlined,
  SettingOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import knowledgeBaseApi, { ModulePreferences } from '../api/knowledgeBase';

const { Text } = Typography;

interface Props {
  /**
   * 模块名称
   * @example 'consultation' | 'contract_review' | 'risk_analysis' | 'litigation_analysis'
   */
  moduleName: 'consultation' | 'contract_review' | 'risk_analysis' | 'litigation_analysis';

  /**
   * 模块显示名称
   * @example '智能咨询' | '合同审查' | '风险评估'
   */
  moduleLabel?: string;

  /**
   * 可选的知识源列表
   * 如果不提供，则从 API 获取
   */
  availableStores?: string[];

  /**
   * 样式类名
   */
  style?: React.CSSProperties;

  /**
   * 状态变化回调
   */
  onChange?: (enabled: boolean, stores?: string[]) => void;
}

const ModuleKnowledgeToggle: React.FC<Props> = ({
  moduleName,
  moduleLabel,
  availableStores,
  style,
  onChange,
}) => {
  // ============ 状态管理 ============
  const [loading, setLoading] = useState(false);
  const [preferences, setPreferences] = useState<ModulePreferences>({
    module_name: moduleName,
    knowledge_base_enabled: false,
    enabled_stores: [],
  });
  const [stores, setStores] = useState<string[]>([]);
  const [hasLoaded, setHasLoaded] = useState(false);

  // ============ 数据加载 ============
  const fetchPreferences = async () => {
    setLoading(true);
    try {
      const response = await knowledgeBaseApi.getModulePreferences(moduleName);
      const data = response.data.data;
      setPreferences(data);

      // 如果没有提供可用知识源列表，则使用偏好设置中的
      if (!availableStores && data.enabled_stores) {
        setStores(data.enabled_stores);
      } else if (availableStores) {
        setStores(availableStores);
      }

      setHasLoaded(true);
    } catch (error: any) {
      console.error('加载偏好设置失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPreferences();

    // 如果提供了可用知识源列表，使用它
    if (availableStores) {
      setStores(availableStores);
    }
  }, [moduleName]);

  // ============ 事件处理 ============
  const handleToggle = async (enabled: boolean) => {
    setLoading(true);
    try {
      const newPrefs: ModulePreferences = {
        ...preferences,
        knowledge_base_enabled: enabled,
        // 如果启用且没有选择知识源，默认选择所有可用源
        enabled_stores: enabled && (!preferences.enabled_stores || preferences.enabled_stores.length === 0)
          ? stores
          : preferences.enabled_stores,
      };

      await knowledgeBaseApi.saveModulePreferences(moduleName, newPrefs);
      setPreferences(newPrefs);

      message.success(`知识库已${enabled ? '启用' : '禁用'}`);
      onChange?.(enabled, newPrefs.enabled_stores);
    } catch (error: any) {
      message.error(`操作失败: ${error.response?.data?.detail || error.message}`);
      // 回滚状态
      setPreferences(preferences);
    } finally {
      setLoading(false);
    }
  };

  const handleStoresChange = async (selectedStores: string[]) => {
    setLoading(true);
    try {
      const newPrefs: ModulePreferences = {
        ...preferences,
        enabled_stores: selectedStores,
      };

      await knowledgeBaseApi.saveModulePreferences(moduleName, newPrefs);
      setPreferences(newPrefs);

      message.success('知识源设置已保存');
      onChange?.(preferences.knowledge_base_enabled, selectedStores);
    } catch (error: any) {
      message.error(`保存失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // ============ 渲染辅助 ============
  const getModuleName = () => {
    if (moduleLabel) return moduleLabel;

    const nameMap: Record<string, string> = {
      consultation: '智能咨询',
      contract_review: '合同审查',
      risk_analysis: '风险评估',
      litigation_analysis: '案件分析',
    };

    return nameMap[moduleName] || moduleName;
  };

  // ============ 主渲染 ============
  if (!hasLoaded) {
    return null; // 或者显示加载状态
  }

  return (
    <Card
      size="small"
      style={style}
      title={
        <Space>
          <DatabaseOutlined />
          <Text>知识库增强</Text>
          <Tooltip title="启用知识库后，系统将基于本地和外部知识库提供更准确的法律依据">
            <InfoCircleOutlined style={{ color: '#999' }} />
          </Tooltip>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* 开关 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Text>启用知识库增强：</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              ({getModuleName()})
            </Text>
          </Space>
          <Switch
            checked={preferences.knowledge_base_enabled}
            onChange={handleToggle}
            loading={loading}
            checkedChildren="开启"
            unCheckedChildren="关闭"
          />
        </div>

        {/* 知识源选择 */}
        {preferences.knowledge_base_enabled && (
          <div style={{ marginTop: 8 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                选择知识源：
              </Text>
              <Select
                mode="multiple"
                placeholder="选择要使用的知识源"
                value={preferences.enabled_stores}
                onChange={handleStoresChange}
                loading={loading}
                style={{ width: '100%' }}
                maxTagCount="responsive"
                options={stores.map((store) => ({
                  label: store,
                  value: store,
                }))}
              />
            </Space>
          </div>
        )}

        {/* 提示信息 */}
        {!preferences.knowledge_base_enabled && (
          <div
            style={{
              marginTop: 8,
              padding: '8px 12px',
              background: '#f0f5ff',
              borderRadius: 4,
              border: '1px solid #adc6ff',
            }}
          >
            <Text type="secondary" style={{ fontSize: 12 }}>
              <InfoCircleOutlined /> 开启知识库增强后，系统将引用现行法律法规和案例，提供更准确的法律依据
            </Text>
          </div>
        )}
      </Space>
    </Card>
  );
};

export default ModuleKnowledgeToggle;
