// frontend/src/api/index.ts
import axios, { AxiosResponse, AxiosRequestConfig } from 'axios';
import { getApiBaseUrl } from '../utils/apiConfig';
import {
  User,
  Template,
  Category,
  ApiResponse,
  PaginatedResponse,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  TaskModificationRequest,
  FileGenerateRequest,
  ChatResponse,
  ChatMessage,
  TemplateSearchRequest,
  CategoryCreateRequest,
  GuidanceRequest,
  GuidanceResponse,
  ConsultationRequest,
  ConsultationResponse,
  ContractGenerationAnalyzeRequest,
  ContractGenerationAnalyzeResponse,
  ContractGenerationResponse,
  DocumentProcessRequest,
  DocumentProcessResponse
} from '../types';
import { Task } from '../types/task';
import { SearchResponse, SearchParams } from '../types/search';

// ==================== 类型定义 ====================

// 任务列表项类型（用于工作台展示）
interface TaskItem {
  id: string;
  title: string;
  status: string;
  progress: number;
  time: string;
  created_at?: string;
}

// 任务统计类型
interface TaskStats {
  in_progress: number;
  completed: number;
  total: number;
}

// 法律咨询文件上传响应类型
interface ConsultationFileUploadResponse {
  file_id: string;
  filename: string;
  file_type: string;
  content_preview: string;
  message: string;
}

// 文件信息类型
interface ConsultationFileInfo {
  file_id: string;
  filename: string;
  file_type: string;
  content: string;
  metadata: Record<string, any>;
}

// 新增类型：合同审查相关响应
interface ContractUploadResponse {
  contract_id: number;
  config: any;
  token: string;
  filename: string;
  preprocess_info?: {
    original_format: string;
    converted: boolean;
    final_format: string;
    metadata?: any;
  };
}

interface MetadataResponse {
  metadata: {
    contract_name?: string;
    parties?: string;
    amount?: string;
    contract_type?: string;
    core_types?: string;
    core_terms?: string;
  };
}

interface ReviewResultsResponse {
  status: string;
  metadata: any;
  stance: string;
  review_items: Array<{
    id: number;
    issue_type: string;
    quote: string;
    explanation: string;
    suggestion: string;
    severity: string;
    action_type: string;
    item_status: string;
  }>;
}

interface ApiClient {
  // --- 用户 & 认证 ---
  registerUser: (data: RegisterRequest) => Promise<AxiosResponse<User>>;
  loginUser: (data: LoginRequest) => Promise<AxiosResponse<LoginResponse>>;
  getCurrentUser: () => Promise<AxiosResponse<User>>;
  getSystemStats: () => Promise<AxiosResponse<ApiResponse>>;
  getUserList: (params?: { page?: number; size?: number }) => Promise<AxiosResponse<PaginatedResponse<User>>>;
  deleteTemplate: (id: string) => Promise<AxiosResponse<void>>;

  // --- 任务 & 工作流 ---
  startWorkflow: (formData: FormData) => Promise<AxiosResponse<{ task_id: string }>>;
  getTaskStatus: (taskId: string) => Promise<AxiosResponse<Task>>;
  sendModificationRequest: (taskId: string, payload: TaskModificationRequest) => Promise<AxiosResponse<Task>>;
  generateFile: (taskId: string, payload: FileGenerateRequest) => Promise<AxiosResponse<{ file_url: string }>>;
  createAnalysisTask: (formData: FormData) => Promise<AxiosResponse<{ task_id: string }>>;
  getTaskHistory: () => Promise<AxiosResponse<PaginatedResponse<Task>>>;
  getTaskById: (taskId: string) => Promise<AxiosResponse<Task>>;

  // --- 任务管理（新增）---
  getTasks: (params?: { status?: string; limit?: number; skip?: number }) => Promise<AxiosResponse<TaskItem[]>>;
  getTasksStats: () => Promise<AxiosResponse<TaskStats>>;
  getUnviewedTasks: () => Promise<AxiosResponse<TaskItem[]>>;
  markTaskAsViewed: (taskId: string) => Promise<AxiosResponse<{ success: boolean; message: string }>>;

