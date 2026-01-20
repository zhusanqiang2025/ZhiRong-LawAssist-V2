// frontend/src/pages/admin/views/TemplateManager.tsx
import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Input, Space, Tag, Modal, Form,
  Upload, Select, message, Popconfirm, Switch, Tree, Row, Col,
  Typography, Tooltip, Divider, Cascader
} from 'antd';
import {
  UploadOutlined, DeleteOutlined, SettingOutlined,
  EyeOutlined, EditOutlined, FolderOutlined, FileTextOutlined,
  ReloadOutlined, DatabaseOutlined, ApartmentOutlined
} from '@ant-design/icons';
import { contractTemplateApi } from '../../../api/contractTemplates';
import type { ContractTemplate, CategoryTreeItem } from '../../../types/contract';
import TemplateContractFeaturesEditor from '../../../components/TemplateContractFeaturesEditor';
import type { ContractFeaturesData } from '../../../components/TemplateContractFeaturesEditor';
import ReactMarkdown from 'react-markdown';
import { getApiBaseUrl } from '../../../utils/apiConfig';

const { Text, Paragraph } = Typography;
const { Option, OptGroup } = Select;

const TemplateManager: React.FC = () => {
  // ==================== 1. 状态定义 ====================
  // 数据源状态
  const [templates, setTemplates] = useState<ContractTemplate[]>([]);
  const [categories, setCategories] = useState<CategoryTreeItem[]>([]);
  const [contractTypeOptions, setContractTypeOptions] = useState<any[]>([]); // V3 下拉框数据
  const [filteredTemplates, setFilteredTemplates] = useState<ContractTemplate[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  
  // UI 控制状态
  const [loading, setLoading] = useState(false);
  const [uploadVisible, setUploadVisible] = useState(false);
  const [viewContentVisible, setViewContentVisible] = useState(false);
  const [editContentVisible, setEditContentVisible] = useState(false);
  const [featuresEditorVisible, setFeaturesEditorVisible] = useState(false);
  
  // 当前操作对象状态
  const [currentTemplate, setCurrentTemplate] = useState<ContractTemplate | null>(null);
  const [currentCategoryPath, setCurrentCategoryPath] = useState<string[]>([]);
  const [templateContent, setTemplateContent] = useState('');
  
  // 管理工具状态
  const [rebuildingIndex, setRebuildingIndex] = useState(false);
  const [indexStats, setIndexStats] = useState<any>(null);

  const [form] = Form.useForm();
  const [editForm] = Form.useForm();

  // ==================== 2. 初始化与数据加载 ====================
  
  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchCategories(),      // 左侧树
        fetchContractTypeOptions(), // 上传用的下拉框
        fetchTemplates(),       // 模板列表
        fetchIndexStats()       // 索引统计
      ]);
    } catch (e) {
      console.error('初始化数据失败:', e);
    } finally {
      setLoading(false);
    }
  };

  // 获取左侧分类树
  const fetchCategories = async () => {
    try {
      const data = await contractTemplateApi.getCategoryTree(true);
      setCategories(data);
    } catch (e) {
      console.error('加载分类失败:', e);
    }
  };

  // 获取所有模板 (支持分页循环加载所有)
  const fetchTemplates = async () => {
    try {
      const res = await contractTemplateApi.getTemplates({
        scope: 'all',
        page: 1,
        page_size: 1000
      });
      // 如果后端分页，这里简单起见只取第一页，或者您可以保留原来的循环逻辑
      setTemplates(res.templates);
    } catch (e) {
      message.error('加载模板列表失败');
    }
  };

  // 【核心新增】获取合同类型下拉选项 (V3)
  const fetchContractTypeOptions = async () => {
    try {
      // 调用 api 中新加的方法
      const options = await contractTemplateApi.getContractTypeOptions();
      
      // 分组处理
      const grouped: Record<string, any[]> = {};
      options.forEach(opt => {
        if (!grouped[opt.group]) grouped[opt.group] = [];
        grouped[opt.group].push(opt);
      });
      
      const groupedArray = Object.entries(grouped).map(([group, items]) => ({
        label: group,
        options: items
      }));
      setContractTypeOptions(groupedArray);
    } catch (e) {
      console.error('加载合同类型选项失败:', e);
    }
  };

  // 获取索引统计信息
  const fetchIndexStats = async () => {
    try {
      const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
      const response = await fetch(`${getApiBaseUrl()}/rag/index/stats`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setIndexStats(data);
      }
    } catch (e) {
      console.error('获取索引统计失败:', e);
    }
  };

  // ==================== 3. 筛选与逻辑处理 ====================

  // 筛选逻辑
  useEffect(() => {
    if (!selectedCategory) {
      setFilteredTemplates(templates);
    } else {
      const filtered = templates.filter(t => 
        t.category === selectedCategory || 
        t.subcategory === selectedCategory || 
        t.primary_contract_type === selectedCategory
      );
      setFilteredTemplates(filtered);
    }
  }, [selectedCategory, templates]);

  // 查找分类路径 (用于编辑时的级联回显)
  const findTemplateCategoryPath = (template: ContractTemplate): string[] => {
    const findPath = (cats: CategoryTreeItem[], targetName: string, path: string[] = []): string[] | null => {
      for (const cat of cats) {
        const currentPath = [...path, cat.name];
        if (cat.name === targetName) return currentPath;
        if (cat.children && cat.children.length > 0) {
          const result = findPath(cat.children, targetName, currentPath);
          if (result) return result;
        }
      }
      return null;
    };
    // 优先使用模板的 category，如果没有则不回显
    return findPath(categories, template.category) || [template.category];
  };

  // 渲染级联选择器数据
  const renderCategoryCascader = (data: CategoryTreeItem[]): any[] => {
    return data.map(item => ({
      label: item.name,
      value: item.name,
      children: item.children && item.children.length > 0 ? renderCategoryCascader(item.children) : undefined
    }));
  };

  // ==================== 4. 操作处理函数 ====================

  // 【核心修改】上传处理 (V3)
  const handleUpload = async (values: any) => {
    const formData = new FormData();
    formData.append('file', values.file.fileList[0].originFileObj);
    formData.append('name', values.name);
    
    // 强制使用下拉框选中的具体类型名 (如"房屋租赁合同")
    formData.append('category', values.category);
    
    formData.append('is_public', String(values.is_public !== false));
    if (values.description) formData.append('description', values.description);

    try {
      setLoading(true);
      await contractTemplateApi.uploadTemplate(formData);
      message.success('上传成功！已关联知识图谱特征');
      setUploadVisible(false);
      form.resetFields();
      fetchTemplates();
      fetchIndexStats(); // 更新统计
    } catch (error: any) {
      message.error(error.response?.data?.detail || '上传失败');
    } finally {
      setLoading(false);
    }
  };

  // 重建索引
  const handleRebuildIndex = async () => {
    setRebuildingIndex(true);
    try {
      const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
      const response = await fetch(`${getApiBaseUrl()}/rag/index/index-all`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        message.success('索引重建完成');
        fetchIndexStats();
      } else {
        message.error('重建失败');
      }
    } catch (e) {
      message.error('操作异常');
    } finally {
      setRebuildingIndex(false);
    }
  };

  // 查看内容
  const handleViewContent = async (template: ContractTemplate) => {
    setCurrentTemplate(template);
    setTemplateContent('加载中...');
    try {
      const res = await contractTemplateApi.getTemplateContent(template.id);
      setTemplateContent(res.content);
    } catch (e) {
      setTemplateContent('读取失败');
    }
    setViewContentVisible(true);
  };

  // 编辑内容 (初始化表单)
  const handleEditContent = async (template: ContractTemplate) => {
    setCurrentTemplate(template);
    setTemplateContent('加载中...');
    try {
      const res = await contractTemplateApi.getTemplateContent(template.id);
      
      // 尝试回显分类
      const path = findTemplateCategoryPath(template);
      
      editForm.setFieldsValue({
        name: template.name,
        content: res.content,
        // 注意：编辑时我们暂时还是允许改"目录"，或者你可以根据需求锁死
        categoryPath: path 
      });
    } catch (e) {
      editForm.setFieldsValue({ name: template.name, content: '读取失败' });
    }
    setEditContentVisible(true);
  };

  // 保存内容编辑
  const handleSaveContent = async (values: any) => {
    if (!currentTemplate) return;
    try {
      const formData = new FormData();
      formData.append('name', values.name);
      
      // 保持原有逻辑：如果改了分类，取最后一级
      if (values.categoryPath && Array.isArray(values.categoryPath)) {
        formData.append('category', values.categoryPath[values.categoryPath.length - 1]);
      }
      
      // 模拟文件上传来更新内容
      const blob = new Blob([values.content], { type: 'text/markdown' });
      formData.append('file', blob, `${values.name}.md`);

      await contractTemplateApi.updateTemplate(currentTemplate.id, formData);
      message.success('更新成功');
      setEditContentVisible(false);
      fetchTemplates();
    } catch (e) {
      message.error('更新失败');
    }
  };

  // 删除模板
  const handleDelete = async (id: string) => {
    try {
      await contractTemplateApi.deleteTemplate(id);
      message.success('删除成功');
      fetchTemplates();
    } catch (e) {
      message.error('删除失败');
    }
  };

  // ==================== 5. UI 渲染配置 ====================

  // 左侧树渲染
  const renderCategoryTree = (data: CategoryTreeItem[]): any[] => {
    return data.map(item => ({
      title: (
        <Space>
          {item.children && item.children.length > 0 ? <FolderOutlined style={{color: '#1890ff'}} /> : <FileTextOutlined />}
          <span>{item.name}</span>
        </Space>
      ),
      key: item.name,
      children: item.children && item.children.length > 0 ? renderCategoryTree(item.children) : undefined
    }));
  };

  // 表格列定义
  const columns = [
    {
      title: '模板名称',
      dataIndex: 'name',
      key: 'name',
      width: 300,
      render: (text: string, r: ContractTemplate) => (
        <Space>
           <FileTextOutlined style={{ color: '#52c41a' }} />
           <Space direction="vertical" size={0}>
             <Text strong>{text}</Text>
             <Text type="secondary" style={{fontSize: 11}}>{r.file_name}</Text>
           </Space>
        </Space>
      )
    },
    {
      title: '合同类型',
      dataIndex: 'category',
      width: 150,
      render: (text: string) => <Tag color="blue">{text}</Tag>
    },
    {
      title: '知识图谱状态',
      key: 'features',
      width: 120,
      render: (_: any, r: ContractTemplate) => {
        const hasKgLink = r.metadata_info?.knowledge_graph_link;
        return hasKgLink ? (
          <Tooltip title={`已关联类型: ${r.metadata_info?.knowledge_graph_link?.name}`}>
            <Tag color="green" icon={<ApartmentOutlined />}>已关联</Tag>
          </Tooltip>
        ) : (
          <Tooltip title="未关联图谱，使用自动提取特征">
            <Tag color="orange">LLM提取</Tag>
          </Tooltip>
        );
      }
    },
    {
      title: '权限',
      dataIndex: 'is_public',
      width: 80,
      render: (pub: boolean) => <Tag>{pub ? '公开' : '私有'}</Tag>
    },
    {
      title: '操作',
      key: 'action',
      width: 250,
      fixed: 'right' as const,
      render: (_: any, r: ContractTemplate) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewContent(r)}>
            预览
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditContent(r)}>
            编辑
          </Button>
          <Button 
            type="link" 
            size="small" 
            icon={<SettingOutlined />}
            onClick={() => {
              setCurrentTemplate(r);
              setCurrentCategoryPath(findTemplateCategoryPath(r));
              setFeaturesEditorVisible(true);
            }}
          >
            特征
          </Button>
          <Popconfirm title="确定删除?" onConfirm={() => handleDelete(r.id)}>
            <Button type="link" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <>
      <Card
        title="合同模板管理"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchInitialData}>刷新</Button>
            <Button icon={<DatabaseOutlined />} onClick={fetchIndexStats}>统计</Button>
            
            <Popconfirm
              title="确定重建索引？"
              description="耗时操作，用于修复搜索不准的问题"
              onConfirm={handleRebuildIndex}
            >
              <Button icon={<SettingOutlined />} loading={rebuildingIndex}>重建索引</Button>
            </Popconfirm>
            
            <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadVisible(true)}>
              上传模板
            </Button>
          </Space>
        }
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          管理所有合同模板文件。V3版本支持上传时自动关联知识图谱，并生成向量索引以支持智能搜索。
        </Paragraph>

        {/* 索引统计面板 */}
        {indexStats && (
          <Card size="small" style={{ marginBottom: 16, background: '#f9f9f9' }}>
            <Space split={<Divider type="vertical" />}>
              <Text>📚 数据库: <Text strong>{indexStats.database?.count}</Text></Text>
              <Text>🔍 向量索引: <Text strong>{indexStats.vector_store?.count}</Text></Text>
              <Text>✅ 覆盖率: <Tag color="blue">{indexStats.coverage}</Tag></Text>
            </Space>
          </Card>
        )}

        <Row gutter={16}>
          {/* 左侧树 */}
          <Col span={5} style={{ borderRight: '1px solid #f0f0f0' }}>
            <div style={{ marginBottom: 12 }}>
              <Button type={!selectedCategory ? 'primary' : 'default'} block size="small" onClick={() => setSelectedCategory(null)}>
                显示全部
              </Button>
            </div>
            <Tree
              treeData={renderCategoryTree(categories)}
              onSelect={(keys) => setSelectedCategory(keys[0] as string)}
              selectedKeys={selectedCategory ? [selectedCategory] : []}
              height={600}
              defaultExpandAll
            />
          </Col>
          
          {/* 右侧列表 */}
          <Col span={19}>
            <Table 
              columns={columns} 
              dataSource={filteredTemplates} 
              rowKey="id"
              loading={loading}
              size="small"
              pagination={{ pageSize: 15, showTotal: (total) => `共 ${total} 条` }}
            />
          </Col>
        </Row>
      </Card>

      {/* 1. 上传弹窗 (V3 核心改造) */}
      <Modal
        title="上传新模板 (V3)"
        open={uploadVisible}
        onCancel={() => { setUploadVisible(false); form.resetFields(); }}
        footer={null}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleUpload}>
          <Form.Item label="选择文件" name="file" rules={[{ required: true, message: '请选择文件' }]}>
            <Upload maxCount={1} beforeUpload={() => false}>
              <Button icon={<UploadOutlined />}>点击上传 (.docx/.pdf/.md)</Button>
            </Upload>
          </Form.Item>

          <Form.Item label="模板名称" name="name" rules={[{ required: true }]}>
            <Input placeholder="例如：标准房屋租赁合同" />
          </Form.Item>

          {/* 核心：合同类型选择器 */}
          <Form.Item 
            label="合同类型 (关联知识图谱)" 
            name="category" 
            rules={[{ required: true, message: '必须选择合同类型' }]}
            tooltip="选择系统中已定义的合同类型，系统将自动继承其法律特征"
          >
            <Select 
              placeholder="请选择具体合同类型" 
              showSearch
              filterOption={(input, option) => 
                String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            >
              {contractTypeOptions.map((group) => (
                <OptGroup key={group.label} label={group.label}>
                  {group.options.map((opt: any) => (
                    <Option key={opt.value} value={opt.value}>
                      {opt.label}
                    </Option>
                  ))}
                </OptGroup>
              ))}
            </Select>
          </Form.Item>

          <Form.Item label="备注描述" name="description">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Form.Item name="is_public" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="公开" unCheckedChildren="私有" />
          </Form.Item>

          <Button type="primary" htmlType="submit" block loading={loading}>
            开始上传
          </Button>
        </Form>
      </Modal>

      {/* 2. 预览弹窗 */}
      <Modal 
        title={currentTemplate?.name}
        open={viewContentVisible}
        onCancel={() => setViewContentVisible(false)}
        width={800}
        footer={null}
      >
        <div style={{ maxHeight: '60vh', overflow: 'auto', padding: 20, background: '#f5f5f5' }}>
          <ReactMarkdown>{templateContent}</ReactMarkdown>
        </div>
      </Modal>

      {/* 3. 编辑内容弹窗 (保留旧功能) */}
      <Modal
        title="编辑模板内容"
        open={editContentVisible}
        onCancel={() => setEditContentVisible(false)}
        onOk={editForm.submit}
        width={800}
        okText="保存"
      >
        <Form form={editForm} onFinish={handleSaveContent} layout="vertical">
          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          {/* 编辑时允许修改归类(保留级联选择器以便归档) */}
          <Form.Item name="categoryPath" label="所属分类 (目录)">
            <Cascader options={renderCategoryCascader(categories)} changeOnSelect />
          </Form.Item>
          <Form.Item name="content" label="模板内容 (Markdown)" rules={[{ required: true }]}>
            <Input.TextArea rows={15} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 4. 特征编辑器 (保留旧功能) */}
      {currentTemplate && (
        <TemplateContractFeaturesEditor
          visible={featuresEditorVisible}
          template={currentTemplate}
          selectedCategoryPath={currentCategoryPath}
          onCancel={() => {
            setFeaturesEditorVisible(false);
            setCurrentTemplate(null);
          }}
          onSave={async (data: ContractFeaturesData) => {
            try {
              await contractTemplateApi.updateContractFeatures(currentTemplate.id, data);
              message.success('特征更新成功');
              setFeaturesEditorVisible(false);
              fetchTemplates();
            } catch (e) {
              message.error('特征更新失败');
            }
          }}
        />
      )}
    </>
  );
};

export default TemplateManager;