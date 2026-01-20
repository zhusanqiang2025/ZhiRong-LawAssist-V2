// frontend/src/pages/admin/views/LitigationRulePackagesManager.tsx
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
  Typography,
  InputNumber
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
import { litigationRulePackagesApi } from '../../../api/litigationRulePackages';
import type { LitigationRulePackage, LitigationRule } from '../../../api/litigationRulePackages';
import {
  LITIGATION_PACKAGE_CATEGORIES,
  LITIGATION_CASE_TYPES,
  LITIGATION_POSITIONS,
  TARGET_DOCUMENT_TYPES
} from '../../../api/litigationRulePackages';

const { TextArea } = Input;
const { Option } = Select;
const { Title, Text } = Typography;

const LitigationRulePackagesManager: React.FC = () => {
  const [packages, setPackages] = useState<LitigationRulePackage[]>([]);
  const [loading, setLoading] = useState(false);
  const [caseTypeFilter, setCaseTypeFilter] = useState<string | undefined>();
  const [modalVisible, setModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [currentPackage, setCurrentPackage] = useState<LitigationRulePackage | null>(null);
  const [editingRules, setEditingRules] = useState<LitigationRule[]>([]);
  const [form] = Form.useForm();

  // 加载规则包列表
  const loadPackages = async () => {
    setLoading(true);
    try {
      const data = await litigationRulePackagesApi.listPackages(caseTypeFilter);
      setPackages(data.packages);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载规则包失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPackages();
  }, [caseTypeFilter]);

  // 切换状态
  const handleToggleStatus = async (pkg: LitigationRulePackage) => {
    try {
      await litigationRulePackagesApi.togglePackageStatus(pkg.package_id);
      message.success('状态更新成功');
      loadPackages();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '状态更新失败');
    }
  };

  // 删除规则包
  const handleDelete = async (packageId: string) => {
    try {
      await litigationRulePackagesApi.deletePackage(packageId);
      message.success('删除成功');
      loadPackages();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 编辑规则包
  const handleEdit = (pkg: LitigationRulePackage) => {
    setCurrentPackage(pkg);
    form.setFieldsValue({
      package_name: pkg.package_name,
      package_category: pkg.package_category,
      case_type: pkg.case_type,
      description: pkg.description,
      applicable_positions: pkg.applicable_positions,
      target_documents: pkg.target_documents,
      is_active: pkg.is_active,
      version: pkg.version
    });
    setEditingRules(pkg.rules || []);
    setModalVisible(true);
  };

  // 查看规则包详情
  const handleViewDetail = (pkg: LitigationRulePackage) => {
    setCurrentPackage(pkg);
    setDetailModalVisible(true);
  };

  // 新建规则包
  const handleCreate = () => {
    setCurrentPackage(null);
    form.resetFields();
    setEditingRules([
      { rule_id: '', rule_name: '', rule_prompt: '', priority: 10 }
    ]);
    setModalVisible(true);
  };

  // 保存规则包
  const handleSave = async () => {
    try {
      const values = await form.validateFields();

      const packageData = {
        package_id: currentPackage?.package_id || values.package_name.toLowerCase().replace(/\s+/g, '_'),
        ...values,
        rules: editingRules
      };

      if (currentPackage) {
        await litigationRulePackagesApi.updatePackage(currentPackage.package_id, packageData);
        message.success('更新成功');
      } else {
        await litigationRulePackagesApi.createPackage(packageData);
        message.success('创建成功');
      }

      setModalVisible(false);
      loadPackages();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '保存失败');
    }
  };

  // 添加规则
  const handleAddRule = () => {
    setEditingRules([
      ...editingRules,
      {
        rule_id: `RULE${String(editingRules.length + 1).padStart(3, '0')}`,
        rule_name: '',
        rule_prompt: '',
        priority: 10
      }
    ]);
  };

  // 删除规则
  const handleRemoveRule = (index: number) => {
    const newRules = editingRules.filter((_, i) => i !== index);
    setEditingRules(newRules);
  };

  // 更新规则字段
  const handleUpdateRule = (index: number, field: keyof LitigationRule, value: any) => {
    const newRules = [...editingRules];
    newRules[index] = { ...newRules[index], [field]: value };
    setEditingRules(newRules);
  };

  const columns: ColumnsType<LitigationRulePackage> = [
    {
      title: '规则包ID',
      dataIndex: 'package_id',
      key: 'package_id',
      width: 200,
      ellipsis: true,
      render: (text, record) => (
        <Space>
          {record.is_system && <Tag color="gold">系统</Tag>}
          <Text code copyable>{text}</Text>
        </Space>
      )
    },
    {
      title: '规则包名称',
      dataIndex: 'package_name',
      key: 'package_name',
      width: 200,
      ellipsis: { showTitle: false },
      render: (text) => (
        <Tooltip placement="topLeft" title={text}>
          {text}
        </Tooltip>
      )
    },
    {
      title: '分类',
      dataIndex: 'package_category',
      key: 'package_category',
      width: 120,
      render: (category) => {
        const cat = LITIGATION_PACKAGE_CATEGORIES.find(c => c.value === category);
        return <Tag color="blue">{cat?.label || category}</Tag>;
      }
    },
    {
      title: '案件类型',
      dataIndex: 'case_type',
      key: 'case_type',
      width: 150,
      render: (caseType) => {
        const ct = LITIGATION_CASE_TYPES.find(c => c.value === caseType);
        return <Tag color="cyan">{ct?.label || caseType}</Tag>;
      }
    },
    {
      title: '规则数量',
      dataIndex: 'rules',
      key: 'rules',
      width: 100,
      render: (rules) => (
        <Badge count={rules?.length || 0} showZero style={{ backgroundColor: '#52c41a' }} />
      )
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (active, record) => (
        <Tooltip title={record.is_system ? '系统规则包不能修改状态' : ''}>
          <Switch
            checked={active}
            onChange={() => handleToggleStatus(record)}
            disabled={record.is_system}
            checkedChildren="启用"
            unCheckedChildren="禁用"
          />
        </Tooltip>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right' as const,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record)}
            />
          </Tooltip>
          {!record.is_system && (
            <>
              <Tooltip title="编辑">
                <Button
                  type="text"
                  icon={<EditOutlined />}
                  onClick={() => handleEdit(record)}
                />
              </Tooltip>
              <Popconfirm
                title="确定要删除这个规则包吗？"
                onConfirm={() => handleDelete(record.package_id)}
                okText="确定"
                cancelText="取消"
              >
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                />
              </Popconfirm>
            </>
          )}
        </Space>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <Space>
            <Title level={4} style={{ margin: 0 }}>
              案件分析规则包管理
            </Title>
            <Text type="secondary">（共 {packages.length} 个规则包）</Text>
          </Space>
        }
        extra={
          <Space>
            <Select
              placeholder="筛选案件类型"
              style={{ width: 200 }}
              allowClear
              onChange={setCaseTypeFilter}
            >
              {LITIGATION_CASE_TYPES.map(ct => (
                <Option key={ct.value} value={ct.value}>
                  {ct.label}
                </Option>
              ))}
            </Select>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadPackages}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              新建规则包
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={packages}
          rowKey="package_id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* 编辑/新建规则包 Modal */}
      <Modal
        title={
          <Space>
            {currentPackage ? <EditOutlined /> : <PlusOutlined />}
            <span>{currentPackage ? '编辑规则包' : '新建规则包'}</span>
          </Space>
        }
        open={modalVisible}
        onOk={handleSave}
        onCancel={() => setModalVisible(false)}
        width={900}
        okText="保存"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            is_active: true,
            version: '1.0',
            applicable_positions: ['plaintiff'],
            target_documents: ['contract']
          }}
        >
          {!currentPackage && (
            <Form.Item
              name="package_name"
              label="规则包名称"
              rules={[{ required: true, message: '请输入规则包名称' }]}
            >
              <Input placeholder="例如：合同履约分析规则包" />
            </Form.Item>
          )}

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="package_category"
                label="规则包分类"
                rules={[{ required: true, message: '请选择分类' }]}
              >
                <Select placeholder="选择分类">
                  {LITIGATION_PACKAGE_CATEGORIES.map(cat => (
                    <Option key={cat.value} value={cat.value}>
                      {cat.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="case_type"
                label="案件类型"
                rules={[{ required: true, message: '请选择案件类型' }]}
              >
                <Select placeholder="选择案件类型">
                  {LITIGATION_CASE_TYPES.map(ct => (
                    <Option key={ct.value} value={ct.value}>
                      {ct.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="description"
            label="规则包描述"
          >
            <TextArea
              rows={3}
              placeholder="描述这个规则包的用途和适用场景"
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="applicable_positions"
                label="适用诉讼地位"
                rules={[{ required: true, message: '请选择适用诉讼地位' }]}
              >
                <Select mode="multiple" placeholder="选择适用诉讼地位">
                  {LITIGATION_POSITIONS.map(pos => (
                    <Option key={pos.value} value={pos.value}>
                      {pos.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="target_documents"
                label="目标文档类型"
                rules={[{ required: true, message: '请选择目标文档类型' }]}
              >
                <Select mode="multiple" placeholder="选择目标文档类型">
                  {TARGET_DOCUMENT_TYPES.map(doc => (
                    <Option key={doc.value} value={doc.value}>
                      {doc.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="version"
                label="版本号"
                rules={[{ required: true, message: '请输入版本号' }]}
              >
                <Input placeholder="1.0" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="is_active"
                label="是否启用"
                valuePropName="checked"
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left">分析规则</Divider>

          <List
            dataSource={editingRules}
            renderItem={(rule, index) => (
              <List.Item
                key={index}
                style={{
                  border: '1px solid #f0f0f0',
                  borderRadius: 8,
                  marginBottom: 16,
                  padding: 16,
                  backgroundColor: '#fafafa'
                }}
              >
                <Row gutter={[16, 16]} style={{ width: '100%' }}>
                  <Col span={6}>
                    <div style={{ marginBottom: 8 }}>
                      <Text strong>规则ID</Text>
                    </div>
                    <Input
                      value={rule.rule_id}
                      onChange={(e) => handleUpdateRule(index, 'rule_id', e.target.value)}
                      placeholder="RULE001"
                    />
                  </Col>
                  <Col span={18}>
                    <div style={{ marginBottom: 8 }}>
                      <Text strong>规则名称</Text>
                    </div>
                    <Input
                      value={rule.rule_name}
                      onChange={(e) => handleUpdateRule(index, 'rule_name', e.target.value)}
                      placeholder="规则名称"
                    />
                  </Col>
                  <Col span={24}>
                    <div style={{ marginBottom: 8 }}>
                      <Text strong>规则提示词</Text>
                    </div>
                    <TextArea
                      rows={2}
                      value={rule.rule_prompt}
                      onChange={(e) => handleUpdateRule(index, 'rule_prompt', e.target.value)}
                      placeholder="规则的分析提示词"
                    />
                  </Col>
                  <Col span={18}>
                    <div style={{ marginBottom: 8 }}>
                      <Text strong>优先级</Text>
                    </div>
                    <InputNumber
                      min={1}
                      max={10}
                      value={rule.priority}
                      onChange={(value) => handleUpdateRule(index, 'priority', value || 10)}
                      style={{ width: '100%' }}
                    />
                  </Col>
                  <Col span={6} style={{ textAlign: 'right' }}>
                    <Button
                      type="text"
                      danger
                      icon={<MinusCircleOutlined />}
                      onClick={() => handleRemoveRule(index)}
                    >
                      删除规则
                    </Button>
                  </Col>
                </Row>
              </List.Item>
            )}
          />

          <Button
            type="dashed"
            onClick={handleAddRule}
            block
            icon={<PlusCircleOutlined />}
          >
            添加分析规则
          </Button>
        </Form>
      </Modal>

      {/* 查看详情 Modal */}
      <Modal
        title={
          <Space>
            <EyeOutlined />
            <span>规则包详情</span>
          </Space>
        }
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={900}
      >
        {currentPackage && (
          <div>
            <Descriptions
              column={2}
              items={[
                { label: '规则包ID', children: <Text code>{currentPackage.package_id}</Text> },
                { label: '规则包名称', children: currentPackage.package_name },
                { label: '分类', children: <Tag color="blue">{currentPackage.package_category}</Tag> },
                { label: '案件类型', children: <Tag color="cyan">{currentPackage.case_type}</Tag> },
                { label: '版本', children: currentPackage.version },
                {
                  label: '状态',
                  children: currentPackage.is_active
                    ? <Tag color="success" icon={<CheckCircleOutlined />}>启用</Tag>
                    : <Tag color="default" icon={<CloseCircleOutlined />}>禁用</Tag>
                },
                {
                  label: '类型',
                  children: currentPackage.is_system
                    ? <Tag color="gold">系统预定义</Tag>
                    : <Tag color="blue">用户自定义</Tag>
                },
                {
                  label: '创建时间',
                  children: currentPackage.created_at
                    ? new Date(currentPackage.created_at).toLocaleString('zh-CN')
                    : '-'
                },
                {
                  label: '适用诉讼地位',
                  children: currentPackage.applicable_positions?.map(pos => {
                    const p = LITIGATION_POSITIONS.find(item => item.value === pos);
                    return <Tag key={pos}>{p?.label || pos}</Tag>;
                  })
                },
                {
                  label: '目标文档',
                  children: currentPackage.target_documents?.map(doc => {
                    const d = TARGET_DOCUMENT_TYPES.find(item => item.value === doc);
                    return <Tag key={doc}>{d?.label || doc}</Tag>;
                  })
                },
                { label: '描述', children: currentPackage.description, span: 2 }
              ]}
            />

            <Divider orientation="left">分析规则列表</Divider>

            <List
              dataSource={currentPackage.rules}
              renderItem={(rule) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<Badge count={rule.priority} style={{ backgroundColor: '#52c41a' }} />}
                    title={
                      <Space>
                        <Text code>{rule.rule_id}</Text>
                        <Text strong>{rule.rule_name}</Text>
                      </Space>
                    }
                    description={rule.rule_prompt}
                  />
                </List.Item>
              )}
            />
          </div>
        )}
      </Modal>
    </div>
  );
};

// 内联 Descriptions 组件以避免导入问题
const Descriptions: React.FC<{
  column: number;
  items: Array<{
    label: string;
    children: React.ReactNode;
    span?: number;
  }>;
}> = ({ column, items }) => (
  <div style={{ display: 'grid', gridTemplateColumns: `repeat(${column}, 1fr)`, gap: 16 }}>
    {items.map((item, index) => (
      <div key={index} style={item.span ? { gridColumn: `span ${item.span}` } : {}}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {item.label}
        </Text>
        <div style={{ marginTop: 4 }}>{item.children}</div>
      </div>
    ))}
  </div>
);

export default LitigationRulePackagesManager;
