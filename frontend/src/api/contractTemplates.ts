// frontend/src/api/contractTemplates.ts
import axios from 'axios';
// 引入我们在 types/contract.ts 中定义的类型
import type {
  ContractTemplate,
  TemplateListResponse,
  CategoryTreeItem,
  ContractLegalFeatures,
  TemplateInfo
} from '../types/contract';

// 重新导出类型，方便其他文件导入
export type { ContractTemplate, CategoryTreeItem, TemplateListResponse, ContractLegalFeatures, TemplateInfo };

// 创建专用的 axios 实例
// 逻辑：如果是生产环境(PROD)，且没有设置环境变量，则使用相对路径（即当前域名）
// 否则使用环境变量，最后回退到 localhost
const baseUrl = import.meta.env.VITE_API_BASE_URL
  ? import.meta.env.VITE_API_BASE_URL
  : (import.meta.env.PROD ? '' : 'http://localhost:8000');

const apiClient = axios.create({
  baseURL: baseUrl + '/api/v1',
  timeout: 30000,
});

// 请求拦截器：添加 token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：处理错误
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期，跳转到登录页
      localStorage.removeItem('accessToken');
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// 为了兼容旧代码引用，重新导出部分类型别名
export type TransactionNature = string;
export type ContractObject = string;
export type Complexity = string;
export type Stance = string;
export type PrimaryContractType = string;

// 查询参数接口
export interface TemplateSearchParams {
  keyword?: string;
  category?: string; // 支持按一级分类筛选
  subcategory?: string; // 支持按二级分类筛选
  tags?: string[];
  is_featured?: boolean;
  is_free?: boolean;
  scope?: 'public' | 'my' | 'all';
  page?: number;
  page_size?: number;
}

export interface SearchRequest {
  query: string;
  category?: string;
  top_k?: number;
  use_rerank?: boolean;
}

export interface SearchResponse {
  templates: any[]; // 简化定义
  query: string;
  total_count: number;
}

