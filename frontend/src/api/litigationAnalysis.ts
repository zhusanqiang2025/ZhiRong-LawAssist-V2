// frontend/src/api/litigationAnalysis.ts
/**
 * 案件分析模块 API 客户端
 */

import { axiosInstance } from './index';
import type {
  LitigationAnalysisSession,
  LitigationAnalysisResult,
  LitigationAnalysisRequest,
  LitigationCasePackage,
  LitigationPreorganizationResult,
  Stage2AnalysisResult,
  GenerateDraftsResult
} from '../types/litigationAnalysis';

const BASE_URL = '/litigation-analysis';

// ==================== 案件类型包管理 ====================

/**
 * 获取案件类型包列表
 */
export const listCasePackages = async (params?: {
  case_type?: string;
  category?: string;
  is_active?: boolean;
}) => {
  const response = await axiosInstance.get(`${BASE_URL}/packages`, { params });
  return response.data;
};

/**
 * 获取案件类型包详情
 */
export const getCasePackage = async (packageId: string) => {
  const response = await axiosInstance.get<LitigationCasePackage>(
    `${BASE_URL}/packages/${packageId}`
  );
  return response.data;
};

/**
 * 创建案件类型包
 */
export const createCasePackage = async (data: any) => {
  const response = await axiosInstance.post(`${BASE_URL}/packages`, data);
  return response.data;
};

/**
 * 更新案件类型包
 */
export const updateCasePackage = async (packageId: string, data: any) => {
  const response = await axiosInstance.put(`${BASE_URL}/packages/${packageId}`, data);
  return response.data;
};

/**
 * 删除案件类型包
 */
export const deleteCasePackage = async (packageId: string) => {
  await axiosInstance.delete(`${BASE_URL}/packages/${packageId}`);
};

// ==================== 文档上传 ====================

/**
 * 上传案件文档
 */
export const uploadCaseDocuments = async (sessionId: string, files: File[]) => {
  const formData = new FormData();
  formData.append('session_id', sessionId);

  files.forEach(file => {
    formData.append('files', file);
  });

  const response = await axiosInstance.post(`${BASE_URL}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });

  return response.data;
};

// ==================== 分析启动 ====================

/**
 * 启动案件分析
 */
export const startCaseAnalysis = async (request: LitigationAnalysisRequest) => {
  const response = await axiosInstance.post(`${BASE_URL}/start`, request);
  return response.data;
};

// ==================== 状态查询 ====================

/**
 * 获取案件分析状态
 */
export const getCaseStatus = async (sessionId: string) => {
  const response = await axiosInstance.get(`${BASE_URL}/status/${sessionId}`);
  return response.data;
};

/**
 * 获取案件分析结果
 */
export const getCaseResult = async (sessionId: string) => {
  const response = await axiosInstance.get<LitigationAnalysisResult>(
    `${BASE_URL}/result/${sessionId}`
  );
  return response.data;
};

// ==================== 报告下载 ====================

/**
 * 下载预整理报告
 */
export const downloadPreorganizationReport = async (
  sessionId: string,
  format: 'docx' | 'pdf' = 'docx'
) => {
  const response = await axiosInstance.get(
    `${BASE_URL}/preorganization-report/${sessionId}`,
    {
      params: { format },
      responseType: 'blob'
    }
  );

  // 创建下载链接
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `litigation_preorg_${sessionId}.${format}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);

  return response.data;
};

/**
 * 下载案件分析报告
 */
export const downloadAnalysisReport = async (
  sessionId: string,
  format: 'docx' | 'pdf' = 'docx'
) => {
  const response = await axiosInstance.get(
    `${BASE_URL}/report/${sessionId}/download`,
    {
      params: { format },
      responseType: 'blob'
    }
  );

  // 创建下载链接
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `litigation_analysis_${sessionId}.${format}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);

  return response.data;
};

// ==================== 会话管理 ====================

/**
 * 获取用户的案件分析会话列表
 */
export const listCaseSessions = async (params?: {
  skip?: number;
  limit?: number;
}) => {
  const response = await axiosInstance.get(`${BASE_URL}/sessions`, { params });
  return response.data;
};

/**
 * 取消案件分析
 */
export const cancelCaseAnalysis = async (sessionId: string) => {
  const response = await axiosInstance.post(`${BASE_URL}/cancel/${sessionId}`);
  return response.data;
};

// ==================== 3阶段架构：阶段2 - 全案分析 ====================

/**
 * 阶段2：全案分析（不包含文书生成）
 */
export const analyzeLitigationCase = async (params: {
  preorganized_data: LitigationPreorganizationResult;
  case_position: string;
  analysis_scenario: string;
  case_package_id: string;
  case_type?: string;
  user_input?: string;
  analysis_mode?: string;
  selected_model?: string;
}): Promise<Stage2AnalysisResult> => {
  const formData = new FormData();
  formData.append('preorganized_data', JSON.stringify(params.preorganized_data));
  formData.append('case_position', params.case_position);
  formData.append('analysis_scenario', params.analysis_scenario);
  formData.append('case_package_id', params.case_package_id);

  if (params.case_type) formData.append('case_type', params.case_type);
  if (params.user_input) formData.append('user_input', params.user_input);
  if (params.analysis_mode) formData.append('analysis_mode', params.analysis_mode);
  if (params.selected_model) formData.append('selected_model', params.selected_model);

  const response = await axiosInstance.post<Stage2AnalysisResult>(
    `${BASE_URL}/analyze`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' }
    }
  );

  return response.data;
};

// ==================== 3阶段架构：阶段3 - 文书生成 ====================

/**
 * 阶段3：按需生成法律文书
 */
export const generateLitigationDocuments = async (params: {
  session_id: string;
  case_position: string;
  analysis_scenario: string;
  analysis_result?: Stage2AnalysisResult;
}): Promise<GenerateDraftsResult> => {
  const formData = new FormData();
  formData.append('session_id', params.session_id);
  formData.append('case_position', params.case_position);
  formData.append('analysis_scenario', params.analysis_scenario);

  if (params.analysis_result) {
    formData.append('analysis_result', JSON.stringify(params.analysis_result));
  }

  const response = await axiosInstance.post<GenerateDraftsResult>(
    `${BASE_URL}/generate-drafts`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' }
    }
  );

  return response.data;
};

// ==================== 导出统一的 API 对象 ====================

/**
 * 案件分析 API 对象（用于兼容旧的导入方式）
 */
export const caseAnalysisApi = {
  // 案件类型包管理
  listCasePackages,
  getCasePackage,
  createCasePackage,
  updateCasePackage,
  deleteCasePackage,

  // 文档上传
  uploadCaseDocuments,

  // 分析启动
  startCaseAnalysis,

  // 状态查询
  getCaseStatus,
  getCaseResult,

  // 报告下载
  downloadPreorganizationReport,
  downloadAnalysisReport,

  // 会话管理
  listCaseSessions,
  cancelCaseAnalysis,

  // 3阶段架构：阶段2 - 全案分析
  analyzeLitigationCase,

  // 3阶段架构：阶段3 - 文书生成
  generateLitigationDocuments,
};
