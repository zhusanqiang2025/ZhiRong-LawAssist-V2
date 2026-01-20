// frontend/src/hooks/useConsultationSession.ts
/**
 * 智能咨询会话管理Hook
 *
 * 负责管理对话会话的生命周期：
 * - 创建新会话
 * - 继续历史会话
 * - 保存会话到历史
 * - 加载历史列表
 * - 删除会话
 */

import { useState, useCallback } from 'react';
import { message } from 'antd';
import api from '../api';

// ==================== 类型定义 ====================

export interface ConsultationMessage {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'assistant_specialist';
  timestamp: string | Date;
  suggestions?: string[];
  actionButtons?: any[];
  confidence?: number;
  isConfirmation?: boolean;
  suggestedQuestions?: string[];
  directQuestions?: string[];
}

export interface ConsultationSession {
  sessionId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  messages: ConsultationMessage[];
  status: 'active' | 'archived';
  specialistType?: string;
  classification?: any;
}

export interface SessionState {
  currentSession: ConsultationSession | null;
  historySessions: ConsultationSession[];
  isHistorySidebarOpen: boolean;
}

// ==================== Hook ====================

export function useConsultationSession() {
  const [currentSession, setCurrentSession] = useState<ConsultationSession | null>(null);
  const [historySessions, setHistorySessions] = useState<ConsultationSession[]>([]);
  const [isHistorySidebarOpen, setIsHistorySidebarOpen] = useState(false);

  /**
   * 创建新会话
   */
  const createNewSession = useCallback(async () => {
    try {
      const response = await api.post('/consultation/new-session');

      if (response.data && response.data.session_id) {
        const newSession: ConsultationSession = {
          sessionId: response.data.session_id,
          title: '新对话',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messageCount: 0,
          messages: [],
          status: 'active'
        };

        setCurrentSession(newSession);

        // 保存到sessionStorage
        sessionStorage.setItem('consultation_session_id', response.data.session_id);
        sessionStorage.removeItem('consultation_session_temp'); // 清除临时会话

        console.log('[会话管理] 创建新会话:', response.data.session_id);

        return newSession;
      } else {
        throw new Error('创建会话失败：无session_id');
      }
    } catch (error: any) {
      console.error('[会话管理] 创建新会话失败:', error);
      message.error('创建新会话失败');
      return null;
    }
  }, []);

  /**
   * 继续历史会话
   */
  const continueSession = useCallback(async (sessionId: string) => {
    try {
      const response = await api.post(`/consultation/history/${sessionId}/continue`);

      if (response.data && response.data.success && response.data.session) {
        const session = response.data.session;

        // 转换消息格式
        const messages: ConsultationMessage[] = (session.messages || []).map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp)
        }));

        const continuedSession: ConsultationSession = {
          sessionId: session.session_id,
          title: session.title,
          createdAt: session.created_at,
          updatedAt: session.updated_at,
          messageCount: session.message_count || messages.length,
          messages: messages,
          status: 'active',
          specialistType: session.specialist_type,
          classification: session.classification
        };

        setCurrentSession(continuedSession);

        // 保存到sessionStorage
        sessionStorage.setItem('consultation_session_id', session.session_id);

        // 关闭历史侧边栏
        setIsHistorySidebarOpen(false);

        message.success('已加载历史会话');

        console.log('[会话管理] 继续会话:', session.session_id);

        return continuedSession;
      } else {
        throw new Error('加载会话失败');
      }
    } catch (error: any) {
      console.error('[会话管理] 继续会话失败:', error);
      message.error('加载历史会话失败');
      return null;
    }
  }, []);

  /**
   * 保存当前会话到历史
   */
  const saveCurrentSession = useCallback(async (messages: ConsultationMessage[], title?: string) => {
    if (!currentSession || messages.length === 0) {
      console.warn('[会话管理] 无法保存会话：无会话或无消息');
      return false;
    }

    try {
      // 生成标题（使用首条用户消息）
      const sessionTitle = title || messages.find(m => m.role === 'user')?.content?.substring(0, 50) + '...' || '对话记录';

      const payload = {
        session_id: currentSession.sessionId,
        messages: messages,
        title: sessionTitle,
        specialist_type: currentSession.specialistType,
        classification: currentSession.classification
      };

      const response = await api.post('/consultation/save-history', payload);

      if (response.data && response.data.success) {
        console.log('[会话管理] 会话已保存到历史:', currentSession.sessionId);

        // 重新加载历史列表
        await loadHistorySessions();

        return true;
      } else {
        throw new Error('保存失败');
      }
    } catch (error: any) {
      console.error('[会话管理] 保存会话失败:', error);
      // 静默失败，不打扰用户
      return false;
    }
  }, [currentSession]);

  /**
   * 加载历史会话列表
   */
  const loadHistorySessions = useCallback(async () => {
    try {
      const response = await api.get('/consultation/history', {
        params: { limit: 50 }
      });

      if (response.data && response.data.sessions) {
        const sessions: ConsultationSession[] = response.data.sessions.map((s: any) => ({
          sessionId: s.session_id,
          title: s.title,
          createdAt: s.created_at,
          updatedAt: s.updated_at,
          messageCount: s.message_count,
          messages: (s.messages || []).map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          })),
          status: s.status,
          specialistType: s.specialist_type,
          classification: s.classification
        }));

        setHistorySessions(sessions);

        console.log('[会话管理] 加载历史列表:', sessions.length);

        return sessions;
      }
    } catch (error: any) {
      console.error('[会话管理] 加载历史列表失败:', error);
      return [];
    }
  }, []);

  /**
   * 删除会话
   */
  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      const response = await api.delete(`/consultation/history/${sessionId}`);

      if (response.data && response.data.success) {
        // 从列表中移除
        setHistorySessions(prev => prev.filter(s => s.sessionId !== sessionId));

        // 如果删除的是当前会话，清空当前会话
        if (currentSession?.sessionId === sessionId) {
          setCurrentSession(null);
          sessionStorage.removeItem('consultation_session_id');
        }

        message.success('会话已删除');

        console.log('[会话管理] 删除会话:', sessionId);

        return true;
      } else {
        throw new Error('删除失败');
      }
    } catch (error: any) {
      console.error('[会话管理] 删除会话失败:', error);
      message.error('删除会话失败');
      return false;
    }
  }, [currentSession]);

  /**
   * 切换历史侧边栏
   */
  const toggleHistorySidebar = useCallback(() => {
    setIsHistorySidebarOpen(prev => {
      const newState = !prev;

      // 打开时加载历史列表
      if (newState && historySessions.length === 0) {
        loadHistorySessions();
      }

      return newState;
    });
  }, [historySessions.length, loadHistorySessions]);

  /**
   * 初始化：检查是否有现有会话
   */
  const initializeSession = useCallback(async () => {
    const savedSessionId = sessionStorage.getItem('consultation_session_id');

    if (savedSessionId) {
      // 有session_id，设置为当前会话（但不加载消息，让用户自己选择）
      setCurrentSession({
        sessionId: savedSessionId,
        title: '继续对话',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messageCount: 0,
        messages: [],
        status: 'active'
      });

      console.log('[会话管理] 检测到现有会话:', savedSessionId);
    } else {
      // 无session_id，创建新会话
      await createNewSession();
    }

    // 加载历史列表
    await loadHistorySessions();
  }, [createNewSession, loadHistorySessions]);

  return {
    // 状态
    currentSession,
    historySessions,
    isHistorySidebarOpen,

    // 操作方法
    createNewSession,
    continueSession,
    saveCurrentSession,
    loadHistorySessions,
    deleteSession,
    toggleHistorySidebar,
    initializeSession,

    // 辅助属性
    isFollowUp: currentSession?.messageCount > 0
  };
}