export const contractTemplateApi = {
  // ==================== 1. 模板管理 ====================
  
  // [新增] 获取合同类型下拉选项 (用于前端 Select 组件)
  getContractTypeOptions: async (): Promise<Array<{ label: string; value: string; group: string }>> => {
    const response = await apiClient.get('/contract/options/contract-types');
    return response.data;
  },
  // 获取模板列表 (支持分页和筛选)
  getTemplates: async (params: TemplateSearchParams = {}): Promise<TemplateListResponse> => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          queryParams.append(key, value.join(','));
        } else {
          queryParams.append(key, String(value));
        }
      }
    });
    const response = await apiClient.get(`/contract/?${queryParams.toString()}`);
    return response.data;
  },

  // 获取模板详情
  getTemplate: async (templateId: string): Promise<ContractTemplate> => {
    const response = await apiClient.get(`/contract/${templateId}`);
    return response.data;
  },

  // 上传模板 (支持 Word/PDF 转 Markdown + V2 特征)
  uploadTemplate: async (formData: FormData): Promise<ContractTemplate> => {
    const response = await apiClient.post('/contract/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  // 更新模板 (支持文件替换和元数据更新)
  updateTemplate: async (templateId: string, formData: FormData): Promise<ContractTemplate> => {
    const response = await apiClient.put(`/contract/${templateId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  // 删除模板
  deleteTemplate: async (templateId: string): Promise<void> => {
    await apiClient.delete(`/contract/${templateId}`);
  },

  // 更新合同法律特征 (管理员)
  updateContractFeatures: async (templateId: string, features: ContractLegalFeatures): Promise<void> => {
    await apiClient.put(`/contract/${templateId}/contract-features`, features);
  },

  // 获取模板内容 (用于编辑预览)
  getTemplateContent: async (templateId: string): Promise<{ content: string; file_type: string }> => {
    const response = await apiClient.get(`/contract/${templateId}/content`);
    return response.data;
  },

  // 获取模板预览
  getTemplatePreview: async (templateId: string): Promise<{ content: string; file_type: string }> => {
    const response = await apiClient.get(`/contract/${templateId}/preview`);
    return response.data;
  },

  // 评价模板
  rateTemplate: async (templateId: string, rating: number): Promise<void> => {
    await apiClient.post(`/contract/${templateId}/rate`, { rating });
  },

  // 下载模板
  downloadTemplate: async (templateId: string): Promise<void> => {
    const baseURL = import.meta.env.VITE_API_BASE_URL
      ? import.meta.env.VITE_API_BASE_URL
      : (import.meta.env.PROD ? '' : 'http://localhost:8000');
    const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
    const url = `${baseURL}/contract/${templateId}/download`;

    // 使用 fetch 下载流
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) throw new Error('下载失败');

    const blob = await response.blob();
    // 尝试从 Content-Disposition 获取文件名
    const disposition = response.headers.get('Content-Disposition');
    let filename = 'contract_template.docx';
    if (disposition) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) filename = decodeURIComponent(match[1]);
    }

    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },

  // ==================== 2. 分类管理 (Category) ====================

  // 获取分类树 (带模板数量统计)
  getCategoryTree: async (includeInactive: boolean = false): Promise<CategoryTreeItem[]> => {
    // 修正：对应后端的新路由 /tree
    const response = await apiClient.get(`/categories/tree?include_inactive=${includeInactive}`);
    return response.data;
  },

  // 新增分类
  createCategory: async (data: { name: string; parent_id?: number; description?: string }): Promise<CategoryTreeItem> => {
    const response = await apiClient.post('/categories/', data);
    return response.data;
  },

  // 更新分类
  updateCategory: async (id: number, data: Partial<CategoryTreeItem>): Promise<CategoryTreeItem> => {
    const response = await apiClient.put(`/categories/${id}`, data);
    return response.data;
  },

  // 删除分类
  deleteCategory: async (id: number): Promise<void> => {
    await apiClient.delete(`/categories/${id}`);
  },

  // ==================== 3. 智能检索 (RAG) ====================

  searchTemplates: async (req: SearchRequest): Promise<SearchResponse> => {
    const response = await apiClient.post('/rag/retrieve', req);
    return response.data;
  },

  // ==================== 4. 知识图谱 (Knowledge Graph) ====================

  // 获取所有合同类型
  getAllContractTypes: async (): Promise<{
    contract_types: Array<{
      name: string;
      aliases: string[];
      category: string;
      subcategory?: string;
      legal_features: any;
      recommended_template_ids: string[];
    }>;
    total_count: number;
  }> => {
    const response = await apiClient.get('/knowledge-graph/contract-types');
    return response.data;
  },

  // 根据关键词搜索合同类型
  searchContractTypes: async (query: string): Promise<{
    contract_types: Array<{
      name: string;
      aliases: string[];
      category: string;
      subcategory?: string;
      legal_features: any;
      recommended_template_ids: string[];
    }>;
    total_count: number;
  }> => {
    const response = await apiClient.post('/knowledge-graph/search-by-keywords', { query });
    return response.data;
  },

  // 根据合同名称获取法律特征（用于自动填充表单）
  getLegalFeatures: async (contractName: string): Promise<{
    transaction_nature: string;
    contract_object: string;
    complexity: string;
    stance: string;
    consideration_type: string;
    consideration_detail: string;
    transaction_characteristics: string;
    usage_scenario?: string;
    legal_basis?: string[];
  }> => {
    const response = await apiClient.get(`/knowledge-graph/legal-features/${encodeURIComponent(contractName)}`);
    return response.data;
  },

  // 根据分类获取合同类型列表（用于当分类是大类时）
  getContractTypesByCategory: async (category: string, subcategory?: string): Promise<{
    contract_types: Array<{
      name: string;
      aliases: string[];
      category: string;
      subcategory?: string;
      legal_features: any;
      recommended_template_ids: string[];
    }>;
    total_count: number;
  }> => {
    const params = subcategory ? `?subcategory=${encodeURIComponent(subcategory)}` : '';
    const response = await apiClient.get(`/knowledge-graph/categories/${encodeURIComponent(category)}/contract-types${params}`);
    return response.data;
  },

  // ==================== 5. 知识图谱管理 ====================

  // 创建合同类型
  createContractType: async (data: {
    name: string;
    aliases?: string[];
    category: string;
    subcategory?: string;
    legal_features: any;
    recommended_template_ids?: string[];
  }): Promise<any> => {
    const response = await apiClient.post('/knowledge-graph/admin/contract-types', data);
    return response.data;
  },

  // 更新合同类型
  updateContractType: async (contractName: string, data: {
    name?: string;
    aliases?: string[];
    category?: string;
    subcategory?: string;
    legal_features?: any;
    recommended_template_ids?: string[];
  }): Promise<any> => {
    const response = await apiClient.put(`/knowledge-graph/admin/contract-types/${encodeURIComponent(contractName)}`, data);
    return response.data;
  },

  // 删除合同类型
  deleteContractType: async (contractName: string): Promise<any> => {
    const response = await apiClient.delete(`/knowledge-graph/admin/contract-types/${encodeURIComponent(contractName)}`);
    return response.data;
  },

  // 导出知识图谱
  exportKnowledgeGraph: async (): Promise<any> => {
    const response = await apiClient.get('/knowledge-graph/admin/export');
    return response.data;
  },

  // 从合同分类同步知识图谱
  syncFromCategories: async (): Promise<{
    message: string;
    added: number;
    skipped: number;
    total: number;
  }> => {
    const response = await apiClient.post('/knowledge-graph/admin/sync-from-categories');
    return response.data;
  },

  // ==================== 6. AI 完善功能 ====================

  // AI 批量完善法律特征
  aiEnhanceLegalFeatures: async (params: {
    contract_names?: string[];
    force?: boolean;
  }): Promise<{
    message: string;
    total: number;
    success: number;
    failed: number;
    skipped: number;
    errors: string[];
  }> => {
    // AI 批量处理可能需要很长时间，设置 10 分钟超时
    const response = await apiClient.post('/knowledge-graph/admin/ai-enhance', params, {
      timeout: 600000 // 10 分钟超时
    });
    return response.data;
  },

  // AI 完善单个合同的法律特征
  aiEnhanceSingleContract: async (contractName: string): Promise<{
    message: string;
    contract_type: any;
  }> => {
    // 单个合同处理可能需要 30 秒，设置 60 秒超时
    const response = await apiClient.post(`/knowledge-graph/admin/ai-enhance/${encodeURIComponent(contractName)}`, {}, {
      timeout: 60000 // 60 秒超时
    });
    return response.data;
  },

  // ==================== 7. 模板处理功能 ====================

  // 处理现有模板，关联知识图谱并提取结构
  processExistingTemplates: async (force: boolean = false): Promise<{
    message: string;
    total: number;
    processed: number;
    matched: number;
    errors: string[];
  }> => {
    const response = await apiClient.post('/knowledge-graph/admin/process-templates', null, {
      params: { force },
      timeout: 300000 // 5 分钟超时
    });
    return response.data;
  }
};