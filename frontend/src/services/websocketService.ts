// frontend/src/services/websocketService.ts
/**
 * WebSocket 客户端服务 - 用于实时任务进度追踪
 */
import { TaskProgress } from '../types/task';
import { logger } from '../utils/logger';
import { getWsBaseUrl } from '../utils/apiConfig';

export interface TaskProgressMessage {
  type: 'task_status' | 'task_progress' | 'task_completed' | 'task_error' | 'pong' | 'error';
  data?: {
    task_id: string;
    status?: string;
    progress?: number;
    current_node?: string;
    node_progress?: Record<string, any>;
    workflow_steps?: Array<{
      name: string;
      order: number;
      estimated_time: number;
      status: string;
      progress: number;
    }>;
    estimated_time_remaining?: number;
    error_message?: string;
    result?: any;
    completed_at?: string;
    created_at?: string;
    updated_at?: string;
  };
  message?: string;
  timestamp: string;
}

export interface WebSocketCallbacks {
  onProgress?: (progress: TaskProgress) => void;
  onCompleted?: (result: any) => void;
  onError?: (error: string) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
}

export class TaskWebSocketService {
  private static instance: TaskWebSocketService | null = null;
  private ws: WebSocket | null = null;
  private taskId: string | null = null;
  private token: string | null = null;
  private callbacks: WebSocketCallbacks = {};
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // 1秒
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private isConnecting = false;
  private isConnected = false;

  // WebSocket连接URL（使用动态配置）
  private get wsUrl(): string {
    return `${getWsBaseUrl()}/api/v1/tasks/ws`;
  }

  private constructor() {}

  /**
   * 获取单例实例
   */
  public static getInstance(): TaskWebSocketService {
    if (!TaskWebSocketService.instance) {
      TaskWebSocketService.instance = new TaskWebSocketService();
    }
    return TaskWebSocketService.instance;
  }

  /**
   * 连接到WebSocket服务器
   */
  public async connect(taskId: string, token: string, callbacks?: WebSocketCallbacks): Promise<void> {
    // 如果已经连接到同一个任务，先断开
    if (this.isConnected && this.taskId === taskId) {
      logger.websocket('Already connected to the same task');
      return;
    }

    // 断开现有连接
    this.disconnect();

    this.taskId = taskId;
    this.token = token;
    this.callbacks = callbacks || {};

    try {
      await this.connectWithRetry();
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
      if (this.callbacks.onError) {
        this.callbacks.onError('WebSocket连接失败');
      }
    }
  }

  /**
   * 带重试的连接方法
   */
  private async connectWithRetry(): Promise<void> {
    if (this.isConnecting) {
      return;
    }

    this.isConnecting = true;

    while (this.reconnectAttempts < this.maxReconnectAttempts) {
      try {
        await this.createConnection();
        return; // 连接成功，退出重试循环
      } catch (error) {
        this.reconnectAttempts++;
        console.warn(`WebSocket connection attempt ${this.reconnectAttempts} failed:`, error);

        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          // 等待后重试
          await this.delay(this.reconnectDelay * this.reconnectAttempts);
        }
      }
    }

