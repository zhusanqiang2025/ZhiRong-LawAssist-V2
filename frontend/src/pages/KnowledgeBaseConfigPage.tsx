// frontend/src/pages/KnowledgeBaseConfigPage.tsx
/**
 * 知识库配置页面
 *
 * 功能：
 * 1. 知识源管理（本地、飞书）
 * 2. 知识源状态监控
 * 3. 模块级偏好设置
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Switch,
  Modal,
  Form,
  Input,
  message,
  Typography,
  Tabs,
  Descriptions,
  Statistic,
  Row,
  Col,
  Alert,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
} from '@ant-design/icons';
import knowledgeBaseApi, {
  KnowledgeSource,
  FeishuConfig,
  HealthInfo,
  ModulePreferences,
} from '../api/knowledgeBase';
import { useSessionPersistence } from '../hooks/useSessionPersistence';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

interface Props {
  onBack?: () => void;
}

const KnowledgeBaseConfigPage: React.FC<Props> = ({ onBack }) => {
  // ========== 会话持久化 ==========
  interface KnowledgeBaseConfigSessionData {
    activeTab: string;
    modulePreferences: {
      consultation: ModulePreferences;
      contract_review: ModulePreferences;
      risk_analysis: ModulePreferences;
    };
  }

  const {
    hasSession,
    saveSession,
    clearSession,
    isLoading: isRestoringSession,
  } = useSessionPersistence<KnowledgeBaseConfigSessionData>('knowledge_base_config_session', {
    expirationTime: 2 * 60 * 60 * 1000, // 2小时
    onRestore: (sessionId, data) => {
      console.log('[知识库配置] 恢复会话:', data);
      setActiveTab(data.activeTab || 'sources');
      setModulePreferences(data.modulePreferences);
      message.success('已恢复之前的配置会话');
    },
  });

  // 保存会话状态
  const saveCurrentState = () => {
    saveSession(Date.now().toString(), {
      activeTab,
      modulePreferences,
    });
  };
  // ========== 会话持久化结束 ==========

  // ============ 状态管理 ============
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null);
  const [feishuModalVisible, setFeishuModalVisible] = useState(false);
  const [testConnectionLoading, setTestConnectionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('sources');

  // 模块偏好设置状态
  const [modulePreferences, setModulePreferences] = useState<{
    consultation: ModulePreferences;
    contract_review: ModulePreferences;
    risk_analysis: ModulePreferences;
  }>({
    consultation: {
      module_name: 'consultation',
      knowledge_base_enabled: false,
      enabled_stores: [],
    },
    contract_review: {
      module_name: 'contract_review',
      knowledge_base_enabled: false,
      enabled_stores: [],
    },
    risk_analysis: {
      module_name: 'risk_analysis',
      knowledge_base_enabled: false,
      enabled_stores: [],
    },
  });

  const [feishuForm] = Form.useForm();

  // ============ 数据加载 ============
  const fetchKnowledgeSources = async () => {
    setLoading(true);
    try {
      const response = await knowledgeBaseApi.getKnowledgeSources();
      setSources(response.data.data.sources || []);
      message.success('知识源列表加载成功');
    } catch (error: any) {
      message.error(`加载失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchHealthCheck = async () => {
    try {
      const response = await knowledgeBaseApi.healthCheck();
      setHealthInfo(response.data.data);
    } catch (error: any) {
      console.error('健康检查失败:', error);
    }
  };

  const fetchModulePreferences = async () => {
    const modules = ['consultation', 'contract_review', 'risk_analysis'];
    const preferences: any = {};

    for (const module of modules) {
      try {
        const response = await knowledgeBaseApi.getModulePreferences(module);
        preferences[module] = response.data.data;
      } catch (error) {
        // 如果没有配置，使用默认值
        preferences[module] = {
          module_name: module,
          knowledge_base_enabled: false,
          enabled_stores: [],
        };
      }
    }

    setModulePreferences(preferences);
  };

  useEffect(() => {
    fetchKnowledgeSources();
    fetchHealthCheck();
    fetchModulePreferences();
  }, []);

  // 监听状态变化，自动保存会话
  useEffect(() => {
    if (activeTab || modulePreferences) {
      saveCurrentState();
    }
  }, [activeTab, modulePreferences]);

  // ============ 事件处理 ============
  const handleToggleSource = async (sourceId: string, enabled: boolean) => {
    try {
      await knowledgeBaseApi.toggleKnowledgeSource(sourceId, enabled);
      message.success(`知识源已${enabled ? '启用' : '禁用'}`);
      fetchKnowledgeSources();
      fetchHealthCheck();
    } catch (error: any) {
      message.error(`操作失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleConfigureFeishu = async () => {
    try {
      const values = await feishuForm.validateFields();
      setTestConnectionLoading(true);

      await knowledgeBaseApi.configureFeishuSource(values);

      message.success('飞书知识源配置成功');
      setFeishuModalVisible(false);
      feishuForm.resetFields();
      fetchKnowledgeSources();
      fetchHealthCheck();
    } catch (error: any) {
      if (error.errorFields) {
        // 表单验证错误
        return;
      }
      message.error(`配置失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setTestConnectionLoading(false);
    }
  };

  const handleSaveModulePreferences = async (moduleName: string, preferences: ModulePreferences) => {
    try {
      await knowledgeBaseApi.saveModulePreferences(moduleName, preferences);
      message.success('偏好设置已保存');
    } catch (error: any) {
      message.error(`保存失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  // ============ 渲染辅助函数 ============
  const renderSourceIcon = (type: string) => {
    switch (type) {
      case 'local':
        return <DatabaseOutlined style={{ fontSize: 20, color: '#1890ff' }} />;
      case 'feishu':
        return <CloudServerOutlined style={{ fontSize: 20, color: '#52c41a' }} />;
      default:
        return <DatabaseOutlined style={{ fontSize: 20 }} />;
    }
  };

  const renderStatusTag = (status: string) => {
    switch (status) {
      case 'connected':
        return (
          <Tag icon={<CheckCircleOutlined />} color="success">
            已连接
          </Tag>
        );
      case 'disconnected':
        return (
          <Tag icon={<CloseCircleOutlined />} color="default">
            未连接
          </Tag>
        );
      case 'error':
        return (
          <Tag icon={<CloseCircleOutlined />} color="error">
            错误
          </Tag>
        );
      default:
        return <Tag>{status}</Tag>;
    }
  };

  const sourcesColumns = [
    {
      title: '知识源',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: KnowledgeSource) => (
        <Space>
          {renderSourceIcon(record.type)}
          <span>
            <Text strong>{name}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              类型: {record.type === 'local' ? '本地' : '飞书'}
            </Text>
          </span>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => renderStatusTag(status),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (priority: number) => <Tag color={priority <= 2 ? 'blue' : 'default'}>{priority}</Tag>,
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled: boolean, record: KnowledgeSource) => (
        <Switch
          checked={enabled}
          onChange={(checked) => handleToggleSource(record.id, checked)}
          disabled={record.type === 'local'} // 本地知识库始终启用
        />
      ),
    },
    {
      title: '最后同步',
      dataIndex: 'last_sync',
      key: 'last_sync',
      width: 180,
      render: (time: string) => (time ? new Date(time).toLocaleString('zh-CN') : '-'),
    },
  ];

  // ============ 渲染知识源管理表格 ============
  const renderSourcesTable = () => (
    <Card
      title="知识源管理"
      extra={
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              fetchKnowledgeSources();
              fetchHealthCheck();
            }}
          >
            刷新
          </Button>
          {sources.filter((s) => s.type === 'feishu').length === 0 && (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setFeishuModalVisible(true)}
            >
              添加飞书知识源
            </Button>
          )}
        </Space>
      }
    >
      <Table
        columns={sourcesColumns}
        dataSource={sources}
        rowKey="id"
        loading={loading}
        pagination={false}
      />
    </Card>
  );

  // ============ 渲染健康状态 ============
  const renderHealthStatus = () => {
    if (!healthInfo) {
      return <Card title="系统健康状态">加载中...</Card>;
    }

    return (
      <Card title="系统健康状态">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic
              title="知识源总数"
              value={healthInfo.total_stores}
              prefix={<DatabaseOutlined />}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="可用知识源"
              value={healthInfo.available_stores}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="可用率"
              value={
                healthInfo.total_stores > 0
                  ? Math.round((healthInfo.available_stores / healthInfo.total_stores) * 100)
                  : 0
              }
              suffix="%"
              valueStyle={{
                color:
                  healthInfo.available_stores === healthInfo.total_stores
                    ? '#3f8600'
                    : '#cf1322',
              }}
            />
          </Col>
        </Row>

        <Descriptions
          title="知识源详情"
          bordered
          column={1}
          style={{ marginTop: 24 }}
        >
          {healthInfo.stores.map((store) => (
            <Descriptions.Item
              key={store.name}
              label={
                <Space>
                  {renderSourceIcon(store.name.includes('本地') ? 'local' : 'feishu')}
                  {store.name}
                </Space>
              }
            >
              {store.available ? (
                <Tag color="success">可用</Tag>
              ) : (
                <Tag color="error">不可用</Tag>
              )}
              <Text type="secondary">优先级: {store.priority}</Text>
            </Descriptions.Item>
          ))}
        </Descriptions>
      </Card>
    );
  };

  // ============ 渲染模块偏好设置 ============
  const renderModulePreferences = () => (
    <Card title="模块知识库偏好设置">
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* 智能咨询模块 */}
        <Card
          type="inner"
          title="智能咨询模块"
          extra={
            <Switch
              checked={modulePreferences.consultation.knowledge_base_enabled}
              onChange={(checked) => {
                const newPrefs = {
                  ...modulePreferences.consultation,
                  knowledge_base_enabled: checked,
                };
                setModulePreferences({ ...modulePreferences, consultation: newPrefs });
                handleSaveModulePreferences('consultation', newPrefs);
              }}
            />
          }
        >
          <Descriptions column={1} size="small">
            <Descriptions.Item label="状态">
              {modulePreferences.consultation.knowledge_base_enabled ? (
                <Tag color="success">已启用知识库增强</Tag>
              ) : (
                <Tag color="default">未启用</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="启用的知识源">
              {modulePreferences.consultation.enabled_stores &&
              modulePreferences.consultation.enabled_stores.length > 0 ? (
                modulePreferences.consultation.enabled_stores.map((store) => (
                  <Tag key={store}>{store}</Tag>
                ))
              ) : (
                <Text type="secondary">未选择</Text>
              )}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 合同审查模块 */}
        <Card
          type="inner"
          title="合同审查模块"
          extra={
            <Switch
              checked={modulePreferences.contract_review.knowledge_base_enabled}
              onChange={(checked) => {
                const newPrefs = {
                  ...modulePreferences.contract_review,
                  knowledge_base_enabled: checked,
                };
                setModulePreferences({ ...modulePreferences, contract_review: newPrefs });
                handleSaveModulePreferences('contract_review', newPrefs);
              }}
            />
          }
        >
          <Descriptions column={1} size="small">
            <Descriptions.Item label="状态">
              {modulePreferences.contract_review.knowledge_base_enabled ? (
                <Tag color="success">已启用知识库增强</Tag>
              ) : (
                <Tag color="default">未启用</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="启用的知识源">
              {modulePreferences.contract_review.enabled_stores &&
              modulePreferences.contract_review.enabled_stores.length > 0 ? (
                modulePreferences.contract_review.enabled_stores.map((store) => (
                  <Tag key={store}>{store}</Tag>
                ))
              ) : (
                <Text type="secondary">未选择</Text>
              )}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 风险评估模块 */}
        <Card
          type="inner"
          title="风险评估模块"
          extra={
            <Switch
              checked={modulePreferences.risk_analysis.knowledge_base_enabled}
              onChange={(checked) => {
                const newPrefs = {
                  ...modulePreferences.risk_analysis,
                  knowledge_base_enabled: checked,
                };
                setModulePreferences({ ...modulePreferences, risk_analysis: newPrefs });
                handleSaveModulePreferences('risk_analysis', newPrefs);
              }}
            />
          }
        >
          <Descriptions column={1} size="small">
            <Descriptions.Item label="状态">
              {modulePreferences.risk_analysis.knowledge_base_enabled ? (
                <Tag color="success">已启用知识库增强</Tag>
              ) : (
                <Tag color="default">未启用</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="启用的知识源">
              {modulePreferences.risk_analysis.enabled_stores &&
              modulePreferences.risk_analysis.enabled_stores.length > 0 ? (
                modulePreferences.risk_analysis.enabled_stores.map((store) => (
                  <Tag key={store}>{store}</Tag>
                ))
              ) : (
                <Text type="secondary">未选择</Text>
              )}
            </Descriptions.Item>
          </Descriptions>
        </Card>
      </Space>
    </Card>
  );

  // ============ 渲染飞书配置模态框 ============
  const renderFeishuModal = () => (
    <Modal
      title="配置飞书知识源"
      open={feishuModalVisible}
      onOk={handleConfigureFeishu}
      onCancel={() => {
        setFeishuModalVisible(false);
        feishuForm.resetFields();
      }}
      confirmLoading={testConnectionLoading}
      width={600}
      destroyOnClose
    >
      <Form form={feishuForm} layout="vertical">
        <Form.Item
          label="App ID"
          name="app_id"
          rules={[{ required: true, message: '请输入飞书应用 ID' }]}
          extra="从飞书开放平台应用凭证中获取"
        >
          <Input placeholder="cli_xxxxxxxxxxxxx" />
        </Form.Item>

        <Form.Item
          label="App Secret"
          name="app_secret"
          rules={[{ required: true, message: '请输入飞书应用密钥' }]}
          extra="从飞书开放平台应用凭证中获取"
        >
          <Input.Password placeholder="请输入应用密钥" />
        </Form.Item>

        <Form.Item
          label="Wiki Space ID"
          name="wiki_space_id"
          rules={[{ required: true, message: '请输入 Wiki 空间 ID' }]}
          extra="飞书知识库空间的唯一标识"
        >
          <Input placeholder="xxxxxxxxxxxxxxxxxxxx" />
        </Form.Item>

        <Form.Item
          label="启用状态"
          name="enabled"
          valuePropName="checked"
          initialValue={true}
        >
          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
        </Form.Item>
      </Form>

      <div style={{ background: '#f0f5ff', padding: 12, borderRadius: 4, marginTop: 16 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          <strong>配置说明：</strong>
          <br />
          1. 在飞书开放平台创建自建应用
          <br />
          2. 获取 App ID 和 App Secret
          <br />
          3. 授予应用"知识库"读取权限
          <br />
          4. 获取 Wiki 空间 ID（从知识库 URL 中获取）
        </Text>
      </div>
    </Modal>
  );

  // ============ 主渲染 ============
  return (
    <div style={{ padding: 24 }}>
      {onBack && (
        <Button
          icon={<DatabaseOutlined />}
          onClick={onBack}
          style={{ marginBottom: 16 }}
        >
          返回
        </Button>
      )}

      {/* 会话恢复提示 */}
      {hasSession && (
        <Alert
          message="检测到之前的配置会话"
          description="系统已自动恢复您上次的知识库配置状态。您可以直接继续配置，或点击下方按钮清除会话重新开始。"
          type="info"
          showIcon
          closable
          action={
            <Button
              size="small"
              onClick={() => {
                clearSession();
                message.info('已清除会话记录');
              }}
            >
              清除会话
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      <Title level={2}>知识库配置</Title>
      <Text type="secondary">
        管理知识源、配置各模块的知识库增强功能
      </Text>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{ marginTop: 24 }}
      >
        <TabPane tab="知识源管理" key="sources">
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {renderHealthStatus()}
            {renderSourcesTable()}
          </Space>
        </TabPane>

        <TabPane tab="模块偏好设置" key="preferences">
          {renderModulePreferences()}
        </TabPane>
      </Tabs>

      {renderFeishuModal()}
    </div>
  );
};

export default KnowledgeBaseConfigPage;
