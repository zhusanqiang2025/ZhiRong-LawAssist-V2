// frontend/src/components/TemplateContractFeaturesEditor.tsx
import React, { useState, useEffect } from 'react';
import {
  Modal, Form, Select, Input, Switch, Space, Typography, Divider, Row, Col, Tag, Button, Alert, message
} from 'antd';
import type { ContractTemplate, ContractLegalFeatures } from '../types/contract';
import { contractTemplateApi } from '../api/contractTemplates';

const { Title, Text } = Typography;
const { Option } = Select;
const { TextArea } = Input;

// Select with tags for legal_basis field
const SelectWithTags: React.FC<{
  value?: string[];
  onChange?: (value: string[]) => void;
  placeholder?: string;
}> = ({ value = [], onChange, placeholder = '请输入法律依据' }) => {
  const [inputValue, setInputValue] = useState('');

  const handleInputConfirm = () => {
    if (inputValue && !value.includes(inputValue)) {
      onChange?.([...value, inputValue]);
    }
    setInputValue('');
  };

  const handleTagClose = (removedTag: string) => {
    onChange?.(value.filter(tag => tag !== removedTag));
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space size="small" wrap>
        {value.map((tag) => (
          <Tag key={tag} closable onClose={() => handleTagClose(tag)} color="blue">
            {tag}
          </Tag>
        ))}
      </Space>
      <Input
        placeholder={placeholder}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onPressEnter={handleInputConfirm}
        onBlur={handleInputConfirm}
      />
    </Space>
  );
};

interface TemplateContractFeaturesEditorProps {
  visible: boolean;
  template: ContractTemplate | null;
  selectedCategoryPath?: string[];
  onCancel: () => void;
  onSave: (features: ContractFeaturesData) => Promise<void>;
  loading?: boolean;
}

export interface ContractFeaturesData {
  primary_contract_type?: string;
  secondary_types?: string[];

  // 模板变体字段
  version_type?: string;
  stance_tendency?: string;
  detailed_usage_scenario?: string;

  // 知识图谱7个法律特征字段
  transaction_nature?: string;        // 交易性质
  contract_object?: string;           // 合同标的
  consideration_type?: string;        // 对价类型
  consideration_detail?: string;      // 对价详情
  transaction_characteristics?: string; // 交易特征
  usage_scenario?: string;            // 适用场景
  legal_basis?: string[];             // 法律依据
}

// ==================== 模板变体字段选项 ====================

const VERSION_TYPE_OPTIONS = [
  { value: '标准版', label: '标准版（默认）' },
  { value: '简化版', label: '简化版（条款简化）' },
  { value: '详细版', label: '详细版（条款完整）' },
];

const STANCE_TENDENCY_OPTIONS = [
  { value: '中立', label: '中立（双方平衡）' },
  { value: '甲方', label: '甲方（偏向甲方）' },
  { value: '乙方', label: '乙方（偏向乙方）' },
];

// ==================== 知识图谱法律特征选项 ====================

// 1. 交易性质选项
const TRANSACTION_NATURE_OPTIONS = [
  { value: '转移所有权', label: '转移所有权（买卖）' },
  { value: '提供服务', label: '提供服务（服务/委托）' },
  { value: '许可使用', label: '许可使用（技术转让/特许经营）' },
  { value: '合作经营', label: '合作经营（合伙/联营）' },
  { value: '融资借贷', label: '融资借贷（借款/融资租赁）' },
  { value: '劳动用工', label: '劳动用工（劳动合同）' },
  { value: '股权投资', label: '股权投资（投资/并购）' },
  { value: '资产处置', label: '资产处置（转让/重组）' },
  { value: '知识产权', label: '知识产权（IP交易/授权）' },
  { value: '借款融资', label: '借款融资' },
  { value: '消费保管', label: '消费保管' },
  { value: '其他', label: '其他' },
];

