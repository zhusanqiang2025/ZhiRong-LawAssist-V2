// frontend/src/utils/litigationAnalysisHistoryManager.ts
/**
 * 案件分析历史记录管理器
 *
 * 功能：
 * - 同步后端会话列表
 * - 本地缓存优化性能
 * - 区分未完成/已完成任务
 * - 删除任务管理
 */

import api from '../api';

export interface LitigationHistoryItem {
  session_id: string;
  title: string;
  timestamp: number;
  status: 'pending' | 'processing' | 'started' | 'completed' | 'failed' | 'cancelled';
  case_type: string;
  case_position: string;
  is_completed: boolean;
}

const STORAGE_PREFIX = 'litigation_analysis_history_';
const STORAGE_INDEX_KEY = 'litigation_analysis_history_index';
const STORAGE_INCOMPLETE_KEY = 'litigation_analysis_incomplete_count';
const CACHE_DURATION = 5 * 60 * 1000; // 5分钟缓存

class LitigationAnalysisHistoryManager {
  private lastSyncTime = 0;

  /**
   * 同步历史记录列表
   */
  async syncHistoryList(): Promise<LitigationHistoryItem[]> {
    try {
      // 检查缓存
      const now = Date.now();
      if (now - this.lastSyncTime < CACHE_DURATION) {
        const cached = this.getFromCache();
        if (cached && cached.length > 0) return cached;
      }

      // 从后端获取 - 使用统一的任务接口
      const response = await api.get('/api/v1/tasks', {
        params: { status: 'pending,processing,completed' }
      });

      // 过滤出案件分析的任务
      const litigationTasks = response.data.filter(
        (item: any) => item.source === 'litigation_analysis'
      );

      const sessions: LitigationHistoryItem[] = litigationTasks.map((s: any) => ({
        session_id: s.id,
        title: s.title || '案件分析',
        timestamp: new Date(s.created_at).getTime(),
        status: s.status,
        case_type: s.case_type || '未知',
        case_position: s.case_position || '未知',
        is_completed: s.status === 'completed'
      }));

      // 保存到缓存
      this.saveToCache(sessions);

      // 更新未完成计数
      const incompleteCount = sessions.filter(item =>
        item.status === 'pending' ||
        item.status === 'processing' ||
        item.status === 'started'
      ).length;
      this.updateIncompleteCount(incompleteCount);

      this.lastSyncTime = now;

      return sessions;
    } catch (error) {
      console.error('[案件分析历史记录管理器] 同步失败:', error);
      // 降级到缓存
      return this.getFromCache() || [];
    }
  }

  /**
   * 获取未完成任务列表
   */
  async getIncompleteTasks(): Promise<LitigationHistoryItem[]> {
    const all = await this.syncHistoryList();
    return all.filter(item =>
      item.status === 'pending' ||
      item.status === 'processing' ||
      item.status === 'started'
    );
  }

  /**
   * 获取已完成任务列表
   */
  async getCompletedTasks(): Promise<LitigationHistoryItem[]> {
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
      const count = localStorage.getItem(STORAGE_INCOMPLETE_KEY);
      return count ? parseInt(count, 10) : 0;
    } catch {
      return 0;
    }
  }

  /**
   * 加载历史会话详情
   */
  async loadSession(sessionId: string): Promise<any> {
    try {
      const response = await api.get(`/api/v1/litigation-analysis/result/${sessionId}`);

      // 标记为已完成
      await this.markAsCompleted(sessionId);

      return response.data;
    } catch (error) {
      console.error('[案件分析历史记录管理器] 加载会话失败:', error);
      return null;
    }
  }

  /**
   * 删除会话
   */
  async deleteSession(sessionId: string): Promise<boolean> {
    try {
      console.log('[案件分析历史记录管理器] 开始删除会话:', sessionId);
      const response = await api.delete(`/api/v1/litigation-analysis/sessions/${sessionId}`);
      console.log('[案件分析历史记录管理器] 删除会话响应:', response.data);

      // 从缓存中移除
      this.removeFromCache(sessionId);

      console.log('[案件分析历史记录管理器] 会话删除成功:', sessionId);
      return true;
    } catch (error: any) {
      console.error('[案件分析历史记录管理器] 删除会话失败:', error);
      console.error('[案件分析历史记录管理器] 错误详情:', {
        status: error.response?.status,
        data: error.response?.data,
        message: error.message
      });
      return false;
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
  private saveToCache(items: LitigationHistoryItem[]): void {
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
      console.error('[案件分析历史记录管理器] 保存缓存失败:', error);
    }
  }

  private getFromCache(): LitigationHistoryItem[] | null {
    try {
      const indexData = localStorage.getItem(STORAGE_INDEX_KEY);
      if (!indexData) return null;

      const index: string[] = JSON.parse(indexData);
      const items: LitigationHistoryItem[] = [];

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

  private updateCacheItem(sessionId: string, updates: Partial<LitigationHistoryItem>): void {
    try {
      const data = localStorage.getItem(`${STORAGE_PREFIX}${sessionId}`);
      if (data) {
        const item = JSON.parse(data);
        const updated = { ...item, ...updates };
        localStorage.setItem(`${STORAGE_PREFIX}${sessionId}`, JSON.stringify(updated));
      }
    } catch (error) {
      console.error('[案件分析历史记录管理器] 更新缓存失败:', error);
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
      console.error('[案件分析历史记录管理器] 移除缓存失败:', error);
    }
  }

  private updateIncompleteCount(count: number): void {
    try {
      localStorage.setItem(STORAGE_INCOMPLETE_KEY, count.toString());
    } catch (error) {
      console.error('[案件分析历史记录管理器] 更新未完成任务计数失败:', error);
    }
  }

  private async markAsCompleted(sessionId: string): Promise<void> {
    try {
      // 更新本地缓存
      this.updateCacheItem(sessionId, { is_completed: true });

      // 减少未完成任务计数
      const currentCount = this.getIncompleteCount();
      if (currentCount > 0) {
        this.updateIncompleteCount(currentCount - 1);
      }
    } catch (error) {
      console.error('[案件分析历史记录管理器] 标记已完成失败:', error);
    }
  }
}

export const litigationAnalysisHistoryManager = new LitigationAnalysisHistoryManager();
