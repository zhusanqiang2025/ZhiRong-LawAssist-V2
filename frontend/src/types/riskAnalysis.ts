// frontend/src/types/riskAnalysis.ts
/**
 * 风险分析模块类型定义
 */

// 风险等级
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

// 分析状态
export type AnalysisStatus = 'pending' | 'parsing' | 'analyzing' | 'completed' | 'failed';

// 分析场景类型
export type SceneType = 'equity_penetration' | 'contract_risk' | 'compliance_review' | 'tax_risk';

// 文档片段引用
export interface RiskSectionRef {
  doc_id: string;
  page?: number;
  text: string;
  highlight: boolean;
}

// 风险项
export interface RiskItem {
  id: number;
  session_id: number;
  title: string;
  description: string;
  risk_level: RiskLevel;
  confidence: number;
  reasons: string[];
  suggestions: string[];
  source_type: string;
  source_rules?: number[];
  related_sections?: RiskSectionRef[];
  graph_data?: any;
  created_at: string;
}

// 风险分析会话
export interface RiskAnalysisSession {
  id: number;
  session_id: string;
  status: AnalysisStatus;
  scene_type: SceneType;
  user_description?: string;
  summary?: string;
  risk_distribution?: {
    high: number;
    medium: number;
    low: number;
  };
  total_confidence?: number;
  report_md?: string;
  created_at: string;
  completed_at?: string;
  risk_items?: RiskItem[];
}

// 提交分析请求
export interface RiskAnalysisSubmitRequest {
  scene_type: SceneType;
  user_description?: string;
  document_ids?: string[];
  enable_custom_rules?: boolean;
}

// WebSocket 进度消息
export interface WebSocketProgressMessage {
  session_id: string;
  status: AnalysisStatus;
  progress: number; // 0-1
  message: string;
}

// 节点进度消息
export interface NodeProgressMessage {
  type: 'node_progress';
  node: 'documentPreorganization' | 'multiModelAnalysis' | 'reportGeneration';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  progress: number; // 0-1
}

// 扩展 WebSocket 消息类型
export type WebSocketMessage = WebSocketProgressMessage | NodeProgressMessage;

// 场景配置
export interface SceneConfig {
  id: SceneType;
  name: string;
  description: string;
  icon: string;
  color: string;
  placeholder: string;
}

// 场景配置预设
export const SCENE_CONFIGS: Record<SceneType, SceneConfig> = {
  equity_penetration: {
    id: 'equity_penetration',
    name: '股权穿透风险分析',
    description: '分析公司股权结构，识别潜在的控制权和关联交易风险',
    icon: 'apartment',
    color: '#722ed1',
    placeholder: '请描述需要分析的股权结构，例如：分析A公司的实际控制人和关联交易风险...'
  },
  contract_risk: {
    id: 'contract_risk',
    name: '合同条款风险分析',
    description: '识别合同条款中的法律风险点',
    icon: 'file-search',
    color: '#fa8c16',
    placeholder: '请描述合同背景和需要关注的重点...'
  },
  compliance_review: {
    id: 'compliance_review',
    name: '合规审查',
    description: '审查文档是否符合相关法律法规要求',
    icon: 'shield-check',
    color: '#52c41a',
    placeholder: '请说明合规审查的具体要求...'
  },
  tax_risk: {
    id: 'tax_risk',
    name: '税务风险分析',
    description: '识别税务相关的潜在风险',
    icon: 'calculator',
    color: '#13c2c2',
    placeholder: '请描述税务背景和关注点...'
  }
};

// API 响应类型
export interface RiskAnalysisSubmitResponse {
  session_id: string;
  status: string;
  message: string;
}

export interface RiskAnalysisUploadResponse {
  file_id: string;
  file_path: string;
  message: string;
}

export interface RiskAnalysisStartResponse {
  message: string;
  session_id: string;
}

export interface RiskAnalysisStatusResponse {
  session_id: string;
  status: string;
  summary?: string;
  risk_distribution?: {
    high: number;
    medium: number;
    low: number;
  };
}

// ==================== 风险规则包类型 ====================

// 规则项类型
export interface RiskRule {
  rule_id: string;
  rule_name: string;
  rule_prompt: string;
  priority: number;
  risk_type?: string;
  default_risk_level?: 'low' | 'medium' | 'high' | 'critical';
}

// 规则包类型
export interface RiskRulePackage {
  id: number;
  package_id: string;
  package_name: string;
  package_category: string;
  description?: string;
  applicable_scenarios?: string[];
  target_entities?: string[];
  rules: RiskRule[];
  is_active: boolean;
  is_system: boolean;
  version?: string;
  creator_id?: number;
  created_at: string;
  updated_at: string;
}

// API 响应类型 - 规则包列表
export interface RiskRulePackagesResponse {
  packages: RiskRulePackage[];
}

// 创建/更新请求类型
export interface RiskRulePackageRequest {
  package_id?: string;  // 更新时需要
  package_name: string;
  package_category: string;
  description?: string;
  applicable_scenarios?: string[];
  target_entities?: string[];
  rules: RiskRule[];
  is_active?: boolean;
}

// 规则包分类选项
export const RULE_PACKAGE_CATEGORIES = [
  { value: 'equity_risk', label: '股权风险' },
  { value: 'investment_risk', label: '投资风险' },
  { value: 'governance_risk', label: '治理风险' },
  { value: 'contract_risk', label: '合同风险' },
  { value: 'tax_risk', label: '税务风险' }
] as const;

export type RulePackageCategory = typeof RULE_PACKAGE_CATEGORIES[number]['value'];

// ==================== 评估视角类型 ====================

// 评估视角定义
export interface EvaluationPerspective {
  id: string;  // 对应规则包的 package_id
  name: string;
  category: RulePackageCategory;
  description?: string;
  priority: number;  // 1-10，数字越小优先级越高
  rule_count?: number;
  is_active?: boolean;
}

// 评估视角预设配置
export const EVALUATION_PERSPECTIVES: Omit<EvaluationPerspective, 'priority'>[] = [
  {
    id: 'company_mingling_risk',
    name: '公司混同风险',
    category: 'governance_risk',
    description: '识别人格混同、资金混同、业务混同等公司治理风险',
  },
  {
    id: 'contract_clause_risk',
    name: '合同条款风险',
    category: 'contract_risk',
    description: '分析合同条款的完整性、合法性和潜在风险',
  },
  {
    id: 'investment_project_risk',
    name: '投资项目风险',
    category: 'investment_risk',
    description: '评估投资项目的市场、财务、法律等综合风险',
  },
  {
    id: 'tax_compliance_risk',
    name: '税务风险',
    category: 'tax_risk',
    description: '识别税务合规、税收筹划、发票管理等税务风险',
  },
  {
    id: 'equity_penetration_risk',
    name: '股权穿透风险',
    category: 'equity_risk',
    description: '穿透股权结构，识别实际控制人和关联交易风险',
  },
];

// 评估视角选择器状态
export interface PerspectiveSelectorState {
  selected: EvaluationPerspective[];  // 已选择的视角（带优先级）
  available: EvaluationPerspective[];  // 可用的视角
}