// 2. 合同标的选择项
const CONTRACT_OBJECT_OPTIONS = [
  { value: '不动产', label: '不动产（房产、土地）' },
  { value: '动产', label: '动产（商品、设备）' },
  { value: '智力成果', label: '智力成果（软件、专利、著作权）' },
  { value: '服务', label: '服务（人力服务）' },
  { value: '股权', label: '股权（股权转让）' },
  { value: '资金', label: '资金（借款、投资）' },
  { value: '劳动力', label: '劳动力' },
  { value: '其他', label: '其他' },
];

// 3. 对价类型选项
const CONSIDERATION_TYPE_OPTIONS = [
  { value: '有偿', label: '有偿（支付对价）' },
  { value: '无偿', label: '无偿（无对价）' },
  { value: '混合', label: '混合（部分有偿）' },
];

// 4. 对价详情选项
const CONSIDERATION_DETAIL_OPTIONS = [
  { value: '双方协商', label: '双方协商' },
  { value: '固定价格', label: '固定价格' },
  { value: '按市场价格', label: '按市场价格' },
  { value: '利息形式', label: '利息形式' },
  { value: '租金形式', label: '租金形式' },
  { value: '服务费', label: '服务费' },
  { value: '分期付款', label: '分期付款' },
  { value: '股权置换', label: '股权置换' },
  { value: '无对价', label: '无对价' },
  { value: '无偿给予', label: '无偿给予' },
  { value: '其他', label: '其他' },
];

// ==================== 其他选项 ====================

// 10个一级分类（用于 primary_contract_type 字段）
const PRIMARY_CONTRACT_TYPES = [
  '民法典典型合同',
  '非典型商事合同',
  '劳动与人力资源',
  '行业特定合同',
  '争议解决与法律程序',
  '婚姻家事与私人财富',
  '公司治理与合规',
  '政务与公共服务',
  '跨境与国际合同',
  '通用框架与兜底协议',
];

// 三级分类映射表（用于 secondary_types 字段）
const TERTIARY_CONTRACT_TYPES: Record<string, string[]> = {
  '民法典典型合同': [
    '动产买卖合同', '不动产买卖合同',
    '公益赠与合同', '一般赠与合同',
    '个人借款合同', '企业借款合同', '委托贷款合同',
    '住宅租赁合同', '商业租赁合同', '融资租赁合同',
    '工程承揽合同', '加工承揽合同', '定作合同',
    '建设工程施工合同', '工程总承包合同', '分包合同', '勘察设计合同',
    '公路货物运输合同', '多式联运合同', '物流服务合同',
    '技术开发合同', '技术转让合同', '技术咨询合同', '技术服务合同',
    '委托代理合同', '委托管理合同', '授权委托书',
    '前期物业服务合同', '物业管理服务合同',
    '行纪合同', '中介合同', '居间合同',
  ],
  '非典型商事合同': [
    '股权转让协议', '增资扩股协议', '股东协议', '投资合作协议', '股权代持协议', '股权回购协议', '并购重组协议',
    '普通合伙协议', '有限合伙协议', '项目联营协议', '联合体投标协议',
    '特许经营合同', '品牌加盟合同', '代理经销合同',
    '商标授权许可协议', '专利实施许可协议', 'IP衍生品开发协议',
  ],
  '劳动与人力资源': [
    '劳动合同(固定期限)', '劳动合同(无固定期限)', '聘用协议',
    '劳务派遣协议', '非全日制用工协议', '实习协议', '返聘协议',
    '保密协议(劳动版)', '竞业限制协议', '培训服务协议', '员工期权激励协议',
  ],
  '行业特定合同': [
    '软件开发合同', 'SaaS服务协议', '数据处理协议(DPA)', '平台用户协议', '隐私政策',
    '演艺经纪合同', '影视投资制作合同', '著作权转让协议', 'MCN签约协议',
    'OEM/ODM代工协议', '长期供货框架协议', '质量保证协议(QA)', '设备采购合同',
  ],
  '争议解决与法律程序': [
    '庭外和解协议', '民事调解协议', '赔偿谅解协议', '交通事故赔偿协议', '劳动争议和解书',
    '还款计划书', '债务重组协议', '以物抵债协议', '债权转让通知书', '催款函',
  ],
  '婚姻家事与私人财富': [
    '婚前财产协议', '婚内财产协议', '离婚协议书', '分居协议', '抚养权变更协议',
    '遗赠扶养协议', '分家析产协议', '意定监护协议', '家族信托契约',
  ],
  '公司治理与合规': [
    '公司章程', '股东会议事规则', '董事会议事规则', '监事会议事规则', '发起人协议',
    '一致行动人协议', '投票权委托协议', '代持股协议',
  ],
  '政务与公共服务': [
    '政府采购合同', 'PPP项目合同', '特许经营权协议', '国有土地使用权出让合同',
  ],
  '跨境与国际合同': [
    '国际货物买卖合同', '国际独家代理协议', '国际分销协议',
  ],
  '通用框架与兜底协议': [
    '合作备忘录(MOU)', '合作意向书(LOI)', '战略合作框架协议', '保密协议(通用NDA)',
    '通用服务协议(标准版)', '通用采购协议', '简单欠条', '收据',
    '承诺书', '免责声明', '授权委托书(通用)', '催告函',
  ],
};

