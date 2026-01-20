// frontend/src/pages/admin/views/ReviewRulesManager.tsx
import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Space,
  message,
  Tag,
  Popconfirm,
  Switch,
  InputNumber,
  Row,
  Col,
  Divider
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  ImportOutlined
} from '@ant-design/icons';
import api from '../../../api';

const { TextArea } = Input;
const { Option } = Select;

interface ReviewRule {
  id: number;
  name: string;
  description?: string;
  content: string;
  rule_category: 'universal' | 'feature' | 'stance' | 'custom';
  priority: number;
  is_active: boolean;
  is_system: boolean;
  creator_id?: number;
  created_at: string;
}

const ReviewRulesManager: React.FC = () => {
  const [rules, setRules] = useState<ReviewRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<ReviewRule | null>(null);
  const [form] = Form.useForm();
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [migrating, setMigrating] = useState(false);

  useEffect(() => {
    fetchRules();
  }, [categoryFilter]);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const params = categoryFilter ? { rule_category: categoryFilter } : {};
      const response = await api.get('/api/v1/admin/rules', { params });
      setRules(response.data.items || []); // API 返回 {items: [], total: n, page: n, size: n}
    } catch (error: any) {
      message.error(error.response?.data?.detail || '获取规则列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleMigrateFromJson = async () => {
    setMigrating(true);
    try {
      const response = await api.post('/api/v1/admin/rules/migrate-from-json');
      message.success(`迁移成功！${response.data.message}`);
      fetchRules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '迁移失败');
    } finally {
      setMigrating(false);
    }
  };

  const handleCreate = () => {
    setEditingRule(null);
    form.resetFields();
    form.setFieldsValue({
      rule_category: 'custom',
      is_system: false,
      priority: 0,
      is_active: true
    });
    setModalVisible(true);
  };

  const handleEdit = (rule: ReviewRule) => {
    setEditingRule(rule);
    form.setFieldsValue(rule);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      console.log(`[删除规则] 开始删除规则 ID: ${id}`);
      const response = await api.delete(`/api/v1/admin/rules/${id}`);
      console.log(`[删除规则] 删除成功:`, response.data);
      message.success(`删除成功: ${response.data.message || '规则已删除'}`);
      fetchRules();
    } catch (error: any) {
      console.error(`[删除规则] 删除失败:`, error);
      console.error(`[删除规则] 错误详情:`, error.response?.data);
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const handleToggle = async (id: number) => {
    try {
      await api.put(`/api/v1/admin/rules/${id}/toggle`);
      message.success('状态更新成功');
      fetchRules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '更新失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingRule) {
        await api.put(`/api/v1/admin/rules/${editingRule.id}`, values);
        message.success('更新成功');
      } else {
        await api.post('/api/v1/admin/rules', values);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchRules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const getCategoryName = (category: string) => {
    const map: Record<string, string> = {
      'universal': '通用规则',
      'feature': '特征规则',
      'stance': '立场规则',
      'custom': '自定义规则'
    };
    return map[category] || category;
  };

  const getCategoryColor = (category: string) => {
    const map: Record<string, string> = {
      'universal': 'blue',
      'feature': 'purple',
      'stance': 'orange',
      'custom': 'green'
    };
    return map[category] || 'default';
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 60,
      key: 'id'
    },
    {
      title: '规则名称',
      dataIndex: 'name',
      key: 'name',
      width: 300,
      render: (name: string, record: ReviewRule) => (
        <Space direction="vertical" size={0}>
          <Space>
            {name}
            {record.is_system && <Tag color="purple">系统</Tag>}
          </Space>
          {record.description && (
            <div style={{ fontSize: '12px', color: '#999' }}>
              {record.description}
            </div>
          )}
        </Space>
      )
    },
    {
      title: '类别',
      dataIndex: 'rule_category',
      key: 'rule_category',
      width: 120,
      render: (category: string) => (
        <Tag color={getCategoryColor(category)}>
          {getCategoryName(category)}
        </Tag>
      ),
      filters: [
        { text: '通用规则', value: 'universal' },
        { text: '特征规则', value: 'feature' },
        { text: '立场规则', value: 'stance' },
        { text: '自定义规则', value: 'custom' }
      ]
    },
    {
      title: '规则内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (content: string) => (
        <div style={{ fontSize: '12px', color: '#666' }} title={content}>
          {content.length > 80 ? content.substring(0, 80) + '...' : content}
        </div>
      )
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      width: 80,
      key: 'priority',
      sorter: (a: ReviewRule, b: ReviewRule) => a.priority - b.priority
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      key: 'is_active',
      render: (active: boolean) => (
        active ? <Tag color="success" icon={<CheckCircleOutlined />}>启用</Tag> : <Tag color="default" icon={<CloseCircleOutlined />}>禁用</Tag>
      )
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      fixed: 'right' as const,
      render: (_: any, record: ReviewRule) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Button
            type="text"
            size="small"
            onClick={() => handleToggle(record.id)}
          >
            {record.is_active ? '禁用' : '启用'}
          </Button>
          <Popconfirm
            title="确定删除此规则吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              size="small"
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
    <div>
      <Card
        title="审查规则管理"
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchRules}
            >
              刷新
            </Button>
            <Popconfirm
              title="从 JSON 文件迁移规则到数据库"
              description="这将清除现有的系统规则，然后从 review_rules.json 文件导入新的规则。"
              onConfirm={handleMigrateFromJson}
              okText="确定迁移"
              cancelText="取消"
            >
              <Button
                icon={<ImportOutlined />}
                loading={migrating}
              >
                从 JSON 迁移规则
              </Button>
            </Popconfirm>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              新建规则
            </Button>
          </Space>
        }
      >
        <div style={{ marginBottom: 16 }}>
          <Space>
            <span>筛选：</span>
            <Select
              style={{ width: 150 }}
              placeholder="选择类别"
              allowClear
              value={categoryFilter}
              onChange={setCategoryFilter}
            >
              <Option value="universal">通用规则</Option>
              <Option value="feature">特征规则</Option>
              <Option value="stance">立场规则</Option>
              <Option value="custom">自定义规则</Option>
            </Select>
          </Space>
        </div>

        <Divider orientation="left">规则说明</Divider>
        <div style={{ marginBottom: 16, padding: '12px', background: '#f5f5f5', borderRadius: '4px', fontSize: '13px' }}>
          <Space direction="vertical" size={4}>
            <div><strong>通用规则</strong>：适用于所有合同的基础审查（如形式质量、定义一致性、争议解决等）</div>
            <div><strong>特征规则</strong>：基于交易性质（转移所有权、提供服务等）和合同标的（不动产、动产等）的专项规则</div>
            <div><strong>立场规则</strong>：根据甲方/乙方立场的防御性审查规则</div>
            <div><strong>自定义规则</strong>：用户个人定制的审查规则</div>
          </Space>
        </div>

        <Table
          columns={columns}
          dataSource={rules}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1200 }}
        />
      </Card>

      <Modal
        title={editingRule ? '编辑规则' : '新建规则'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={800}
        okText="确定"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          autoComplete="off"
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="规则名称"
                name="name"
                rules={[{ required: true, message: '请输入规则名称' }]}
              >
                <Input placeholder="如：付款节点审查" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="规则类别"
                name="rule_category"
                rules={[{ required: true, message: '请选择规则类别' }]}
              >
                <Select>
                  <Option value="universal">通用规则</Option>
                  <Option value="feature">特征规则</Option>
                  <Option value="stance">立场规则</Option>
                  <Option value="custom">自定义规则</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="规则描述"
            name="description"
          >
            <Input placeholder="简要描述此规则的用途" />
          </Form.Item>

          <Form.Item
            label="优先级"
            name="priority"
            tooltip="数字越小越优先"
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            label="是否为系统规则"
            name="is_system"
            valuePropName="checked"
            tooltip="系统规则仅管理员可编辑"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            label="是否启用"
            name="is_active"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            label="规则内容"
            name="content"
            rules={[{ required: true, message: '请输入规则内容' }]}
            tooltip="详细的审查规则说明，将用于 AI 审查提示"
          >
            <TextArea
              rows={10}
              placeholder="请输入详细的审查规则内容，包括审查要点、判断标准等..."
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ReviewRulesManager;
