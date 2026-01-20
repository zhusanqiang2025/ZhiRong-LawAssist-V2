// frontend/src/utils/WebSocketManager.ts
/**
 * WebSocket 管理器
 *
 * 提供WebSocket连接管理、自动重连、降级轮询等功能
 * 用于任务进度实时推送
 */
import { getWsBaseUrl } from './apiConfig';

export interface WebSocketMessage {
  type: 'progress' | 'notification' | 'error';
  task_id: string;
  progress?: number;
  current_node?: string;
  message?: string;
  node_progress?: Record<string, any>;
  timestamp?: string;
  notification_type?: 'completed' | 'failed' | 'warning';
  data?: Record<string, any>;
}

export type MessageHandler = (data: WebSocketMessage) => void;

export class TaskWebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000; // 最大30秒
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private pollingInterval: NodeJS.Timeout | null = null;
  private taskId: string = '';
  private isConnected: boolean = false;
  private isPolling: boolean = false;

  /**
   * 连接WebSocket
   *
   * @param taskId 任务ID
   * @param wsUrl WebSocket URL（可选，默认使用配置的地址）
   */
  connect(taskId: string, wsUrl?: string): void {
    this.taskId = taskId;

    // 如果已经连接，先断开
    if (this.ws) {
      this.disconnect();
    }

    // 构建WebSocket URL（使用动态配置）
    const defaultWsUrl = `${getWsBaseUrl()}/tasks/${taskId}/ws`;
    const url = wsUrl || defaultWsUrl;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log(`[WebSocket] Connected for task ${taskId}`);
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;

        // 停止轮询
        this.stopPolling();

        // 触发连接事件
        this.trigger('connected', {
          type: 'progress',
          task_id: taskId,
          message: 'WebSocket connected'
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          this.trigger(data.type, data);
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };

      this.ws.onclose = (event) => {
        console.log(`[WebSocket] Disconnected (code: ${event.code})`);
        this.isConnected = false;
        this.ws = null;

        // 触发断开事件
        this.trigger('disconnected', {
          type: 'progress',
          task_id: taskId,
          message: 'WebSocket disconnected'
        });

        // 尝试重连
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        } else {
          console.warn('[WebSocket] Max reconnect attempts reached, switching to polling');
          this.startPolling();
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        this.trigger('error', {
          type: 'error',
          task_id: taskId,
          message: 'WebSocket error occurred'
        });
      };

    } catch (error) {
      console.error('[WebSocket] Failed to create connection:', error);
      // 降级到轮询
      this.startPolling();
    }
  }

  /**
   * 安排重连
   */
  private scheduleReconnect(): void {
    const delay = this.reconnectDelay;
    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.reconnectAttempts++;
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      this.connect(this.taskId);
    }, delay);
  }

  /**
   * 启动轮询降级
   */
  private startPolling(): void {
    if (this.isPolling) {
      return;
    }

    console.log('[WebSocket] Starting polling fallback');
    this.isPolling = true;

    // 立即执行一次
    this.pollStatus();

    // 每5秒轮询一次
    this.pollingInterval = setInterval(() => {
      this.pollStatus();
    }, 5000);
  }

  /**
   * 停止轮询
   */
  private stopPolling(): void {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    this.isPolling = false;
  }

  /**
   * 轮询任务状态
   */
  private async pollStatus(): Promise<void> {
    try {
      const response = await fetch(`${getWsBaseUrl().replace(/^wss?:/, 'http:')}/tasks/${this.taskId}/status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
        }
      });

      if (response.ok) {
        const data = await response.json();

        // 触发进度事件
        this.trigger('progress', {
          type: 'progress',
          task_id: this.taskId,
          progress: data.progress,
          current_node: data.current_node,
          message: data.current_node || '',
          node_progress: data.node_progress,
          timestamp: new Date().toISOString()
        });

        // 如果任务完成，停止轮询
        if (data.status === 'completed' || data.status === 'failed') {
          this.stopPolling();

          this.trigger(data.status === 'completed' ? 'completed' : 'failed', {
            type: 'notification',
            task_id: this.taskId,
            notification_type: data.status as 'completed' | 'failed',
            message: data.status === 'completed' ? '任务完成' : '任务失败',
            data
          });
        }
      }
    } catch (error) {
      console.error('[WebSocket] Polling failed:', error);
    }
  }

  /**
   * 注册消息处理器
   *
   * @param type 消息类型
   * @param handler 处理函数
   */
  on(type: string, handler: MessageHandler): void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type)!.push(handler);
  }

  /**
   * 移除消息处理器
   *
   * @param type 消息类型
   * @param handler 处理函数
   */
  off(type: string, handler: MessageHandler): void {
    const handlers = this.messageHandlers.get(type);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  /**
   * 触发事件
   *
   * @param type 事件类型
   * @param data 消息数据
   */
  private trigger(type: string, data: WebSocketMessage): void {
    const handlers = this.messageHandlers.get(type);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error(`[WebSocket] Handler error for type "${type}":`, error);
        }
      });
    }
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    this.stopPolling();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;

    // 清除所有处理器
    this.messageHandlers.clear();
  }

  /**
   * 获取连接状态
   */
  getConnectionState(): {
    isConnected: boolean;
    isPolling: boolean;
    reconnectAttempts: number;
  } {
    return {
      isConnected: this.isConnected,
      isPolling: this.isPolling,
      reconnectAttempts: this.reconnectAttempts
    };
  }
}

// 创建全局单例实例（可选）
export const wsManager = new TaskWebSocketManager();

// 导出便捷钩子
export const useTaskWebSocket = (taskId: string) => {
  const manager = new TaskWebSocketManager();
  manager.connect(taskId);
  return manager;
};
