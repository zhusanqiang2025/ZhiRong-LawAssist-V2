// frontend/src/hooks/useRiskAnalysisTasks.ts
/**
 * 风险评估多任务管理 Hook
 *
 * 管理多个并发的风险评估任务
 * 支持任务创建、切换、删除、持久化
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { message } from 'antd';
import api from '../api';
import { websocketPool } from '../utils/websocketPool';
import {
  saveTasksToStorage,
  loadTasksFromStorage,
  restoreMultipleTasks,
  updateLastActiveTask,
  removeTaskFromStorage,
  canCreateNewTask,
  getMaxConcurrentTasks
} from '../utils/taskStorage';

// 分析状态类型
export type AnalysisStatus = 'idle' | 'analyzing' | 'completed' | 'failed';

// 节点进度类型
export type NodeProgressStatus = 'pending' | 'processing' | 'completed' | 'failed';

// 分析状态接口
export interface AnalysisState {
  status: AnalysisStatus;
  sessionId: string;
  progress: number;
  message: string;
  nodeProgress: {
    documentPreorganization: NodeProgressStatus;
    multiModelAnalysis: NodeProgressStatus;
    reportGeneration: NodeProgressStatus;
  };
  report?: any;
  comparison?: any;
  diagrams?: any;
  preorganizationData?: any;
  enhancedAnalysisData?: any;
  showPreorganizationConfirm?: boolean;
  createdAt?: string;
  userInput?: string;
}

// 创建任务参数
export interface CreateTaskParams {
  uploadId?: string;
  packageId?: string;
  userInput: string;
}

// Hook 返回值
export interface UseRiskAnalysisTasksResult {
  // 任务数据
  tasks: Map<string, AnalysisState>;
  activeTaskId: string | null;
  isLoading: boolean;

  // 操作方法
  createTask: (params: CreateTaskParams) => Promise<string | null>;
  switchTask: (sessionId: string) => void;
  removeTask: (sessionId: string) => void;
  refreshTaskList: () => Promise<void>;

  // 工具方法
  canCreateNew: () => boolean;
  getInProgressCount: () => number;
  getCompletedCount: () => number;
  getTaskById: (sessionId: string) => AnalysisState | undefined;
}

export function useRiskAnalysisTasks(): UseRiskAnalysisTasksResult {
  const [tasks, setTasks] = useState<Map<string, AnalysisState>>(new Map());
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 使用 ref 跟踪是否已初始化
  const isInitialized = useRef<boolean>(false);

  /**
   * 初始化：恢复已保存的任务
   */
  useEffect(() => {
    if (isInitialized.current) return;

    const initializeTasks = async () => {
      setIsLoading(true);

      try {
        // 从 localStorage 读取任务列表
        const storage = loadTasksFromStorage();

        if (storage && storage.activeSessionIds.length > 0) {
          console.log('[useRiskAnalysisTasks] 恢复任务:', storage.activeSessionIds);

          // 从后端批量恢复任务状态
          const restoredTasks = await restoreMultipleTasks(storage.activeSessionIds);

          if (restoredTasks.size > 0) {
            // 转换为 AnalysisState 格式
            const tasksMap = new Map<string, AnalysisState>();

            restoredTasks.forEach((taskData: any, sessionId: string) => {
              tasksMap.set(sessionId, {
                status: taskData.status || 'pending',
                sessionId: sessionId,
                progress: 0,
                message: '已恢复',
                nodeProgress: {
                  documentPreorganization: 'pending',
                  multiModelAnalysis: 'pending',
                  reportGeneration: 'pending',
                },
                createdAt: taskData.created_at,
                userInput: taskData.user_description,
              });

              // 重新连接 WebSocket
              websocketPool.connect(sessionId, (data) => {
                handleWebSocketMessage(sessionId, data);
              });
            });

            setTasks(tasksMap);

            // 恢复最后活动的任务
            if (storage.lastActiveSessionId && tasksMap.has(storage.lastActiveSessionId)) {
              setActiveTaskId(storage.lastActiveSessionId);
            } else if (tasksMap.size > 0) {
              // 否则选择第一个任务
              const firstTaskId = Array.from(tasksMap.keys())[0];
              setActiveTaskId(firstTaskId);
            }

            message.success(`已恢复 ${restoredTasks.size} 个任务`);
          }
        }

        isInitialized.current = true;
      } catch (error) {
        console.error('[useRiskAnalysisTasks] 初始化失败:', error);
      } finally {
        setIsLoading(false);
      }
    };

    initializeTasks();

    // 清理函数
    return () => {
      websocketPool.disconnectAll();
    };
  }, []);

  /**
   * 处理 WebSocket 消息
   */
  const handleWebSocketMessage = useCallback((sessionId: string, data: any) => {
    console.log(`[useRiskAnalysisTasks] WebSocket 消息: ${sessionId}`, data);

    setTasks(prev => {
      const task = prev.get(sessionId);
      if (!task) return prev;

      const updatedTask = { ...task };

      switch (data.type) {
        case 'progress':
          updatedTask.progress = data.progress;
          updatedTask.message = data.message;
          break;

        case 'node_progress':
          updatedTask.progress = Math.round(data.progress * 100);
          if (updatedTask.nodeProgress) {
            updatedTask.nodeProgress = {
              ...updatedTask.nodeProgress,
              [data.node]: data.status,
            };
          }
          break;

        case 'preorganization_completed':
          updatedTask.preorganizationData = {
            basic: data.preorganized_data || {},
            enhanced: data.enhanced_data || {},
          };
          updatedTask.enhancedAnalysisData = data.enhanced_analysis || null;
          updatedTask.showPreorganizationConfirm = true;
          updatedTask.progress = 33;
          updatedTask.message = '文档预整理完成，请确认信息后继续';
          break;

        case 'complete':
          updatedTask.status = 'completed';
          updatedTask.progress = 100;
          updatedTask.message = '分析已完成';
          updatedTask.nodeProgress = {
            documentPreorganization: 'completed',
            multiModelAnalysis: 'completed',
            reportGeneration: 'completed',
          };
          break;

        case 'error':
          updatedTask.status = 'failed';
          updatedTask.message = data.message || '分析失败';
          break;
      }

      const newTasks = new Map(prev);
      newTasks.set(sessionId, updatedTask);

      // 保存到 localStorage
      saveTasksToStorage(newTasks, activeTaskId);

      return newTasks;
    });
  }, [activeTaskId]);

  /**
   * 创建新任务
   */
  const createTask = useCallback(async (params: CreateTaskParams): Promise<string | null> => {
    // 检查并发限制
    const inProgressCount = getInProgressCount();
    if (!canCreateNewTask(inProgressCount)) {
      message.warning(`已达到最大并发任务数（${getMaxConcurrentTasks()}），请等待现有任务完成`);
      return null;
    }

    try {
      setIsLoading(true);

      // 1. 创建会话
      const createResponse = await api.post('/api/v1/risk-analysis-v2/create-session', {
        upload_id: params.uploadId || undefined,
        package_id: params.packageId || undefined,
        user_input: params.userInput
      });

      const sessionId = createResponse.data.session_id;
      console.log('[useRiskAnalysisTasks] 创建会话:', sessionId);

      // 2. 初始化任务状态
      const newTask: AnalysisState = {
        status: 'pending',
        sessionId: sessionId,
        progress: 0,
        message: '任务已创建',
        nodeProgress: {
          documentPreorganization: 'pending',
          multiModelAnalysis: 'pending',
          reportGeneration: 'pending',
        },
        createdAt: new Date().toISOString(),
        userInput: params.userInput,
      };

      setTasks(prev => {
        const newTasks = new Map(prev);
        newTasks.set(sessionId, newTask);

        // 保存到 localStorage
        saveTasksToStorage(newTasks, sessionId);

        return newTasks;
      });

      // 3. 连接 WebSocket
      websocketPool.connect(sessionId, (data) => {
        handleWebSocketMessage(sessionId, data);
      });

      // 4. 启动分析
      await api.post(`/api/v1/risk-analysis-v2/start/${sessionId}`, {
        stop_after_preorganization: true
      });

      // 5. 更新任务状态
      setTasks(prev => {
        const newTasks = new Map(prev);
        const task = newTasks.get(sessionId);
        if (task) {
          task.status = 'analyzing';
          task.message = '正在分析...';
        }
        return newTasks;
      });

      // 6. 切换到新任务
      setActiveTaskId(sessionId);
      updateLastActiveTask(sessionId);

      message.success('任务已创建，正在后台执行');
      return sessionId;

    } catch (error: any) {
      console.error('[useRiskAnalysisTasks] 创建任务失败:', error);
      message.error(error.response?.data?.detail || '创建任务失败');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [handleWebSocketMessage, getInProgressCount, activeTaskId]);

  /**
   * 切换活动任务
   */
  const switchTask = useCallback((sessionId: string) => {
    console.log('[useRiskAnalysisTasks] 切换任务:', sessionId);

    setActiveTaskId(sessionId);
    updateLastActiveTask(sessionId);

    // 保存到 localStorage
    saveTasksToStorage(tasks, sessionId);
  }, [tasks]);

  /**
   * 删除任务
   */
  const removeTask = useCallback((sessionId: string) => {
    console.log('[useRiskAnalysisTasks] 删除任务:', sessionId);

    // 断开 WebSocket
    websocketPool.disconnect(sessionId);

    // 从状态中移除
    setTasks(prev => {
      const newTasks = new Map(prev);
      newTasks.delete(sessionId);

      // 保存到 localStorage
      saveTasksToStorage(newTasks, activeTaskId);

      return newTasks;
    });

    // 从 localStorage 移除
    removeTaskFromStorage(sessionId);

    // 如果删除的是活动任务，切换到其他任务
    if (activeTaskId === sessionId) {
      const remainingTasks = Array.from(tasks.keys()).filter(id => id !== sessionId);
      if (remainingTasks.length > 0) {
        setActiveTaskId(remainingTasks[0]);
        updateLastActiveTask(remainingTasks[0]);
      } else {
        setActiveTaskId(null);
      }
    }

    message.success('任务已删除');
  }, [activeTaskId, tasks]);

  /**
   * 刷新任务列表
   */
  const refreshTaskList = useCallback(async () => {
    console.log('[useRiskAnalysisTasks] 刷新任务列表');

    try {
      setIsLoading(true);

      // 从后端获取所有任务
      const response = await api.get('/api/v1/tasks?limit=20');
      const backendTasks = response.data;

      // 过滤出风险评估任务
      const riskTasks = backendTasks.filter((task: any) => task.source === 'risk_analysis');

      console.log('[useRiskAnalysisTasks] 获取到任务:', riskTasks.length);

      // 更新任务状态
      const tasksMap = new Map<string, AnalysisState>();

      riskTasks.forEach((task: any) => {
        const existingTask = tasks.get(task.id);
        tasksMap.set(task.id, {
          status: task.status === '进行中' ? 'analyzing' : task.status === '已完成' ? 'completed' : 'failed',
          sessionId: task.id,
          progress: task.progress || 0,
          message: existingTask?.message || '已加载',
          nodeProgress: existingTask?.nodeProgress || {
            documentPreorganization: 'pending',
            multiModelAnalysis: 'pending',
            reportGeneration: 'pending',
          },
          createdAt: task.created_at,
          userInput: existingTask?.userInput,
        });
      });

      setTasks(tasksMap);

    } catch (error: any) {
      console.error('[useRiskAnalysisTasks] 刷新任务列表失败:', error);
      message.error('刷新失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsLoading(false);
    }
  }, [tasks]);

  /**
   * 检查是否可以创建新任务
   */
  const canCreateNewCallback = useCallback((): boolean => {
    return canCreateNewTask(getInProgressCount());
  }, [getInProgressCount]);

  /**
   * 获取进行中的任务数
   */
  const getInProgressCountCallback = useCallback((): number => {
    return Array.from(tasks.values()).filter(
      task => task.status === 'analyzing' || task.status === 'pending'
    ).length;
  }, [tasks]);

  /**
   * 获取已完成的任务数
   */
  const getCompletedCountCallback = useCallback((): number => {
    return Array.from(tasks.values()).filter(
      task => task.status === 'completed'
    ).length;
  }, [tasks]);

  /**
   * 根据 ID 获取任务
   */
  const getTaskByIdCallback = useCallback((sessionId: string): AnalysisState | undefined => {
    return tasks.get(sessionId);
  }, [tasks]);

  return {
    tasks,
    activeTaskId,
    isLoading,

    createTask,
    switchTask,
    removeTask,
    refreshTaskList,

    canCreateNew: canCreateNewCallback,
    getInProgressCount: getInProgressCountCallback,
    getCompletedCount: getCompletedCountCallback,
    getTaskById: getTaskByIdCallback,
  };
}