  // --- 智能对话 ---
  smartChat: (message: string, conversationHistory?: ChatMessage[], sessionId?: string) => Promise<AxiosResponse<ChatResponse>>;
  streamChat: (message: string, conversationHistory?: ChatMessage[], sessionId?: string) => Promise<AxiosResponse<ChatResponse>>;
  getChatSuggestions: () => Promise<AxiosResponse<string[]>>;
  checkChatHealth: () => Promise<AxiosResponse<ApiResponse>>;
  clearChatSession: (sessionId: string) => Promise<AxiosResponse<void>>;

  // --- 智能引导和智能咨询接口 ---
  intelligentGuidance: (data: GuidanceRequest) => Promise<AxiosResponse<GuidanceResponse>>;
  legalExpertConsultation: (data: ConsultationRequest) => Promise<AxiosResponse<ConsultationResponse>>;
  guidanceAnalysisWorkflow: (data: GuidanceRequest) => Promise<AxiosResponse<GuidanceResponse>>;
  expertConsultationWorkflow: (data: ConsultationRequest) => Promise<AxiosResponse<ConsultationResponse>>;

  // --- 合同模版 ---
  getTemplates: (params: TemplateSearchRequest) => Promise<AxiosResponse<PaginatedResponse<Template>>>;
  searchTemplates: (data: TemplateSearchRequest) => Promise<AxiosResponse<PaginatedResponse<Template>>>;
  uploadTemplate: (formData: FormData) => Promise<AxiosResponse<Template>>;
  downloadTemplate: (templateId: string) => Promise<AxiosResponse<{ file_url: string }>>;
  rateTemplate: (templateId: string, rating: number) => Promise<AxiosResponse<void>>;
  getTemplateCategories: () => Promise<AxiosResponse<Category[]>>;

  // --- 分类管理接口 ---
  getCategoryList: () => Promise<AxiosResponse<Category[]>>;
  createCategory: (data: CategoryCreateRequest) => Promise<AxiosResponse<Category>>;
  updateCategory: (id: number, data: Partial<CategoryCreateRequest>) => Promise<AxiosResponse<Category>>;
  deleteCategory: (id: number) => Promise<AxiosResponse<void>>;

  // --- 新合同审查接口（替换旧的） ---
  uploadContract: (file: File) => Promise<AxiosResponse<ContractUploadResponse>>;
  extractContractMetadata: (contractId: number) => Promise<AxiosResponse<MetadataResponse>>;
  startDeepReview: (contractId: number, stance: string, metadata?: any, enableCustomRules?: boolean) => Promise<AxiosResponse<any>>;
  getReviewResults: (contractId: number) => Promise<AxiosResponse<ReviewResultsResponse>>;

  // --- 审查意见编辑与修订 ---
  updateReviewItem: (itemId: number, data: { explanation: string; suggestion: string }) => Promise<AxiosResponse<any>>;
  applyRevisions: (contractId: number, reviewItemIds: number[], autoApply?: boolean) => Promise<AxiosResponse<any>>;
  getRevisionConfig: (contractId: number) => Promise<AxiosResponse<any>>;
  downloadContract: (contractId: number, docType: 'original' | 'revised') => Promise<Blob>;

  // --- 合同生成接口 ---
  analyzeRequirement: (data: ContractGenerationAnalyzeRequest) => Promise<AxiosResponse<ContractGenerationAnalyzeResponse>>;
  generateContract: (formData: FormData) => Promise<AxiosResponse<ContractGenerationResponse>>;
  generateContractFiles: (formData: FormData) => Promise<AxiosResponse<DocumentProcessResponse>>;
  continueGeneration: (sessionId: string, clarification: string) => Promise<AxiosResponse<ContractGenerationResponse>>;
  processDocument: (data: DocumentProcessRequest) => Promise<AxiosResponse<DocumentProcessResponse>>;
  checkContractGenerationHealth: () => Promise<AxiosResponse<any>>;

