// frontend/src/types/litigationAnalysis.ts
/**
 * 案件分析模块类型定义
 */

// ==================== 枚举类型 ====================

export enum CaseType {
  CONTRACT_PERFORMANCE = 'contract_performance',
  COMPLAINT_DEFENSE = 'complaint_defense',
  JUDGMENT_APPEAL = 'judgment_appeal',
  EVIDENCE_PRESERVATION = 'evidence_preservation',
  ENFORCEMENT = 'enforcement',
  ARBITRATION = 'arbitration',
  DEBT_COLLECTION = 'debt_collection',
  LABOR_DISPUTE = 'labor_dispute',
  IP_INFRINGEMENT = 'ip_infringement',
  MARINE_ACCIDENT = 'marine_accident'
}

export enum CasePosition {
  PLAINTIFF = 'plaintiff',
  DEFENDANT = 'defendant',
  APPELLANT = 'appellant',
  APPELLEE = 'appellee',
  APPLICANT = 'applicant',
  RESPONDENT = 'respondent',
  THIRD_PARTY = 'third_party'
}

export enum AnalysisStatus {
  PENDING = 'pending',
  PARSING = 'parsing',
  ANALYZING = 'analyzing',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

export enum StrengthLevel {
  STRONG = 'strong',
  MEDIUM = 'medium',
  WEAK = 'weak'
}

// ==================== 案件类型包 ====================

export interface LitigationCaseRule {
  rule_id: string;
  rule_name: string;
  rule_prompt: string;
  priority: number;
}

export interface LitigationCasePackage {
  id: number;
  package_id: string;
  package_name: string;
  package_category: string;
  case_type: string;
  description?: string;
  applicable_positions?: string[];
  target_documents?: string[];
  rules: LitigationCaseRule[];
  is_active: boolean;
  is_system: boolean;
  version?: string;
  creator_id?: number;
  created_at: string;
  updated_at: string;
}

// ==================== 证据分析 ====================

export interface EvidenceItem {
  evidence_id: string;
  evidence_type: string;
  evidence_name: string;
  description: string;
  admissibility: boolean;
  weight: number;
  relevance: number;
  facts_to_prove: string[];
  status: string;
}

export interface EvidenceAnalysisResult {
  evidence_items: EvidenceItem[];
  admissible_count: number;
  average_weight: number;
  evidence_gaps: string[];
}

// ==================== 案件强弱分析 ====================

export interface CaseStrengthResult {
  overall_strength: number;
  strength_level: StrengthLevel;
  key_facts: string[];
  legal_basis: string[];
  strengths: string[];
  weaknesses: string[];
  risks: string[];
}

// ==================== 时间线 ====================

export interface TimelineEventData {
  event_date: string;
  event_type: string;
  description: string;
  importance: string;
  legal_significance?: string;
  related_documents?: string[];
  related_evidence?: string[];
}

export interface TimelineResult {
  events: TimelineEventData[];
  critical_events: TimelineEventData[];
  statute_implications: Record<string, any>;
  visualization_data: Record<string, any>;
}

// ==================== 证据链 ====================

export interface EvidenceChainData {
  fact: string;
  evidence: EvidenceItem[];
  completeness: number;
  weak_points: string[];
}

export interface EvidenceChainResult {
  chains: EvidenceChainData[];
  completeness: number;
  weak_points: string[];
  visualization_data: Record<string, any>;
}

// ==================== 策略 ====================

export interface Strategy {
  strategy_id: string;
  title: string;
  description: string;
  priority: string;
  type: string;
  actions: string[];
  expected_outcome?: string;
  risks?: string[];
}

// ==================== 争议焦点 ====================

export interface LegalIssue {
  title: string;
  description: string;
  importance: string;
}

// ==================== 分析结果 ====================

export interface LitigationAnalysisResult {
  case_summary: string;
  case_strength: CaseStrengthResult;
  evidence_assessment: EvidenceAnalysisResult;
  legal_issues: LegalIssue[];
  timeline: TimelineResult;
  evidence_chain: EvidenceChainResult;
  strategies: Strategy[];
  risk_warnings: string[];
  recommendations: Array<{ title: string; description: string }>;
}

// ==================== 会话 ====================

export interface LitigationAnalysisSession {
  id: number;
  session_id: string;
  user_id: number;
  status: string;
  case_type: string;
  case_position: string;
  user_input?: string;
  package_id: string;
  document_ids?: string[];
  case_summary?: string;
  win_probability?: number;
  model_results?: Record<string, any>;
  selected_model?: string;
  created_at: string;
  completed_at?: string;
}

// ==================== 请求类型 ====================

export interface LitigationAnalysisRequest {
  package_id: string;
  case_type: CaseType;
  case_position: CasePosition;
  user_input?: string;
  document_ids?: string[];
}

// ==================== WebSocket 消息 ====================

export interface WebSocketProgressMessage {
  session_id: string;
  type: 'progress' | 'complete' | 'error' | 'evidence_analysis' | 'strategies_generated';
  status?: string;
  progress?: number;
  message?: string;
  stage?: string;
  data?: any;
}

// ==================== 预整理模块类型 ====================

/**
 * 文档类型（诉讼专用）
 */
export type LitigationDocumentType =
  | 'lawyer_letter'        // 律师函
  | 'demand_letter'        // 催款通知/催告函
  | 'meeting_minutes'      // 会议纪要
  | 'agreement'            // 协议/合同
  | 'correspondence'       // 往来函件
  | 'complaint'            // 起诉状
  | 'defense'              // 答辩状
  | 'evidence_list'        // 证据清单
  | 'evidence_material'    // 证据材料
  | 'court_statement'      // 庭审陈述
  | 'judgment'             // 判决书
  | 'ruling'               // 裁定书
  | 'mediation_statement'  // 调解书
  | 'court_order'          // 法院通知书
  | 'other_litigation_doc';// 其他诉讼文档

/**
 * 主体角色（诉讼专用）
 */
export type PartyRoleType =
  | 'plaintiff'     // 原告
  | 'applicant'     // 申请人
  | 'defendant'     // 被告
  | 'respondent'    // 被申请人
  | 'third_party'   // 第三人
  | 'appellant'     // 上诉人
  | 'appellee'      // 被上诉人
  | 'court'         // 法院
  | 'arbitrator'    // 仲裁员
  | 'other_party';  // 其他主体

/**
 * 诉讼主体信息（预整理）
 */
export interface PartyInfo {
  name: string;
  role: PartyRoleType;
  identification?: string;
  description?: string;
  confidence: number;
}

/**
 * 单个文档的诉讼分析结果（预整理）- 优化版（参考风险评估模块）
 */
export interface LitigationDocumentAnalysis {
  file_id: string;
  file_name: string;
  file_type: LitigationDocumentType;

