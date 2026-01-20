// frontend/src/pages/TemplateEditPage.tsx
import React, { useState, useEffect } from 'react';
import {
  Button,
  Card,
  Layout,
  Typography,
  message,
  Space,
  Input,
  Select,
  Form,
  Upload,
  Spin,
  Alert,
  Divider,
  Tabs,
  Row,
  Col,
  Tag,
  Descriptions,
  Tooltip
} from 'antd';
import {
  ArrowLeftOutlined,
  SaveOutlined,
  UploadOutlined,
  FileTextOutlined,
  EditOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { contractTemplateApi } from '../api/contractTemplates';
import type { ContractTemplate } from '../types/contract';
import './TemplateEditPage.css';

const { Header, Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;
const { TabPane } = Tabs;
const { Dragger } = Upload;
const { Option } = Select;

interface TemplateContent {
  template_id: string;
  name: string;
  content: string;
  file_type: string;
  editable: boolean;
}

interface KnowledgeGraphFeatures {
  matched_contract_type: string | null;
  legal_features: {
    transaction_nature: string;
    contract_object: string;
    complexity: string;
    stance: string;
    consideration_type: string;
    consideration_detail: string;
    transaction_characteristics: string;
    usage_scenario?: string;
    legal_basis?: string[];
  } | null;
  usage_scenario: string | null;
  legal_basis: string[];
  match_confidence: number;
}

const TemplateEditPage: React.FC = () => {
  const { templateId } = useParams<{ templateId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [template, setTemplate] = useState<ContractTemplate | null>(null);
  const [contentData, setContentData] = useState<TemplateContent | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [content, setContent] = useState('');
  const [fileList, setFileList] = useState<any[]>([]);
  const [kgFeatures, setKgFeatures] = useState<KnowledgeGraphFeatures | null>(null);

  const [form] = Form.useForm();

  // 权限检查
  const isAdmin = user?.is_admin || false;

  useEffect(() => {
    if (!isAdmin) {
      message.error('仅管理员可以编辑模板');
      navigate('/contract');
      return;
    }
    loadTemplate();
    loadCategories();
  }, [templateId]);

  const loadCategories = async () => {
    try {
      const cats = await contractTemplateApi.getCategoryTree();
      setCategories(cats.map(c => c.name));
    } catch (error) {
      console.error('加载分类失败:', error);
    }
  };

  const loadTemplate = async () => {
    setLoading(true);
    let found: ContractTemplate | undefined;

    try {
      // 获取模板基本信息
      const templates = await contractTemplateApi.getTemplates({ page: 1, page_size: 1000 });
      found = templates.templates.find(t => t.id === templateId);

      if (!found) {
        message.error('模板不存在');
        navigate('/contract');
        return;
      }

      setTemplate(found);

      // 尝试加载模板内容
      try {
        if (!templateId) {
          throw new Error('Template ID is missing');
        }

        const contentData = await contractTemplateApi.getTemplateContent(templateId);
        setContentData({
          ...contentData,
          template_id: templateId,
          name: found.name,
          editable: ['.docx', '.doc', '.txt', '.md', '.rtf'].includes(found.file_type.toLowerCase())
        });
        setContent(contentData.content);

        // 设置表单初始值
        form.setFieldsValue({
          name: found.name,
          category: found.category,
          subcategory: found.subcategory,
          description: found.description,
          is_public: found.is_public,
          keywords: found.keywords?.join(', ') || '',
          tags: found.tags?.join(', ') || ''
        });

        // 同步知识图谱特征
        if (found.name) {
          await syncKnowledgeGraphFeatures(found.name);
        }
      } catch (contentError) {
        console.warn('无法加载模板内容:', contentError);
        setContentData(null);

        // 仍然设置表单初始值
        form.setFieldsValue({
          name: found.name,
          category: found.category,
          subcategory: found.subcategory,
          description: found.description,
          is_public: found.is_public,
          keywords: found.keywords?.join(', ') || '',
          tags: found.tags?.join(', ') || ''
        });

        // 同步知识图谱特征
        if (found.name) {
          await syncKnowledgeGraphFeatures(found.name);
        }
      }
    } catch (error) {
      console.error('加载模板失败:', error);
      message.error('加载模板失败');
    } finally {
      setLoading(false);
    }
  };

  // ✨ 同步知识图谱法律特征
  const syncKnowledgeGraphFeatures = async (contractName: string) => {
    try {
      setSyncing(true);
      const features = await contractTemplateApi.getLegalFeatures(contractName);

      setKgFeatures({
        matched_contract_type: contractName,
        legal_features: features,
        usage_scenario: features.usage_scenario || '',
        legal_basis: features.legal_basis || [],
        match_confidence: 1.0
      });

      // 自动填充表单
      if (features) {
        form.setFieldsValue({
          transaction_nature: features.transaction_nature,
          contract_object: features.contract_object,
          complexity: features.complexity,
          stance: features.stance
        });
      }

      message.success('已同步知识图谱法律特征');
    } catch (error: any) {
      console.log('知识图谱中未找到该合同类型的法律特征');
      setKgFeatures(null);
    } finally {
      setSyncing(false);
    }
  };

  const handleSave = async (values: any) => {
    if (!templateId) return;

    setSaving(true);
    try {
      const updateData: any = {
        name: values.name,
        category: values.category,
        subcategory: values.subcategory,
        description: values.description,
        is_public: values.is_public,
        keywords: values.keywords,
        tags: values.tags
      };

      // 如果有内容编辑且文件可编辑
      if (content && contentData?.editable && content !== contentData.content) {
        updateData.content = content;
      }

      // 如果有新文件上传
      if (fileList.length > 0 && fileList[0].originFileObj) {
        // 创建新的FormData对象用于文件上传
        const formData = new FormData();
        formData.append('file', fileList[0].originFileObj);

        // 添加其他字段到formData
        Object.keys(updateData).forEach(key => {
          formData.append(key, updateData[key]);
        });

        await contractTemplateApi.updateTemplate(templateId, formData);
      } else {
        // 如果没有新文件，只更新元数据
        await contractTemplateApi.updateTemplate(templateId, updateData);
      }

      message.success('模板已更新');
      navigate('/contract');
    } catch (error: any) {
      console.error('保存失败:', error);
      message.error(error.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleFileChange = (info: any) => {
    setFileList(info.fileList);
  };

  if (loading) {
    return (
      <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
        <Content style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
          <Spin size="large" tip="加载中..." />
        </Content>
      </Layout>
    );
  }

  if (!template) {
    return null;
  }

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Header style={{
        background: '#fff',
        padding: '0 24px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <Space>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/contract')}>
            返回
          </Button>
          <Title level={3} style={{ margin: 0 }}>编辑模板</Title>
          <Tag color="blue">管理员模式</Tag>
        </Space>
        <Space>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={() => form.submit()}
          >
            保存更改
          </Button>
        </Space>
      </Header>

      <Content style={{ padding: '24px', maxWidth: 1200, margin: '0 auto', width: '100%' }}>
        <Alert
          message="管理员编辑模式"
          description="您正在以管理员身份编辑此模板。您的更改将立即生效。"
          type="info"
          showIcon
          icon={<CheckCircleOutlined />}
          style={{ marginBottom: 24 }}
        />

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          onValuesChange={(changedValues) => {
            // 当模板名称改变时，自动同步知识图谱
            if (changedValues.name) {
              syncKnowledgeGraphFeatures(changedValues.name);
            }
          }}
        >
          <Tabs defaultActiveKey="metadata">
            <TabPane tab="基本信息" key="metadata">
              <Card>
                <Row gutter={24}>
                  <Col span={12}>
                    <Form.Item
                      label="模板名称"
                      name="name"
                      rules={[{ required: true, message: '请输入模板名称' }]}
                    >
                      <Input
                        placeholder="请输入模板名称"
                        prefix={<EditOutlined />}
                        suffix={
                          <Tooltip title="修改名称后将自动同步知识图谱中的法律特征">
                            <InfoCircleOutlined style={{ color: '#1890ff' }} />
                          </Tooltip>
                        }
                      />
                    </Form.Item>
                  </Col>

                  <Col span={12}>
                    <Form.Item
                      label="类别"
                      name="category"
                      rules={[{ required: true, message: '请选择类别' }]}
                    >
                      <Select placeholder="请选择类别" showSearch allowClear>
                        {categories.map(cat => (
                          <Option key={cat} value={cat}>{cat}</Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </Col>

                  <Col span={12}>
                    <Form.Item label="子类别" name="subcategory">
                      <Input placeholder="请输入子类别（可选）" />
                    </Form.Item>
                  </Col>

                  <Col span={12}>
                    <Form.Item
                      label="公开状态"
                      name="is_public"
                      valuePropName="checked"
                    >
                      <Select>
                        <Option value={true}>公开</Option>
                        <Option value={false}>私有</Option>
                      </Select>
                    </Form.Item>
                  </Col>

                  <Col span={24}>
                    <Form.Item label="描述" name="description">
                      <TextArea rows={3} placeholder="请输入模板描述" />
                    </Form.Item>
                  </Col>

                  <Col span={12}>
                    <Form.Item label="关键词" name="keywords">
                      <Input placeholder="用逗号分隔，如: 劳动,合同,员工" />
                    </Form.Item>
                  </Col>

                  <Col span={12}>
                    <Form.Item label="标签" name="tags">
                      <Input placeholder="用逗号分隔，如: 正式,标准模板" />
                    </Form.Item>
                  </Col>
                </Row>
              </Card>

              {/* ✨ 知识图谱法律特征卡片 */}
              {kgFeatures?.legal_features && (
                <Card
                  title={
                    <Space>
                      <SyncOutlined spin={syncing} />
                      <span>知识图谱法律特征</span>
                      <Tag color="green">已同步</Tag>
                    </Space>
                  }
                  style={{ marginTop: 16 }}
                >
                  <Alert
                    message="自动同步"
                    description="以下法律特征已从知识图谱中自动同步，您也可以手动修改。"
                    type="success"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />

                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="交易性质" name="transaction_nature">
                        <Select placeholder="选择交易性质">
                          <Option value="转移所有权">转移所有权</Option>
                          <Option value="提供服务">提供服务</Option>
                          <Option value="许可使用">许可使用</Option>
                          <Option value="合作经营">合作经营</Option>
                          <Option value="融资借贷">融资借贷</Option>
                          <Option value="劳动用工">劳动用工</Option>
                          <Option value="争议解决">争议解决</Option>
                        </Select>
                      </Form.Item>
                    </Col>

                    <Col span={8}>
                      <Form.Item label="合同标的" name="contract_object">
                        <Select placeholder="选择合同标的">
                          <Option value="货物">货物</Option>
                          <Option value="工程">工程</Option>
                          <Option value="智力成果">智力成果</Option>
                          <Option value="服务">服务</Option>
                          <Option value="股权">股权</Option>
                          <Option value="资金">资金</Option>
                          <Option value="劳动力">劳动力</Option>
                          <Option value="不动产">不动产</Option>
                          <Option value="动产">动产</Option>
                        </Select>
                      </Form.Item>
                    </Col>

                    <Col span={8}>
                      <Form.Item label="复杂程度" name="complexity">
                        <Select placeholder="选择复杂程度">
                          <Option value="简单">简单</Option>
                          <Option value="中等">中等</Option>
                          <Option value="复杂">复杂</Option>
                        </Select>
                      </Form.Item>
                    </Col>

                    <Col span={8}>
                      <Form.Item label="起草立场" name="stance">
                        <Select placeholder="选择起草立场">
                          <Option value="甲方">甲方</Option>
                          <Option value="乙方">乙方</Option>
                          <Option value="中立">中立</Option>
                          <Option value="平衡">平衡</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                  </Row>

                  {kgFeatures.legal_features && (
                    <>
                      <Divider style={{ margin: '16px 0' }} />
                      <Descriptions bordered size="small" column={2}>
                        <Descriptions.Item label="交易对价类型">
                          {kgFeatures.legal_features.consideration_type}
                        </Descriptions.Item>
                        <Descriptions.Item label="交易对价详情">
                          {kgFeatures.legal_features.consideration_detail}
                        </Descriptions.Item>
                        <Descriptions.Item label="交易特征" span={2}>
                          {kgFeatures.legal_features.transaction_characteristics}
                        </Descriptions.Item>
                        <Descriptions.Item label="适用场景" span={2}>
                          {kgFeatures.usage_scenario}
                        </Descriptions.Item>
                        {kgFeatures.legal_basis && kgFeatures.legal_basis.length > 0 && (
                          <Descriptions.Item label="法律依据" span={2}>
                            {kgFeatures.legal_basis.map((basis, idx) => (
                              <Tag key={idx} color="blue">{basis}</Tag>
                            ))}
                          </Descriptions.Item>
                        )}
                      </Descriptions>
                    </>
                  )}
                </Card>
              )}

              {/* 当没有知识图谱特征时显示提示 */}
              {!kgFeatures?.legal_features && (
                <Card
                  title={
                    <Space>
                      <SyncOutlined />
                      <span>知识图谱法律特征</span>
                      <Tag color="default">未同步</Tag>
                    </Space>
                  }
                  style={{ marginTop: 16 }}
                >
                  <Alert
                    message="未找到知识图谱特征"
                    description={
                      <span>
                        知识图谱中未找到该模板对应的法律特征。请检查模板名称是否正确，
                        或在知识图谱管理中添加该合同类型的法律特征。
                      </span>
                    }
                    type="warning"
                    showIcon
                  />
                </Card>
              )}
            </TabPane>

            <TabPane tab="内容编辑" key="content">
              {contentData ? (
                contentData.editable ? (
                  <Card>
                    <Alert
                      message="内容编辑"
                      description="您可以直接编辑模板内容。更改将保存为新的文档文件。"
                      type="warning"
                      showIcon
                      style={{ marginBottom: 16 }}
                    />
                    <TextArea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      rows={20}
                      placeholder="模板内容..."
                      style={{ fontFamily: 'monospace' }}
                    />
                  </Card>
                ) : (
                  <Card>
                    <Alert
                      message="不支持在线编辑"
                      description={`此文件类型（${contentData.file_type}）不支持在线编辑。您可以上传新文件来替换。`}
                      type="warning"
                      showIcon
                    />
                  </Card>
                )
              ) : (
                <Card>
                  <Alert
                    message="内容加载失败"
                    description="无法加载模板内容，可能文件格式不支持或文件已损坏。"
                    type="error"
                    showIcon
                  />
                </Card>
              )}
            </TabPane>

            <TabPane tab="文件替换" key="file">
              <Card>
                <Alert
                  message="文件替换"
                  description="上传新文件将完全替换当前模板文件。原文件将被删除。"
                  type="warning"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
                <Dragger
                  fileList={fileList}
                  onChange={handleFileChange}
                  beforeUpload={() => false}
                  maxCount={1}
                  accept=".docx,.doc,.pdf"
                >
                  <p className="ant-upload-drag-icon">
                    <UploadOutlined />
                  </p>
                  <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                  <p className="ant-upload-hint">
                    支持 .docx, .doc, .pdf 格式
                  </p>
                </Dragger>

                {template && (
                  <div style={{ marginTop: 16 }}>
                    <Text type="secondary">当前文件: {template.file_name}</Text>
                    <br />
                    <Text type="secondary">文件类型: {template.file_type}</Text>
                    <br />
                    <Text type="secondary">文件大小: {(template.file_size / 1024).toFixed(2)} KB</Text>
                  </div>
                )}
              </Card>
            </TabPane>
          </Tabs>
        </Form>
      </Content>
    </Layout>
  );
};

export default TemplateEditPage;
