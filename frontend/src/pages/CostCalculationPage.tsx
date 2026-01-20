// frontend/src/pages/CostCalculationPage.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  InputNumber,
  Table,
  Typography,
  Alert,
  Space,
  Row,
  Col,
  Divider,
  Spin,
  message,
  Upload,
  Tag,
  Tabs,
  Radio,
  Checkbox,
  Dropdown
} from 'antd';
import {
  CalculatorOutlined,
  SyncOutlined,
  UploadOutlined,
  FileTextOutlined,
  EditOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  ArrowLeftOutlined,
  UserOutlined,
  FileSearchOutlined,
  SearchOutlined,
  AppstoreOutlined,
  FileProtectOutlined,
  DiffOutlined
} from '@ant-design/icons';
import type { UploadProps, MenuProps } from 'antd';
import api from '../api';
import { CostCalculationRequest, CostCalculationResponse } from '../types/requests';
import type { CaseInfo } from '../types/requests';
import EnhancedModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import { useSessionPersistence } from '../hooks/useSessionPersistence';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;
const { TextArea } = Input;
const { Dragger } = Upload;

const CostCalculationPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CostCalculationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 新增：智能提取模式相关状态
  const [activeMode, setActiveMode] = useState<'manual' | 'smart'>('manual');
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractedInfo, setExtractedInfo] = useState<CaseInfo | null>(null);

  // 新增：用户选择
  const [stance, setStance] = useState<'plaintiff' | 'defendant' | 'applicant' | 'respondent'>('plaintiff');
  const [includeLawyerFee, setIncludeLawyerFee] = useState(true);
  const [lawyerFeeBasis, setLawyerFeeBasis] = useState<string>('');
  const [lawyerFeeRate, setLawyerFeeRate] = useState<number | undefined>();

  // ========== 会话持久化 ==========
  // 定义会话数据类型
  interface CostCalculationSessionData {
    activeMode: 'manual' | 'smart';
    formValues: CostCalculationRequest | null;
    result: CostCalculationResponse | null;
    stance: 'plaintiff' | 'defendant' | 'applicant' | 'respondent';
    includeLawyerFee: boolean;
    lawyerFeeBasis: string;
    lawyerFeeRate?: number;
    extractedInfo: CaseInfo | null;
  }

  const {
    sessionId: persistedSessionId,
    sessionData: persistedSessionData,
    hasSession,
    saveSession,
    clearSession,
    isLoading: isRestoringSession
  } = useSessionPersistence<CostCalculationSessionData>('cost_calculation_session', {
    expirationTime: 2 * 60 * 60 * 1000, // 2小时过期
    onRestore: (restoredSessionId, restoredData) => {
      console.log('[费用测算] 恢复会话:', restoredSessionId, restoredData);

      // 恢复会话状态
      setActiveMode(restoredData.activeMode);
      setStance(restoredData.stance);
      setIncludeLawyerFee(restoredData.includeLawyerFee);
      setLawyerFeeBasis(restoredData.lawyerFeeBasis || '');
      setLawyerFeeRate(restoredData.lawyerFeeRate);

      // 恢复表单数据
      if (restoredData.formValues) {
        form.setFieldsValue(restoredData.formValues);
      }

      // 恢复计算结果
      if (restoredData.result) {
        setResult(restoredData.result);
      }

      // 恢复智能提取的信息
      if (restoredData.extractedInfo) {
        setExtractedInfo(restoredData.extractedInfo);
      }

      message.success('已恢复之前的费用测算会话');
    }
  });
  // ========== 会话持久化结束 ==========

  // 自动保存会话数据
  useEffect(() => {
    if (persistedSessionId) {
      const formValues = form.getFieldsValue() as CostCalculationRequest;
      saveSession(persistedSessionId, {
        activeMode,
        formValues,
        result,
        stance,
        includeLawyerFee,
        lawyerFeeBasis,
        lawyerFeeRate,
        extractedInfo
      });
    }
  }, [activeMode, result, stance, includeLawyerFee, lawyerFeeBasis, lawyerFeeRate, extractedInfo, form, persistedSessionId, saveSession]);

  const caseTypes = [
    { value: 'contract_dispute', label: '合同纠纷' },
    { value: 'labor_dispute', label: '劳动争议' },
    { value: 'intellectual_property', label: '知识产权' },
    { value: 'marriage_family', label: '婚姻家庭' },
    { value: 'traffic_accident', label: '交通事故' },
    { value: 'criminal_case', label: '刑事案件' },
    { value: 'administrative_litigation', label: '行政诉讼' },
    { value: 'real_estate_dispute', label: '房产纠纷' },
    { value: 'construction_project', label: '建设工程' },
    { value: 'medical_dispute', label: '医疗纠纷' },
    { value: 'company_law', label: '公司法务' },
    { value: 'other', label: '其他类型' },
  ];

  const columns = [
    {
      title: '费用项目',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '金额(元)',
      dataIndex: 'amount',
      key: 'amount',
      render: (text: number) => text.toLocaleString('zh-CN', { minimumFractionDigits: 2 }),
      sorter: (a: any, b: any) => a.amount - b.amount,
    },
  ];

  // === 原有手动输入模式的处理函数 ===
  const handleCalculate = async (values: CostCalculationRequest) => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.calculateCost(values);
      setResult(response.data);

      // 生成会话ID并保存会话
      const sessionId = `cost_calc_${Date.now()}`;
      saveSession(sessionId, {
        activeMode: 'manual',
        formValues: values,
        result: response.data,
        stance,
        includeLawyerFee,
        lawyerFeeBasis,
        lawyerFeeRate,
        extractedInfo: null
      });

      message.success('费用计算完成');
    } catch (err) {
      console.error('费用计算失败:', err);
      setError('费用计算失败，请稍后重试或联系管理员');
      message.error('费用计算失败');
    } finally {
      setLoading(false);
    }
  };

  // === 新增：智能提取模式的处理函数 ===

  // 1. 上传文件
  const handleUploadDocuments = async () => {
    if (uploadedFiles.length === 0) {
      message.warning('请先上传案件资料');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();

      // 从 uploadedFiles 状态中获取实际文件对象
      // 注意：由于 Upload 组件的 beforeUpload 返回 false，
      // 文件对象存储在 fileList 的 originFileObj 属性中
      for (const fileItem of uploadedFiles) {
        const file = fileItem.originFileObj;
        if (file) {
          formData.append('files', file);
        }
      }

      // 验证是否有文件被添加到 FormData
      const hasFiles = formData.getAll('files').length > 0;
      if (!hasFiles) {
        message.error('未能获取文件，请重新选择文件');
        setUploading(false);
        return;
      }

      const response = await api.uploadCostCalcDocuments(formData);

      if (response.data.success) {
        message.success('资料上传成功，正在提取案件信息...');

        // 自动触发信息提取
        const fileIds = response.data.files.map((f: any) => f.file_id);
        setTimeout(() => handleExtractInfo(response.data.upload_id, fileIds), 500);
      }
    } catch (error: any) {
      console.error('上传失败:', error);
      message.error(error.response?.data?.detail || '上传失败，请重试');
    } finally {
      setUploading(false);
    }
  };

  // 2. 提取案件信息
  const handleExtractInfo = async (currentUploadId: string, fileIds: string[]) => {
    setExtracting(true);
    try {
      const response = await api.extractCostCalcCaseInfo({
        upload_id: currentUploadId,
        file_names: fileIds
      });

      if (response.data.success && response.data.case_info) {
        setExtractedInfo(response.data.case_info);
        form.setFieldsValue(response.data.case_info);
        message.success('案件信息提取成功');

        // 显示警告（如果有）
        if (response.data.warnings && response.data.warnings.length > 0) {
          message.warning(response.data.warnings.join('; '));
        }
      } else {
        message.error(response.data.error || '信息提取失败');
      }
    } catch (error: any) {
      console.error('提取失败:', error);
      message.error(error.response?.data?.detail || '信息提取失败');
    } finally {
      setExtracting(false);
    }
  };

  // 3. 使用提取的信息计算费用（V2）
  const handleCalculateV2 = async () => {
    if (!extractedInfo) {
      message.warning('请先提取或填写案件信息');
      return;
    }

    setLoading(true);
    try {
      const values = await form.validateFields();

      const response = await api.calculateCostV2({
        case_info: {
          ...values,
          parties: values.parties || [],
          litigation_requests: values.litigation_requests || []
        },
        stance: stance,
        include_lawyer_fee: includeLawyerFee,
        lawyer_fee_basis: lawyerFeeBasis || undefined,
        lawyer_fee_rate: lawyerFeeRate
      });

      if (response.data.success) {
        setResult(response.data);

        // 生成会话ID并保存会话
        const sessionId = `cost_calc_${Date.now()}`;
        saveSession(sessionId, {
          activeMode: 'smart',
          formValues: values,
          result: response.data,
          stance,
          includeLawyerFee,
          lawyerFeeBasis,
          lawyerFeeRate,
          extractedInfo
        });

        message.success('费用计算完成');
      }
    } catch (error: any) {
      console.error('计算失败:', error);
      message.error(error.response?.data?.detail || '费用计算失败');
    } finally {
      setLoading(false);
    }
  };

  // 文件上传配置
  const uploadProps: UploadProps = {
    name: 'files',
    multiple: true,
    fileList: [],
    accept: '.docx,.doc,.pdf,.txt,.jpg,.jpeg,.png',
    beforeUpload: (file) => {
      const isValidType = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'image/jpeg',
        'image/png'
      ].includes(file.type);

      if (!isValidType) {
        const fileExt = file.name.split('.').pop()?.toLowerCase();
        const validExts = ['docx', 'doc', 'pdf', 'txt', 'jpg', 'jpeg', 'png'];
        if (!validExts.includes(fileExt || '')) {
          message.error('只支持上传 Word、PDF、TXT、图片文件');
          return Upload.LIST_IGNORE;
        }
      }

      const isValidSize = file.size <= 50 * 1024 * 1024;
      if (!isValidSize) {
        message.error('文件大小不能超过 50MB');
        return Upload.LIST_IGNORE;
      }

      return false;
    },
    onChange: (info) => {
      setUploadedFiles(info.fileList);
    },
    onRemove: (file) => {
      setUploadedFiles(uploadedFiles.filter(f => f.uid !== file.uid));
    }
  };

  const handleReset = () => {
    form.resetFields();
    setResult(null);
    setError(null);
    setUploadedFiles([]);
    setExtractedInfo(null);
    setStance('plaintiff');
    setIncludeLawyerFee(true);
    setLawyerFeeBasis('');
    setLawyerFeeRate(undefined);
    // 清除持久化会话
    clearSession();
  };

  // 顶部导航栏 - 功能模块快捷入口
  const quickNavItems: MenuProps['items'] = [
    { key: 'divider1', type: 'divider' },
    {
      key: 'consultation',
      label: '智能咨询',
      icon: <UserOutlined />,
      onClick: () => navigate('/consultation')
    },
    {
      key: 'legal-analysis',
      label: '法律分析',
      icon: <FileSearchOutlined />,
      onClick: () => navigate('/analysis')
    },
    {
      key: 'legal-search',
      label: '法律检索',
      icon: <SearchOutlined />,
      onClick: () => message.info('法律检索功能开发中')
    },
    { key: 'divider2', type: 'divider' },
    {
      key: 'template-search',
      label: '模板查询',
      icon: <AppstoreOutlined />,
      onClick: () => navigate('/contract')
    },
    {
      key: 'contract-generation',
      label: '合同生成',
      icon: <FileProtectOutlined />,
      onClick: () => navigate('/contract/generate')
    },
    {
      key: 'contract-review',
      label: '合同审查',
      icon: <DiffOutlined />,
      onClick: () => navigate('/contract/review')
    },
    { key: 'divider3', type: 'divider' },
    {
      key: 'cost-calculation',
      label: '费用测算',
      icon: <CalculatorOutlined />,
      disabled: true,
      onClick: () => navigate('/cost-calculation')
    },
  ];

  // 渲染手动输入模式
  const renderManualMode = () => (
    <Card title="手动输入案件信息" style={{ marginBottom: 24 }}>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleCalculate}
      >
        <Form.Item
          label="案件类型"
          name="case_type"
          rules={[{ required: true, message: '请选择案件类型' }]}
        >
          <Select placeholder="请选择案件类型">
            {caseTypes.map(type => (
              <Option key={type.value} value={type.value}>
                {type.label}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          label="案件描述"
          name="case_description"
          rules={[{ required: true, message: '请输入案件描述' }]}
        >
          <TextArea
            rows={6}
            placeholder="请简要描述案件情况，包括争议焦点、涉及金额等信息。例如：买卖合同纠纷，对方未按时交付货物，造成损失约10万元。"
          />
        </Form.Item>

        <Form.Item
          label="案件标的额（元）"
          name="case_amount"
        >
          <InputNumber
            style={{ width: '100%' }}
            placeholder="请输入案件标的额（可选）"
            min={0}
            step={1000}
          />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={loading} icon={<SyncOutlined spin={loading} />}>
              计算费用
            </Button>
            <Button onClick={handleReset}>
              重置
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );

  // 渲染智能提取模式
  const renderSmartMode = () => (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* 步骤1：上传文件 */}
      <Card title="1. 上传案件资料" extra={extractedInfo && <Tag color="success"><CheckCircleOutlined /> 已完成</Tag>}>
        <Alert
          message="请上传案件相关资料"
          description="支持上传起诉状、答辩状、证据材料等文件。系统将自动提取案件类型、当事人信息、诉讼请求等关键信息。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Dragger {...uploadProps} style={{ marginBottom: 16 }}>
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
          <p className="ant-upload-hint">
            支持上传 Word、PDF、TXT、图片文件，单个文件不超过 50MB
          </p>
        </Dragger>

        {uploadedFiles.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <Text strong>已上传文件：</Text>
            <div style={{ marginTop: 8 }}>
              {uploadedFiles.map((file) => (
                <Tag key={file.uid} closable onClose={() => {
                  setUploadedFiles(uploadedFiles.filter(f => f.uid !== file.uid));
                }} style={{ marginBottom: 4 }}>
                  <FileTextOutlined style={{ marginRight: 4 }} />
                  {file.name}
                </Tag>
              ))}
            </div>
          </div>
        )}

        <Button
          type="primary"
          icon={<ArrowRightOutlined />}
          onClick={handleUploadDocuments}
          loading={uploading}
          disabled={uploadedFiles.length === 0}
          block
        >
          提取案件信息
        </Button>
      </Card>

      {/* 步骤2：确认和编辑信息 */}
      {extracting ? (
        <Card title="2. 确认案件信息">
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" />
            <Paragraph style={{ marginTop: 16 }}>正在分析案件资料，提取关键信息...</Paragraph>
          </div>
        </Card>
      ) : extractedInfo ? (
        <Card
          title="2. 确认案件信息"
          extra={<Button type="link" icon={<EditOutlined />}>编辑</Button>}
        >
          <Form
            form={form}
            layout="vertical"
            initialValues={extractedInfo}
          >
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="案件类型"
                  name="case_type"
                  rules={[{ required: true, message: '请选择案件类型' }]}
                >
                  <Select placeholder="请选择案件类型">
                    {caseTypes.map(type => (
                      <Option key={type.value} value={type.value}>
                        {type.label}
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>

              <Col span={12}>
                <Form.Item label="标的额（元）" name="case_amount">
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="请输入标的额（可选）"
                    min={0}
                    step={1000}
                  />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item label="当事人" name="parties">
              <Select
                mode="tags"
                placeholder="请输入当事人名称，按回车添加"
                tokenSeparators={[',', '，', ';', '；']}
              />
            </Form.Item>

            <Form.Item
              label="诉讼请求"
              name="litigation_requests"
              tooltip="这是费用计算的核心依据，请务必填写准确"
            >
              <Select
                mode="tags"
                placeholder="请输入诉讼请求，按回车添加"
                tokenSeparators={[',', '，', ';', '；']}
              />
            </Form.Item>

            <Form.Item
              label="案件概况"
              name="case_description"
              rules={[{ required: true, message: '请输入案件概况' }]}
            >
              <TextArea rows={4} placeholder="请简要描述案件基本情况..." />
            </Form.Item>

            <Divider>诉讼立场</Divider>

            <Form.Item label="您的立场">
              <Radio.Group value={stance} onChange={(e) => setStance(e.target.value)}>
                <Radio value="plaintiff">原告</Radio>
                <Radio value="defendant">被告</Radio>
                <Radio value="applicant">申请人</Radio>
                <Radio value="respondent">被申请人</Radio>
              </Radio.Group>
            </Form.Item>

            <Divider>律师费设置</Divider>

            <Form.Item>
              <Checkbox
                checked={includeLawyerFee}
                onChange={(e) => setIncludeLawyerFee(e.target.checked)}
              >
                计算律师费
              </Checkbox>
            </Form.Item>

            {includeLawyerFee && (
              <>
                <Form.Item label="律师费计费依据">
                  <TextArea
                    rows={3}
                    placeholder="例如：风险代理、按标的额比例、固定费用等。如果不填写，系统将按通用标准估算。"
                    value={lawyerFeeBasis}
                    onChange={(e) => setLawyerFeeBasis(e.target.value)}
                  />
                </Form.Item>

                {lawyerFeeBasis && (
                  <Form.Item label="费率（%）">
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="例如：3-10，按标的额的百分比"
                      min={0}
                      max={100}
                      value={lawyerFeeRate}
                      onChange={(value) => setLawyerFeeRate(value)}
                    />
                  </Form.Item>
                )}
              </>
            )}

            <Form.Item style={{ marginTop: 24 }}>
              <Space>
                <Button onClick={() => setExtractedInfo(null)}>
                  重新上传
                </Button>
                <Button
                  type="primary"
                  size="large"
                  icon={<CalculatorOutlined />}
                  onClick={handleCalculateV2}
                  loading={loading}
                >
                  计算费用
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      ) : (
        <Card title="2. 确认案件信息">
          <Alert
            message="请先上传案件资料"
            description="系统将自动提取案件信息，您也可以在提取后进行编辑。"
            type="info"
            showIcon
          />
        </Card>
      )}
    </Space>
  );

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#f5f5f5' }}>
      {/* 统一导航栏 */}
      <EnhancedModuleNavBar currentModuleKey="cost-calculation" />

      <div style={{ flex: 1, padding: '24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
        {/* 会话恢复提示 */}
        {hasSession && (
          <Alert
            message="检测到之前的会话"
            description={
              <Space direction="vertical" size="small">
                <Text>系统检测到您之前有一个未完成的费用测算会话。您可以：</Text>
                <Space>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => {
                      // 会话已经在 onRestore 中自动恢复
                      message.info('会话已恢复');
                    }}
                  >
                    继续之前的计算
                  </Button>
                  <Button
                    size="small"
                    onClick={() => {
                      clearSession();
                      handleReset();
                      message.info('已开始新的计算');
                    }}
                  >
                    重新开始
                  </Button>
                </Space>
              </Space>
            }
            type="info"
            showIcon
            closable
            style={{ marginBottom: 24 }}
          />
        )}

        <Tabs
          activeKey={activeMode}
          onChange={(key) => {
            setActiveMode(key as 'manual' | 'smart');
            setResult(null);
            setError(null);
            handleReset();
          }}
          items={[
            {
              key: 'manual',
              label: '手动输入',
              children: (
                <Row gutter={24}>
                  <Col span={12}>
                    {renderManualMode()}
                    {error && (
                      <Alert
                        message="计算错误"
                        description={error}
                        type="error"
                        showIcon
                        style={{ marginTop: 24 }}
                      />
                    )}
                  </Col>
                  <Col span={12}>
                    <Card title="计算结果">
                      {loading ? (
                        <div style={{ textAlign: 'center', padding: '40px 0' }}>
                          <Spin size="large" />
                          <Paragraph style={{ marginTop: 16 }}>正在计算费用，请稍候...</Paragraph>
                        </div>
                      ) : result ? (
                        <>
                          <div style={{ marginBottom: 24, padding: '16px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4 }}>
                            <Text strong style={{ fontSize: 18 }}>
                              总费用估算: <Text type="success" style={{ fontSize: 24 }}>{result.total_cost.toLocaleString('zh-CN', { minimumFractionDigits: 2 })} 元</Text>
                            </Text>
                          </div>

                          <div style={{ marginBottom: 24 }}>
                            <Title level={4}>费用明细</Title>
                            <Table
                              columns={columns}
                              dataSource={result.cost_breakdown.map((item, index) => ({ ...item, key: index }))}
                              pagination={false}
                              size="small"
                            />
                          </div>

                          <div style={{ marginBottom: 24 }}>
                            <Title level={4}>计算依据</Title>
                            <Paragraph>{result.calculation_basis}</Paragraph>
                          </div>

                          <Divider />

                          <Alert
                            message="重要提示"
                            description={
                              <div>
                                <Paragraph>{result.disclaimer}</Paragraph>
                                <Paragraph type="secondary" italic>
                                  以上费用为估算值，实际费用可能因具体情况、地区差异、律师收费标准等因素而有所不同。
                                  建议在实际委托前与律师详细沟通具体收费标准。
                                </Paragraph>
                              </div>
                            }
                            type="info"
                            showIcon
                          />
                        </>
                      ) : (
                        <div style={{ textAlign: 'center', padding: '40px 0', color: '#bfbfbf' }}>
                          <CalculatorOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                          <Paragraph>请输入案件信息并点击"计算费用"按钮</Paragraph>
                          <Paragraph type="secondary">
                            系统将根据《诉讼费用交纳办法》等相关法规，
                            为您提供诉讼费、保全费、执行费、律师费等费用的估算
                          </Paragraph>
                        </div>
                      )}
                    </Card>
                  </Col>
                </Row>
              )
            },
            {
              key: 'smart',
              label: '智能提取',
              children: (
                <Row gutter={24}>
                  <Col span={12}>
                    {renderSmartMode()}
                    {error && (
                      <Alert
                        message="计算错误"
                        description={error}
                        type="error"
                        showIcon
                        style={{ marginTop: 24 }}
                      />
                    )}
                  </Col>
                  <Col span={12}>
                    <Card title="计算结果">
                      {loading ? (
                        <div style={{ textAlign: 'center', padding: '40px 0' }}>
                          <Spin size="large" />
                          <Paragraph style={{ marginTop: 16 }}>正在计算费用，请稍候...</Paragraph>
                        </div>
                      ) : result ? (
                        <>
                          <div style={{ marginBottom: 24, padding: '16px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4 }}>
                            <Text strong style={{ fontSize: 18 }}>
                              总费用估算: <Text type="success" style={{ fontSize: 24 }}>{result.total_cost.toLocaleString('zh-CN', { minimumFractionDigits: 2 })} 元</Text>
                            </Text>
                          </div>

                          <div style={{ marginBottom: 24 }}>
                            <Title level={4}>费用明细</Title>
                            <Table
                              columns={columns}
                              dataSource={result.cost_breakdown.map((item, index) => ({ ...item, key: index }))}
                              pagination={false}
                              size="small"
                            />
                          </div>

                          <div style={{ marginBottom: 24 }}>
                            <Title level={4}>计算依据</Title>
                            <Paragraph>{result.calculation_basis}</Paragraph>
                          </div>

                          <Divider />

                          <Alert
                            message="重要提示"
                            description={
                              <div>
                                <Paragraph>{result.disclaimer}</Paragraph>
                                <Paragraph type="secondary" italic>
                                  以上费用为估算值，实际费用可能因具体情况、地区差异、律师收费标准等因素而有所不同。
                                  建议在实际委托前与律师详细沟通具体收费标准。
                                </Paragraph>
                              </div>
                            }
                            type="info"
                            showIcon
                          />
                        </>
                      ) : (
                        <div style={{ textAlign: 'center', padding: '40px 0', color: '#bfbfbf' }}>
                          <CalculatorOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                          <Paragraph>请上传案件资料并提取信息后点击"计算费用"</Paragraph>
                          <Paragraph type="secondary">
                            系统将根据《诉讼费用交纳办法》等相关法规，
                            为您提供诉讼费、保全费、执行费、律师费等费用的估算
                          </Paragraph>
                        </div>
                      )}
                    </Card>
                  </Col>
                </Row>
              )
            }
          ]}
        />
      </div>
    </div>
  );
};

export default CostCalculationPage;
