// frontend/src/utils/websocketPool.ts
/**
 * WebSocket 连接池
 *
 * 管理多个并发的 WebSocket 连接，支持心跳机制和自动重连
 * 用于风险评估模块的多任务支持
 */

export interface WebSocketMessageHandler {
  (data: any): void;
}

export interface WebSocketPoolConfig {
  heartbeatInterval?: number;  // 心跳间隔（毫秒）
  reconnectAttempts?: number;  // 重连尝试次数
  reconnectDelay?: number;     // 重连延迟（毫秒）
}

class WebSocketConnectionPool {
  private connections: Map<string, WebSocket> = new Map();
  private heartbeatIntervals: Map<string, NodeJS.Timeout> = new Map();
  private messageHandlers: Map<string, WebSocketMessageHandler> = new Map();
  private reconnectTimers: Map<string, NodeJS.Timeout> = new Map();
  private reconnectAttempts: Map<string, number> = new Map();

  private config: Required<WebSocketPoolConfig>;

  constructor(config: WebSocketPoolConfig = {}) {
    this.config = {
      heartbeatInterval: config.heartbeatInterval || 10000,  // 默认 10 秒
      reconnectAttempts: config.reconnectAttempts || 3,       // 默认 3 次
      reconnectDelay: config.reconnectDelay || 2000,          // 默认 2 秒
    };
  }

  /**
   * 为指定会话建立 WebSocket 连接
   *
   * @param sessionId - 会话 ID
   * @param onMessage - 消息处理回调
   * @param wsUrl - WebSocket URL（可选，默认自动生成）
   */
  connect(sessionId: string, onMessage: WebSocketMessageHandler, wsUrl?: string): void {
    // 如果已存在连接，先断开
    if (this.connections.has(sessionId)) {
      console.log(`[WebSocketPool] 连接已存在，先断开: ${sessionId}`);
      this.disconnect(sessionId);
    }

    // 生成 WebSocket URL
    const url = wsUrl || this.generateWebSocketUrl(sessionId);

    console.log(`[WebSocketPool] 正在连接: ${sessionId} -> ${url}`);

    try {
      const ws = new WebSocket(url);

      // 连接打开
      ws.onopen = () => {
        console.log(`[WebSocketPool] 连接已建立: ${sessionId}`);

        // 启动心跳
        const heartbeatInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, this.config.heartbeatInterval);

        this.heartbeatIntervals.set(sessionId, heartbeatInterval);

        // 重置重连计数
        this.reconnectAttempts.set(sessionId, 0);

        // 清除重连定时器
        const reconnectTimer = this.reconnectTimers.get(sessionId);
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          this.reconnectTimers.delete(sessionId);
        }
      };

      // 接收消息
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // 处理心跳响应
          if (data.type === 'pong') {
            return;
          }

