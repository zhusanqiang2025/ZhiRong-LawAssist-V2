import { axiosInstance } from './index';

/**
 * 审查规则接口
 */
export interface ReviewRule {
  id: number;
  name: string;
  description?: string;
  content: string;
  rule_category: 'universal' | 'feature' | 'stance' | 'custom';
  priority: number;
  is_active: boolean;
  is_system: boolean;
  creator_id?: number;
  created_at: string;
  apply_to_category_ids?: number[];
  target_stance?: '甲方' | '乙方' | '中立' | string;
}

/**
 * 创建规则请求
 */
export interface CreateRuleRequest {
  name: string;
  description?: string;
  content: string;
  rule_category: 'universal' | 'feature' | 'stance' | 'custom';
  priority: number;
  is_active: boolean;
  apply_to_category_ids?: number[];
  target_stance?: string;
}

/**
 * 更新规则请求
 */
export interface UpdateRuleRequest {
  name?: string;
  description?: string;
  content?: string;
  rule_category?: string;
  priority?: number;
  is_active?: boolean;
  apply_to_category_ids?: number[];
  target_stance?: string;
}

/**
 * 审查规则 API
 */
export const reviewRulesApi = {
  /**
   * 获取规则列表
   */
  getRules: async (params?: {
    rule_category?: string;
    is_system?: boolean;
    is_active?: boolean;
    page?: number;
    size?: number;
  }) => {
    const response = await axiosInstance.get<{ items: ReviewRule[]; total: number }>('/admin/rules', { params });
    return response.data;
  },

  /**
   * 获取单个规则详情
   */
  getRule: async (ruleId: number) => {
    const response = await axiosInstance.get<ReviewRule>(`/admin/rules/${ruleId}`);
    return response.data;
  },

  /**
   * 创建规则
   */
  createRule: async (data: CreateRuleRequest) => {
    const response = await axiosInstance.post<{ id: number; name: string; message: string }>('/admin/rules', data);
    return response.data;
  },

  /**
   * 更新规则
   */
  updateRule: async (ruleId: number, data: UpdateRuleRequest) => {
    const response = await axiosInstance.put<{ id: number; name: string; message: string }>(`/admin/rules/${ruleId}`, data);
    return response.data;
  },

  /**
   * 删除规则
   */
  deleteRule: async (ruleId: number) => {
    const response = await axiosInstance.delete<{ message: string; deleted_rule_id: number }>(`/admin/rules/${ruleId}`);
    return response.data;
  },

  /**
   * 切换规则状态
   */
  toggleRule: async (ruleId: number) => {
    const response = await axiosInstance.put<{ id: number; is_active: boolean; message: string }>(`/admin/rules/${ruleId}/toggle`);
    return response.data;
  },

  /**
   * 从 JSON 迁移规则到数据库
   */
  migrateFromJson: async () => {
    const response = await axiosInstance.post('/admin/rules/migrate-from-json');
    return response.data;
  }
};

export type { ReviewRule, CreateRuleRequest, UpdateRuleRequest };
