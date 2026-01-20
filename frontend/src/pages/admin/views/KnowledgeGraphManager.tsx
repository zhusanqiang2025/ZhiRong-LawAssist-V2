import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Space, Tag, Modal, Form, Input, Select, Cascader, AutoComplete,
  message, Popconfirm, Tooltip, Typography, Row, Col, Checkbox, Progress, Alert
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  ReloadOutlined, FileTextOutlined, ExportOutlined, SyncOutlined,
  ThunderboltOutlined, StopOutlined
} from '@ant-design/icons';
import { contractTemplateApi } from '../../../api/contractTemplates';
import type { CategoryTreeItem } from '../../../types/contract';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// 法律特征选项
const LEGAL_FEATURE_OPTIONS = {
  transaction_nature: [
    '转移所有权', '提供服务', '许可使用', '合作经营', '融资借贷', '劳动用工', '争议解决'
  ],
  contract_object: [
    '货物', '工程', '智力成果', '服务', '股权', '资金', '劳动力', '不动产', '动产'
  ],
  consideration_type: ['有偿', '无偿', '混合']
};

interface ContractTypeDefinition {
  name: string;
  aliases: string[];
  category: string; // 一级分类
  subcategory?: string; // 二级分类
  third_category?: string; // 三级分类
  legal_features: {
    transaction_nature: string;
    contract_object: string;
    consideration_type: string;
    consideration_detail: string;
    transaction_characteristics: string;
    usage_scenario?: string;
    legal_basis?: string[];
  };
  recommended_template_ids: string[];
}

