// API request/response types
import { User } from './auth';  // 仅从 auth 导入 User，避免循环依赖
import { ApiResponse } from './api';

// Authentication types
export interface RegisterRequest {
  email: string;
  phone?: string;
  password: string;
  full_name?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

// Task types
export interface TaskCreateRequest {
  type: string;
  input_data: Record<string, any>;
}

export interface TaskModificationRequest {
  task_id?: string;
  modification_type?: string;
  modification_data?: Record<string, any>;
  original_content?: string; // Add missing property
  modification_suggestion?: string; // Add missing property
  type?: string; // Add missing property
}

export interface FileGenerateRequest {
  task_id?: string;
  file_type?: string;
  template_id?: string;
  content?: string; // Add missing property
  format?: 'word' | 'pdf'; // Add missing property
  doc_type?: string; // Add missing property
}

// Chat types
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface ChatRequest {
  message: string;
  conversation_history?: ChatMessage[];
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  suggestions?: string[];
  action_buttons?: Array<{ text: string; action: string }>; // Action buttons
  confidence?: number; // Confidence score
}

// Template types
export interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  file_url: string;
  download_count: number;
  rating: number;
  created_at: string;
  updated_at: string;
}

export interface TemplateSearchRequest {
  query?: string;
  category?: string;
  page?: number;
  size?: number;
}

export interface TemplateUploadRequest {
  name: string;
  description: string;
  category: string;
  file: File;
}

export interface TemplateRatingRequest {
  rating: number;
}

