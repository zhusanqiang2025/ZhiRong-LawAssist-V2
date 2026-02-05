/**
 * System API 客户端
 * 提供系统级别的数据导入/导出功能
 */

import axios from 'axios';
import { getApiBaseUrl } from '../utils/apiConfig';

const API_BASE_URL = getApiBaseUrl();

// 创建一个 axios 实例用于系统 API
const systemAxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// 添加请求拦截器，自动附加 token
systemAxiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 添加响应拦截器，处理 401 错误
systemAxiosInstance.interceptors.response.use(
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

export interface SystemDataExport {
  version: string;
  exported_at: string;
  categories: CategoryExport[];
  knowledge_types: KnowledgeTypeExport[];
  review_rules: ReviewRuleExport[];
  risk_packages: RiskPackageExport[];
  litigation_packages: LitigationPackageExport[];
}

export interface CategoryExport {
  id: number;
  name: string;
  code: string | null;
  parent_id: number | null;
  sort_order: number;
  is_active: boolean;
  meta_info: any;
}

export interface KnowledgeTypeExport {
  id: number;
  name: string;
  linked_category_id: number | null;
  category: string | null;
  subcategory: string | null;
  transaction_nature: string | null;
  contract_object: string | null;
  stance: string | null;
  transaction_characteristics: string | null;
  usage_scenario: string | null;
  legal_basis: any;
  is_active: boolean;
  is_system: boolean;
  created_at: string;
  updated_at?: string;
}

export interface ReviewRuleExport {
  id: number;
  name: string;
  description: string | null;
  content: string | null;
  rule_category: string;
  priority: number;
  is_active: boolean;
  is_system: boolean;
  apply_to_category_ids: any;
  target_stance: string | null;
  created_at: string;
  updated_at?: string;
}

export interface RiskPackageExport {
  package_id: string;
  package_name: string;
  package_category: string;
  description: string | null;
  applicable_scenarios: any;
  target_entities: any;
  rules: any;
  is_active: boolean;
  is_system: boolean;
  version: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface LitigationPackageExport {
  package_id: string;
  package_name: string;
  package_category: string;
  case_type: string;
  description: string | null;
  applicable_positions: any;
  target_documents: any;
  rules: any;
  is_active: boolean;
  is_system: boolean;
  version: string | null;
  created_at?: string;
  updated_at?: string;
}

export type ExportModule = 'all' | 'categories' | 'knowledge' | 'rules' | 'risk' | 'litigation';

class SystemApi {
  private axiosInstance: typeof systemAxiosInstance;

  constructor() {
    this.axiosInstance = systemAxiosInstance;
  }

  /**
   * 导出系统数据
   * @param module 指定导出的模块，不指定则导出全部
   */
  async exportData(module?: ExportModule): Promise<SystemDataExport> {
    const params = module ? `?module=${module}` : '';
    const response = await this.axiosInstance.get(`/api/v1/system/data/export${params}`);
    return response.data;
  }

  /**
   * 导入系统数据
   * @param file JSON 文件
   */
  async importData(file: File): Promise<{ success: boolean; message: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.axiosInstance.post('/api/v1/system/data/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  }

  /**
   * 下载导出数据为 JSON 文件
   * @param data 导出的数据
   * @param filename 文件名
   */
  downloadAsJson(data: any, filename: string): void {
    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
}

export const systemApi = new SystemApi();