  // ============= 新增：优化字段（参考风险评估模块）============
  document_title?: string;        // 文档标题（如"股权转让协议"、"民事起诉状"等）
  document_subtype?: string;       // 文档子类型（如"合同纠纷起诉状"、"股权转让协议"等）
  document_purpose?: string;       // 文档目的（1-2句话说明用途）
  party_positions?: string;        // 各方立场或诉求描述
  risk_signals?: string[];         // 风险信号列表

  // 文档核心内容（根据文档类型有不同结构）
  content_summary: string;

  // 起诉状特有字段
  plaintiffs?: string[];           // 原告列表
  defendants?: string[];          // 被告列表
  litigation_claims?: string[];   // 诉讼请求
  case_facts_summary?: string;    // 案件事实和理由概要（500字内）

  // 判决书特有字段
  case_name?: string;             // 案件名称
  case_number?: string;           // 案号
  judgment_result?: string;       // 判决结果
  judgment_reasons?: string[];    // 判决理由总结（每条不超过300字）

  // 其他文档通用字段
  key_facts: string[];
  key_dates: string[];
  key_amounts: string[];
  parties: PartyInfo[];
  metadata?: Record<string, any>;
  analysis_time?: string;
}

/**
 * 文档关联关系类型
 */
export type RelationshipType =
  | 'references'        // 引用
  | 'relates_to'        // 相关
  | 'contradicts'       // 矛盾
  | 'supports'          // 支持
  | 'is_evidence_for'   // 是...的证据
  | 'is_response_to';   // 是...的回复

/**
 * 文档之间的关联关系（预整理）
 */
export interface DocumentRelationship {
  source_file_id: string;
  target_file_id: string;
  relationship_type: RelationshipType;
  description: string;
  confidence: number;
}

/**
 * 文档质量评估（预整理）
 */
export interface QualityAssessment {
  clarity_score: number;
  completeness_score: number;
  evidence_chain_score: number;
}

/**
 * 时间线事件（预整理）
 */
export interface TimelineEvent {
  date: string;
  source_file: string;
  description: string;
}

/**
 * 争议焦点（预整理）
 */
export interface DisputePoint {
  point: string;
  source_file: string;
}

/**
 * 跨文档综合信息
 */
export interface CrossDocumentInfo {
  all_parties: PartyInfo[];
  timeline: TimelineEvent[];
  dispute_points: DisputePoint[];
  disputed_amount?: string;
  case_overview?: string;  // 新增：案件全景综述
}

/**
 * 案件预整理结果
 */
export interface LitigationPreorganizationResult {
  session_id: string;
  document_analyses?: LitigationDocumentAnalysis[];  // 可选：文档分析列表（旧结构）
  document_summaries?: Record<string, any>;          // 可选：文档摘要字典（新结构）
  cross_document_info: CrossDocumentInfo;
  document_relationships: DocumentRelationship[];
  quality_assessment: QualityAssessment;
  processed_at: string;
  enhanced_analysis_compatible?: any;                // 可选：增强分析数据（兼容性字段）
}

/**
 * 诉讼地位（用户选择）
 */
export type LitigationPosition =
  | 'plaintiff'   // 原告或申请人
  | 'defendant'   // 被告或被申请人
  | 'third_party' // 第三人
  | 'appellant'   // 上诉人
  | 'custom';     // 其他（手动输入）

/**
 * 分析目标（用户选择）- 优化版
 */
export type AnalysisGoal =
  | 'prosecution' // 起诉方案
  | 'defense'     // 应诉方案
  | 'custom';     // 其他（请手动输入）

/**
 * 分析立场选项（用于前端下拉菜单）
 */
export const ANALYSIS_GOAL_OPTIONS = [
  { value: 'prosecution', label: '起诉方案', description: '准备发起诉讼，需要评估可行性和证据' },
  { value: 'defense', label: '应诉方案', description: '已被起诉，需要准备答辩和抗辩' },
  { value: 'custom', label: '其他（请手动输入）', description: '请具体描述您的分析场景和需求' }
];

/**
 * 预整理后的分析请求
 */
export interface LitigationAnalysisWithPreorganizationRequest {
  session_id: string;
  case_type: string;
  litigation_position: LitigationPosition;
  analysis_goal: string;
  background_info?: string;
  focus_points?: string;
  document_analyses: LitigationDocumentAnalysis[];
  cross_document_info: CrossDocumentInfo;
}

// ==================== 辅助映射 ====================

/**
 * 文档类型中文标签映射
 * 注意：需要与后端 enhanced_case_preorganization.py 中的 doc_type 保持一致
 */
export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  // 仲裁类
  'arbitration_application': '仲裁申请书',
  'arbitration_award': '仲裁裁决书',
  'arbitration_notice': '仲裁通知书',
  'arbitration_doc': '其他仲裁文书',

