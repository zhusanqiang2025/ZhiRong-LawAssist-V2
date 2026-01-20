// frontend/src/utils/riskAnalysisHistoryManager.ts
/**
 * 风险分析历史记录管理器
 *
 * 功能：
 * - 同步后端会话列表
 * - 本地缓存优化性能
 * - 区分未完成/已完成任务
 * - 未读计数管理
 */

import api from '../api';

export interface RiskAnalysisHistoryItem {
  session_id: string;
  title: string;
  timestamp: number;
  status: 'pending' | 'parsing' | 'analyzing' | 'completed' | 'failed';
  scene_type: string;
  document_count: number;
  is_completed: boolean;  // ✅ 修改：使用 is_completed 替代 is_unread
}

export interface RiskAnalysisHistory {
  session_id: string;
  title: string;
  timestamp: number;
  status: string;
  summary?: string;
  risk_distribution?: object;
  scene_type: string;
  document_count: number;
  is_completed: boolean;  // ✅ 修改：使用 is_completed
}

const STORAGE_PREFIX = 'risk_analysis_history_';
const STORAGE_INDEX_KEY = 'risk_analysis_history_index';
const STORAGE_UNREAD_KEY = 'risk_analysis_unread_count';
const CACHE_DURATION = 5 * 60 * 1000; // 5分钟缓存

class RiskAnalysisHistoryManager {
  private lastSyncTime = 0;

  /**
   * 同步历史记录列表
   */
  async syncHistoryList(): Promise<RiskAnalysisHistoryItem[]> {
    try {
      // 检查缓存
      const now = Date.now();
      if (now - this.lastSyncTime < CACHE_DURATION) {
        const cached = this.getFromCache();
        if (cached && cached.length > 0) return cached;
      }

      // 从后端获取
      const response = await api.get('/risk-analysis-v2/sessions');
      const sessions: RiskAnalysisHistoryItem[] = response.data.sessions.map((s: any) => ({
        session_id: s.session_id,
        title: s.title,
        timestamp: new Date(s.created_at).getTime(),
        status: s.status,
        scene_type: s.scene_type,
        document_count: s.document_count,
        is_completed: s.is_completed  // ✅ 使用后端返回的 is_completed
      }));

      // 保存到缓存
      this.saveToCache(sessions);

      // ✅ 使用新的统计字段
      this.updateIncompleteCount(response.data.incomplete_count);
      this.lastSyncTime = now;

      return sessions;
    } catch (error) {
      console.error('[历史记录管理器] 同步失败:', error);
      // 降级到缓存
      return this.getFromCache() || [];
    }
  }

  /**
   * 获取未完成任务列表
   */
  async getIncompleteTasks(): Promise<RiskAnalysisHistoryItem[]> {
    const all = await this.syncHistoryList();
    return all.filter(item =>
      item.status === 'pending' ||
      item.status === 'parsing' ||
      item.status === 'analyzing'
    );
  }

  /**
   * 获取已完成任务列表
   */
  async getCompletedTasks(): Promise<RiskAnalysisHistoryItem[]> {
    const all = await this.syncHistoryList();
    return all.filter(item =>
      item.status === 'completed' ||
      item.status === 'failed'
    );
  }

  /**
   * 获取未完成任务数量
   */
  getIncompleteCount(): number {
    try {
      const count = localStorage.getItem(STORAGE_UNREAD_KEY);
      return count ? parseInt(count, 10) : 0;
    } catch {
      return 0;
    }
  }

  /**
   * 加载历史会话详情
   */
  async loadSession(sessionId: string): Promise<RiskAnalysisHistory | null> {
    try {
      const response = await api.get(`/risk-analysis-v2/result/${sessionId}`);

      // ✅ 标记为已完成（替代已读）
      await this.markAsCompleted(sessionId);

      return {
        session_id: response.data.session_id,
        title: response.data.title || '风险评估',
        timestamp: new Date(response.data.created_at).getTime(),
        status: response.data.status,
        summary: response.data.summary,
        risk_distribution: response.data.risk_distribution,
        scene_type: response.data.scene_type,
        document_count: response.data.document_count || 0,
        is_completed: response.data.status === 'completed'
      };
    } catch (error) {
      console.error('[历史记录管理器] 加载会话失败:', error);
      return null;
    }
  }