    this.isConnecting = false;
    throw new Error(`Failed to connect after ${this.maxReconnectAttempts} attempts`);
  }

  /**
   * 创建WebSocket连接
   */
  private async createConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        if (!this.taskId || !this.token) {
          throw new Error('Task ID and token are required');
        }

        const wsUrl = `${this.wsUrl}/${this.taskId}?token=${encodeURIComponent(this.token)}`;
        logger.websocket('Connecting to WebSocket:', wsUrl);

        this.ws = new WebSocket(wsUrl);

        // 连接成功
        this.ws.onopen = () => {
          logger.websocket('WebSocket connected successfully');
          this.isConnected = true;
          this.isConnecting = false;
          this.reconnectAttempts = 0;

          // 启动心跳
          this.startHeartbeat();

          if (this.callbacks.onConnected) {
            this.callbacks.onConnected();
          }

          resolve();
        };

        // 接收消息
        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        // 连接关闭
        this.ws.onclose = (event) => {
          logger.websocket('WebSocket disconnected:', { code: event.code, reason: event.reason });
          this.isConnected = false;
          this.isConnecting = false;
          this.stopHeartbeat();

          if (this.callbacks.onDisconnected) {
            this.callbacks.onDisconnected();
          }

          // 如果不是正常关闭，尝试重连
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
              this.connectWithRetry().catch(console.error);
            }, this.reconnectDelay * (this.reconnectAttempts + 1));
          }
        };

        // 连接错误
        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.isConnecting = false;

          if (this.reconnectAttempts === 0) {
            reject(error);
          }
        };

      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  /**
   * 处理WebSocket消息
   */
  private handleMessage(data: string): void {
    try {
      const message: TaskProgressMessage = JSON.parse(data);
      console.log('[WebSocket Service] 收到消息:', message.type, message);

      switch (message.type) {
        case 'task_status':
        case 'task_progress':
          if (message.data && this.callbacks.onProgress) {
            const progress: TaskProgress = {
              taskId: message.data.task_id,
              status: (message.data.current_node || message.data.status || 'processing') as 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled',
              progress: message.data.progress || 0,
              currentNode: message.data.message || message.data.current_node || '', // ✅ 使用 message 字段作为当前节点描述
              nodeProgress: message.data.node_progress || {},
              workflowSteps: (message.data.workflow_steps || []).map((step: any) => ({
                ...step,
                estimatedTime: step.estimated_time
              })),
              estimatedTimeRemaining: message.data.estimated_time_remaining,
              errorMessage: message.data.error_message,
              timestamp: message.timestamp
            };
            this.callbacks.onProgress(progress);
          }
          break;

        case 'task_completed':
          console.log('[WebSocket] 收到 task_completed 消息:', message);
          if (this.callbacks.onCompleted && message.data) {
            console.log('[WebSocket] 调用 onCompleted 回调，result:', message.data.result);
            this.callbacks.onCompleted(message.data.result);
          } else {
            console.error('[WebSocket] onCompleted 回调缺失或 message.data 为空', {
              hasCallback: !!this.callbacks.onCompleted,
              hasData: !!message.data,
              data: message.data
            });
          }
          break;

        case 'task_error':
          if (this.callbacks.onError && message.message) {
            this.callbacks.onError(message.message);
          }
          break;

        case 'pong':
          // 心跳响应，无需特殊处理
          console.debug('Received pong');
          break;

        case 'error':
          if (this.callbacks.onError && message.message) {
            this.callbacks.onError(message.message);
          }
          break;

        default:
          console.warn('Unknown message type:', message.type);
      }

    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  /**
   * 发送消息
   */
  public sendMessage(message: any): void {
    if (this.ws && this.isConnected) {
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
      }
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  /**
   * 发送心跳
   */
  public ping(): void {
    this.sendMessage({ type: 'ping' });
  }

  /**
   * 请求当前状态
   */
  public requestStatus(): void {
    this.sendMessage({ type: 'get_status' });
  }

  /**
   * 启动心跳
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      this.ping();
    }, 30000); // 每30秒发送一次心跳
  }

  /**
   * 停止心跳
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * 断开连接
   */
  public disconnect(): void {
    this.stopHeartbeat();

    if (this.ws) {
      // 正常关闭连接
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.isConnected = false;
    this.isConnecting = false;
    this.taskId = null;
    this.token = null;
    this.callbacks = {};
    this.reconnectAttempts = 0;
  }

  /**
   * 获取连接状态
   */
  public getConnectionStatus(): {
    isConnected: boolean;
    isConnecting: boolean;
    taskId: string | null;
  } {
    return {
      isConnected: this.isConnected,
      isConnecting: this.isConnecting,
      taskId: this.taskId
    };
  }

  /**
   * 延时函数
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * 清理资源
   */
  public destroy(): void {
    this.disconnect();
    TaskWebSocketService.instance = null;
  }
}

// 导出单例实例
export const taskWebSocketService = TaskWebSocketService.getInstance();

// 便捷函数
export const connectToTaskProgress = (
  taskId: string,
  token: string,
  callbacks?: WebSocketCallbacks
): Promise<void> => {
  return taskWebSocketService.connect(taskId, token, callbacks);
};

export const disconnectFromTaskProgress = (): void => {
  taskWebSocketService.disconnect();
};

export const getWebSocketStatus = () => {
  return taskWebSocketService.getConnectionStatus();
};