const KnowledgeGraphManager: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [contractTypes, setContractTypes] = useState<ContractTypeDefinition[]>([]);
  const [categories, setCategories] = useState<CategoryTreeItem[]>([]); // 分类树数据
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ContractTypeDefinition | null>(null);
  const [originalName, setOriginalName] = useState<string>(''); // 用于更新时的原名
  const [form] = Form.useForm();

  // AI 完善相关状态
  const [aiEnhancing, setAiEnhancing] = useState(false);
  const [aiProgress, setAiProgress] = useState({ current: 0, total: 0 });
  const [selectedRows, setSelectedRows] = useState<React.Key[]>([]);

  // 获取所有合同类型
  const fetchContractTypes = async () => {
    setLoading(true);
    try {
      const data = await contractTemplateApi.getAllContractTypes();
      setContractTypes(data.contract_types);
    } catch (error) {
      message.error('加载知识图谱失败');
    } finally {
      setLoading(false);
    }
  };

  // 获取分类树
  const fetchCategories = async () => {
    try {
      const data = await contractTemplateApi.getCategoryTree(true);
      setCategories(data);
    } catch (error) {
      message.error('加载分类失败');
    }
  };

  useEffect(() => {
    fetchContractTypes();
    fetchCategories();
  }, []);

  // 提交表单（新增/修改）
  const handleSubmit = async (values: any) => {
    try {
      // 从 category_path 数组中提取分类层级
      const categoryPath = values.category_path || [];
      const category_level_1 = categoryPath[0] || '';
      const category_level_2 = categoryPath[1] || '';
      const category_level_3 = categoryPath[2] || '';

      // 构建法律特征对象
      const legalFeatures = {
        transaction_nature: values.transaction_nature,
        contract_object: values.contract_object,
        consideration_type: values.consideration_type,
        consideration_detail: values.consideration_detail,
        transaction_characteristics: values.transaction_characteristics,
        usage_scenario: values.usage_scenario || '',
        legal_basis: values.legal_basis ? values.legal_basis.split('\n').filter((s: string) => s.trim()) : []
      };

      const requestData = {
        name: values.name,
        aliases: values.aliases ? values.aliases.split(',').map((s: string) => s.trim()).filter((s: string) => s) : [],
        category: category_level_1,
        subcategory: category_level_2 || '',
        legal_features: legalFeatures,
        recommended_template_ids: []
      };

      if (editingRecord) {
        await contractTemplateApi.updateContractType(originalName, requestData);
        message.success('更新成功');
      } else {
        await contractTemplateApi.createContractType(requestData);
        message.success('创建成功');
      }

      setModalVisible(false);
      form.resetFields();
      setEditingRecord(null);
      setOriginalName('');
      fetchContractTypes();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  // 删除合同类型
  const handleDelete = async (name: string) => {
    try {
      await contractTemplateApi.deleteContractType(name);
      message.success('删除成功');
      fetchContractTypes();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 打开编辑框
  const handleEdit = (record: ContractTypeDefinition) => {
    setEditingRecord(record);
    setOriginalName(record.name);

    // 构建分类路径
    const categoryPath = findCategoryPath(record.category, record.subcategory, record.third_category);

    form.setFieldsValue({
      name: record.name,
      aliases: record.aliases.join(', '),
      category_path: categoryPath.length > 0 ? categoryPath : undefined,
      transaction_nature: record.legal_features.transaction_nature,
      contract_object: record.legal_features.contract_object,
      consideration_type: record.legal_features.consideration_type,
      consideration_detail: record.legal_features.consideration_detail,
      transaction_characteristics: record.legal_features.transaction_characteristics,
      usage_scenario: record.legal_features.usage_scenario || '',
      legal_basis: record.legal_features?.legal_basis?.join('\n') || ''
    });
    setModalVisible(true);
  };

  // 打开新增框
  const handleAdd = () => {
    setEditingRecord(null);
    setOriginalName('');
    form.resetFields();
    form.setFieldsValue({
      consideration_type: '有偿'
    });
    setModalVisible(true);
  };

  // 导出知识图谱
  const handleExport = async () => {
    try {
      const data = await contractTemplateApi.exportKnowledgeGraph();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `knowledge_graph_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch (error) {
      message.error('导出失败');
    }
  };

  // 从合同分类同步
  const handleSyncFromCategories = async () => {
    try {
      const result = await contractTemplateApi.syncFromCategories();
      message.success(`同步完成：新增 ${result.added} 个合同类型，跳过 ${result.skipped} 个，当前总计 ${result.total} 个`);
      fetchContractTypes(); // 刷新列表
    } catch (error: any) {
      message.error(error.response?.data?.detail || '同步失败');
    }
  };

  // AI 批量完善法律特征
  const handleAiEnhance = async (contractNames?: string[]) => {
    try {
      setAiEnhancing(true);
      setAiProgress({ current: 0, total: contractNames?.length || contractTypes.length });

      message.loading({ content: 'AI 正在完善法律特征，这可能需要几分钟...', key: 'ai-enhance', duration: 0 });

      const result = await contractTemplateApi.aiEnhanceLegalFeatures({
        contract_names: contractNames,
        force: false // 不强制重新生成已有的完善特征
      });

      message.destroy(); // 关闭 loading

      if (result.failed > 0) {
        message.warning(`AI 完善完成：成功 ${result.success} 个，失败 ${result.failed} 个，跳过 ${result.skipped} 个`);
        if (result.errors.length > 0) {
          console.error('AI 完善错误:', result.errors);
        }
      } else {
        message.success(`AI 完善成功：共处理 ${result.total} 个，成功 ${result.success} 个，跳过 ${result.skipped} 个`);
      }

      fetchContractTypes(); // 刷新列表
      setSelectedRows([]); // 清空选择
    } catch (error: any) {
      message.destroy();
      message.error(error.response?.data?.detail || 'AI 完善失败');
    } finally {
      setAiEnhancing(false);
      setAiProgress({ current: 0, total: 0 });
    }
  };

  // AI 完善单个合同
  const handleAiEnhanceSingle = async (contractName: string) => {
    try {
      message.loading({ content: `AI 正在完善 "${contractName}" 的法律特征...`, key: 'ai-single', duration: 0 });

      await contractTemplateApi.aiEnhanceSingleContract(contractName);

      message.destroy();
      message.success(`"${contractName}" 的法律特征已完善`);
      fetchContractTypes(); // 刷新列表
    } catch (error: any) {
      message.destroy();
      message.error(error.response?.data?.detail || 'AI 完善失败');
    }
  };

  // 转换分类树为 Cascader 选项格式
  const transformCategoryTree = (tree: CategoryTreeItem[]): any[] => {
    return tree.map(item => ({
      value: item.name,
      label: item.name,
      children: item.children && item.children.length > 0
        ? transformCategoryTree(item.children)
        : undefined
    }));
  };

  // 根据分类名称查找分类路径（用于编辑时回显）
  const findCategoryPath = (categoryName: string, subcategoryName?: string, thirdCategoryName?: string): string[] => {
    const path: string[] = [];

    // 查找一级分类
    const level1 = categories.find(c => c.name === categoryName);
    if (level1) {
      path.push(level1.name);

      // 如果有二级分类，查找二级分类
      if (subcategoryName && level1.children) {
        const level2 = level1.children.find(c => c.name === subcategoryName);
        if (level2) {
          path.push(level2.name);

          // 如果有三级分类，查找三级分类
          if (thirdCategoryName && level2.children) {
            const level3 = level2.children.find(c => c.name === thirdCategoryName);
            if (level3) {
              path.push(level3.name);
            }
          }
        }
      }
    }

    return path;
  };

  const columns = [
    {
      title: '合同名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      fixed: 'left' as const,
      render: (text: string) => (
        <Space>
          <FileTextOutlined style={{ color: '#1890ff' }} />
          <span style={{ fontWeight: 600 }}>{text}</span>
        </Space>
      )
    },
    {
      title: '分类层级',
      key: 'category',
      width: 250,
      render: (_: any, record: ContractTypeDefinition) => (
        <Space direction="vertical" size={0}>
          <Tag color="blue">{record.category}</Tag>
          {record.subcategory && <Tag color="cyan">{record.subcategory}</Tag>}
        </Space>
      )
    },
    {
      title: '法律特征',
      key: 'features',
      width: 400,
      render: (_: any, record: ContractTypeDefinition) => (
        <Space direction="vertical" size={2} style={{ fontSize: '12px' }}>
          <div>
            <Text type="secondary">交易性质：</Text>
            <Tag>{record.legal_features.transaction_nature}</Tag>
          </div>
          <div>
            <Text type="secondary">合同标的：</Text>
            <Tag>{record.legal_features.contract_object}</Tag>
          </div>
          <div>
            <Text type="secondary">交易对价：</Text>
            <Tag>{record.legal_features.consideration_type}，{record.legal_features.consideration_detail}</Tag>
          </div>
          <Tooltip title={record.legal_features.transaction_characteristics}>
            <div style={{ maxWidth: 300 }}>
              <Text type="secondary" ellipsis>特征：{record.legal_features.transaction_characteristics}</Text>
            </div>
          </Tooltip>
        </Space>
      )
    },
    {
      title: '别名',
      dataIndex: 'aliases',
      key: 'aliases',
      width: 200,
      render: (aliases: string[]) => (
        <Space size={[4, 4]} wrap>
          {aliases.map((alias, idx) => (
            <Tag key={idx} color="default">{alias}</Tag>
          ))}
        </Space>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      fixed: 'right' as const,
      render: (_: any, record: ContractTypeDefinition) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => handleAiEnhanceSingle(record.name)}
            style={{ color: '#52c41a' }}
          >
            AI完善
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此合同类型？"
            description="删除后不可恢复"
            onConfirm={() => handleDelete(record.name)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <>
      <Card
        title="合同法律特征知识图谱"
        extra={
          <Space>
            <Button
              icon={<SyncOutlined />}
              onClick={handleSyncFromCategories}
            >
              同步分类
            </Button>
            <Button
              icon={<ExportOutlined />}
              onClick={handleExport}
            >
              导出
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchContractTypes}
            >
              刷新
            </Button>
            <Button
              icon={<ThunderboltOutlined />}
              onClick={() => handleAiEnhance(selectedRows.length > 0 ? selectedRows as string[] : undefined)}
              disabled={aiEnhancing}
              type="primary"
              style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}
            >
              {aiEnhancing ? 'AI完善中...' : selectedRows.length > 0 ? `AI完善选中 (${selectedRows.length})` : 'AI完善全部'}
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleAdd}
            >
              新增合同类型
            </Button>
          </Space>
        }
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          管理合同类型与法律特征的映射关系，完善知识图谱。人工复核和维护合同类型的六维法律特征定义。
        </Paragraph>

        {aiEnhancing && (
          <Alert
            message="AI 正在完善法律特征"
            description={
              <div style={{ marginTop: 8 }}>
                <Progress
                  percent={Math.round((aiProgress.current / aiProgress.total) * 100)}
                  status="active"
                  format={(percent) => `${aiProgress.current}/${aiProgress.total}`}
                />
              </div>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Table
          columns={columns}
          dataSource={contractTypes}
          rowKey="name"
          loading={loading}
          size="small"
          pagination={{
            pageSize: 20,
            showTotal: (total) => `共 ${total} 个合同类型`
          }}
          scroll={{ x: 1400 }}
          rowSelection={{
            selectedRowKeys: selectedRows,
            onChange: (selectedRowKeys: React.Key[]) => {
              setSelectedRows(selectedRowKeys);
            },
          }}
        />
      </Card>

      {/* 新增/编辑 Modal */}
      <Modal
        title={editingRecord ? "编辑合同类型" : "新增合同类型"}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
          setEditingRecord(null);
          setOriginalName('');
        }}
        onOk={form.submit}
        width={800}
        okText="保存"
        cancelText="取消"
        style={{ top: 20 }}
        bodyStyle={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Title level={5}>基本信息</Title>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="合同名称"
                rules={[{ required: true, message: '请输入合同名称' }]}
              >
                <Input placeholder="例如：不动产买卖合同" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="aliases"
                label="别名（用逗号分隔）"
              >
                <Input placeholder="例如：房屋买卖合同, 房产买卖合同" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="category_path"
            label="合同分类"
            rules={[{ required: true, message: '请选择合同分类' }]}
            tooltip="从合同分类管理系统中选择分类路径"
          >
            <Cascader
              options={transformCategoryTree(categories)}
              placeholder="请选择分类（支持一/二/三级）"
              showSearch
              changeOnSelect
              expandTrigger="hover"
            />
          </Form.Item>

          <Title level={5} style={{ marginTop: 16 }}>法律特征</Title>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="transaction_nature"
                label="交易性质"
                rules={[{ required: true, message: '请输入或选择交易性质' }]}
                tooltip="可从选项中选择或输入自定义值"
              >
                <AutoComplete
                  options={LEGAL_FEATURE_OPTIONS.transaction_nature.map(opt => ({ value: opt, label: opt }))}
                  placeholder="选择或输入交易性质"
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="contract_object"
                label="合同标的"
                rules={[{ required: true, message: '请输入或选择合同标的' }]}
                tooltip="可从选项中选择或输入自定义值"
              >
                <AutoComplete
                  options={LEGAL_FEATURE_OPTIONS.contract_object.map(opt => ({ value: opt, label: opt }))}
                  placeholder="选择或输入合同标的"
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="consideration_type"
                label="交易对价类型"
                rules={[{ required: true, message: '请输入或选择交易对价类型' }]}
                tooltip="可从选项中选择或输入自定义值"
              >
                <AutoComplete
                  options={LEGAL_FEATURE_OPTIONS.consideration_type.map(opt => ({ value: opt, label: opt }))}
                  placeholder="选择或输入对价类型"
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="consideration_detail"
                label="交易对价具体说明"
                rules={[{ required: true, message: '请输入交易对价具体说明' }]}
              >
                <Input placeholder="例如：双方协商、固定价格、按市场价格" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="transaction_characteristics"
            label="交易特征"
            rules={[{ required: true, message: '请输入交易特征' }]}
            tooltip="描述该合同类型的特殊法律特征"
          >
            <TextArea
              rows={2}
              placeholder="例如：占有转移+办理所有权转移登记实现交付"
            />
          </Form.Item>

          <Form.Item
            name="usage_scenario"
            label="使用场景"
          >
            <TextArea
              rows={2}
              placeholder="描述适用场景，例如：适用于房屋、商铺等不动产所有权转让"
            />
          </Form.Item>

          <Form.Item
            name="legal_basis"
            label="法律依据（每行一个）"
          >
            <TextArea
              rows={3}
              placeholder="例如：&#10;民法典第209条&#10;民法典第214条"
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default KnowledgeGraphManager;
