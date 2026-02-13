// frontend/src/pages/UserKnowledgeBasePage.tsx
/**
 * 用户知识库管理页面
 * 允许用户管理自己的私有知识库内容
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Table,
  Typography,
  Space,
  message,
  Modal,
  Form,
  Input,
  Tag,
  Popconfirm,
  Upload,
  Alert,
  Progress,
  Tooltip,
  Row,
  Col,
  Statistic,
  Empty,
  Divider,
  Select,
  TreeSelect,
} from 'antd';
import {
  DeleteOutlined,
  EditOutlined,
  UploadOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  ArrowLeftOutlined,
  SearchOutlined,
  FolderOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { knowledgeBaseApi } from '../api/knowledgeBase';
import { contractTemplateApi } from '../api/contractTemplates';
import type { CategoryTreeItem } from '../types/contract';
import './UserKnowledgeBasePage.css';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

// ==================== 类型定义 ====================

interface UserKbDocument {
  id: number;
  doc_id: string;
  title: string;
  content: string;
  category?: string;
  category_id?: number;
  category_name_cache?: string;
  tags?: string[];
  source_type: string;
  status: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  extra_data?: Record<string, any>;
}

interface DuplicateCheckResult {
  success: boolean;
  data: {
    is_duplicate: boolean;
    similarity: number;
    original_item?: {
      id: string;
      title: string;
      content: string;
      source: string;
    };
    recommendation: string;
    action: 'allow' | 'warn' | 'block';
  };
}

interface UploadStep {
  title: string;
  status?: 'wait' | 'process' | 'finish' | 'error';
  content?: React.ReactNode;
}

// ==================== 组件 ====================

const UserKnowledgeBasePage: React.FC = () => {
  const navigate = useNavigate();

  // 数据状态
  const [documents, setDocuments] = useState<UserKbDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });

  // 上传相关状态
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [uploadForm] = Form.useForm();
  const [currentUploadStep, setCurrentUploadStep] = useState(0);
  const [uploadSteps, setUploadSteps] = useState<UploadStep[]>([]);
  const [isCheckingDuplicate, setIsCheckingDuplicate] = useState(false);
  const [duplicateCheckResult, setDuplicateCheckResult] = useState<DuplicateCheckResult | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [fileContent, setFileContent] = useState('');

  // 编辑相关状态
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingDocument, setEditingDocument] = useState<UserKbDocument | null>(null);
  const [editForm] = Form.useForm();

  // 搜索状态
  const [searchQuery, setSearchQuery] = useState('');

  // 统计数据
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    public: 0,
  });

  // 分类树数据
  const [categoryTree, setCategoryTree] = useState<CategoryTreeItem[]>([]);

  // ==================== 数据加载 ====================

  const fetchCategories = async () => {
    try {
      const data = await contractTemplateApi.getCategoryTree(true);
      setCategoryTree(data);
    } catch (error: any) {
      console.error('加载分类失败:', error);
    }
  };

  const fetchDocuments = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const response = await knowledgeBaseApi.getUserDocuments({
        page,
        size: pageSize,
        search: searchQuery || undefined,
      });

      if (response.data.success) {
        setDocuments(response.data.data.items || []);
        setPagination({
          current: page,
          pageSize,
          total: response.data.data.total || 0,
        });

        // 更新统计数据
        setStats({
          total: response.data.data.total || 0,
          active: response.data.data.items?.filter((d: UserKbDocument) => d.status === 'active').length || 0,
          public: response.data.data.items?.filter((d: UserKbDocument) => d.is_public).length || 0,
        });
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载文档失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
    fetchCategories();
  }, [searchQuery]);

  // ==================== 上传流程 ====================

  const handleUploadClick = () => {
    setUploadSteps([
      { title: '上传文件', status: 'process' },
      { title: '内容提取', status: 'wait' },
      { title: '重复检测', status: 'wait' },
      { title: '确认信息', status: 'wait' },
      { title: '完成上传', status: 'wait' },
    ]);
    setCurrentUploadStep(0);
    setDuplicateCheckResult(null);
    setFileContent('');
    setUploadedFile(null);
    uploadForm.resetFields();
    setUploadModalVisible(true);
  };

  const handleFileSelect = async (file: File) => {
    setUploadedFile(file);
    setCurrentUploadStep(1);

    try {
      // 检查文件大小（限制50MB）
      const maxSize = 50 * 1024 * 1024;
      if (file.size > maxSize) {
        message.error('文件过大，请上传小于50MB的文件');
        setCurrentUploadStep(0);
        return false;
      }

      // 只读取文本文件进行重复检测
      const fileName = file.name.toLowerCase();
      const textExtensions = ['.txt', '.md', '.json', '.xml', '.csv'];
      const isTextFile = textExtensions.some(ext => fileName.endsWith(ext));

      let text = '';
      if (isTextFile) {
        // 文本文件直接读取内容
        text = await file.text();
        setFileContent(text);
      } else {
        // 非文本文件（PDF、Word、图片等），由后端处理
        text = `[文件: ${file.name}] 由后端DocumentPreprocessor处理`;
        setFileContent(text);
      }

      setCurrentUploadStep(2);
      setIsCheckingDuplicate(true);

      // 调用重复检测 API（对于非文本文件，只基于文件名和类型检测）
      const response = await knowledgeBaseApi.checkDuplicate({
        title: file.name,
        content: text,
        category: uploadForm.getFieldValue('category'),
      });

      setDuplicateCheckResult(response.data);
      setUploadSteps((prev) => {
        const newSteps = [...prev];
        newSteps[2] = {
          title: '重复检测',
          status: 'finish',
          content: renderDuplicateResult(response.data),
        };
        return newSteps;
      });

      setCurrentUploadStep(3);
    } catch (error: any) {
      message.error('文件处理失败: ' + (error.response?.data?.detail || error.message));
      setCurrentUploadStep(0);
    } finally {
      setIsCheckingDuplicate(false);
    }

    return false; // 阻止自动上传
  };

  const renderDuplicateResult = (result: DuplicateCheckResult['data']) => {
    const { is_duplicate, similarity, recommendation, action } = result;

    if (action === 'block') {
      return (
        <Alert
          type="error"
          icon={<CloseCircleOutlined />}
          message={`高度重复（相似度 ${(similarity * 100).toFixed(1)}%）`}
          description={
            <div>
              <p>{recommendation}</p>
              {result.original_item && (
                <p>
                  系统已有文档：<strong>{result.original_item.title}</strong>
                </p>
              )}
            </div>
          }
          showIcon
        />
      );
    }

    if (action === 'warn') {
      return (
        <Alert
          type="warning"
          icon={<WarningOutlined />}
          message={`内容相似（相似度 ${(similarity * 100).toFixed(1)}%）`}
          description={
            <div>
              <p>{recommendation}</p>
              {result.original_item && (
                <p>
                  相似文档：<strong>{result.original_item.title}</strong>
                </p>
              )}
            </div>
          }
          showIcon
        />
      );
    }

    return (
      <Alert
        type="success"
        icon={<CheckCircleOutlined />}
        message="检测通过"
        description="该内容为独立内容，可以安全上传"
        showIcon
      />
    );
  };

  const handleUploadSubmit = async () => {
    if (!uploadedFile) {
      message.warning('请先上传文件');
      return;
    }

    if (duplicateCheckResult?.data.action === 'block') {
      message.warning('该内容与系统知识库高度重复，无法上传');
      return;
    }

    setCurrentUploadStep(4);

    try {
      const values = await uploadForm.validateFields();

      const formData = new FormData();
      formData.append('file', uploadedFile);
      if (values.title) {
        formData.append('title', values.title);
      }
      // 不再发送 content，由后端 DocumentPreprocessor 处理
      if (values.category_id) {
        formData.append('category_id', values.category_id.toString());
      }
      if (values.tags) {
        formData.append('tags', JSON.stringify(values.tags));
      }
      if (values.is_public !== undefined) {
        formData.append('is_public', values.is_public.toString());
      }

      await knowledgeBaseApi.uploadUserDocument(formData);

      message.success('文档上传成功');
      setUploadModalVisible(false);
      fetchDocuments(pagination.current, pagination.pageSize);
    } catch (error: any) {
      message.error('上传失败: ' + (error.response?.data?.detail || error.message));
      setCurrentUploadStep(3);
    }
  };

  // ==================== 文档操作 ====================

  const handleEdit = (record: UserKbDocument) => {
    setEditingDocument(record);
    editForm.setFieldsValue({
      title: record.title,
      content: record.content,
      category_id: record.category_id,
      tags: record.tags,
      is_public: record.is_public,
    });
    setEditModalVisible(true);
  };

  const handleEditSubmit = async () => {
    if (!editingDocument) return;

    try {
      const values = await editForm.validateFields();

      await knowledgeBaseApi.updateUserDocument(editingDocument.id.toString(), {
        title: values.title,
        content: values.content,
        category_id: values.category_id,
        tags: values.tags,
        is_public: values.is_public,
      });

      message.success('文档更新成功');
      setEditModalVisible(false);
      fetchDocuments(pagination.current, pagination.pageSize);
    } catch (error: any) {
      message.error('更新失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await knowledgeBaseApi.deleteUserDocument(id.toString());
      message.success('文档删除成功');
      fetchDocuments(pagination.current, pagination.pageSize);
    } catch (error: any) {
      message.error('删除失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  // ==================== 表格列定义 ====================

  // 转换分类树为 TreeSelect 数据格式
  const convertCategoryTreeToTreeSelect = (categories: CategoryTreeItem[]): any[] => {
    return categories.map(cat => ({
      title: cat.name,
      value: cat.id,
      key: cat.id,
      children: cat.children && cat.children.length > 0
        ? convertCategoryTreeToTreeSelect(cat.children)
        : undefined,
      icon: <FolderOutlined />,
    }));
  };

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text: string, record: UserKbDocument) => (
        <Space direction="vertical" size={0}>
          <Text strong>{text}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.source_type === 'upload' ? '文件上传' : '手动添加'}
          </Text>
        </Space>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category_id',
      key: 'category_id',
      width: 150,
      render: (_: any, record: UserKbDocument) => {
        const categoryName = record.category_name_cache || record.category;
        return categoryName ? <Tag color="blue">{categoryName}</Tag> : '-';
      },
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 150,
      render: (tags: string[]) =>
        tags && tags.length > 0 ? (
          <Space size={4} wrap>
            {tags.slice(0, 2).map((tag, index) => (
              <Tag key={index} color="geekblue">
                {tag}
              </Tag>
            ))}
            {tags.length > 2 && <Tag>+{tags.length - 2}</Tag>}
          </Space>
        ) : (
          '-'
        ),
    },
    {
      title: '可见性',
      dataIndex: 'is_public',
      key: 'is_public',
      width: 100,
      render: (isPublic: boolean) =>
        isPublic ? (
          <Tag color="green" icon={<CheckCircleOutlined />}>
            公开
          </Tag>
        ) : (
          <Tag color="default">私有</Tag>
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const statusConfig: Record<string, { color: string; text: string }> = {
          active: { color: 'success', text: '活跃' },
          archived: { color: 'default', text: '归档' },
          deleted: { color: 'error', text: '删除' },
        };
        const config = statusConfig[status] || { color: 'default', text: status };
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      fixed: 'right' as const,
      render: (_: any, record: UserKbDocument) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
              disabled={record.status === 'deleted'}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除"
            description="删除后将无法恢复，是否继续？"
            onConfirm={() => handleDelete(record.id)}
            okText="确认"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                disabled={record.status === 'deleted'}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ==================== 渲染 ====================

  return (
    <div className="user-kb-page">
      {/* 顶部导航栏 */}
      <Card className="kb-header-card">
        <Row align="middle" justify="space-between">
          <Col>
            <Space size="middle">
              <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
                返回工作台
              </Button>
              <DatabaseOutlined style={{ fontSize: 24, color: '#1890ff' }} />
              <div>
                <Title level={3} style={{ margin: 0 }}>
                  我的知识库
                </Title>
                <Text type="secondary">管理您的私有法律知识库内容</Text>
              </div>
            </Space>
          </Col>
          <Col>
            <Button type="primary" icon={<UploadOutlined />} onClick={handleUploadClick}>
              上传文档
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="文档总数"
              value={stats.total}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="活跃文档"
              value={stats.active}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="公开文档"
              value={stats.public}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 文档列表 */}
      <Card style={{ marginTop: 16 }} title="我的文档">
        <Space style={{ marginBottom: 16 }} size="middle">
          <Input.Search
            placeholder="搜索文档标题或内容..."
            allowClear
            style={{ width: 400 }}
            onSearch={setSearchQuery}
            prefix={<SearchOutlined />}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={documents}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => fetchDocuments(page, pageSize),
          }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <div>
                    <p>您还没有上传任何文档</p>
                    <p className="text-secondary">点击上方"上传文档"按钮开始构建您的知识库</p>
                  </div>
                }
              />
            ),
          }}
        />
      </Card>

      {/* 上传模态框 */}
      <Modal
        title="上传文档到知识库"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        onOk={handleUploadSubmit}
        okText="确认上传"
        cancelText="取消"
        width={700}
        okButtonProps={{
          disabled: duplicateCheckResult?.data.action === 'block' || currentUploadStep < 3,
        }}
      >
        <div style={{ marginBottom: 24 }}>
          <Progress
            percent={(currentUploadStep / 4) * 100}
            status={currentUploadStep === 4 ? 'success' : 'active'}
            strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }}
          />
        </div>

        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* 步骤1：上传文件 */}
          <div>
            <Text strong>1. 上传文件</Text>
            <div style={{ marginTop: 8 }}>
              <Upload.Dragger
                accept=".txt,.md,.doc,.docx,.pdf,.rtf,.odt,.jpg,.jpeg,.png,.bmp,.tiff,.gif"
                maxCount={1}
                beforeUpload={handleFileSelect}
                fileList={[]}
                disabled={currentUploadStep >= 3}
              >
                <p className="ant-upload-drag-icon">
                  <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                <p className="ant-upload-hint">
                  支持 .txt、.md、.doc、.docx、.pdf、.rtf、.odt、.jpg、.png 等格式
                  <br/>
                  文档类文件会自动提取文本，图片文件会自动OCR识别
                </p>
              </Upload.Dragger>
            </div>
          </div>

          {/* 步骤3：重复检测结果 */}
          {currentUploadStep >= 2 && (
            <div>
              <Text strong>3. 重复检测结果</Text>
              <div style={{ marginTop: 8 }}>
                {isCheckingDuplicate ? (
                  <div style={{ textAlign: 'center', padding: 20 }}>
                    <Progress type="circle" status="active" />
                    <p style={{ marginTop: 8 }}>正在检测内容重复度...</p>
                  </div>
                ) : (
                  duplicateCheckResult && renderDuplicateResult(duplicateCheckResult.data)
                )}
              </div>
            </div>
          )}

          {/* 步骤4：确认信息 */}
          {currentUploadStep >= 3 && duplicateCheckResult?.data.action !== 'block' && (
            <div>
              <Text strong>4. 确认文档信息</Text>
              <Form form={uploadForm} layout="vertical" style={{ marginTop: 8 }}>
                <Form.Item
                  name="title"
                  label="文档标题"
                  initialValue={uploadedFile?.name}
                  rules={[{ required: true, message: '请输入文档标题' }]}
                >
                  <Input placeholder="请输入文档标题" />
                </Form.Item>

                <Form.Item name="category_id" label="文档分类">
                  <TreeSelect
                    placeholder="选择文档所属分类"
                    allowClear
                    showSearch
                    treeDefaultExpandAll
                    treeNodeFilterProp="title"
                    treeData={convertCategoryTreeToTreeSelect(categoryTree)}
                  />
                </Form.Item>

                <Form.Item name="tags" label="标签">
                  <Select mode="tags" placeholder="输入标签，按回车添加" />
                </Form.Item>

                <Form.Item
                  name="is_public"
                  label="可见性"
                  valuePropName="checked"
                  initialValue={false}
                >
                  <Select>
                    <Option value={false}>私有（仅自己可见）</Option>
                    <Option value={true}>公开（团队共享）</Option>
                  </Select>
                </Form.Item>
              </Form>
            </div>
          )}
        </Space>
      </Modal>

      {/* 编辑模态框 */}
      <Modal
        title="编辑文档"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        onOk={handleEditSubmit}
        okText="保存"
        cancelText="取消"
        width={700}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="title"
            label="文档标题"
            rules={[{ required: true, message: '请输入文档标题' }]}
          >
            <Input placeholder="请输入文档标题" />
          </Form.Item>

          <Form.Item
            name="content"
            label="文档内容"
            rules={[{ required: true, message: '请输入文档内容' }]}
          >
            <TextArea rows={10} placeholder="请输入文档内容" />
          </Form.Item>

          <Form.Item name="category_id" label="文档分类">
            <TreeSelect
              placeholder="选择文档所属分类"
              allowClear
              showSearch
              treeDefaultExpandAll
              treeNodeFilterProp="title"
              treeData={convertCategoryTreeToTreeSelect(categoryTree)}
            />
          </Form.Item>

          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签，按回车添加" />
          </Form.Item>

          <Form.Item name="is_public" label="可见性" valuePropName="checked">
            <Select>
              <Option value={false}>私有（仅自己可见）</Option>
              <Option value={true}>公开（团队共享）</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UserKnowledgeBasePage;
