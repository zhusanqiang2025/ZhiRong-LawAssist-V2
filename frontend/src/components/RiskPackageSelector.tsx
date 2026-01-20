// frontend/src/components/RiskPackageSelector.tsx - 多选版本（调试）
import React, { useState, useEffect } from 'react';
import {
  Select,
  Tag,
  Typography,
  Space,
  Tooltip,
  Alert,
  message
} from 'antd';
import {
  InfoCircleOutlined,
  CheckCircleOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import type { RiskRulePackage } from '../types/riskAnalysis';
import { riskRulePackagesApi } from '../api/riskRulePackages';

const { Text } = Typography;

interface RiskPackageSelectorProps {
  value?: string[];
  onChange?: (packageIds: string[]) => void;
  categoryFilter?: string;
  disabled?: boolean;
  packages?: RiskRulePackage[];
  onPackagesLoad?: (packages: RiskRulePackage[]) => void;
}

// 分类映射
const CATEGORY_MAP: Record<string, { label: string; color: string; icon: string }> = {
  'equity_risk': { label: '股权风险', color: 'blue', icon: '🏢' },
  'investment_risk': { label: '投资风险', color: 'gold', icon: '💼' },
  'governance_risk': { label: '治理风险', color: 'purple', icon: '⚖️' },
  'contract_risk': { label: '合同风险', color: 'orange', icon: '📄' },
  'tax_risk': { label: '税务风险', color: 'green', icon: '🧾' },
  'litigation_risk': { label: '诉讼风险', color: 'red', icon: '⚖️' }
};

const RiskPackageSelector: React.FC<RiskPackageSelectorProps> = ({
  value = [],
  onChange,
  categoryFilter,
  disabled = false,
  packages: externalPackages,
  onPackagesLoad
}) => {
  const [internalPackages, setInternalPackages] = useState<RiskRulePackage[]>([]);
  const [loading, setLoading] = useState(false);

  // 使用外部传入的 packages 或内部加载的
  const packages = externalPackages || internalPackages;

  console.log('[RiskPackageSelector] 渲染中...', {
    externalPackages: externalPackages?.length,
    internalPackages: internalPackages.length,
    totalPackages: packages.length,
    loading
  });

  // 加载规则包列表
  useEffect(() => {
    if (!externalPackages) {
      loadPackages();
    }
  }, [categoryFilter]);

  const loadPackages = async () => {
    setLoading(true);
    try {
      console.log('[RiskPackageSelector] 开始加载规则包...');
      console.log('[RiskPackageSelector] 当前 token:', localStorage.getItem('accessToken')?.substring(0, 20) + '...');

      const data = await riskRulePackagesApi.listPackages(categoryFilter);
      console.log('[RiskPackageSelector] 加载成功:', data.packages?.length || 0, '个规则包');
      console.log('[RiskPackageSelector] 规则包列表:', data.packages);
      setInternalPackages(data.packages || []);
      onPackagesLoad?.(data.packages || []);
    } catch (error: any) {
      console.error('[RiskPackageSelector] 加载失败:', error);
      console.error('[RiskPackageSelector] 错误详情:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });

      // 如果是 401 错误，显示提示
      if (error.response?.status === 401) {
        console.error('[RiskPackageSelector] 认证失败，请先登录');
        message.error('加载规则包失败：请先登录');
      } else {
        message.error(`加载规则包失败: ${error.message || '未知错误'}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (packageIds: string[]) => {
    console.log('[RiskPackageSelector] 选择变更:', packageIds);
    if (onChange) {
      onChange(packageIds);
    }
  };

  return (
    <div>
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        {/* 标题 */}
        <div>
          <Space>
            <Text strong style={{ fontSize: 13 }}>选择规则包：</Text>
            <Tooltip title="可以选择多个规则包，选中的规则包可以拖拽调整优先级顺序">
              <InfoCircleOutlined style={{ color: '#1890ff' }} />
            </Tooltip>
          </Space>
        </div>

        {/* 下拉多选框 */}
        {loading ? (
          <Alert
            message={<Space><LoadingOutlined /> 正在加载规则包...</Space>}
            type="info"
          />
        ) : packages.length === 0 ? (
          <Alert
            message="暂无可用的规则包"
            description="请先在管理后台创建规则包"
            type="warning"
            showIcon
          />
        ) : (
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            placeholder="请选择一个或多个规则包"
            value={value}
            onChange={handleChange}
            disabled={disabled}
            filterOption={(input, option) => {
              const pkg = packages.find(p => p.package_id === option?.value);
              if (!pkg) return false;
              const searchText = `${pkg.package_name} ${pkg.description}`.toLowerCase();
              return searchText.includes(input.toLowerCase());
            }}
            optionLabelProp="label"
            maxTagCount="responsive"
            size="large"
            listHeight={400}
            showSearch
            allowClear
          >
            {packages.map(pkg => {
              const categoryInfo = CATEGORY_MAP[pkg.package_category] || {
                label: pkg.package_category,
                color: 'default',
                icon: '📦'
              };

              const isSelected = value.includes(pkg.package_id);

              return (
                <Select.Option
                  key={pkg.package_id}
                  value={pkg.package_id}
                  label={pkg.package_name}
                  disabled={!pkg.is_active}
                >
                  <div style={{
                    padding: '8px 4px',
                    backgroundColor: isSelected ? '#e6f7ff' : 'transparent',
                    borderRadius: 4
                  }}>
                    {/* 第一行：图标和名称 */}
                    <div style={{ marginBottom: 4 }}>
                      <Space>
                        <span style={{ fontSize: 16 }}>{categoryInfo.icon}</span>
                        <Text strong style={{ fontSize: 14 }}>{pkg.package_name}</Text>
                        {isSelected && <CheckCircleOutlined style={{ color: '#52c41a', marginLeft: 8 }} />}
                      </Space>
                    </div>

                    {/* 第二行：标签 */}
                    <div style={{ marginBottom: 4 }}>
                      <Space wrap size="small">
                        <Tag color={categoryInfo.color}>{categoryInfo.label}</Tag>
                        {pkg.version && <Tag color="cyan">v{pkg.version}</Tag>}
                        {pkg.is_system && <Tag color="blue">官方</Tag>}
                        {pkg.rules && <Tag>{pkg.rules.length} 条规则</Tag>}
                        {!pkg.is_active && <Tag color="default">已禁用</Tag>}
                      </Space>
                    </div>

                    {/* 第三行：描述 */}
                    {pkg.description && (
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {pkg.description.length > 100
                            ? pkg.description.substring(0, 100) + '...'
                            : pkg.description}
                        </Text>
                      </div>
                    )}
                  </div>
                </Select.Option>
              );
            })}
          </Select>
        )}

        {/* 已选择的数量提示 */}
        {value.length > 0 && (
          <Alert
            message={
              <Space>
                <CheckCircleOutlined style={{ color: '#52c41a' }} />
                <span>已选择 {value.length} 个规则包，可以在下方拖拽调整优先级</span>
              </Space>
            }
            type="success"
            showIcon={false}
            style={{ fontSize: 12 }}
          />
        )}
      </Space>
    </div>
  );
};

export default RiskPackageSelector;