// 自定义值输入组件
interface CustomInputFieldProps {
  value?: string;
  onChange?: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder: string;
  label: string;
}

const CustomInputField: React.FC<CustomInputFieldProps> = ({
  value,
  onChange,
  options,
  placeholder,
  label
}) => {
  const [isCustom, setIsCustom] = useState(false);
  const [customValue, setCustomValue] = useState('');

  React.useEffect(() => {
    const isInOptions = options.some(opt => opt.value === value);
    setIsCustom(!isInOptions && !!value);
    if (!isInOptions && value) {
      setCustomValue(value);
    }
  }, [value, options]);

  const handleSelectChange = (newValue: string) => {
    if (newValue === '__custom__') {
      setIsCustom(true);
      onChange?.('');
    } else {
      setIsCustom(false);
      onChange?.(newValue);
    }
  };

  const handleCustomInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setCustomValue(val);
    onChange?.(val);
  };

  if (isCustom) {
    return (
      <Space.Compact style={{ width: '100%' }}>
        <Input
          placeholder={`输入自定义${label}`}
          value={customValue}
          onChange={handleCustomInputChange}
          allowClear
        />
        <Button
          onClick={() => {
            setIsCustom(false);
            onChange?.(options[0]?.value);
          }}
        >
          使用预设
        </Button>
      </Space.Compact>
    );
  }

  return (
    <Space.Compact style={{ width: '100%' }}>
      <Select
        placeholder={placeholder}
        value={value}
        onChange={handleSelectChange}
        showSearch
        allowClear
        style={{ flex: 1 }}
      >
        {options.map(opt => (
          <Option key={opt.value} value={opt.value}>{opt.label}</Option>
        ))}
        <Option key="__custom__" value="__custom__">
          <Tag color="blue">自定义值</Tag>
        </Option>
      </Select>
    </Space.Compact>
  );
};

