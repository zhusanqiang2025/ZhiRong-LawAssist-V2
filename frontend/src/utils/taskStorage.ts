// frontend/src/utils/taskStorage.ts
/**
 * 风险评估任务持久化工具
 *
 * 管理任务的 localStorage 存储和恢复
 * 支持多任务的保存、加载、清理
 */

import api from '../api';

export interface TaskStorageData {
  sessionId: string;
  title: string;
  createdAt: string;
  status: string;
}

export interface RiskAnalysisStorage {
  activeSessionIds: string[];      // 进行中的任务 ID 列表
  lastActiveSessionId: string;     // 最后查看的任务 ID
  timestamp: number;               // 保存时间戳
}

const STORAGE_KEY = 'risk_analysis_tasks';
const MAX_ACTIVE_TASKS = 5;        // 最大并发任务数

/**
 * 保存任务列表到 localStorage
 *
 * @param tasks - 任务映射表
 * @param activeSessionId - 当前活动任务 ID
 */
export function saveTasksToStorage(
  tasks: Map<string, any>,
  activeSessionId: string | null = null
): void {
  try {
    // 提取进行中的任务 ID
    const activeSessionIds = Array.from(tasks.entries())
      .filter(([_, task]) => {
        const status = task.status || task.analysisState?.status;
        return status === 'analyzing' || status === 'pending' || status === 'processing';
      })
      .map(([sessionId, _]) => sessionId)
      .slice(0, MAX_ACTIVE_TASKS);  // 最多保存 5 个

    const storage: RiskAnalysisStorage = {
      activeSessionIds,
      lastActiveSessionId: activeSessionId || '',
      timestamp: Date.now()
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(storage));

    console.log(`[TaskStorage] 已保存 ${activeSessionIds.length} 个任务到 localStorage`, storage);
  } catch (error) {
    console.error('[TaskStorage] 保存任务失败:', error);
  }
}

/**
 * 从 localStorage 读取任务列表
 *
 * @returns 存储的任务数据
 */
export function loadTasksFromStorage(): RiskAnalysisStorage | null {
  try {
    const storageJson = localStorage.getItem(STORAGE_KEY);
    if (!storageJson) {
      console.log('[TaskStorage] localStorage 中没有任务数据');
      return null;
    }

    const storage: RiskAnalysisStorage = JSON.parse(storageJson);

    // 检查是否过期（24 小时）
    const EXPIRATION_TIME = 24 * 60 * 60 * 1000;
    if (Date.now() - storage.timestamp > EXPIRATION_TIME) {
      console.log('[TaskStorage] 任务数据已过期，清理');
      clearTasksFromStorage();
      return null;
    }

    console.log('[TaskStorage] 从 localStorage 加载任务:', storage);
    return storage;
  } catch (error) {
    console.error('[TaskStorage] 读取任务失败:', error);
    return null;
  }
}

/**
 * 清除 localStorage 中的任务数据
 */
export function clearTasksFromStorage(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
    console.log('[TaskStorage] 已清除 localStorage 中的任务数据');
  } catch (error) {
    console.error('[TaskStorage] 清除任务失败:', error);
  }
}

/**
 * 添加任务 ID 到存储
 *
 * @param sessionId - 任务 ID
 */
export function addTaskToStorage(sessionId: string): void {
  try {
    const storage = loadTasksFromStorage();
    if (!storage) {
      const newStorage: RiskAnalysisStorage = {
        activeSessionIds: [sessionId],
        lastActiveSessionId: sessionId,
        timestamp: Date.now()
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newStorage));
    } else {
      // 避免重复
      if (!storage.activeSessionIds.includes(sessionId)) {
        storage.activeSessionIds.unshift(sessionId);
        // 限制数量
        if (storage.activeSessionIds.length > MAX_ACTIVE_TASKS) {
          storage.activeSessionIds = storage.activeSessionIds.slice(0, MAX_ACTIVE_TASKS);
        }
      }
      storage.lastActiveSessionId = sessionId;
      storage.timestamp = Date.now();
      localStorage.setItem(STORAGE_KEY, JSON.stringify(storage));
    }

    console.log(`[TaskStorage] 已添加任务: ${sessionId}`);
  } catch (error) {
    console.error('[TaskStorage] 添加任务失败:', error);
  }
}

/**
 * 从存储中移除任务 ID
 *
 * @param sessionId - 任务 ID
 */
