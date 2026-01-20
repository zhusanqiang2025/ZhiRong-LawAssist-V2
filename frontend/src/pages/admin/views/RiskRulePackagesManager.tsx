// frontend/src/pages/admin/views/RiskRulePackagesManager.tsx
import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  message,
  Popconfirm,
  Tooltip,
  Divider,
  List,
  Badge,
  Row,
  Col,
  Typography
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MinusCircleOutlined,
  PlusCircleOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { riskRulePackagesApi } from '../../../api/riskRulePackages';
import type { RiskRulePackage, RiskRule } from '../../../types/riskAnalysis';
import { RULE_PACKAGE_CATEGORIES } from '../../../types/riskAnalysis';

const { TextArea } = Input;
const { Option } = Select;
const { Title, Text } = Typography;

const RiskRulePackagesManager: React.FC = () => {
  const [packages, setPackages] = useState<RiskRulePackage[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [modalVisible, setModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [currentPackage, setCurrentPackage] = useState<RiskRulePackage | null>(null);
  const [editingRules, setEditingRules] = useState<RiskRule[]>([]);
  const [form] = Form.useForm();

  // 加载规则包列表
  const loadPackages = async () => {
    setLoading(true);
    try {
      const data = await riskRulePackagesApi.listPackages(categoryFilter);
      setPackages(data.packages);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载规则包失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPackages();
  }, [categoryFilter]);

  // 切换状态
  const handleToggleStatus = async (pkg: RiskRulePackage) => {
    try {
      await riskRulePackagesApi.togglePackageStatus(pkg.package_id, !pkg.is_active);
      message.success('状态更新成功');
      loadPackages();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '状态更新失败');
    }
  };

  // 删除规则包
  const handleDelete = async (packageId: string) => {
    try {
      await riskRulePackagesApi.deletePackage(packageId);
      message.success('删除成功');
      loadPackages();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 编辑规则包
  const handleEdit = (pkg: RiskRulePackage) => {
    setCurrentPackage(pkg);
    form.setFieldsValue({
      package_name: pkg.package_name,
      package_category: pkg.package_category,
      description: pkg.description,
      applicable_scenarios: pkg.applicable_scenarios || [],
      target_entities: pkg.target_entities || [],
      is_active: pkg.is_active,
      version: pkg.version,
      rules: pkg.rules || []
    });
    // 加载规则列表
    setEditingRules(pkg.rules || []);
    setModalVisible(true);
  };

  // 查看详情
  const handleViewDetail = (pkg: RiskRulePackage) => {
    setCurrentPackage(pkg);
    setDetailModalVisible(true);
  };

  // 创建新规则包
  const handleCreate = () => {
    setCurrentPackage(null);
    form.resetFields();
    form.setFieldsValue({
      package_category: 'equity_risk',
      is_active: true,
      version: '1.0.0',
      rules: []
    });
    setEditingRules([]);
    setModalVisible(true);
  };

  // 添加规则
  const handleAddRule = () => {
    const newRule: RiskRule = {
      rule_id: `RULE_${Date.now()}`,
      rule_name: '',
      rule_prompt: '',
      priority: 5,
      risk_type: '',
      default_risk_level: 'medium'
    };
    setEditingRules([...editingRules, newRule]);
  };

  // 更新规则
  const handleUpdateRule = (index: number, field: keyof RiskRule, value: any) => {
    const updatedRules = [...editingRules];
    updatedRules[index] = {
      ...updatedRules[index],
      [field]: value
    };
    setEditingRules(updatedRules);
  };

  // 删除规则
  const handleDeleteRule = (index: number) => {
    const updatedRules = editingRules.filter((_, i) => i !== index);
    setEditingRules(updatedRules);
  };

  // 保存规则包
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      // 使用 editingRules 而不是 form 中的 rules
      const submitData = {
        ...values,
        rules: editingRules
      };

      if (currentPackage) {
        // 更新
        await riskRulePackagesApi.updatePackage(currentPackage.package_id, submitData);
        message.success('更新成功');
      } else {
        // 创建
        await riskRulePackagesApi.createPackage(submitData);
        message.success('创建成功');
      }

      setModalVisible(false);
      setEditingRules([]);
      loadPackages();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  // 获取分类名称
  const getCategoryName = (category: string) => {
    const found = RULE_PACKAGE_CATEGORIES.find(c => c.value === category);
    return found?.label || category;
  };

  // 获取分类颜色
  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'equity_risk': 'purple',
      'investment_risk': 'blue',
      'governance_risk': 'orange',
      'contract_risk': 'red',
      'tax_risk': 'green'
    };
    return colors[category] || 'default';
  };

  // 表格列定义
  const columns: ColumnsType<RiskRulePackage> = [
    {
      title: '规则包ID',
      dataIndex: 'package_id',
      key: 'package_id',
      width: 200,
      render: (text) => <code>{text}</code>
    },
    {
      title: '规则包名称',
      dataIndex: 'package_name',
      key: 'package_name',
      width: 200,
      render: (name: string, record: RiskRulePackage) => (
        <Space direction="vertical" size={0}>
          <Space>
            {name}
            {record.is_system && <Tag color="purple">系统</Tag>}
          </Space>
          {record.description && (
            <div style={{ fontSize: '12px', color: '#999' }}>
              {record.description.length > 50
                ? record.description.substring(0, 50) + '...'
                : record.description}
            </div>
          )}
        </Space>
      )
    },
    {
      title: '分类',
      dataIndex: 'package_category',
      key: 'package_category',
      width: 120,
      render: (category) => (
        <Tag color={getCategoryColor(category)}>
          {getCategoryName(category)}
        </Tag>
      )
    },
    {
      title: '规则数量',
      dataIndex: 'rules',
      key: 'rule_count',
      width: 100,
      render: (rules: RiskRule[]) => <Badge count={rules?.length || 0} showZero />
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80,
      render: (version: string) => version || '-'
    },
    {
      title: '系统预定义',
      dataIndex: 'is_system',
      key: 'is_system',
      width: 100,
      render: (isSystem: boolean) => (
        <Tag color={isSystem ? 'gold' : 'default'}>
          {isSystem ? '是' : '否'}
        </Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (isActive: boolean, record: RiskRulePackage) => (
        <Switch
          checked={isActive}
          onChange={() => handleToggleStatus(record)}
          checkedChildren="启用"
          unCheckedChildren="禁用"
        />
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right' as const,
      render: (_, record: RiskRulePackage) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record)}
            >
              详情
            </Button>
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            >
              编辑
            </Button>
          </Tooltip>
          <Popconfirm
            title={record.is_system ? "这是系统预定义规则包，确定要删除吗？" : "确定要删除这个规则包吗？"}
            onConfirm={() => handleDelete(record.package_id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <Card
      title="风险评估规则包管理"
      extra={
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={loadPackages}
          >
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreate}
          >
            创建规则包
          </Button>
        </Space>
      }
    >
      <div style={{ marginBottom: 16 }}>
        <Space>
          <span>筛选分类：</span>
          <Select
            style={{ width: 200 }}
            placeholder="全部"
            allowClear
            value={categoryFilter}
            onChange={setCategoryFilter}
          >
            {RULE_PACKAGE_CATEGORIES.map(opt => (
              <Option key={opt.value} value={opt.value}>
                {opt.label}
              </Option>
            ))}
          </Select>
        </Space>
      </div>

      <Divider orientation="left">规则说明</Divider>
      <div style={{
        marginBottom: 16,
        padding: '12px',
        background: '#f5f5f5',
        borderRadius: '4px',
        fontSize: '13px'
      }}>
        <Space direction="vertical" size={4}>
          <div><strong>股权风险</strong>：分析公司股权结构、识别控制权和关联交易风险</div>
          <div><strong>投资风险</strong>：评估投资项目的市场、财务、法律合规、运营等风险</div>
          <div><strong>治理风险</strong>：识别公司人格混同、内部控制等治理结构风险</div>
          <div><strong>合同风险</strong>：识别合同条款中的法律风险点</div>
          <div><strong>税务风险</strong>：识别税务相关的潜在风险</div>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={packages}
        rowKey="package_id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        scroll={{ x: 1200 }}
      />

      {/* 详情弹窗 */}
      <Modal
        title="规则包详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={800}
      >
        {currentPackage && (
          <div>
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <div>
                <h4>基本信息</h4>
                <p><strong>规则包ID：</strong><code>{currentPackage.package_id}</code></p>
                <p><strong>规则包名称：</strong>{currentPackage.package_name}</p>
                <p><strong>分类：</strong>
                  <Tag color={getCategoryColor(currentPackage.package_category)}>
                    {getCategoryName(currentPackage.package_category)}
                  </Tag>
                </p>
                <p><strong>描述：</strong>{currentPackage.description || '无'}</p>
                <p><strong>版本：</strong>{currentPackage.version || '无'}</p>
                <p><strong>状态：</strong>
                  {currentPackage.is_active
                    ? <Tag icon={<CheckCircleOutlined />} color="success">启用</Tag>
                    : <Tag icon={<CloseCircleOutlined />}>禁用</Tag>
                  }
                </p>
                <p><strong>系统预定义：</strong>{currentPackage.is_system ? '是' : '否'}</p>
              </div>

              <div>
                <h4>适用信息</h4>
                <p><strong>适用场景：</strong>{currentPackage.applicable_scenarios?.join(', ') || '无'}</p>
                <p><strong>目标实体：</strong>{currentPackage.target_entities?.join(', ') || '无'}</p>
              </div>

              <div>
                <h4>规则列表（{currentPackage.rules?.length || 0} 条）</h4>
                <List
                  dataSource={currentPackage.rules || []}
                  renderItem={(rule: RiskRule, index: number) => (
                    <List.Item>
                      <List.Item.Meta
                        title={
                          <Space>
                            <Badge count={index + 1} />
                            <strong>{rule.rule_name}</strong>
                            <Tag color="blue">优先级: {rule.priority}</Tag>
                          </Space>
                        }
                        description={
                          <div style={{ marginTop: 8 }}>
                            <p style={{ margin: 0, color: '#666' }}>{rule.rule_prompt}</p>
                          </div>
                        }
                      />
                    </List.Item>
                  )}
                />
              </div>

              <div>
                <h4>时间信息</h4>
                <p><strong>创建时间：</strong>{new Date(currentPackage.created_at).toLocaleString()}</p>
                <p><strong>更新时间：</strong>{new Date(currentPackage.updated_at).toLocaleString()}</p>
              </div>
            </Space>
          </div>
        )}
      </Modal>

      {/* 编辑/创建弹窗 */}
      <Modal
        title={currentPackage ? '编辑规则包' : '创建规则包'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => {
          setModalVisible(false);
          setCurrentPackage(null);
          form.resetFields();
          setEditingRules([]);
        }}
        width={1000}
        okText="确定"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="规则包名称"
                name="package_name"
                rules={[{ required: true, message: '请输入规则包名称' }]}
              >
                <Input placeholder="如：股权穿透风险评估规则包" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="分类"
                name="package_category"
                rules={[{ required: true, message: '请选择分类' }]}
              >
                <Select>
                  {RULE_PACKAGE_CATEGORIES.map(opt => (
                    <Option key={opt.value} value={opt.value}>
                      {opt.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="描述"
            name="description"
          >
            <TextArea
              rows={2}
              placeholder="简要描述此规则包的用途和适用场景"
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="适用场景"
                name="applicable_scenarios"
              >
                <Select
                  mode="tags"
                  placeholder="输入适用场景"
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="目标实体"
                name="target_entities"
              >
                <Select
                  mode="tags"
                  placeholder="输入目标实体类型"
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="版本号"
                name="version"
              >
                <Input placeholder="如：1.0.0" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="状态"
                name="is_active"
                valuePropName="checked"
              >
                <Switch
                  checkedChildren="启用"
                  unCheckedChildren="禁用"
                />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left">
            <Space>
              <span>风险规则列表</span>
              <Badge count={editingRules.length} showZero />
            </Space>
          </Divider>

          <div style={{ marginBottom: 16 }}>
            <Button
              type="dashed"
              onClick={handleAddRule}
              block
              icon={<PlusOutlined />}
            >
              添加规则
            </Button>
          </div>

          {editingRules.length > 0 ? (
            <List
              dataSource={editingRules}
              renderItem={(rule, index) => (
                <List.Item
                  key={index}
                  style={{
                    border: '1px solid #d9d9d9',
                    borderRadius: '4px',
                    marginBottom: '8px',
                    padding: '12px',
                    backgroundColor: '#fafafa'
                  }}
                >
                  <List.Item.Meta
                    title={
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Row gutter={8} align="middle">
                          <Col span={6}>
                            <Text strong>规则ID:</Text>
                            <Input
                              size="small"
                              value={rule.rule_id}
                              onChange={(e) => handleUpdateRule(index, 'rule_id', e.target.value)}
                              placeholder="如：RISK001"
                              style={{ marginTop: 4 }}
                            />
                          </Col>
                          <Col span={18}>
                            <Text strong>规则名称:</Text>
                            <Input
                              size="small"
                              value={rule.rule_name}
                              onChange={(e) => handleUpdateRule(index, 'rule_name', e.target.value)}
                              placeholder="规则名称"
                              style={{ marginTop: 4 }}
                            />
                          </Col>
                        </Row>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" style={{ width: '100%' }} size="small">
                        <div>
                          <Text type="secondary">规则提示词：</Text>
                          <TextArea
                            size="small"
                            rows={2}
                            value={rule.rule_prompt}
                            onChange={(e) => handleUpdateRule(index, 'rule_prompt', e.target.value)}
                            placeholder="描述规则的具体内容和检查要点"
                            style={{ marginTop: 4 }}
                          />
                        </div>
                        <Row gutter={8}>
                          <Col span={6}>
                            <Text type="secondary">优先级:</Text>
                            <Input
                              type="number"
                              size="small"
                              value={rule.priority}
                              onChange={(e) => handleUpdateRule(index, 'priority', parseInt(e.target.value) || 1)}
                              min={1}
                              max={10}
                              style={{ marginTop: 4 }}
                            />
                          </Col>
                          <Col span={6}>
                            <Text type="secondary">风险类型:</Text>
                            <Input
                              size="small"
                              value={rule.risk_type}
                              onChange={(e) => handleUpdateRule(index, 'risk_type', e.target.value)}
                              placeholder="如：control_risk"
                              style={{ marginTop: 4 }}
                            />
                          </Col>
                          <Col span={6}>
                            <Text type="secondary">默认风险等级:</Text>
                            <Select
                              size="small"
                              value={rule.default_risk_level}
                              onChange={(value) => handleUpdateRule(index, 'default_risk_level', value)}
                              style={{ width: '100%', marginTop: 4 }}
                            >
                              <Option value="critical">严重</Option>
                              <Option value="high">高</Option>
                              <Option value="medium">中</Option>
                              <Option value="low">低</Option>
                            </Select>
                          </Col>
                          <Col span={6}>
                            <Button
                              type="text"
                              danger
                              size="small"
                              icon={<DeleteOutlined />}
                              onClick={() => handleDeleteRule(index)}
                              style={{ marginTop: 4 }}
                            >
                              删除此规则
                            </Button>
                          </Col>
                        </Row>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          ) : (
            <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
              暂无规则，点击上方按钮添加
            </div>
          )}
        </Form>
      </Modal>
    </Card>
  );
};

export default RiskRulePackagesManager;