  // 执行类
  'execution_application': '执行申请书',
  'execution_order': '执行裁定书',
  'execution_notice': '执行通知书',
  'execution_doc': '其他执行文书',
  'preservation_application': '保全申请书',

  // 诉讼类
  'complaint': '起诉状',
  'defense': '答辩状',
  'appeal': '上诉状',

  // 法院裁判
  'judgment': '判决书',
  'ruling': '裁定书',
  'mediation': '调解书',

  // 证据材料
  'evidence': '证据材料',

  // 基础合同/函件
  'contract': '合同/协议',
  'lawyer_letter': '律师函',
  'correspondence': '往来函件',

  // 兼容旧类型（用于风险分析模块等其他场景）
  'demand_letter': '催款通知',
  'meeting_minutes': '会议纪要',
  'agreement': '协议/合同',
  'evidence_list': '证据清单',
  'evidence_material': '证据材料',
  'court_statement': '庭审陈述',
  'mediation_statement': '调解书',
  'court_order': '法院通知书',
  'other_litigation_doc': '其他诉讼文档',

  // 默认兜底
  'default': '其他文书'
};

/**
 * 主体角色中文标签映射
 */
export const PARTY_ROLE_LABELS: Record<PartyRoleType, string> = {
  'plaintiff': '原告',
  'applicant': '申请人',
  'defendant': '被告',
  'respondent': '被申请人',
  'third_party': '第三人',
  'appellant': '上诉人',
  'appellee': '被上诉人',
  'court': '法院',
  'arbitrator': '仲裁员',
  'other_party': '其他主体'
};