          // 调用注册的消息处理器
          const handler = this.messageHandlers.get(sessionId);
          if (handler) {
            handler(data);
          }
        } catch (error) {
          console.error(`[WebSocketPool] 消息解析错误: ${sessionId}`, error);
        }
      };

      // 连接错误
      ws.onerror = (error) => {
        console.error(`[WebSocketPool] 连接错误: ${sessionId}`, error);
      };

      // 连接关闭
      ws.onclose = (event) => {
        console.log(`[WebSocketPool] 连接已关闭: ${sessionId}, code=${event.code}`);

        // 清理资源
        this.cleanup(sessionId);

        // 尝试重连（如果不是主动关闭）
        if (event.code !== 1000) {
          this.attemptReconnect(sessionId, onMessage, wsUrl);
        }
      };

      // 保存连接和消息处理器
      this.connections.set(sessionId, ws);
      this.messageHandlers.set(sessionId, onMessage);

    } catch (error) {
      console.error(`[WebSocketPool] 创建连接失败: ${sessionId}`, error);
    }
  }

  /**
   * 断开指定会话的连接
   *
   * @param sessionId - 会话 ID
   */
  disconnect(sessionId: string): void {
    const ws = this.connections.get(sessionId);
    if (ws) {
      console.log(`[WebSocketPool] 主动断开连接: ${sessionId}`);
      ws.close(1000, 'Client closing');  // 1000 = 正常关闭
      this.cleanup(sessionId);
    }

    // 清除重连定时器
    const reconnectTimer = this.reconnectTimers.get(sessionId);
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      this.reconnectTimers.delete(sessionId);
    }

    // 重置重连计数
    this.reconnectAttempts.delete(sessionId);
  }

  /**
   * 断开所有连接
   */
  disconnectAll(): void {
    console.log(`[WebSocketPool] 断开所有连接，共 ${this.connections.size} 个`);

    this.connections.forEach((_, sessionId) => {
      this.disconnect(sessionId);
    });
  }

  /**
   * 向指定会话发送消息
   *
   * @param sessionId - 会话 ID
   * @param data - 要发送的数据
   * @returns 是否发送成功
   */
  send(sessionId: string, data: any): boolean {
    const ws = this.connections.get(sessionId);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
      return true;
    }
    console.warn(`[WebSocketPool] 无法发送消息，连接不存在或未打开: ${sessionId}`);
    return false;
  }

  /**
   * 检查连接是否打开
   *
   * @param sessionId - 会话 ID
   * @returns 连接是否打开
   */
  isConnected(sessionId: string): boolean {
    const ws = this.connections.get(sessionId);
    return ws?.readyState === WebSocket.OPEN;
  }

  /**
   * 获取活跃连接数
   *
   * @returns 活跃连接数
   */
  getConnectionCount(): number {
    return this.connections.size;
  }

  /**
   * 获取所有活跃的会话 ID
   *
   * @returns 会话 ID 数组
   */
  getActiveSessionIds(): string[] {
    return Array.from(this.connections.keys());
  }

  /**
   * 清理资源
   *
   * @param sessionId - 会话 ID
   */
  private cleanup(sessionId: string): void {
    // 清除心跳定时器
    const heartbeatInterval = this.heartbeatIntervals.get(sessionId);
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      this.heartbeatIntervals.delete(sessionId);
    }

    // 删除连接引用
    this.connections.delete(sessionId);
    this.messageHandlers.delete(sessionId);
  }

  /**
   * 尝试重连
   *
   * @param sessionId - 会话 ID
   * @param onMessage - 消息处理回调
   * @param wsUrl - WebSocket URL
   */
  private attemptReconnect(
    sessionId: string,
    onMessage: WebSocketMessageHandler,
    wsUrl?: string
  ): void {
    const attempts = this.reconnectAttempts.get(sessionId) || 0;

    if (attempts >= this.config.reconnectAttempts) {
      console.error(`[WebSocketPool] 重连失败，已达最大尝试次数: ${sessionId}`);
      this.reconnectAttempts.delete(sessionId);
      return;
    }

    const nextAttempt = attempts + 1;
    this.reconnectAttempts.set(sessionId, nextAttempt);

    console.log(`[WebSocketPool] 计划重连 (${nextAttempt}/${this.config.reconnectAttempts}): ${sessionId}`);

    const reconnectTimer = setTimeout(() => {
      console.log(`[WebSocketPool] 正在重连 (${nextAttempt}/${this.config.reconnectAttempts}): ${sessionId}`);
      this.connect(sessionId, onMessage, wsUrl);
    }, this.config.reconnectDelay);

    this.reconnectTimers.set(sessionId, reconnectTimer);
  }

  /**
   * 生成 WebSocket URL
   *
   * @param sessionId - 会话 ID
   * @returns WebSocket URL
   */
  private generateWebSocketUrl(sessionId: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/api/v1/risk-analysis-v2/ws/${sessionId}`;
  }
}

// 导出单例
export const websocketPool = new WebSocketConnectionPool();

// 导出类（用于测试）
export { WebSocketConnectionPool };