  // --- 新增：需求澄清表单接口 ---
  analyzeAndGetClarificationForm: (data: { user_input: string; uploaded_files?: string[]; planning_mode?: 'multi_model' | 'single_model' }) => Promise<AxiosResponse<any>>;
  generateContractWithFormData: (data: any) => Promise<AxiosResponse<ContractGenerationResponse>>;
  getTemplatePreview: (templateId: string) => Promise<AxiosResponse<any>>;
  // 【新增】Step 2 LLM 提取接口
  extractModificationTerminationInfo: (data: { user_input: string; analysis_result?: any }) => Promise<AxiosResponse<any>>;
  // --- 合同健康度评估 ---
  getHealthAssessment: (contractId: number) => Promise<AxiosResponse<any>>;

  // --- 新增：合同规划专用接口 ---
  generateContractPlanOnly: (data: { user_input: string; planning_mode: string; uploaded_files?: File[]; session_id?: string }) => Promise<AxiosResponse<any>>;
  generateContractsFromPlan: (data: { plan_id: string; session_id?: string }) => Promise<AxiosResponse<any>>;

  // --- 新增：合同生成历史任务接口 ---
  getContractGenerationTasks: (params?: { skip?: number; limit?: number; planning_mode?: string; status?: string }) => Promise<AxiosResponse<{ tasks: any[]; total: number }>>;
  getContractGenerationTaskDetail: (taskId: string) => Promise<AxiosResponse<any>>;

  // --- 文档预览接口 ---
  getDocumentPreviewConfig: (filename: string) => Promise<AxiosResponse<any>>;

  // --- 法律咨询接口 ---
  submitLegalQuestion: (data: ConsultationRequest) => Promise<AxiosResponse<ConsultationResponse>>;

  // --- 费用计算接口 ---
  calculateCost: (data: any) => Promise<AxiosResponse<any>>;

  // --- 费用计算 V2 接口（新增：支持资料上传和信息提取）---
  uploadCostCalcDocuments: (formData: FormData) => Promise<AxiosResponse<any>>;
  extractCostCalcCaseInfo: (data: { upload_id: string; file_names: string[] }) => Promise<AxiosResponse<any>>;
  calculateCostV2: (data: any) => Promise<AxiosResponse<any>>;

  // --- 风险评估接口 ---
  submitRiskAnalysis: (data: any) => Promise<AxiosResponse<{ session_id: string; status: string; message: string }>>;
  uploadRiskDocument: (file: File, sessionId: string) => Promise<AxiosResponse<{ file_id: string; file_path: string; message: string }>>;
  startRiskAnalysis: (sessionId: string) => Promise<AxiosResponse<{ message: string; session_id: string }>>;
  getRiskAnalysisStatus: (sessionId: string) => Promise<AxiosResponse<any>>;
  getRiskAnalysisResult: (sessionId: string) => Promise<AxiosResponse<any>>;

  // --- 全局搜索接口 ---
  globalSearch: (params: SearchParams) => Promise<AxiosResponse<SearchResponse>>;

  // --- 通用 HTTP ---
  get: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
  post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
  put: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
  delete: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
}

