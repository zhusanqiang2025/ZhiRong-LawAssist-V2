// frontend/src/types/search.ts
/**
 * 全局搜索相关类型定义
 */

/** 搜索结果项 */
export interface SearchResult {
  /** 结果ID */
  id: string;
  /** 结果类型：module-功能模块, task-历史任务, legal-法律知识 */
  type: 'module' | 'task' | 'legal';
  /** 结果标题 */
  title: string;
  /** 结果描述 */
  description: string;
  /** 分类 */
  category?: string;
  /** 跳转URL */
  url?: string;
}

/** 搜索响应 */
export interface SearchResponse {
  /** 搜索关键词 */
  query: string;
  /** 结果总数 */
  total: number;
  /** 搜索结果列表 */
  results: SearchResult[];
  /** 各类型结果数量统计 */
  facets: {
    module: number;
    task: number;
    legal: number;
  };
}

/** 搜索请求参数 */
export interface SearchParams {
  /** 搜索关键词 */
  query: string;
  /** 结果类型过滤（逗号分隔：module,task,legal） */
  types?: string;
}