export function removeTaskFromStorage(sessionId: string): void {
  try {
    const storage = loadTasksFromStorage();
    if (!storage) return;

    storage.activeSessionIds = storage.activeSessionIds.filter(id => id !== sessionId);

    // 如果移除的是最后活动任务，更新为其他任务
    if (storage.lastActiveSessionId === sessionId) {
      storage.lastActiveSessionId = storage.activeSessionIds[0] || '';
    }

    storage.timestamp = Date.now();

    // 如果没有任务了，清除存储
    if (storage.activeSessionIds.length === 0) {
      clearTasksFromStorage();
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(storage));
    }

    console.log(`[TaskStorage] 已移除任务: ${sessionId}`);
  } catch (error) {
    console.error('[TaskStorage] 移除任务失败:', error);
  }
}

/**
 * 更新最后活动任务
 *
 * @param sessionId - 任务 ID
 */
export function updateLastActiveTask(sessionId: string): void {
  try {
    const storage = loadTasksFromStorage();
    if (!storage) {
      addTaskToStorage(sessionId);
      return;
    }

    storage.lastActiveSessionId = sessionId;
    storage.timestamp = Date.now();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(storage));

    console.log(`[TaskStorage] 已更新最后活动任务: ${sessionId}`);
  } catch (error) {
    console.error('[TaskStorage] 更新最后活动任务失败:', error);
  }
}

/**
 * 从后端恢复任务状态
 *
 * @param sessionId - 任务 ID
 * @returns 任务状态
 */
export async function restoreTaskFromBackend(sessionId: string): Promise<any | null> {
  try {
    const response = await api.get(`/risk-analysis-v2/status/${sessionId}`);
    const taskData = response.data;

    console.log(`[TaskStorage] 从后端恢复任务: ${sessionId}`, taskData);
    return taskData;
  } catch (error: any) {
    console.error(`[TaskStorage] 恢复任务失败: ${sessionId}`, error);

    // 如果任务不存在或已过期，从存储中移除
    if (error.response?.status === 404 || error.response?.status === 400) {
      console.log(`[TaskStorage] 任务不存在或已过期，从存储中移除: ${sessionId}`);
      removeTaskFromStorage(sessionId);
    }

    return null;
  }
}

/**
 * 批量恢复多个任务
 *
 * @param sessionIds - 任务 ID 列表
 * @returns 任务映射表
 */
export async function restoreMultipleTasks(
  sessionIds: string[]
): Promise<Map<string, any>> {
  const tasks = new Map<string, any>();

  const promises = sessionIds.map(async (sessionId) => {
    const taskData = await restoreTaskFromBackend(sessionId);
    if (taskData) {
      tasks.set(sessionId, taskData);
    }
  });

  await Promise.all(promises);

  console.log(`[TaskStorage] 批量恢复任务: ${tasks.size}/${sessionIds.length}`);
  return tasks;
}

/**
 * 检查任务是否过期
 *
 * @param createdAt - 任务创建时间
 * @param maxAge - 最大有效期（毫秒），默认 24 小时
 * @returns 是否过期
 */
export function isTaskExpired(createdAt: string, maxAge: number = 24 * 60 * 60 * 1000): boolean {
  try {
    const createdTime = new Date(createdAt).getTime();
    const now = Date.now();
    return (now - createdTime) > maxAge;
  } catch (error) {
    console.error('[TaskStorage] 检查任务过期失败:', error);
    return true;
  }
}

/**
 * 获取任务相对时间描述
 *
 * @param dateStr - 日期字符串
 * @returns 相对时间描述（如 "10分钟前"）
 */
export function formatRelativeTime(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000 / 60);  // 分钟

    if (diff < 1) return '刚刚';
    if (diff < 60) return `${diff}分钟前`;
    if (diff < 1440) return `${Math.floor(diff / 60)}小时前`;
    if (diff < 43200) return `${Math.floor(diff / 1440)}天前`;

    return date.toLocaleDateString('zh-CN');
  } catch (error) {
    console.error('[TaskStorage] 格式化相对时间失败:', error);
    return '';
  }
}

/**
 * 限制并发任务数
 *
 * @param currentCount - 当前任务数
 * @returns 是否可以创建新任务
 */
export function canCreateNewTask(currentCount: number): boolean {
  return currentCount < MAX_ACTIVE_TASKS;
}

/**
 * 获取最大并发任务数
 *
 * @returns 最大并发任务数
 */
export function getMaxConcurrentTasks(): number {
  return MAX_ACTIVE_TASKS;
}
