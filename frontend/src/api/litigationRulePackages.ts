// frontend/src/api/litigationRulePackages.ts
import axios from 'axios';
import { getApiBaseUrl } from '../utils/apiConfig';

/**
 * 案件分析规则包接口定义
 */
export interface LitigationRule {
  rule_id: string;
  rule_name: string;
  rule_prompt: string;
  priority: number;
}

export interface LitigationRulePackage {
  id?: number;
  package_id: string;
  package_name: string;
  package_category: string;
  case_type: string;
  description?: string;
  applicable_positions: string[];
  target_documents: string[];
  rules: LitigationRule[];
  is_active: boolean;
  is_system: boolean;
  version: string;
  creator_id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface LitigationRulePackagesResponse {
  packages: LitigationRulePackage[];
}

export interface LitigationRulePackageRequest {
  package_id: string;
  package_name: string;
  package_category: string;
  case_type: string;
  description?: string;
  applicable_positions: string[];
  target_documents: string[];
  rules: LitigationRule[];
  is_active?: boolean;
  version?: string;
}

/**
 * 案件分析分类
 */
export const LITIGATION_PACKAGE_CATEGORIES = [
  { value: 'contract_dispute', label: '合同纠纷' },
  { value: 'litigation', label: '诉讼程序' },
  { value: 'procedural', label: '程序事项' },
  { value: 'evidence', label: '证据相关' },
  { value: 'tort', label: '侵权纠纷' },
  { value: 'property', label: '物权纠纷' },
  { value: 'labor', label: '劳动争议' },
  { value: 'family', label: '婚姻家庭' },
  { value: 'intellectual_property', label: '知识产权' },
  { value: 'corporate', label: '公司纠纷' },
  { value: 'criminal', label: '刑事案件' },
  { value: 'administrative', label: '行政诉讼' },
  { value: 'execution', label: '执行案件' },
  { value: 'bankruptcy', label: '破产清算' },
  { value: 'maritime', label: '海商案件' }
] as const;

/**
 * 案件类型
 */
export const LITIGATION_CASE_TYPES = [
  { value: 'contract_performance', label: '合同履约分析' },
  { value: 'complaint_defense', label: '起诉状分析' },
  { value: 'judgment_appeal', label: '判决分析' },
  { value: 'evidence_preservation', label: '保全申请' },
  { value: 'enforcement', label: '强制执行' },
  { value: 'debt_collection', label: '债务追讨' },
  { value: 'labor_dispute', label: '劳动争议' },
  { value: 'ip_infringement', label: '知识产权侵权' },
  { value: 'marine_accident', label: '海事事故' },
  { value: 'breach_of_trust', label: '背信承诺' },
  { value: 'divorce', label: '离婚纠纷' },
  { value: 'inheritance', label: '继承纠纷' },
  { value: 'real_estate', label: '房产纠纷' },
  { value: 'consumer_rights', label: '消费者权益' },
  { value: 'product_liability', label: '产品责任' },
  { value: 'environmental', label: '环境污染' },
  { value: 'securities', label: '证券欺诈' },
  { value: 'antitrust', label: '反垄断' },
  { value: 'fraud', label: '欺诈行为' }
] as const;

/**
 * 诉讼地位
 */
export const LITIGATION_POSITIONS = [
  { value: 'plaintiff', label: '原告' },
  { value: 'defendant', label: '被告' },
  { value: 'third_party', label: '第三人' },
  { value: 'appellant', label: '上诉人' },
  { value: 'appellee', label: '被上诉人' },
  { value: 'applicant', label: '申请人' },
  { value: 'respondent', label: '被申请人' }
] as const;

/**
 * 目标文档类型
 */
export const TARGET_DOCUMENT_TYPES = [
  { value: 'contract', label: '合同' },
  { value: 'agreement', label: '协议' },
  { value: 'supplementary_agreement', label: '补充协议' },
  { value: 'complaint', label: '起诉状' },
  { value: 'judgment', label: '判决书' },
  { value: 'court_order', label: '裁定书' },
  { value: 'court_record', label: '庭审笔录' },
  { value: 'evidence', label: '证据材料' },
  { value: 'application', label: '申请书' },
  { value: 'court_document', label: '法院文书' },
  { value: 'asset_proof', label: '财产证明' },
  { value: 'asset_info', label: '财产信息' },
  { value: 'other', label: '其他' }
] as const;

// 创建专用的 axios 实例
const apiClient = axios.create({
  baseURL: getApiBaseUrl() + '/api/v1',
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
 * 案件分析规则包管理 API
 */
export const litigationRulePackagesApi = {
  /**
   * 获取规则包列表
   * @param caseType 可选的案件类型过滤器
   * @param category 可选的分类过滤器
   * @param isActive 是否仅显示启用的规则包
   */
  listPackages: async (
    caseType?: string,
    category?: string,
    isActive?: boolean
  ): Promise<LitigationRulePackagesResponse> => {
    const params: Record<string, string | boolean> = {};
    if (caseType) params.case_type = caseType;
    if (category) params.category = category;
    if (isActive !== undefined) params.is_active = isActive;

    const response = await apiClient.get<LitigationRulePackagesResponse>(
      '/litigation-analysis/packages',
      { params }
    );
    return response.data;
  },

  /**
   * 获取规则包详情
   * @param packageId 规则包ID
   */
  getPackageDetail: async (packageId: string): Promise<LitigationRulePackage> => {
    const response = await apiClient.get<LitigationRulePackage>(
      `/litigation-analysis/packages/${packageId}`
    );
    return response.data;
  },

  /**
   * 创建规则包（仅管理员）
   * @param data 规则包数据
   */
  createPackage: async (data: LitigationRulePackageRequest): Promise<LitigationRulePackage> => {
    const response = await apiClient.post<LitigationRulePackage>(
      '/litigation-analysis/packages',
      data
    );
    return response.data;
  },

  /**
   * 更新规则包（仅管理员）
   * @param packageId 规则包ID
   * @param data 规则包数据
   */
  updatePackage: async (
    packageId: string,
    data: Partial<LitigationRulePackageRequest>
  ): Promise<LitigationRulePackage> => {
    const response = await apiClient.put<LitigationRulePackage>(
      `/litigation-analysis/packages/${packageId}`,
      data
    );
    return response.data;
  },

  /**
   * 删除规则包（仅管理员）
   * @param packageId 规则包ID
   */
  deletePackage: async (packageId: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(
      `/litigation-analysis/packages/${packageId}`
    );
    return response.data;
  },

  /**
   * 切换规则包状态（仅管理员）
   * @param packageId 规则包ID
   */
  togglePackageStatus: async (packageId: string): Promise<LitigationRulePackage> => {
    const response = await apiClient.post<LitigationRulePackage>(
      `/litigation-analysis/packages/${packageId}/toggle`
    );
    return response.data;
  }
};
