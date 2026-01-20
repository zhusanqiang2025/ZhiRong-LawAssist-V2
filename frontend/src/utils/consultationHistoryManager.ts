// frontend/src/utils/consultationHistoryManager.ts
/**
 * 智能咨询历史记录管理器
 *
 * 功能：
 * 1. 保存对话历史到 localStorage
 * 2. 加载历史记录
 * 3. 删除历史记录
 * 4. 获取所有历史记录列表
 *
 * 设计原则：
 * - 完全独立于实时对话状态
 * - 不干扰多轮对话功能
 * - 使用深拷贝避免状态污染
 */

import { Message } from '../pages/LegalConsultationPage';

export interface ConsultationHistory {
  id: string;           // 会话 ID（使用时间戳 + 随机数）
  title: string;        // 会话标题（使用第一个问题）
  timestamp: number;    // 创建时间
  messages: Message[];  // 完整对话记录
  currentExpertType: string;  // 当前专家类型
}

export interface ConsultationHistoryItem {
  id: string;
  title: string;
  timestamp: number;
  messageCount: number;
}

const STORAGE_PREFIX = 'legal_consult_history_';
const STORAGE_INDEX_KEY = 'legal_consult_history_index';

class ConsultationHistoryManager {
  /**
   * 获取所有历史记录列表（不包含完整消息内容）
   */
  getHistoryList(): ConsultationHistoryItem[] {
    try {
      const indexData = localStorage.getItem(STORAGE_INDEX_KEY);
      if (!indexData) return [];

      const index: string[] = JSON.parse(indexData);
      const historyList: ConsultationHistoryItem[] = [];

      for (const id of index) {
        const data = localStorage.getItem(`${STORAGE_PREFIX}${id}`);
        if (data) {
          const history: ConsultationHistory = JSON.parse(data);
          historyList.push({
            id: history.id,
            title: history.title,
            timestamp: history.timestamp,
            messageCount: history.messages.length
          });
        }
      }

      // 按时间倒序排列
      return historyList.sort((a, b) => b.timestamp - a.timestamp);
    } catch (error) {
      console.error('[历史记录管理器] 获取历史列表失败:', error);
      return [];
    }
  }

  /**
   * 保存当前会话到历史记录
   *
   * @param messages - 完整对话记录
   * @param currentExpertType - 当前专家类型
   * @param existingId - 如果是已存在的会话，传入其 ID
   * @returns 会话 ID
   */
  saveConsultation(
    messages: Message[],
    currentExpertType: string,
    existingId?: string
  ): string {
    try {
      // 提取标题（使用第一个用户消息）
      const firstUserMessage = messages.find(m => m.role === 'user');
      const title = firstUserMessage
        ? (firstUserMessage.content.substring(0, 50) + (firstUserMessage.content.length > 50 ? '...' : ''))
        : '智能咨询会话';

      const id = existingId || `${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      const timestamp = Date.now();

      // 创建历史记录
      const history: ConsultationHistory = {
        id,
        title,
        timestamp,
        messages: JSON.parse(JSON.stringify(messages)), // 深拷贝
        currentExpertType
      };

      // 保存到 localStorage
      localStorage.setItem(`${STORAGE_PREFIX}${id}`, JSON.stringify(history));

      // 更新索引
      this.updateIndex(id);

      console.log('[历史记录管理器] 会话已保存:', id, title);
      return id;
    } catch (error) {
      console.error('[历史记录管理器] 保存会话失败:', error);
      return existingId || '';
    }
  }

  /**
   * 加载历史记录
   *
   * @param id - 会话 ID
   * @returns 完整的历史记录，如果不存在则返回 null
   */
  loadConsultation(id: string): ConsultationHistory | null {
    try {
      const data = localStorage.getItem(`${STORAGE_PREFIX}${id}`);
      if (!data) {
        console.warn('[历史记录管理器] 会话不存在:', id);
        return null;
      }

      const history: ConsultationHistory = JSON.parse(data);
      console.log('[历史记录管理器] 会话已加载:', id, history.title);
      return history;
    } catch (error) {
      console.error('[历史记录管理器] 加载会话失败:', error);
      return null;
    }
  }

  /**
   * 删除历史记录
   *
   * @param id - 会话 ID
   */
  deleteConsultation(id: string): boolean {
    try {
      // 删除会话数据
      localStorage.removeItem(`${STORAGE_PREFIX}${id}`);

      // 从索引中移除
      this.removeFromIndex(id);

      console.log('[历史记录管理器] 会话已删除:', id);
      return true;
    } catch (error) {
      console.error('[历史记录管理器] 删除会话失败:', error);
      return false;
    }
  }

  /**
   * 清空所有历史记录
   */
  clearAllHistory(): boolean {
    try {
      const indexData = localStorage.getItem(STORAGE_INDEX_KEY);
      if (!indexData) return true;

      const index: string[] = JSON.parse(indexData);

      // 删除所有会话数据
      for (const id of index) {
        localStorage.removeItem(`${STORAGE_PREFIX}${id}`);
      }

      // 清空索引
      localStorage.removeItem(STORAGE_INDEX_KEY);

      console.log('[历史记录管理器] 所有历史记录已清空');
      return true;
    } catch (error) {
      console.error('[历史记录管理器] 清空历史记录失败:', error);
      return false;
    }
  }

  /**
   * 更新索引
   */
  private updateIndex(id: string): void {
    try {
      const indexData = localStorage.getItem(STORAGE_INDEX_KEY);
      let index: string[] = indexData ? JSON.parse(indexData) : [];

      // 如果 ID 已存在，先移除（避免重复）
      index = index.filter(existingId => existingId !== id);

      // 添加到索引末尾
      index.push(id);

      localStorage.setItem(STORAGE_INDEX_KEY, JSON.stringify(index));
    } catch (error) {
      console.error('[历史记录管理器] 更新索引失败:', error);
    }
  }

  /**
   * 从索引中移除
   */
  private removeFromIndex(id: string): void {
    try {
      const indexData = localStorage.getItem(STORAGE_INDEX_KEY);
      if (!indexData) return;

      let index: string[] = JSON.parse(indexData);
      index = index.filter(existingId => existingId !== id);

      localStorage.setItem(STORAGE_INDEX_KEY, JSON.stringify(index));
    } catch (error) {
      console.error('[历史记录管理器] 从索引移除失败:', error);
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
      // 今天
      return `今天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    } else if (diffDays === 1) {
      // 昨天
      return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    } else if (diffDays < 7) {
      // 本周
      const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
      return `${weekdays[date.getDay()]} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    } else {
      // 更早
      return `${date.getMonth() + 1}月${date.getDate()}日`;
    }
  }
}

// 导出单例
export const consultationHistoryManager = new ConsultationHistoryManager();