const TemplateContractFeaturesEditor: React.FC<TemplateContractFeaturesEditorProps> = ({
  visible,
  template,
  selectedCategoryPath,
  onCancel,
  onSave,
  loading = false,
}) => {
  const [form] = Form.useForm<ContractFeaturesData>();
  const [primaryType, setPrimaryType] = React.useState<string>();
  const [availableContractTypes, setAvailableContractTypes] = React.useState<Array<{
    name: string;
    category: string;
    subcategory?: string;
  }>>([]);
  const [showContractTypeSelector, setShowContractTypeSelector] = React.useState(false);
  const [loadingContractTypes, setLoadingContractTypes] = React.useState(false);

  const getTertiaryTypes = () => {
    if (!primaryType) return [];
    return TERTIARY_CONTRACT_TYPES[primaryType] || [];
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      await onSave(values);
      form.resetFields();
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onCancel();
  };

  // 当分类路径变化时，从知识图谱获取并自动填充7个法律特征
  useEffect(() => {
    const autoFillFromKnowledgeGraph = async () => {
      if (!selectedCategoryPath || selectedCategoryPath.length === 0 || !visible) {
        setShowContractTypeSelector(false);
        return;
      }

      // 获取最具体的分类名称（最后一级）作为知识图谱合同类型名称
      const contractTypeName = selectedCategoryPath[selectedCategoryPath.length - 1];

      try {
        // 先尝试直接获取该合同类型的法律特征
        const features = await contractTemplateApi.getLegalFeatures(contractTypeName);

        // 成功获取，自动填充7个知识图谱法律特征字段
        form.setFieldsValue({
          transaction_nature: features.transaction_nature,
          contract_object: features.contract_object,
          consideration_type: features.consideration_type,
          consideration_detail: features.consideration_detail,
          transaction_characteristics: features.transaction_characteristics,
          usage_scenario: features.usage_scenario,
          legal_basis: features.legal_basis || [],
        });

        setShowContractTypeSelector(false);
        message.success(`已从知识图谱自动填充"${contractTypeName}"的7个法律特征`);
      } catch (e: any) {
        console.error('从知识图谱获取法律特征失败:', e);
        // 如果是大类（如"民法典典型合同"），获取该类别下的所有合同类型
        if (e.response?.status === 404) {
          try {
            setLoadingContractTypes(true);
            // 尝试获取该分类下的合同类型列表
            const result = await contractTemplateApi.getContractTypesByCategory(contractTypeName);
            setAvailableContractTypes(result.contract_types);
            setShowContractTypeSelector(true);
            message.info(`"${contractTypeName}"是合同分类，请选择具体的合同类型以自动填充法律特征`);
          } catch (categoryError) {
            console.error('获取分类下的合同类型失败:', categoryError);
            setShowContractTypeSelector(false);
          } finally {
            setLoadingContractTypes(false);
          }
        } else {
          setShowContractTypeSelector(false);
        }
      }
    };

    autoFillFromKnowledgeGraph();
  }, [selectedCategoryPath, visible, form]);

  // 处理选择具体的合同类型
  const handleContractTypeSelect = async (contractTypeName: string) => {
    try {
      const features = await contractTemplateApi.getLegalFeatures(contractTypeName);

      form.setFieldsValue({
        transaction_nature: features.transaction_nature,
        contract_object: features.contract_object,
        consideration_type: features.consideration_type,
        consideration_detail: features.consideration_detail,
        transaction_characteristics: features.transaction_characteristics,
        usage_scenario: features.usage_scenario,
        legal_basis: features.legal_basis || [],
      });

      setShowContractTypeSelector(false);
      message.success(`已从知识图谱自动填充"${contractTypeName}"的7个法律特征`);
    } catch (e) {
      console.error('获取法律特征失败:', e);
      message.error('获取法律特征失败，请手动填写');
    }
  };

  // 当模板数据变化时，更新表单（包含模板变体字段）
  React.useEffect(() => {
    if (template && visible) {
      const metadataLegalFeatures = template?.metadata_info?.knowledge_graph_match?.legal_features;

      form.setFieldsValue({
        primary_contract_type: selectedCategoryPath?.[0] || template.primary_contract_type,
        secondary_types: selectedCategoryPath && selectedCategoryPath.length > 1
          ? [selectedCategoryPath[selectedCategoryPath.length - 1]]
          : template.secondary_types,
        // 模板变体字段
        version_type: template.version_type || '标准版',
        stance_tendency: template.stance_tendency || '中立',
        detailed_usage_scenario: template.detailed_usage_scenario,
        // 知识图谱7个法律特征
        transaction_nature: template.transaction_nature,
        contract_object: template.contract_object,
        consideration_type: metadataLegalFeatures?.consideration_type,
        consideration_detail: metadataLegalFeatures?.consideration_detail,
        transaction_characteristics: template.transaction_characteristics,
        usage_scenario: template.usage_scenario,
        legal_basis: metadataLegalFeatures?.legal_basis || [],
      });
      setPrimaryType(selectedCategoryPath?.[0] || template.primary_contract_type);
    }
  }, [template, visible, form, selectedCategoryPath]);

  return (
    <Modal
      title="编辑模板合同法律特征"
      open={visible}
      onOk={handleOk}
      onCancel={handleCancel}
      width={900}
      okText="保存"
      cancelText="取消"
      confirmLoading={loading}
    >
      <Form
        form={form}
        layout="vertical"
      >
        {/* 显示当前分类路径 */}
        {selectedCategoryPath && selectedCategoryPath.length > 0 && (
          <>
            <Alert
              message={
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Text strong>模板合同分类：</Text>
                  <Space wrap>
                    {selectedCategoryPath.map((cat, index) => (
                      <React.Fragment key={cat}>
                        {index > 0 && <Text type="secondary"> &gt; </Text>}
                        <Tag color={index === selectedCategoryPath.length - 1 ? 'blue' : 'default'} style={{ fontSize: 14 }}>
                          {cat}
                        </Tag>
                      </React.Fragment>
                    ))}
                  </Space>
                </Space>
              }
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          </>
        )}

        {/* 当选择的是大类时，显示具体合同类型选择器 */}
        {showContractTypeSelector && (
          <Alert
            message={
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Text strong>请选择具体的合同类型：</Text>
                <Select
                  placeholder="选择具体合同类型以自动填充法律特征"
                  loading={loadingContractTypes}
                  onChange={handleContractTypeSelect}
                  style={{ width: '100%' }}
                  showSearch
                  allowClear
                >
                  {availableContractTypes.map(ct => (
                    <Option key={ct.name} value={ct.name}>
                      {ct.name}
                      {ct.subcategory && <Text type="secondary">（{ct.subcategory}）</Text>}
                    </Option>
                  ))}
                </Select>
              </Space>
            }
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Divider />

        <Title level={5}>模板变体设置</Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
          区分同一合同类型的多个模板
        </Text>

        {/* 第一行：版本类型、立场倾向 */}
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="version_type"
              label="版本类型"
              initialValue="标准版"
              tooltip="标准版：最常用的模板；简化版：条款简化；详细版：条款完整"
            >
              <Select placeholder="请选择版本类型">
                {VERSION_TYPE_OPTIONS.map(opt => (
                  <Option key={opt.value} value={opt.value}>{opt.label}</Option>
                ))}
              </Select>
            </Form.Item>
          </Col>

          <Col span={12}>
            <Form.Item
              name="stance_tendency"
              label="立场倾向"
              initialValue="中立"
              tooltip="模板的起草立场：中立（双方平衡）、甲方（偏向甲方）、乙方（偏向乙方）"
            >
              <Select placeholder="请选择立场倾向">
                {STANCE_TENDENCY_OPTIONS.map(opt => (
                  <Option key={opt.value} value={opt.value}>{opt.label}</Option>
                ))}
              </Select>
            </Form.Item>
          </Col>
        </Row>

        {/* 第二行：详细使用场景说明 */}
        <Row gutter={16}>
          <Col span={24}>
            <Form.Item
              name="detailed_usage_scenario"
              label="详细使用场景说明"
              tooltip="请详细描述该模板变体的具体适用场景，帮助AI准确识别"
            >
              <Input.TextArea
                rows={2}
                placeholder="请输入详细使用场景说明，例如：适用于个人二手房买卖，买方为首次购房者，需要办理按揭贷款"
                showCount
                maxLength={200}
              />
            </Form.Item>
          </Col>
        </Row>

        <Divider />

        <Title level={5}>知识图谱法律特征（7个核心字段）</Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
          合同法律特征用于智能匹配模板，请根据知识图谱标准准确填写。
          <Tag color="blue" style={{ marginLeft: 8 }}>支持自定义值</Tag>
        </Text>

        {/* 第一行：交易性质、合同标的 */}
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="transaction_nature"
              label="交易性质"
              rules={[{ required: true, message: '请选择交易性质' }]}
              tooltip="合同的核心法律特征"
            >
              <CustomInputField
                options={TRANSACTION_NATURE_OPTIONS}
                placeholder="请选择交易性质"
                label="交易性质"
              />
            </Form.Item>
          </Col>

          <Col span={12}>
            <Form.Item
              name="contract_object"
              label="合同标的"
              rules={[{ required: true, message: '请选择合同标的' }]}
              tooltip="交易的具体对象"
            >
              <CustomInputField
                options={CONTRACT_OBJECT_OPTIONS}
                placeholder="请选择合同标的"
                label="合同标的"
              />
            </Form.Item>
          </Col>
        </Row>

        {/* 第二行：对价类型、对价详情 */}
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="consideration_type"
              label="对价类型"
              rules={[{ required: true, message: '请选择对价类型' }]}
              tooltip="交易对价形式：有偿/无偿/混合"
            >
              <Select placeholder="请选择对价类型" allowClear>
                {CONSIDERATION_TYPE_OPTIONS.map(opt => (
                  <Option key={opt.value} value={opt.value}>{opt.label}</Option>
                ))}
              </Select>
            </Form.Item>
          </Col>

          <Col span={12}>
            <Form.Item
              name="consideration_detail"
              label="对价详情"
              rules={[{ required: true, message: '请选择或输入对价详情' }]}
              tooltip="对价的具体说明"
            >
              <CustomInputField
                options={CONSIDERATION_DETAIL_OPTIONS}
                placeholder="请选择对价详情"
                label="对价详情"
              />
            </Form.Item>
          </Col>
        </Row>

        {/* 第三行：交易特征、适用场景 */}
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="transaction_characteristics"
              label="交易特征"
              rules={[{ required: true, message: '请输入交易特征' }]}
              tooltip="描述该合同类型的核心法律特征"
            >
              <Input.TextArea
                rows={2}
                placeholder="请输入交易特征描述"
                showCount
                maxLength={100}
              />
            </Form.Item>
          </Col>

          <Col span={12}>
            <Form.Item
              name="usage_scenario"
              label="适用场景"
              rules={[{ required: true, message: '请输入适用场景' }]}
              tooltip="描述该合同类型的主要应用场景"
            >
              <Input.TextArea
                rows={2}
                placeholder="请输入适用场景描述"
                showCount
                maxLength={100}
              />
            </Form.Item>
          </Col>
        </Row>

        {/* 第四行：法律依据 */}
        <Row gutter={16}>
          <Col span={24}>
            <Form.Item
              name="legal_basis"
              label="法律依据"
              tooltip="相关法律法规条文"
            >
              <SelectWithTags placeholder="请输入法律依据（如：民法典第595条），输入后按回车添加" />
            </Form.Item>
          </Col>
        </Row>

        <Divider />

        <Space direction="vertical" size="small">
          <Text strong>知识图谱法律特征说明：</Text>
          <Text type="secondary">
            • 交易性质：定义合同的核心法律特征（如转移所有权、提供服务、许可使用等）<br/>
            • 合同标的：定义交易的具体对象（如不动产、动产、智力成果、服务等）<br/>
            • 对价类型：定义交易对价形式（有偿/无偿/混合）<br/>
            • 对价详情：定义对价的具体说明（如双方协商、固定价格、利息形式等）<br/>
            • 交易特征：描述该合同类型的核心法律特征<br/>
            • 适用场景：描述该合同类型的主要应用场景<br/>
            • 法律依据：相关法律法规条文<br/>
            • 自定义值：如果预设选项不符合需求，可选择"自定义值"手动输入
          </Text>
        </Space>
      </Form>
    </Modal>
  );
};

export default TemplateContractFeaturesEditor;
