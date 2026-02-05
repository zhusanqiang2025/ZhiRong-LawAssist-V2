import { axiosInstance } from './index';

/**
 * 合同审查模块 API
 * 集中管理所有合同审查相关的 API 调用
 *
 * @module contractReviewApi
 */

export interface ContractReviewMetadata {
  contract_name?: string;
  parties?: string | string[];
  amount?: string;
  contract_type?: string;
  core_terms?: string;
  legal_features?: {
    transaction_structures?: string[];
    [key: string]: any;
  };
  [key: string]: any;
}

export interface DeepReviewRequest {
  stance: string;
  updated_metadata?: ContractReviewMetadata;
  enable_custom_rules?: boolean;
  use_langgraph?: boolean;
  use_celery?: boolean;
  transaction_structures?: string;
}

export const contractReviewApi = {
  /**
   * 上传合同文件
   * @param file - 要上传的文件
   * @returns 上传响应
   */
  uploadContract: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return axiosInstance.post('/contract-review/upload', formData);
  },

  /**
   * 查询合同处理状态
   * @param contractId - 合同ID
   * @returns 处理状态信息
   */
  getProcessingStatus: (contractId: number) =>
    axiosInstance.get(`/contract-review/${contractId}/processing-status`),

  /**
   * 获取 OnlyOffice 编辑器配置
   * @param contractId - 合同ID
   * @returns OnlyOffice 配置信息
   */
  getOnlyOfficeConfig: (contractId: number) =>
    axiosInstance.get(`/contract-review/${contractId}/onlyoffice-config`),

  /**
   * 提取合同元数据
   * @param contractId - 合同ID
   * @returns 元数据提取响应
   */
  extractMetadata: (contractId: number) =>
    axiosInstance.post(`/contract-review/${contractId}/extract-metadata`),

  /**
   * 获取审查任务列表
   * @param params - 查询参数
   * @returns 任务列表
   */
  getReviewTasks: (params?: { page?: number; skip?: number; limit?: number; status?: string }) =>
    axiosInstance.get('/contract-review/review-tasks', { params }),

  /**
   * 获取单个审查任务详情
   * @param taskId - 任务ID
   * @returns 任务详情
   */
  getReviewTask: (taskId: string) =>
    axiosInstance.get(`/contract-review/review-tasks/${taskId}`),

  /**
   * 暂停审查任务
   * @param taskId - 任务ID
   * @returns 暂停响应
   */
  pauseTask: (taskId: string) =>
    axiosInstance.put(`/contract-review/review-tasks/${taskId}/pause`),

  /**
   * 恢复审查任务
   * @param taskId - 任务ID
   * @returns 恢复响应
   */
  resumeTask: (taskId: string) =>
    axiosInstance.put(`/contract-review/review-tasks/${taskId}/resume`),

  /**
   * 删除审查任务
   * @param taskId - 任务ID
   * @returns 删除响应
   */
  deleteTask: (taskId: string) =>
    axiosInstance.delete(`/contract-review/review-tasks/${taskId}`),

  /**
   * 获取合同审查结果
   * @param contractId - 合同ID
   * @returns 审查结果
   */
  getReviewResults: (contractId: number) =>
    axiosInstance.get(`/contract-review/${contractId}/review-results`),

  /**
   * 启动深度合同审查
   * @param contractId - 合同ID
   * @param data - 审查请求参数
   * @returns 审查启动响应
   */
  startDeepReview: (contractId: number, data: DeepReviewRequest) =>
    axiosInstance.post(`/contract-review/${contractId}/deep-review`, data),

  /**
   * 应用审查修订
   * @param contractId - 合同ID
   * @param reviewItemIds - 要应用的审查项ID列表
   * @param autoApply - 是否自动应用
   * @returns 应用修订响应
   */
  applyRevisions: (contractId: number, reviewItemIds: number[], autoApply: boolean = false) =>
    axiosInstance.post(`/contract-review/${contractId}/apply-revisions`, {
      review_item_ids: reviewItemIds,
      auto_apply: autoApply
    }),

  /**
   * 获取修订版文档配置
   * @param contractId - 合同ID
   * @returns 修订配置
   */
  getRevisionConfig: (contractId: number) =>
    axiosInstance.get(`/contract-review/${contractId}/revision-config`),

  /**
   * 下载合同文档
   * @param contractId - 合同ID
   * @param docType - 文档类型（原始或修订版）
   * @returns 文档 Blob 数据
   */
  downloadContract: async (contractId: number, docType: 'original' | 'revised') => {
    const endpoint = docType === 'revised'
      ? `/contract-review/${contractId}/download-revised`
      : `/contract-review/${contractId}/download`;
    const response = await axiosInstance.get(endpoint, {
      responseType: 'blob'
    });
    return response.data;
  },

  /**
   * 获取合同健康度评估
   * @param contractId - 合同ID
   * @returns 健康度评估结果
   */
  getHealthAssessment: (contractId: number) =>
    axiosInstance.get(`/contract-review/${contractId}/health-assessment`),

  /**
   * 更新审查项
   * @param itemId - 审查项ID
   * @param data - 更新数据
   * @returns 更新响应
   */
  updateReviewItem: (itemId: number, data: { explanation: string; suggestion: string }) =>
    axiosInstance.put(`/contract-review/review-items/${itemId}`, data),

  /**
   * 上传审查后合同到飞书多维表
   * @param contractId - 合同ID
   * @param feishuRecordId - 飞书多维表记录ID
   * @returns 上传响应
   */
  uploadRevisedToFeishu: (contractId: number, feishuRecordId: string) => {
    const formData = new FormData();
    formData.append('contract_id', contractId.toString());
    formData.append('feishu_record_id', feishuRecordId);
    return axiosInstance.post(`/contract-review/${contractId}/upload-revised-to-feishu`, formData);
  }
};