/**
 * 文档类型颜色映射（用于UI展示）
 */
export const DOCUMENT_TYPE_COLORS: Partial<Record<LitigationDocumentType, string>> = {
  'lawyer_letter': 'orange',
  'demand_letter': 'red',
  'meeting_minutes': 'cyan',
  'agreement': 'blue',
  'correspondence': 'geekblue',
  'complaint': 'purple',
  'defense': 'magenta',
  'evidence_list': 'green',
  'evidence_material': 'lime',
  'court_statement': 'gold',
  'judgment': 'blue',
  'ruling': 'volcano',
  'mediation_statement': 'green',
  'court_order': 'default'
};

// ==================== 3阶段架构：新增类型 ====================

/**
 * 分析场景枚举
 */
export enum AnalysisScenario {
  PRE_LITIGATION = 'pre_litigation',     // 准备起诉
  DEFENSE = 'defense',                   // 应诉准备
  APPEAL = 'appeal',                     // 上诉
  EXECUTION = 'execution',               // 执行阶段
  PRESERVATION = 'preservation',         // 财产保全
  EVIDENCE_COLLECTION = 'evidence_collection',  // 证据收集
  MEDIATION = 'mediation'                // 调解准备
}

/**
 * 文书草稿类型
 */
export interface DraftDocument {
  document_type: string;
  document_name: string;
  content: string;
  template_info: {
    template_file: string;
    template_version: string;
  };
  placeholders: string[];
  generated_at: string;
}

/**
 * 文书生成结果
 */
export interface GenerateDraftsResult {
  session_id: string;
  draft_documents: DraftDocument[];
  total_count: number;
  completed_at: string;
  message?: string;
}

/**
 * 证据分析点（阶段2）
 */
export interface EvidenceAnalysisPoint {
  issue: string;
  evidence_ref?: string;
}

/**
 * 证据分析结果（阶段2）
 */
export interface EvidenceAnalysisResultStage2 {
  admissibility_assessment: string;
  analysis_points: EvidenceAnalysisPoint[];
  missing_evidence?: string[];
  impeachment_strategy?: string[];
}

/**
 * 模型推演结果（阶段2）
 */
export interface ModelResultsStage2 {
  final_strength: number;
  confidence: number;
  final_summary: string;
  final_facts: string[];
  final_legal_arguments: string[];
  rule_application: string[];
  final_strengths: string[];
  final_weaknesses: string[];
  conclusion: string;
}

/**
 * 策略步骤（阶段2）
 */
export interface StrategyStep {
  step_name: string;
  description: string;
}

/**
 * 诉讼策略（阶段2）
 */
export interface LitigationStrategyStage2 {
  title: string;
  type: string;
  description: string;
  steps: StrategyStep[];
  recommendation_score: number;
  risk_mitigation?: string;
}

/**
 * 时间线事件（阶段2）
 */
export interface TimelineEventStage2 {
  date: string;
  description: string;
  source: string;
}

/**
 * 时间线结果（阶段2）
 */
export interface TimelineResultStage2 {
  events: TimelineEventStage2[];
}

/**
 * 报告元数据（阶段2）
 */
export interface ReportMetadata {
  generated_at: string;
  case_type: string;
  scenario: string;
  draft_documents_available: boolean;
}

/**
 * 报告仪表盘数据（阶段2）
 */
export interface ReportDashboard {
  win_rate: number;
  confidence: number;
  key_facts_count: number;
  risk_count: number;
  strategies_count: number;
}

/**
 * 报告内容（阶段2）
 */
export interface ReportContent {
  summary: string;
  facts: string[];
  timeline: any;
  strategies: any[];
}

/**
 * 结构化报告 JSON（阶段2）
 */
export interface ReportJson {
  meta: ReportMetadata;
  dashboard: ReportDashboard;
  content: ReportContent;
}

/**
 * 阶段2分析结果（全案分析）
 */
export interface Stage2AnalysisResult {
  session_id: string;
  status: string;
  case_type: string;
  case_position: string;
  analysis_scenario: string;
  assembled_rules: string[];
  timeline: TimelineResultStage2;
  evidence_analysis: EvidenceAnalysisResultStage2;
  model_results: ModelResultsStage2;
  strategies: LitigationStrategyStage2[];
  final_report: string;
  report_json: ReportJson;
  completed_at: string;
}