// 防御性函数：清理对象中的循环引用和非序列化数据
const cleanCircularRefs = (obj: any): any => {
  if (obj === null || obj === undefined) return null;
  if (typeof obj !== 'object') return obj;

  // 处理数组
  if (Array.isArray(obj)) {
    return obj.map(cleanCircularRefs).filter(item => item !== null && item !== undefined);
  }

  // 处理普通对象
  const cleaned: any = {};
  const seen = new WeakSet();

  const clean = (value: any, key?: string): any => {
    // 调试：追踪 package_id 的处理
    if (key === 'package_id') {
      console.log('[cleanCircularRefs] 处理 package_id:', value, '类型:', typeof value);
    }

    // 基本类型直接返回
    if (value === null || value === undefined) return null;
    if (typeof value !== 'object') return value;

    // 检测循环引用
    if (seen.has(value)) return null;
    seen.add(value);

    // 过滤掉 DOM 元素
    if (value instanceof HTMLElement) return null;
    if (value instanceof Element) return null;

    // 过滤掉 React 对象（更全面的检测）
    // 检查 React Fiber 相关属性
    const reactKeys = [
      '$$typeof', '_reactInternalFiber', '_reactInternalInstance',
      '_reactRootContainer', '__reactFiber', '__reactProps',
      '_owner', '_store', 'stateNode', 'return', 'alternate',
      'memoizedProps', 'memoizedState', 'pendingProps', 'updateQueue'
    ];
    for (const key of reactKeys) {
      if (key in value) return null;
    }

    // 过滤掉函数
    if (typeof value === 'function') return null;

    // 处理数组
    if (Array.isArray(value)) {
      return value.map((item, idx) => clean(item, `${key}[${idx}]`)).filter(item => item !== null && item !== undefined);
    }

    // 处理普通对象
    const result: any = {};
    for (const key in value) {
      // 跳过内部属性
      if (key.startsWith('__') || key.startsWith('_react') || key.startsWith('__react')) {
        continue;
      }
      if (value.hasOwnProperty(key)) {
        try {
          // 测试是否可安全访问
          const testValue = value[key];
          const cleanedValue = clean(testValue, key);
          if (cleanedValue !== null && cleanedValue !== undefined) {
            result[key] = cleanedValue;
          } else {
            // 调试：显示被过滤的值
            if (key === 'package_id') {
              console.log('[cleanCircularRefs] package_id 被过滤:', testValue, 'cleanedValue:', cleanedValue);
            }
          }
        } catch (e) {
          // 忽略无法访问或序列化的属性
          console.error('[cleanCircularRefs] 处理属性', key, '时出错:', e);
        }
      }
    }
    return result;
  };

  return clean(obj);
};

export const axiosInstance = axios.create({
  baseURL: getApiBaseUrl() + '/api/v1',
  withCredentials: true,
});

// 如果后端使用基于 Cookie 的登录/会话，需要发送凭证
axiosInstance.defaults.withCredentials = true;

// 拦截器保持不变（token 处理、401 跳转）
axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // 调试日志：请求数据
    if (config.url?.includes('/login')) {
      console.log('[Interceptor] Login request config.data type:', config.data?.constructor?.name);
      console.log('[Interceptor] Login request config.data:', config.data);
    }

    // 清理请求数据中的循环引用，但跳过 URLSearchParams 和 FormData
    if (config.data && typeof config.data === 'object' && !(config.data instanceof URLSearchParams) && !(config.data instanceof FormData)) {
      // 调试日志：显示清理前的数据
      if (config.url?.includes('create-session')) {
        console.log('[Interceptor] create-session 清理前:', config.data);
      }
      try {
        config.data = cleanCircularRefs(config.data);
        if (config.url?.includes('create-session')) {
          console.log('[Interceptor] create-session 清理后:', config.data);
        }
      } catch (e) {
        console.warn('[API] Failed to clean circular refs:', e);
      }
    }

    return config;
  },
  (error) => Promise.reject(error)
);

axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