  /**
   * 删除会话
   */
  async deleteSession(sessionId: string): Promise<boolean> {
    try {
      console.log('[历史记录管理器] 开始删除会话:', sessionId);
      const response = await api.delete(`/risk-analysis-v2/sessions/${sessionId}`);
      console.log('[历史记录管理器] 删除会话响应:', response.data);

      // 从缓存中移除
      this.removeFromCache(sessionId);

      console.log('[历史记录管理器] 会话删除成功:', sessionId);
      return true;
    } catch (error: any) {
      console.error('[历史记录管理器] 删除会话失败:', error);
      console.error('[历史记录管理器] 错误详情:', {
        status: error.response?.status,
        data: error.response?.data,
        message: error.message
      });
      return false;
    }
  }

  /**
   * 保存当前会话状态
   */
  async saveCurrentSession(
    sessionId: string,
    title: string,
    status: string
  ): Promise<void> {
    try {
      await api.patch(`/risk-analysis-v2/sessions/${sessionId}/status`, {
        status,
        title
      });

      // 更新缓存
      this.updateCacheItem(sessionId, { status, title });
    } catch (error) {
      console.error('[历史记录管理器] 保存会话失败:', error);
    }
  }

  /**
   * 格式化时间戳
   */
  formatTimestamp(timestamp: number): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return `今天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    } else if (diffDays === 1) {
      return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    } else if (diffDays < 7) {
      const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
      return `${weekdays[date.getDay()]} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    } else {
      return `${date.getMonth() + 1}月${date.getDate()}日`;
    }
  }

  // 私有方法
  private saveToCache(items: RiskAnalysisHistoryItem[]): void {
    try {
      const index = items.map(item => item.session_id);
      localStorage.setItem(STORAGE_INDEX_KEY, JSON.stringify(index));

      items.forEach(item => {
        localStorage.setItem(
          `${STORAGE_PREFIX}${item.session_id}`,
          JSON.stringify(item)
        );
      });
    } catch (error) {
      console.error('[历史记录管理器] 保存缓存失败:', error);
    }
  }

  private getFromCache(): RiskAnalysisHistoryItem[] | null {
    try {
      const indexData = localStorage.getItem(STORAGE_INDEX_KEY);
      if (!indexData) return null;

      const index: string[] = JSON.parse(indexData);
      const items: RiskAnalysisHistoryItem[] = [];

      for (const sessionId of index) {
        const data = localStorage.getItem(`${STORAGE_PREFIX}${sessionId}`);
        if (data) {
          items.push(JSON.parse(data));
        }
      }

      return items;
    } catch {
      return null;
    }
  }

  private updateCacheItem(sessionId: string, updates: Partial<RiskAnalysisHistoryItem>): void {
    try {
      const data = localStorage.getItem(`${STORAGE_PREFIX}${sessionId}`);
      if (data) {
        const item = JSON.parse(data);
        const updated = { ...item, ...updates };
        localStorage.setItem(`${STORAGE_PREFIX}${sessionId}`, JSON.stringify(updated));
      }
    } catch (error) {
      console.error('[历史记录管理器] 更新缓存失败:', error);
    }
  }

  private removeFromCache(sessionId: string): void {
    try {
      localStorage.removeItem(`${STORAGE_PREFIX}${sessionId}`);

      const indexData = localStorage.getItem(STORAGE_INDEX_KEY);
      if (indexData) {
        const index: string[] = JSON.parse(indexData);
        const newIndex = index.filter(id => id !== sessionId);
        localStorage.setItem(STORAGE_INDEX_KEY, JSON.stringify(newIndex));
      }
    } catch (error) {
      console.error('[历史记录管理器] 移除缓存失败:', error);
    }
  }

  private updateIncompleteCount(count: number): void {
    try {
      localStorage.setItem(STORAGE_UNREAD_KEY, count.toString());
    } catch (error) {
      console.error('[历史记录管理器] 更新未完成任务计数失败:', error);
    }
  }

  private async markAsCompleted(sessionId: string): Promise<void> {
    try {
      // 标记为已读（保留向后兼容）
      await api.patch(`/risk-analysis-v2/sessions/${sessionId}/status`, {
        is_unread: false
      });

      // 更新本地缓存
      this.updateCacheItem(sessionId, { is_completed: true });

      // 减少未完成任务计数
      const currentCount = this.getIncompleteCount();
      if (currentCount > 0) {
        this.updateIncompleteCount(currentCount - 1);
      }
    } catch (error) {
      console.error('[历史记录管理器] 标记已完成失败:', error);
    }
  }
}

export const riskAnalysisHistoryManager = new RiskAnalysisHistoryManager();