// Category types
export interface Category {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface CategoryCreateRequest {
  name: string;
  description?: string;
}

// Guidance and Consultation types
export interface GuidanceRequest {
  user_input?: string; // Make optional
  message?: string; // Alias for user_input
  context?: Record<string, any>;
  conversation_history?: ChatMessage[]; // Add conversation history
}

export interface GuidanceResponse {
  recommended_workflow: string;
  explanation: string;
  next_steps: string[];
  response?: string; // Direct response field
  suggestions?: string[]; // Action suggestions
  action_buttons?: Array<{ text: string; action: string }>; // Action buttons
}

export interface ConsultationRequest {
  consultation_type?: string;
  question?: string;
  message?: string;
  context?: Record<string, any>;
  conversation_history?: ChatMessage[];
  uploaded_files?: string[];
  user_confirmed?: boolean;
  selected_suggested_questions?: string[];
  is_follow_up?: boolean; // 新增：多轮对话标志
  session_id?: string; // 新增：会话ID
  previous_specialist_output?: any; // 新增：上一轮专业律师输出
}

// 文档分析类型（用于智能咨询模块）
export interface DocumentAnalysis {
  document_classification?: Record<string, string[]>;
  document_summaries?: Record<string, {
    file_path?: string;
    summary?: string;
    key_parties?: string[];
    key_dates?: string[];
    key_amounts?: string[];
    risk_signals?: string[];
    document_title?: string;     // 文档标题
    document_subtype?: string;   // 文档子类型
  }>;
  timeline?: Array<{ date: string; event: string; document: string }>;
  document_relationships?: Array<{
    source_doc: string;
    target_doc: string;
    relationship_type: string;
    confidence: number;
    reason: string;
  }>;
  all_parties?: Array<{ name: string; role: string; confidence: number }>;
  cross_doc_info?: Record<string, any>;
  legal_issues?: string[];
  dispute_points?: string[];
  evidence_chain?: {
    key_facts: string[];
    evidence_links: Array<{
      from: string;
      to: string;
      type: string;
      description: string;
    }>;
    contradictions: string[];
    gaps: string[];
  };
}

export interface ConsultationResponse {
  response?: string;
  answer?: string;
  suggestions?: string[];
  action_buttons?: Array<{ key: string; label: string }>;
  need_confirmation?: boolean;
  ui_action?: 'show_confirmation' | 'chat_only' | 'show_results' | 'async_processing';
  specialist_role?: string;
  primary_type?: string;
  suggested_questions?: string[];
  direct_questions?: string[];
  final_report?: any;
  session_id?: string;
  confidence?: number;
  // 【新增】Celery任务ID（用于轮询）
  task_id?: string;
  // 【新增】RAG相关属性
  rag_triggered?: boolean;
  rag_sources?: string[];
  // 【新增】动态人设和策略信息
  persona_definition?: {
    role_title?: string;
    professional_background?: string;
    years_of_experience?: string;
    expertise_area?: string[];
    approach_style?: string;
  };
  strategic_focus?: {
    analysis_angle?: string;
    key_points?: string[];
    risk_alerts?: string[];
    attention_matters?: string[];
  };
}

// Contract Review types
export interface ContractReviewUploadResponse {
  filename: string;
  file_url: string;
  upload_time: string;
}

export interface ContractReviewStartResponse {
  task_id: string;
  status: string;
  estimated_time: number;
}

// ==================== 合同生成类型 ====================

export interface ContractGenerationAnalyzeRequest {
  user_input: string;
  file_count?: number;
}

export interface ContractGenerationAnalyzeResponse {
  processing_type: 'contract_modification' | 'contract_termination' | 'single_contract' | 'contract_planning';
  analysis: Record<string, any>;
  clarification_questions: string[];
}

export interface ContractGenerationResponse {
  success: boolean;
  processing_type?: string;
  contracts: GeneratedContract[];
  clarification_questions?: string[];
  error?: string;
}

// ==================== Celery 任务响应类型（新增）====================

export interface ContractGenerationCeleryResponse {
  success: boolean;
  task_system: 'celery' | 'sync';
  task_id?: string;
  task_token?: string;  // ✅ 新增：WebSocket 认证 token
  celery_task_id?: string;
  status?: 'pending' | 'processing' | 'completed' | 'failed';
  message?: string;
}

export interface ContractGenerationSyncResponse {
  success: boolean;
  task_system: 'sync';
  processing_type?: string;
  contracts: GeneratedContract[];
  clarification_questions?: string[];
  answered_count?: number;
  total_questions?: number;
  error?: string;
}

// 联合类型，用于 API 响应
export type ContractGenerationTaskResponse = ContractGenerationCeleryResponse | ContractGenerationSyncResponse;

export interface GeneratedContract {
  filename: string;
  docx_path: string;
  pdf_path?: string;
  preview_url: string;
  download_docx_url: string;
  download_pdf_url?: string;
  plan_index?: number;
  contract_id?: string;
  template_info?: TemplateInfo;
  unanswered_questions?: string[];
  // 新增：生成的文本内容（用于预览）
  content?: string;
  // 新增：是否已生成文件
  file_generated?: boolean;
}

export interface TemplateInfo {
  name: string;
  category?: string;
  subcategory?: string;
  match_source?: 'rag' | 'fallback' | 'none' | 'fallback_error';
  match_score?: number;
  similarity_score?: number;
  rerank_score?: number;
  match_reason?: string;
  description?: string;
  source?: string;
  file_url?: string;
}

export interface DocumentProcessRequest {
  content: string;
  doc_type?: 'contract' | 'letter' | 'judicial';
  filename?: string;
  output_format?: 'docx' | 'pdf';
}

export interface DocumentProcessResponse {
  success: boolean;
  filename: string;
  docx_path: string;
  pdf_path?: string;
  preview_url: string;
  download_docx_url: string;
  download_pdf_url?: string;
  message: string;
}

// ==================== 需求澄清表单类型（新增）====================

export interface ClarificationFormField {
  field_id: string;
  field_type: 'text' | 'number' | 'date' | 'textarea' | 'select' | 'radio' | 'checkbox' | 'money';
  label: string;
  placeholder?: string;
  required: boolean;
  default_value?: string | number | boolean | null;
  validation_rules?: Record<string, any>;
  options?: Array<{ value: string; label: string }>;
}

// 新增：支持后端的 Question 格式
export interface ClarificationFormQuestion {
  id: string;
  question: string;
  type: string;
  required: boolean;
  default?: any;
  options?: Array<{ value: string; label: string }>;
  placeholder?: string;
}

export interface ClarificationFormSection {
  section_id: string;
  section_title: string;
  fields: ClarificationFormField[];
}

export interface ClarificationFormSummary {
  detected_contract_type: string;
  template_match_level: string;
  template_name: string;
  missing_info: string[];
}

// 修改：ClarificationForm 同时支持新旧格式
export interface ClarificationForm {
  form_title?: string;
  form_description?: string;