const api: ApiClient = {
  // --- 原有接口全部保留（这里省略，复制你原来的） ---
  registerUser: (data: RegisterRequest) => axiosInstance.post<User>('/auth/register', data),
  loginUser: (data: LoginRequest) => {
    const formData = new URLSearchParams();
    formData.append('username', data.username);
    formData.append('password', data.password);
    console.log('[API] Login request data:', { username: data.username, hasPassword: !!data.password });
    console.log('[API] FormData content:', formData.toString());
    return axiosInstance.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
      },
    });
  },
  getCurrentUser: () => axiosInstance.post<User>('/auth/test-token'),
  getSystemStats: () => axiosInstance.get('/admin/stats'),
  getUserList: (params) => axiosInstance.get('/admin/users', { params }),
  deleteTemplate: (id) => axiosInstance.delete(`/contract/${id}`),

  startWorkflow: (formData: FormData) => axiosInstance.post('/workflow/start', formData),
  getTaskStatus: (taskId: string) => axiosInstance.get(`/tasks/${taskId}`),
  sendModificationRequest: (taskId: string, payload: TaskModificationRequest) => axiosInstance.post('/workflow/modify', { task_id: taskId, ...payload }),
  generateFile: (taskId: string, payload: FileGenerateRequest) => axiosInstance.post('/file/generate', { task_id: taskId, ...payload }),
  createAnalysisTask: (formData: FormData) => axiosInstance.post('/analysis/', formData),
  getTaskHistory: () => axiosInstance.get('/tasks/history'),
  getTaskById: (taskId: string) => axiosInstance.get(`/tasks/${taskId}`),

  // --- 任务管理（新增）---
  getTasks: (params) => axiosInstance.get('/tasks', { params }),
  getTasksStats: () => axiosInstance.get('/tasks/stats'),
  getUnviewedTasks: () => axiosInstance.get('/tasks/unviewed'),
  markTaskAsViewed: (taskId: string) => axiosInstance.post(`/tasks/${taskId}/mark-viewed`),

  smartChat: (message: string, conversationHistory?: ChatMessage[], sessionId?: string) =>
    axiosInstance.post('/smart-chat/chat', {
      message,
      conversation_history: conversationHistory || [],
      session_id: sessionId
    }),
  streamChat: (message: string, conversationHistory?: ChatMessage[], sessionId?: string) =>
    axiosInstance.post('/smart-chat/stream-chat', {
      message,
      conversation_history: conversationHistory || [],
      session_id: sessionId
    }),
  getChatSuggestions: () => axiosInstance.get('/smart-chat/suggestions'),
  checkChatHealth: () => axiosInstance.get('/smart-chat/health'),
  clearChatSession: (sessionId: string) => axiosInstance.delete(`/smart-chat/session/${sessionId}`),

  intelligentGuidance: (data: GuidanceRequest) => axiosInstance.post('/smart-chat/guidance', data),
  legalExpertConsultation: (data: ConsultationRequest) => axiosInstance.post('/consultation', data),
  guidanceAnalysisWorkflow: (data: GuidanceRequest) => axiosInstance.post('/smart-chat/guidance-analysis', data),
  expertConsultationWorkflow: (data: ConsultationRequest) => axiosInstance.post('/smart-chat/expert-consultation', data),

  getTemplates: (params: TemplateSearchRequest) => axiosInstance.get('/contract/', { params }),
  searchTemplates: (data: TemplateSearchRequest) => axiosInstance.post('/contract/search', data),
  uploadTemplate: (formData: FormData) => axiosInstance.post('/contract/upload', formData),
  downloadTemplate: (templateId: string) => axiosInstance.post(`/contract/${templateId}/download`, {}),
  rateTemplate: (templateId: string, rating: number) => axiosInstance.post(`/contract/${templateId}/rate`, { rating }),
  getTemplateCategories: () => axiosInstance.get('/contract/categories/list'),

  getCategoryList: () => axiosInstance.get('/categories/'),
  createCategory: (data: CategoryCreateRequest) => axiosInstance.post('/categories/', data),
  updateCategory: (id: number, data: Partial<CategoryCreateRequest>) => axiosInstance.put(`/categories/${id}`, data),
  deleteCategory: (id: number) => axiosInstance.delete(`/categories/${id}`),

  // --- 新合同审查接口（完全替换旧的） ---
  uploadContract: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    // 不手动设置 Content-Type，让浏览器/axios 自动加上 boundary
    return axiosInstance.post('/contract/upload', formData);
  },

  extractContractMetadata: (contractId: number) =>
    axiosInstance.post(`/contract/${contractId}/extract-metadata`),

  startDeepReview: (contractId: number, stance: string, metadata?: any, enableCustomRules: boolean = false) =>
    axiosInstance.post(`/contract/${contractId}/deep-review`, {
      stance,
      updated_metadata: metadata,
      enable_custom_rules: enableCustomRules
    }),

  getReviewResults: (contractId: number) =>
    axiosInstance.get(`/contract/${contractId}/review-results`),

  // --- 审查意见编辑与修订 ---
  updateReviewItem: (itemId: number, data: { explanation: string; suggestion: string }) =>
    axiosInstance.put(`/contract/review-items/${itemId}`, data),

  applyRevisions: (contractId: number, reviewItemIds: number[], autoApply: boolean = false) =>
    axiosInstance.post(`/contract/${contractId}/apply-revisions`, {
      review_item_ids: reviewItemIds,
      auto_apply: autoApply
    }),

  getRevisionConfig: (contractId: number) =>
    axiosInstance.get(`/contract/${contractId}/revision-config`),

  downloadContract: async (contractId: number, docType: 'original' | 'revised') => {
    const endpoint = docType === 'revised'
      ? `/contract/${contractId}/download-revised`
      : `/contract/${contractId}/download`;
    const response = await axiosInstance.get(endpoint, {
      responseType: 'blob'
    });
    return response.data;
  },

  // --- 合同健康度评估（新增）---
  getHealthAssessment: (contractId: number) =>
    axiosInstance.get(`/contract/${contractId}/health-assessment`),

  // --- 合同生成接口实现 ---
  analyzeRequirement: (data: ContractGenerationAnalyzeRequest) =>
    axiosInstance.post('/contract-generation/analyze', data),

  generateContract: (formData: FormData) =>
    axiosInstance.post('/contract-generation/generate', formData),

  generateContractFiles: (formData: FormData) =>
    axiosInstance.post('/contract-generation/generate-files', formData),

  continueGeneration: (sessionId: string, clarification: string) => {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('clarification', clarification);
    return axiosInstance.post('/contract-generation/continue', formData);
  },

  processDocument: (data: DocumentProcessRequest) =>
    axiosInstance.post('/contract-generation/process-document', data),

  checkContractGenerationHealth: () =>
    axiosInstance.get('/contract-generation/health'),

  // --- 新增：需求澄清表单接口实现 ---
  analyzeAndGetClarificationForm: (data: { user_input: string; uploaded_files?: string[]; planning_mode?: 'multi_model' | 'single_model' }) =>
    axiosInstance.post('/contract-generation/analyze-and-get-form', data),

  generateContractWithFormData: (data: any) =>
    axiosInstance.post('/contract-generation/generate-with-form', data),

  // --- 新增：Step 2 LLM 提取变更/解除信息接口 ---
  extractModificationTerminationInfo: (data: { user_input: string; analysis_result?: any }) =>
    axiosInstance.post('/contract-generation/extract-modification-termination-info', data),

  getTemplatePreview: (templateId: string) =>
    axiosInstance.get(`/contract-generation/template-preview/${templateId}`),

  // --- 新增：合同规划专用接口实现 ---
  generateContractPlanOnly: (data: { user_input: string; planning_mode: string; uploaded_files?: File[]; session_id?: string }) => {
    const formData = new FormData();
    formData.append('user_input', data.user_input);
    formData.append('planning_mode', data.planning_mode);
    if (data.session_id) {
      formData.append('session_id', data.session_id);
    }
    if (data.uploaded_files) {
      data.uploaded_files.forEach(file => {
        formData.append('uploaded_files', file);
      });
    }
    return axiosInstance.post('/contract-generation/generate-plan-only', formData);
  },

  generateContractsFromPlan: (data: { plan_id: string; session_id?: string }) => {
    const formData = new FormData();
    formData.append('plan_id', data.plan_id);
    if (data.session_id) {
      formData.append('session_id', data.session_id);
    }
    return axiosInstance.post('/contract-generation/generate-from-plan', formData);
  },

  // --- 新增：合同生成历史任务接口实现 ---
  getContractGenerationTasks: (params?: { skip?: number; limit?: number; planning_mode?: string; status?: string }) =>
    axiosInstance.get('/contract-generation/tasks', { params }),

  getContractGenerationTaskDetail: (taskId: string) =>
    axiosInstance.get(`/contract-generation/tasks/${taskId}`),

  // --- 文档预览接口 ---
  getDocumentPreviewConfig: (filename: string) =>
    axiosInstance.get(`/document/preview/by-filename/${filename}`),

  // --- 法律咨询接口实现 ---
  submitLegalQuestion: (data: ConsultationRequest) =>
    axiosInstance.post('/consultation', data),

  // --- 费用计算接口实现 ---
  calculateCost: (data: any) =>
    axiosInstance.post('/cost-calculation', data),

  // --- 费用计算 V2 接口实现（新增：支持资料上传和信息提取）---
  uploadCostCalcDocuments: (formData: FormData) =>
    axiosInstance.post('/cost-calculation/upload', formData),

  extractCostCalcCaseInfo: (data: { upload_id: string; file_names: string[] }) =>
    axiosInstance.post('/cost-calculation/extract', data),

  calculateCostV2: (data: any) =>
    axiosInstance.post('/cost-calculation/calculate-v2', data),

  // --- 风险评估接口实现 ---
  submitRiskAnalysis: (data: any) =>
    axiosInstance.post('/risk-analysis/submit', data),

  uploadRiskDocument: (file: File, sessionId: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);
    return axiosInstance.post('/risk-analysis/upload', formData);
  },

  startRiskAnalysis: (sessionId: string) =>
    axiosInstance.post(`/risk-analysis-v2/start/${sessionId}`),

  getRiskAnalysisStatus: (sessionId: string) =>
    axiosInstance.get(`/risk-analysis/status/${sessionId}`),

  getRiskAnalysisResult: (sessionId: string) =>
    axiosInstance.get(`/risk-analysis/result/${sessionId}`),

  // --- 知识图谱法律特征API（新增）---
  getKnowledgeGraphContractTypes: () =>
    axiosInstance.get('/knowledge-graph/contract-types'),

  getKnowledgeGraphByKeywords: (query: string) =>
    axiosInstance.post('/knowledge-graph/search-by-keywords', { query }),

  getKnowledgeGraphByCategory: (category: string, subcategory?: string) =>
    axiosInstance.get(`/knowledge-graph/categories/${category}/contract-types`, {
      params: subcategory ? { subcategory } : undefined
    }),

  getKnowledgeGraphLegalFeatures: (contractName: string) =>
    axiosInstance.get(`/knowledge-graph/legal-features/${contractName}`),

  // --- 全局搜索API ---
  globalSearch: (params: SearchParams) =>
    axiosInstance.get('/search/global', { params }),

  // --- 通用 ---
  get: <T = any>(url: string, config?: AxiosRequestConfig) => axiosInstance.get(url, config),
  post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => axiosInstance.post(url, data, config),
  put: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => axiosInstance.put(url, data, config),
  delete: <T = any>(url: string, config?: AxiosRequestConfig) => axiosInstance.delete(url, config)
};

