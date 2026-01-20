// frontend/src/api/knowledgeBase.ts
/**
 * 知识库管理 API
 */

import api from './index';

// ==================== 类型定义 ====================

export interface KnowledgeSource {
  id: string;
  name: string;
  type: 'local' | 'feishu' | 'confluence' | 'notion';
  enabled: boolean;
  priority: number;
  status: 'connected' | 'disconnected' | 'error';
  last_sync?: string;
}

export interface FeishuConfig {
  app_id: string;
  app_secret: string;
  wiki_space_id: string;
  enabled: boolean;
}

export interface SearchRequest {
  query: string;
  domain?: string;
  limit?: number;
  enabled_stores?: string[];
}

export interface KnowledgeItem {
  id: string;
  title: string;
  content: string;
  source: string;
  source_store: string;
  url?: string;
  metadata?: Record<string, any>;
  relevance_score: number;
  created_at?: string;
  updated_at?: string;
}

export interface SearchResult {
  query: string;
  items: KnowledgeItem[];
  total: number;
  search_intent?: {
    original_query: string;
    optimized_query: string;
    target_domains: string[];
  };
}

export interface ModulePreferences {
  module_name: string;
  knowledge_base_enabled: boolean;
  enabled_stores?: string[];
  updated_at?: string;
}

export interface HealthInfo {
  total_stores: number;
  available_stores: number;
  stores: Array<{
    name: string;
    available: boolean;
    priority: number;
  }>;
}

export interface CheckDuplicateRequest {
  title: string;
  content: string;
  category?: string;
}

export interface CheckDuplicateResponse {
  success: boolean;
  data: {
    is_duplicate: boolean;
    similarity: number;
    original_item?: {
      id: string;
      title: string;
      content: string;
      source: string;
    };
    recommendation: string;
    action: 'allow' | 'warn' | 'block';
  };
}

export interface UserDocumentsParams {
  page?: number;
  size?: number;
  search?: string;
  status?: string;
}

export interface UploadUserDocumentRequest {
  file: File;
  title?: string;
  content?: string;
  category?: string;
  tags?: string[];
  is_public?: boolean;
}

export interface UpdateUserDocumentRequest {
  title?: string;
  content?: string;
  category?: string;
  tags?: string[];
  is_public?: boolean;
  status?: string;
}

// ==================== API ====================

export const knowledgeBaseApi = {
  /**
   * 获取知识源列表
   */
  getKnowledgeSources: () =>
    api.get('/knowledge-base/sources'),

  /**
   * 配置飞书知识源
   */
  configureFeishuSource: (config: FeishuConfig) =>
    api.post('/knowledge-base/sources/feishu/config', config),

  /**
   * 切换知识源启用状态
   */
  toggleKnowledgeSource: (sourceId: string, enabled: boolean) =>
    api.post(`/knowledge-base/sources/${sourceId}/toggle`, { enabled }),

  /**
   * 搜索知识库
   */
  search: (request: SearchRequest) =>
    api.post('/knowledge-base/search', request),

  /**
   * 获取模块偏好设置
   */
  getModulePreferences: (moduleName: string) =>
    api.get(`/knowledge-base/modules/${moduleName}/preferences`),

  /**
   * 保存模块偏好设置
   */
  saveModulePreferences: (moduleName: string, preferences: ModulePreferences) =>
    api.post(`/knowledge-base/modules/${moduleName}/preferences`, preferences),

  /**
   * 健康检查
   */
  healthCheck: () =>
    api.get('/knowledge-base/health'),

  /**
   * 检测上传内容是否重复
   */
  checkDuplicate: (request: CheckDuplicateRequest) =>
    api.post('/knowledge-base/check-duplicate', request),

  /**
   * 获取用户知识库文档列表
   */
  getUserDocuments: (params?: UserDocumentsParams) =>
    api.get('/knowledge-base/user/documents', { params }),

  /**
   * 上传用户文档
   */
  uploadUserDocument: (formData: FormData) =>
    api.post('/knowledge-base/user/documents', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }),

  /**
   * 更新用户文档
   */
  updateUserDocument: (docId: string, request: UpdateUserDocumentRequest) =>
    api.put(`/knowledge-base/user/documents/${docId}`, request),

  /**
   * 删除用户文档
   */
  deleteUserDocument: (docId: string) =>
    api.delete(`/knowledge-base/user/documents/${docId}`),

  /**
   * 获取用户文档详情
   */
  getUserDocumentDetail: (docId: string) =>
    api.get(`/knowledge-base/user/documents/${docId}`),
};

export default knowledgeBaseApi;