  // 新格式（后端当前返回）
  questions?: ClarificationFormQuestion[];

  // 旧格式（前端期望）
  sections?: ClarificationFormSection[];

  summary?: ClarificationFormSummary;
}

export interface ClarificationFormResponse {
  success: boolean;
  processing_type: string;
  analysis_result: any;
  knowledge_graph_features?: any;
  template_match_result?: any;
  clarification_form: ClarificationForm;
  error?: string;
  // 【新增】提取的变更/解除信息（用于 Step 2 确认）
  extracted_modification_termination_info?: {
    processing_type: 'contract_modification' | 'contract_termination';
    original_contract_info: {
      contract_name: string;
      signing_date: string;
      parties: string[];
      contract_term: string;
      key_terms: Record<string, any>;
    };
    termination_reason?: string;  // 解除场景
    post_termination_arrangements?: Record<string, any>;  // 解除场景
    modification_points?: Array<{  // 变更场景
      clause_number: string;
      original_content: string;
      modified_content: string;
      reason: string;
    }>;
    confidence: number;
  };
}

export interface GenerateWithFormDataRequest {
  user_input: string;
  form_data: Record<string, any>;
  analysis_result: any;
  template_match_result: any;
  knowledge_graph_features: any;
  planning_mode?: string;  // 【新增】规划模式
  skip_template?: boolean;  // 【新增】是否跳过模板
  // 【新增】Step 2 确认的变更/解除信息
  confirmed_modification_termination_info?: {
    processing_type: 'contract_modification' | 'contract_termination';
    original_contract_info: {
      contract_name: string;
      signing_date: string;
      parties: string[];
      contract_term: string;
      key_terms: Record<string, any>;
    };
    termination_reason?: string;  // 解除场景
    post_termination_arrangements?: Record<string, any>;  // 解除场景
    modification_points?: Array<{  // 变更场景
      clause_number: string;
      original_content: string;
      modified_content: string;
      reason: string;
    }>;
    confidence: number;
  };
}

// 文书生成请求类型
export interface DocumentGenerationRequest {
  scenario: string;
  content: string;
  additionalInstructions?: string;
}

// 文书生成响应类型
export interface DocumentGenerationResponse {
  document_id: string;
  content: string;
  status: string;
}

// 文件上传响应类型
export interface FileUploadResponse {
  file_id: string;
  message: string;
}

// 任务状态响应类型
export interface TaskStatusResponse {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  result?: any;
  error?: string;
}

// 【新增】法律咨询任务状态响应类型（用于轮询）
export interface ConsultationTaskStatusResponse {
  status: 'waiting_confirmation' | 'completed' | 'running' | 'not_found';
  session_id: string;
  task_type?: 'assistant' | 'specialist';  // 【新增】任务类型标识
  // 当 status == "waiting_confirmation" 时
  classification?: {
    primary_type: string;
    specialist_role: string;
    suggested_questions: string[];
    direct_questions: string[];
    persona_definition?: any;
    strategic_focus?: any;
  };
  // 当 status == "completed" 时
  result?: {
    legal_analysis: string;
    legal_advice: string;
    risk_warning: string;
    action_steps: string[];
    final_report: string;
  };
  // 当 status == "running" 时
  progress?: number;
  current_step?: string;
  message?: string;
  ui_action?: string;
}

// 【新增】用户决策请求类型
export interface ConsultationDecisionRequest {
  action: 'confirm' | 'cancel';
  selected_suggested_questions?: string[];
  custom_question?: string;
}

// 【新增】用户决策响应类型
export interface ConsultationDecisionResponse {
  success: boolean;
  session_id: string;
  action: 'confirm' | 'cancel';
  // 确认时的响应字段
  next_phase?: 'specialist';
  new_task_id?: string;
  status?: string;
  message?: string;
  // 取消时的响应字段
  saved_to_history?: boolean;
}

// 合同审查请求类型
export interface ContractReviewRequest {
  contract_text: string;
  metadata: {
    contract_name?: string;
    parties?: string;
    amount?: string;
    contract_type?: string;
    core_terms?: string;
  };
  stance: string; // "甲方" | "乙方" | "中立"
}

// 合同审查响应类型
export interface ContractReviewResponse {
  review_id: string;
  summary: string;
  issues: Array<{
    id: number;
    issue_type: string;
    quote: string;
    explanation: string;
    suggestion: string;
    severity: 'high' | 'medium' | 'low';
    action_type: 'warning' | 'suggestion' | 'info';
    status: 'open' | 'resolved';
  }>;
  recommendations: string[];
}

// 法律咨询请求类型
export interface LegalConsultationRequest {
  question: string;
  context?: Record<string, any>;
  uploaded_files?: string[]; // 已上传文件ID列表
  user_confirmed?: boolean; // 用户是否确认转交专业律师
  selected_suggested_questions?: string[]; // 用户选择的建议问题
}

// 文件上传响应类型
export interface ConsultationFileUploadResponse {
  file_id: string;
  filename: string;
  file_type: string;
  content_preview: string;
  message: string;
}

// 文件信息类型
export interface ConsultationFileInfo {
  file_id: string;
  filename: string;
  file_type: string;
  content: string;
  metadata: Record<string, any>;
}

// 法律咨询响应类型
export interface LegalConsultationResponse {
  answer: string;
  specialist_role?: string;
  primary_type?: string;
  confidence?: number;
  relevant_laws?: string[];
  need_confirmation?: boolean;
  response?: string;
  follow_up_questions?: string[];
  suggestions?: string[];
  action_buttons?: Array<{ key: string; label: string }>;
}

// 费用计算请求类型
export interface CostCalculationRequest {
  case_type: string;          // 案件类型
  case_description: string;   // 案件描述
  case_amount?: number;       // 案件标的额
  context?: Record<string, any>; // 上下文信息
}

// 费用项类型
export interface CostItem {
  name: string;               // 费用项目名称
  description: string;        // 费用项目描述
  amount: number;             // 费用金额
  unit: string;               // 费用单位
  quantity: number;           // 数量
}

// 费用计算响应类型
export interface CostCalculationResponse {
  total_cost: number;         // 总费用
  cost_breakdown: CostItem[]; // 费用明细
  calculation_basis: string;  // 计算依据
  disclaimer: string;         // 免责声明
}

// ==================== 费用测算 V2 类型（新增：支持资料上传和信息提取）====================

// 案件信息类型
export interface CaseInfo {
  case_type: string;              // 案件类型
  case_description: string;        // 案件概况
  parties: string[];              // 当事人列表
  litigation_requests: string[]; // 诉讼请求（核心）
  case_amount?: number;           // 标的额
  procedural_position?: string;   // 程序地位（一审/二审/再审）
  case_nature?: string;           // 案件性质（民事/刑事/行政）
}

// 文件信息类型
export interface UploadedFileInfo {
  file_id: string;
  filename: string;
  file_type: string;
  upload_time?: string;
}

// 上传响应类型
export interface CostCalcUploadResponse {
  success: boolean;
  upload_id: string;
  files: UploadedFileInfo[];
  message: string;
}

// 信息提取响应类型
export interface CostCalcExtractionResponse {
  success: boolean;
  case_info?: CaseInfo;
  error?: string;
  warnings?: string[];
}

// 费用计算请求 V2
export interface CostCalculationRequestV2 {
  case_info: CaseInfo;
  stance: 'plaintiff' | 'defendant' | 'applicant' | 'respondent'; // 立场
  include_lawyer_fee: boolean; // 是否计算律师费
  lawyer_fee_basis?: string;   // 律师费计费依据
  lawyer_fee_rate?: number;    // 律师费率（%）
}

// 费用计算响应 V2
export interface CostCalculationResponseV2 {
  success: boolean;
  total_cost: number;
  cost_breakdown: CostItem[];
  calculation_basis: string;
  disclaimer: string;
  warnings?: string[];
}
