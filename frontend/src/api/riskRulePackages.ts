// frontend/src/api/riskRulePackages.ts
import axios from 'axios';
import type {
  RiskRulePackage,
  RiskRulePackagesResponse,
  RiskRulePackageRequest
} from '../types/riskAnalysis';

// 重新导出类型
export type {
  RiskRulePackage,
  RiskRulePackagesResponse,
  RiskRulePackageRequest
};

// 创建专用的 axios 实例
const apiClient = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000') + '/api/v1',
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

/**
 * 风险规则包管理 API
 */
export const riskRulePackagesApi = {
  /**
   * 获取规则包列表
   * @param category 可选的分类过滤器
   */
  listPackages: async (category?: string): Promise<RiskRulePackagesResponse> => {
    const params = category ? { category } : {};
    const response = await apiClient.get<RiskRulePackagesResponse>(
      '/risk-analysis-v2/packages',
      { params }
    );
    return response.data;
  },

  /**
   * 获取规则包详情
   * @param packageId 规则包ID
   */
  getPackageDetail: async (packageId: string): Promise<RiskRulePackage> => {
    const response = await apiClient.get<RiskRulePackage>(
      `/risk-analysis-v2/packages/${packageId}`
    );
    return response.data;
  },

  /**
   * 创建规则包（仅管理员）
   * @param data 规则包数据
   */
  createPackage: async (data: RiskRulePackageRequest): Promise<RiskRulePackage> => {
    const response = await apiClient.post<RiskRulePackage>(
      '/risk-analysis-v2/packages',
      data
    );
    return response.data;
  },

  /**
   * 更新规则包（仅管理员）
   * @param packageId 规则包ID
   * @param data 更新数据
   */
  updatePackage: async (
    packageId: string,
    data: Partial<RiskRulePackageRequest>
  ): Promise<RiskRulePackage> => {
    const response = await apiClient.put<RiskRulePackage>(
      `/risk-analysis-v2/packages/${packageId}`,
      data
    );
    return response.data;
  },

  /**
   * 删除规则包（仅管理员）
   * @param packageId 规则包ID
   */
  deletePackage: async (packageId: string): Promise<void> => {
    await apiClient.delete(`/risk-analysis-v2/packages/${packageId}`);
  },

  /**
   * 切换规则包启用状态（仅管理员）
   * @param packageId 规则包ID
   * @param isActive 是否启用
   */
  togglePackageStatus: async (
    packageId: string,
    isActive: boolean
  ): Promise<RiskRulePackage> => {
    const response = await apiClient.patch<RiskRulePackage>(
      `/risk-analysis-v2/packages/${packageId}/status`,
      { is_active: isActive }
    );
    return response.data;
  }
};
