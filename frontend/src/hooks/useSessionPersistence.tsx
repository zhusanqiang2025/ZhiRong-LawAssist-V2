// frontend/src/hooks/useSessionPersistence.ts
/**
 * 通用会话持久化 Hook
 *
 * 用于管理需要跨页面刷新保持的任务状态和会话数据
 *
 * @example
 * ```typescript
 * const {
 *   sessionId,
 *   sessionData,
 *   saveSession,
 *   restoreSession,
 *   clearSession,
 *   hasSession
 * } = useSessionPersistence('my_module_session_id');
 *
 * // 保存会话
 * saveSession('abc123', { input: 'test', status: 'processing' });
 *
 * // 恢复会话
 * const restored = restoreSession();
 * if (restored) {
 *   console.log('Restored session:', restored.sessionId, restored.data);
 * }
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { message } from 'antd';

export interface SessionPersistenceOptions<T = any> {
  /**
   * 是否在组件挂载时自动恢复会话
   * @default true
   */
  autoRestore?: boolean;

  /**
   * 会话恢复时的回调函数
   */
  onRestore?: (sessionId: string, data: T) => void;

  /**
   * 会话过期时间（毫秒）
   * @default 24 * 60 * 60 * 1000 (24小时)
   */
  expirationTime?: number;

  /**
   * 是否显示恢复提示消息
   * @default true
   */
  showMessage?: boolean;
}

export interface StoredSession<T = any> {
  sessionId: string;
  data: T;
  timestamp: number;
}

/**
 * 通用会话持久化 Hook
 *
 * @param storageKey - localStorage/sessionStorage 的键名
 * @param options - 配置选项
 * @returns 会话管理方法和状态
 */
export function useSessionPersistence<T = any>(
  storageKey: string,
  options: SessionPersistenceOptions<T> = {}
) {
  const {
    autoRestore = true,
    onRestore,
    expirationTime = 24 * 60 * 60 * 1000, // 默认24小时
    showMessage = true
  } = options;

  const [sessionId, setSessionId] = useState<string>('');
  const [sessionData, setSessionData] = useState<T | null>(null);
  const [hasSession, setHasSession] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 使用 ref 存储 onRestore 回调，避免依赖变化导致无限循环
  const onRestoreRef = useRef(onRestore);
  useEffect(() => {
    onRestoreRef.current = onRestore;
  }, [onRestore]);

  /**
   * 从存储中获取会话数据
   */
  const getStoredSession = useCallback((): StoredSession<T> | null => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (!stored) {
        return null;
      }

      const session: StoredSession<T> = JSON.parse(stored);

      // 检查是否过期
      const now = Date.now();
      if (now - session.timestamp > expirationTime) {
        console.log(`[useSessionPersistence] 会话已过期，清理: ${storageKey}`);
        clearSession();
        return null;
      }

      return session;
    } catch (error) {
      console.error('[useSessionPersistence] 读取会话失败:', error);
      return null;
    }
  }, [storageKey, expirationTime]);

  /**
   * 保存会话到存储
   */
  const saveSession = useCallback((id: string, data: T) => {
    try {
      const session: StoredSession<T> = {
        sessionId: id,
        data,
        timestamp: Date.now()
      };

      localStorage.setItem(storageKey, JSON.stringify(session));
      setSessionId(id);
      setSessionData(data);
      setHasSession(true);

      console.log(`[useSessionPersistence] 会话已保存: ${storageKey}`, session);
    } catch (error) {
      console.error('[useSessionPersistence] 保存会话失败:', error);
      if (showMessage) {
        message.error('保存会话失败');
      }
    }
  }, [storageKey, showMessage]);

  /**
   * 更新当前会话数据
   */
  const updateSessionData = useCallback((data: Partial<T>) => {
    if (!sessionId) {
      console.warn('[useSessionPersistence] 没有活动会话，无法更新数据');
      return;
    }

    const updatedData = { ...sessionData, ...data } as T;
    saveSession(sessionId, updatedData);
  }, [sessionId, sessionData, saveSession]);

  /**
   * 恢复会话
   */
  const restoreSession = useCallback((): { sessionId: string; data: T } | null => {
    const session = getStoredSession();

    if (!session) {
      console.log(`[useSessionPersistence] 没有找到可恢复的会话: ${storageKey}`);
      return null;
    }

    console.log(`[useSessionPersistence] 恢复会话: ${storageKey}`, session);

    setSessionId(session.sessionId);
    setSessionData(session.data);
    setHasSession(true);

    // 触发恢复回调
    if (onRestore) {
      onRestore(session.sessionId, session.data);
    }

    return {
      sessionId: session.sessionId,
      data: session.data
    };
  }, [storageKey, getStoredSession, onRestore]);

  /**
   * 清除会话
   */
  const clearSession = useCallback(() => {
    try {
      localStorage.removeItem(storageKey);
      setSessionId('');
      setSessionData(null);
      setHasSession(false);

      console.log(`[useSessionPersistence] 会话已清除: ${storageKey}`);
    } catch (error) {
      console.error('[useSessionPersistence] 清除会话失败:', error);
    }
  }, [storageKey]);

  /**
   * 检查会话是否存在
   */
  const checkSessionExists = useCallback((): boolean => {
    const session = getStoredSession();
    return session !== null;
  }, [getStoredSession]);

  /**
   * 组件挂载时自动恢复会话
   */
  useEffect(() => {
    if (autoRestore) {
      setIsLoading(true);
      const session = getStoredSession();

      if (session) {
        console.log(`[useSessionPersistence] 自动恢复会话: ${storageKey}`);
        setSessionId(session.sessionId);
        setSessionData(session.data);
        setHasSession(true);

        // 使用 ref 中的回调，避免依赖变化
        if (onRestoreRef.current) {
          onRestoreRef.current(session.sessionId, session.data);
        }
      }

      setIsLoading(false);
    }
    // 只依赖必要的值，不包括函数引用
    // getStoredSession 已经通过 useCallback 固定了依赖 [storageKey, expirationTime]
    // onRestore 通过 ref 存储，不需要在依赖数组中
  }, [autoRestore, storageKey]);

  return {
    // 状态
    sessionId,
    sessionData,
    hasSession,
    isLoading,

    // 方法
    saveSession,
    updateSessionData,
    restoreSession,
    clearSession,
    checkSessionExists,
    getStoredSession
  };
}

