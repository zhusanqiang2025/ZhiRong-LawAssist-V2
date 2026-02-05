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
  Divider,
  TreeSelect,
  Tooltip,
  Typography,
  Upload
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  ImportOutlined,
  InfoCircleOutlined,
  ClusterOutlined,
  DownloadOutlined
} from '@ant-design/icons';
// ✅ 使用通用的 api 实例 (axios wrapper)
import api from '../../../api';
import { systemApi } from '../../../api/system';

const { TextArea } = Input;
const { Option } = Select;
const { Text } = Typography;

// ==================== 接口定义 ====================

// 规则接口 (对应后端 Pydantic Schema)
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
  // Hub-and-Spoke 核心字段
  apply_to_category_ids?: number[]; 
  target_stance?: string;           
}

// 分类节点接口 (后端返回的 Tree Item)
interface CategoryNode {
  id: number;
  name: string;
  children?: CategoryNode[];
  [key: string]: any;
}

// ==================== 组件实现 ====================

const ReviewRulesManager: React.FC = () => {
  const [rules, setRules] = useState<ReviewRule[]>([]);
  
  // 分类数据状态
  const [treeData, setTreeData] = useState<any[]>([]); // 给 TreeSelect 用的数据
  const [flatCategories, setFlatCategories] = useState<Map<number, string>>(new Map()); // 给列表页用的 ID->Name 映射
  
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<ReviewRule | null>(null);
  const [form] = Form.useForm();
  
  // 监听表单值以实现动态联动 (Feature/Stance 显示不同选项)
  const ruleCategoryValue = Form.useWatch('rule_category', form);

  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [migrating, setMigrating] = useState(false);

  useEffect(() => {
    fetchRules();
    fetchCategories();
  }, [categoryFilter]);

  // 1. 获取规则列表
  const fetchRules = async () => {
    setLoading(true);
    try {
      const params = categoryFilter ? { rule_category: categoryFilter } : {};
      const response = await api.get('/admin/rules', { params });
      // 兼容后端返回 {items: [...], total: ...} 或直接 [...]
      const items = response.data.items || response.data || [];
      setRules(items);
    } catch (error: any) {
      console.error(error);
      message.error('获取规则列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 2. 获取分类树 (Hub 数据源)
  const fetchCategories = async () => {
    try {
      // ✅ 调用 V3 Tree 接口
      const response = await api.get('/categories/tree'); 
      const rawTree = response.data || [];
      
      // A. 转换为 Antd TreeSelect 格式
      const formattedTree = transformToTreeSelect(rawTree);
      setTreeData(formattedTree);
      
      // B. 拍平数据用于列表页 ID 转 Name
      const mapping = new Map<number, string>();
      flattenTreeToMap(rawTree, mapping);
      setFlatCategories(mapping);
      
    } catch (error) {
      console.warn("加载分类失败:", error);
      // 不阻断页面，只是下拉框会空
    }
  };

  // 辅助：递归转换后端数据 -> Antd 格式
  const transformToTreeSelect = (nodes: any[]): any[] => {
    return nodes.map(node => ({
      title: node.name,
      value: node.id,
      key: node.id,
      children: (node.children && node.children.length > 0) 
        ? transformToTreeSelect(node.children) 
        : []
    }));
  };

  // 辅助：递归提取 ID -> Name 映射
  const flattenTreeToMap = (nodes: any[], map: Map<number, string>) => {
    nodes.forEach(node => {
      map.set(node.id, node.name);
      if (node.children && node.children.length > 0) {
        flattenTreeToMap(node.children, map);
      }
    });
  };

  // 辅助：根据ID数组获取名称字符串
  const getCategoryNamesStr = (ids?: number[]) => {
    if (!ids || ids.length === 0) return [];
    return ids.map(id => flatCategories.get(id) || String(id));
  };

  // ==================== 操作处理 ====================

  const handleMigrateFromJson = async () => {
    setMigrating(true);
    try {
      const response = await api.post('/admin/rules/migrate-from-json');
      message.success(`迁移成功！${response.data.message}`);
      fetchRules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '迁移失败');
    } finally {
      setMigrating(false);
    }
  };

  // 导出规则配置
  const handleExport = async () => {
    try {
      const data = await systemApi.exportData('rules');
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
      systemApi.downloadAsJson(data, `review_rules_export_${timestamp}.json`);
      message.success('导出成功');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '导出失败');
    }
  };

  // 导入规则配置
  const handleImport = async (file: File) => {
    try {
      const result = await systemApi.importData(file);
      if (result.success) {
        message.success('导入成功');
        fetchRules();
      } else {
        message.error(result.message || '导入失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '导入失败');
    }
    return false;
  };

  const handleCreate = () => {
    setEditingRule(null);
    form.resetFields();
    form.setFieldsValue({
      rule_category: 'feature', // 默认引导创建特征规则
      is_system: true,
      priority: 10,
      is_active: true,
      apply_to_category_ids: [],
      target_stance: undefined
    });
    setModalVisible(true);
  };

  const handleEdit = (rule: ReviewRule) => {
    setEditingRule(rule);
    form.setFieldsValue({
      ...rule,
      // 确保 null 转为 undefined 或 空数组，防止 Antd 报错
      apply_to_category_ids: rule.apply_to_category_ids || [],
      target_stance: rule.target_stance || undefined
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/admin/rules/${id}`);
      message.success('规则已删除');
      fetchRules();
    } catch (error: any) {
      message.error('删除失败');
    }
  };

  const handleToggle = async (id: number) => {
    try {
      await api.put(`/admin/rules/${id}/toggle`);
      message.success('状态更新成功');
      fetchRules();
    } catch (error: any) {
      message.error('更新失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      // 数据清洗：如果是通用规则，强行清空绑定，避免脏数据
      if (values.rule_category === 'universal') {
        values.apply_to_category_ids = [];
        values.target_stance = null;
      }

      if (editingRule) {
        await api.put(`/admin/rules/${editingRule.id}`, values);
        message.success('更新成功');
      } else {
        await api.post('/admin/rules', values);
        message.success('创建成功');
      }
      
      setModalVisible(false);
      fetchRules();
    } catch (error: any) {
      console.error(error);
      message.error(error.response?.data?.detail || '操作失败');
    }
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

  // ==================== 表格列定义 ====================

  const columns = [
    {
      title: '规则名称',
      dataIndex: 'name',
      key: 'name',
      width: 220,
      render: (name: string, record: ReviewRule) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          {record.is_system && <Tag bordered={false} color="purple" style={{marginTop: 4}}>系统级</Tag>}
        </Space>
      )
    },
    {
      title: '类型',
      dataIndex: 'rule_category',
      key: 'rule_category',
      width: 100,
      render: (cat: string) => <Tag color={getCategoryColor(cat)}>{cat.toUpperCase()}</Tag>
    },
    // ✅ Hub: 适用分类列 (显示名称而非ID)
    {
      title: <Space><ClusterOutlined /> 适用分类 (Hub)</Space>,
      key: 'categories',
      width: 250,
      render: (_: any, record: ReviewRule) => {
        if (record.rule_category === 'universal') {
          return <Tag color="cyan">所有合同</Tag>;
        }
        const ids = record.apply_to_category_ids || [];
        if (ids.length === 0) return <Text type="secondary" style={{fontSize: 12}}>未绑定(无效)</Text>;
        
        const names = getCategoryNamesStr(ids);
        const showCount = 2; // 最多显示2个，剩下的折叠
        
        return (
          <Space wrap size={4}>
            {names.slice(0, showCount).map((name, i) => (
              <Tag key={i} color="geekblue" style={{maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', verticalAlign: 'top'}}>{name}</Tag>
            ))}
            {names.length > showCount && (
              <Tooltip title={names.slice(showCount).join(', ')}>
                <Tag>+{names.length - showCount}</Tag>
              </Tooltip>
            )}
          </Space>
        );
      }
    },
    // ✅ Spoke: 适用立场列
    {
      title: '适用立场',
      dataIndex: 'target_stance',
      key: 'stance',
      width: 120,
      render: (stance?: string) => {
        if (!stance) return '-';
        const map: Record<string, any> = {
          'buyer': { label: '甲方/买方', color: 'orange' },
          'seller': { label: '乙方/卖方', color: 'green' },
          'neutral': { label: '中立', color: 'default' }
        };
        const info = map[stance] || { label: stance, color: 'default' };
        return <Tag color={info.color}>{info.label}</Tag>;
      }
    },
    {
      title: '内容预览',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      width: 200,
      render: (content: string) => (
        <Tooltip title={content} overlayStyle={{maxWidth: 400}}>
          <div style={{ fontSize: '12px', color: '#666', cursor: 'pointer' }}>
            {content.substring(0, 40)}...
          </div>
        </Tooltip>
      )
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      width: 80,
      sorter: (a: ReviewRule, b: ReviewRule) => a.priority - b.priority,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (active: boolean) => (
        active ? <CheckCircleOutlined style={{color: '#52c41a'}} /> : <CloseCircleOutlined style={{color: '#ff4d4f'}} />
      )
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      fixed: 'right' as const,
      render: (_: any, record: ReviewRule) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定删除?"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
            />
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <Space>
            <span>审查规则管理</span>
            <Tag color="blue">Hub-and-Spoke 架构</Tag>
          </Space>
        }
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => { fetchRules(); fetchCategories(); }}
            >
              刷新
            </Button>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleExport}
            >
              导出配置
            </Button>
            <Upload
              accept=".json"
              showUploadList={false}
              customRequest={({ file }) => handleImport(file as File)}
            >
              <Button icon={<ImportOutlined />}>
                导入配置
              </Button>
            </Upload>
            <Popconfirm
              title="重置规则库"
              description="这将清除现有规则并从 JSON 重新导入。确定继续？"
              onConfirm={handleMigrateFromJson}
            >
              <Button icon={<ImportOutlined />} loading={migrating}>
                重置规则
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
        {/* 筛选区域 */}
        <div style={{ marginBottom: 16 }}>
          <Space>
            <span>类型筛选：</span>
            <Select
              style={{ width: 150 }}
              placeholder="全部类型"
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

        {/* 说明区域 */}
        <div style={{ marginBottom: 24, padding: '16px', background: '#f0f5ff', borderRadius: '8px', border: '1px solid #adc6ff' }}>
          <Row align="middle">
            <Col span={24}>
              <Space direction="vertical" size={4}>
                <Text strong style={{ color: '#10239e' }}><InfoCircleOutlined /> Hub-and-Spoke 动态关联</Text>
                <Text type="secondary" style={{ fontSize: '13px' }}>
                  在此页面配置的规则，会通过 <strong>Category ID</strong> 动态挂载到合同分类上。
                  当用户上传合同并被识别为特定分类时，会自动加载该分类下的所有规则。
                </Text>
              </Space>
            </Col>
          </Row>
        </div>

        <Table
          columns={columns}
          dataSource={rules}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          scroll={{ x: 1300 }}
        />
      </Card>

      {/* 编辑/新建 模态框 */}
      <Modal
        title={
          <Space>
            <span>{editingRule ? '编辑规则' : '新建规则'}</span>
            {editingRule?.is_system && <Tag color="purple">系统规则</Tag>}
          </Space>
        }
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={800}
        maskClosable={false}
        destroyOnClose
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
                rules={[{ required: true, message: '请输入名称' }]}
              >
                <Input placeholder="例如: 劳动合同社保合规" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="规则类别"
                name="rule_category"
                rules={[{ required: true }]}
              >
                <Select>
                  <Option value="universal">通用规则 (Universal)</Option>
                  <Option value="feature">特征规则 (Category Bound)</Option>
                  <Option value="stance">立场规则 (Stance Bound)</Option>
                  <Option value="custom">自定义规则</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item label="规则描述" name="description">
            <Input placeholder="简要描述规则用途" />
          </Form.Item>

          {/* 🔗 动态显示的 Hub-and-Spoke 配置区域 */}
          {(ruleCategoryValue === 'feature' || ruleCategoryValue === 'stance') && (
            <div style={{ background: '#f6ffed', padding: '16px', borderRadius: '4px', marginBottom: '24px', border: '1px solid #b7eb8f' }}>
              <Divider orientation="left" style={{ margin: '0 0 16px 0', fontSize: '13px', color: '#389e0d' }}>
                🔗 Hub-and-Spoke 关联设置
              </Divider>
              
              <Form.Item
                label="适用合同分类 (Hub)"
                name="apply_to_category_ids"
                rules={[{ required: true, message: '请至少选择一个关联分类' }]}
                tooltip="此规则将挂载到选中的分类上。上传对应类型的合同时将自动触发此规则。"
              >
                <TreeSelect
                  treeData={treeData} // ✅ 使用转换后的树数据
                  treeCheckable
                  showCheckedStrategy={TreeSelect.SHOW_PARENT}
                  placeholder="请选择适用的合同类型（可多选）"
                  style={{ width: '100%' }}
                  maxTagCount={3}
                  allowClear
                  treeDefaultExpandAll={false}
                  loading={treeData.length === 0}
                />
              </Form.Item>

              {ruleCategoryValue === 'stance' && (
                <Form.Item
                  label="适用立场 (Stance)"
                  name="target_stance"
                  rules={[{ required: true, message: '请选择适用立场' }]}
                  tooltip="选择此规则适用的立场。Backend 将自动匹配 'buyer' 或 'seller'。"
                >
                  <Select placeholder="请选择立场">
                    {/* ✅ 使用英文值，确保与后端 RuleAssembler 逻辑匹配 */}
                    <Option value="buyer">甲方 / 买方 / 用人单位 (Buyer)</Option>
                    <Option value="seller">乙方 / 卖方 / 劳动者 (Seller)</Option>
                    <Option value="neutral">中立 / 第三方 (Neutral)</Option>
                  </Select>
                </Form.Item>
              )}
            </div>
          )}

          <Form.Item
            label="Prompt指令内容"
            name="content"
            rules={[{ required: true, message: '请输入规则内容' }]}
            tooltip="这是直接发送给 AI 的指令，请清晰描述审查标准"
          >
            <TextArea rows={6} placeholder="输入给 AI 的具体审查指令..." />
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="优先级" name="priority">
                <InputNumber min={0} max={100} style={{width: '100%'}} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="系统规则" name="is_system" valuePropName="checked">
                {/* 创建时允许编辑，编辑时通常锁定 */}
                <Switch disabled={!!editingRule} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="启用状态" name="is_active" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </div>
  );
};

export default ReviewRulesManager;