// ==================== 法律咨询文件上传相关API ====================

// 上传文件用于法律咨询
export const uploadConsultationFile = async (file: File): Promise<ConsultationFileUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await axiosInstance.post('/consultation/upload', formData);
  return response.data;
};

// 获取已上传文件的信息
export const getConsultationFile = async (fileId: string): Promise<ConsultationFileInfo> => {
  const response = await axiosInstance.get(`/consultation/file/${fileId}`);
  return response.data;
};

// 删除已上传的文件
export const deleteConsultationFile = async (fileId: string): Promise<{ message: string }> => {
  const response = await axiosInstance.delete(`/consultation/file/${fileId}`);
  return response.data;
};

// 法律咨询（使用 axiosInstance）
export const consultLaw = async (data: ConsultationRequest): Promise<ConsultationResponse> => {
  // 智能咨询可能需要较长时间（文件分析、LLM调用），设置5分钟超时
  const response = await axiosInstance.post('/consultation', data, {
    timeout: 300000 // 5 分钟超时
  });
  return response.data;
};

// 创建新会话
export const createNewConsultationSession = async (): Promise<{ session_id: string; message: string }> => {
  const response = await axiosInstance.post('/consultation/new-session');
  return response.data;
};

// 重置会话
export const resetConsultationSession = async (sessionId: string): Promise<{ message: string; session_id: string }> => {
  const response = await axiosInstance.post(`/consultation/reset-session/${sessionId}`);
  return response.data;
};

export default api;

// ==================== 风险规则包管理 API ====================

export { riskRulePackagesApi } from './riskRulePackages';

// ==================== 案件分析模块 API ====================

export * as litigationAnalysisApi from './litigationAnalysis';

// ==================== 知识库管理 API ====================

export * as knowledgeBaseApi from './knowledgeBase';
