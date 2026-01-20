// frontend/src/components/TemplateV2Editor.tsx
import React, { useState } from 'react';
import {
  Modal, Form, Select, Input, Switch, Space, Typography, Divider, Row, Col, Tag, Button, Alert
} from 'antd';
import {
  TransactionNature,
  ContractObject,
  Complexity,
  Stance,
  PrimaryContractType
} from '../api/contractTemplates';
import type { ContractTemplate } from '../types/contract';

const { Title, Text } = Typography;
const { Option } = Select;
const { TextArea } = Input;

interface TemplateV2EditorProps {
  visible: boolean;
  template: ContractTemplate | null;
  selectedCategoryPath?: string[]; // 新增：选中的分类路径
  onCancel: () => void;
  onSave: (v2Features: V2FeaturesData) => Promise<void>;
  loading?: boolean;
}

export interface V2FeaturesData {
  primary_contract_type?: PrimaryContractType;
  secondary_types?: string[];
  transaction_nature?: TransactionNature;
  contract_object?: ContractObject;
  complexity?: Complexity;
  stance?: Stance;
  risk_level?: 'low' | 'mid' | 'high';
  is_recommended?: boolean;
  metadata_info?: Record<string, any>;
}

// 增强的选项定义（增加了更多预设值）
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
  { value: '其他', label: '其他' },
];

const CONTRACT_OBJECT_OPTIONS = [
  { value: '货物', label: '货物（商品、设备）' },
  { value: '工程', label: '工程（建设工程）' },
  { value: 'ip', label: '智力成果（软件、专利、著作权）' },
  { value: '服务', label: '服务（人力服务）' },
  { value: '股权', label: '股权（股权转让）' },
  { value: '资金', label: '资金（借款、投资）' },
  { value: 'human_labor', label: '劳动力' },
  { value: 'real_estate', label: '房地产' },
  { value: '无形资产', label: '无形资产（品牌、商誉）' },
  { value: '其他', label: '其他' },
];

const COMPLEXITY_OPTIONS = [
  { value: 'simple', label: '简单（标准化合同）' },
  { value: 'standard_commercial', label: '中等（常规商业合同）' },
  { value: 'complex', label: '复杂（复杂交易结构）' },
  { value: 'very_complex', label: '非常复杂（多方交易/跨境）' },
];

const STANCE_OPTIONS = [
  { value: 'neutral', label: '中立（双方平衡）' },
  { value: 'party_a', label: '甲方（偏向甲方）' },
  { value: 'party_b', label: '乙方（偏向乙方）' },
  { value: 'balanced', label: '平衡（完全对等）' },
  { value: 'multi_party', label: '多方（涉及多方利益）' },
];

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

const RISK_LEVEL_OPTIONS = [
  { value: 'low', label: '低风险（标准化、高频使用）' },
  { value: 'mid', label: '中风险（常规商业条款）' },
  { value: 'high', label: '高风险（复杂条款、需谨慎）' },
];

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

  // 检查当前值是否在预设选项中
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

const TemplateV2Editor: React.FC<TemplateV2EditorProps> = ({
  visible,
  template,
  selectedCategoryPath,
  onCancel,
  onSave,
  loading = false,
}) => {
  const [form] = Form.useForm<V2FeaturesData>();
  const [primaryType, setPrimaryType] = React.useState<string>();

  // 获取当前选中主类型对应的三级分类
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

  // 当模板数据变化或分类路径变化时，更新表单
  React.useEffect(() => {
    if (template && visible) {
      form.setFieldsValue({
        primary_contract_type: selectedCategoryPath?.[0] || template.primary_contract_type,
        secondary_types: selectedCategoryPath && selectedCategoryPath.length > 1
          ? [selectedCategoryPath[selectedCategoryPath.length - 1]]
          : template.secondary_types,
        transaction_nature: template.transaction_nature,
        contract_object: template.contract_object,
        // complexity: template.complexity,  // ContractTemplate 类型中不存在此属性
        // stance: template.stance,          // ContractTemplate 类型中不存在此属性
        risk_level: template.risk_level as 'low' | 'mid' | 'high' | undefined,
        is_recommended: template.is_recommended,
        metadata_info: template.metadata_info,
      });
      setPrimaryType(selectedCategoryPath?.[0] || template.primary_contract_type);
    }
  }, [template, visible, form, selectedCategoryPath]);

  // 将 metadata_info 对象转为 JSON 字符串显示
  const metadataJsonString = React.useMemo(() => {
    if (!template?.metadata_info) return '';
    try {
      return JSON.stringify(template.metadata_info, null, 2);
    } catch {
      return '';
    }
  }, [template?.metadata_info]);

  return (
    <Modal
      title="编辑模板 V2 法律特征"
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
        initialValues={{
          complexity: 'standard_commercial',
          stance: 'neutral',
          risk_level: 'mid',
          is_recommended: false,
        }}
      >
        {/* 新增：显示当前分类路径 */}
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

        <Divider />

        <Title level={5}>V2 四维法律特征</Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
          四维法律特征用于智能匹配模板，请根据合同的实际法律特征准确填写。
          <Tag color="blue" style={{ marginLeft: 8 }}>支持自定义值</Tag>
        </Text>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="transaction_nature"
              label="交易性质"
              rules={[{ required: true, message: '请选择交易性质' }]}
              tooltip="交易的核心法律特征"
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

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="complexity"
              label="复杂程度"
              rules={[{ required: true, message: '请选择复杂程度' }]}
              tooltip="合同的法律和交易复杂度"
            >
              <CustomInputField
                options={COMPLEXITY_OPTIONS}
                placeholder="请选择复杂程度"
                label="复杂程度"
              />
            </Form.Item>
          </Col>

          <Col span={12}>
            <Form.Item
              name="stance"
              label="立场"
              rules={[{ required: true, message: '请选择立场' }]}
              tooltip="合同的起草立场"
            >
              <CustomInputField
                options={STANCE_OPTIONS}
                placeholder="请选择立场"
                label="立场"
              />
            </Form.Item>
          </Col>
        </Row>

        <Divider />

        <Title level={5}>风险与推荐</Title>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="risk_level"
              label="风险等级"
              tooltip="合同条款的复杂性和风险程度"
            >
              <Select placeholder="请选择风险等级">
                {RISK_LEVEL_OPTIONS.map(opt => (
                  <Option key={opt.value} value={opt.value}>{opt.label}</Option>
                ))}
              </Select>
            </Form.Item>
          </Col>

          <Col span={12}>
            <Form.Item
              name="is_recommended"
              label="推荐模板"
              tooltip="是否为高频使用的标准模板"
              valuePropName="checked"
            >
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item
          name="metadata_info"
          label="扩展元数据 (JSON)"
          tooltip="存储其他法律特征和标签，JSON格式"
          initialValue={metadataJsonString}
        >
          <TextArea
            rows={4}
            placeholder={`{"key": "value"}`}
          />
        </Form.Item>

        <Divider />

        <Space direction="vertical" size="small">
          <Text strong>V2 特征说明：</Text>
          <Text type="secondary">
            • 交易性质：定义合同的核心法律特征（如买卖、服务、许可等）<br/>
            • 合同标的：定义交易的具体对象（如货物、IP、服务等）<br/>
            • 复杂程度：评估合同的法律复杂度和交易结构复杂度<br/>
            • 立场：定义合同的起草偏向（甲方、乙方、中立或平衡）<br/>
            • 自定义值：如果预设选项不符合需求，可选择"自定义值"手动输入
          </Text>
        </Space>
      </Form>
    </Modal>
  );
};

export default TemplateV2Editor;