/**
 * 会话持久化 Hook 的工厂函数
 * 用于创建特定模块的持久化 Hook
 *
 * @param moduleName - 模块名称
 * @param defaultOptions - 默认配置选项
 * @returns 自定义 Hook
 *
 * @example
 * ```typescript
 * // 创建诉讼分析模块的持久化 Hook
 * const useLitigationAnalysisPersistence = createSessionPersistenceHook('litigation_analysis', {
 *   expirationTime: 60 * 60 * 1000, // 1小时
 *   onRestore: (sessionId, data) => {
 *     console.log('恢复诉讼分析会话:', sessionId);
 *   }
 * });
 *
 * // 在组件中使用
 * const { sessionId, saveSession, clearSession } = useLitigationAnalysisPersistence();
 * ```
 */
export function createSessionPersistenceHook<T = any>(
  moduleName: string,
  defaultOptions: SessionPersistenceOptions<T> = {}
) {
  const storageKey = `${moduleName}_session`;

  return function (options: SessionPersistenceOptions<T> = {}) {
    const mergedOptions = { ...defaultOptions, ...options };
    return useSessionPersistence<T>(storageKey, mergedOptions);
  };
}

/**
 * 通用会话恢复组件
 *
 * 显示会话恢复提示，提供"继续"或"重新开始"选项
 */
export interface SessionRestorePromptProps {
  hasSession: boolean;
  onContinue: () => void;
  onRestart: () => void;
  message?: string;
  moduleName?: string;
}

export function SessionRestorePrompt({
  hasSession,
  onContinue,
  onRestart,
  message = '检测到之前的会话',
  moduleName = '该任务'
}: SessionRestorePromptProps) {
  if (!hasSession) return null;

  return (
    <div
      style={{
        padding: '12px 16px',
        backgroundColor: '#e6f7ff',
        border: '1px solid #91d5ff',
        borderRadius: '4px',
        marginBottom: '16px'
      }}
    >
      <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>
        ℹ️ {message}
      </div>
      <div style={{ fontSize: '14px', color: '#666', marginBottom: '12px' }}>
        系统检测到您之前有一个未完成的{moduleName}。您可以：
      </div>
      <div style={{ display: 'flex', gap: '8px' }}>
        <button
          onClick={onContinue}
          style={{
            padding: '6px 12px',
            backgroundColor: '#1890ff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          继续
        </button>
        <button
          onClick={onRestart}
          style={{
            padding: '6px 12px',
            backgroundColor: '#fff',
            color: '#666',
            border: '1px solid #d9d9d9',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          重新开始
        </button>
      </div>
    </div>
  );
}
