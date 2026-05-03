import type { RalphEvent } from './ralph-types';

export type RalphEventHandler = (event: RalphEvent) => void;

interface WebSocketMessage {
  data: string;
}

/**
 * Ralph WebSocket 客户端
 * 支持断线重连、sequence 恢复、事件去重
 */
export class RalphWebSocket {
  private baseUrl: string;
  private wsUrl: string;
  private ws: WebSocket | null = null;
  private handlers: Set<RalphEventHandler> = new Set();
  private lastSequence: number = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay: number = 1000; // 初始重连延迟 1 秒
  private readonly maxReconnectDelay: number = 30000; // 最大重连延迟 30 秒
  private isManualDisconnect: boolean = false;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    this.wsUrl = this.buildWebSocketUrl(baseUrl);
  }

  /**
   * 将 http/https URL 转换为 ws/wss URL
   */
  private buildWebSocketUrl(baseUrl: string): string {
    // 相对路径（如 /ws/dashboard）直接返回，浏览器会自动解析
    if (baseUrl.startsWith('/')) {
      return baseUrl;
    }
    // 绝对 URL：转换协议，保留路径
    const trimmed = baseUrl.replace(/\/$/, '');
    const url = new URL(trimmed);
    const wsProtocol = url.protocol === 'https:' ? 'wss' : 'ws';
    return `${wsProtocol}://${url.host}${url.pathname}`;
  }

  /**
   * 获取当前 sequence 编号
   */
  get sequence(): number {
    return this.lastSequence;
  }

  /**
   * 建立 WebSocket 连接
   * 重连时会携带 after_sequence 参数
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isManualDisconnect = false;
    const url = this.buildConnectionUrl();

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      // 连接成功，重置重连延迟
      this.reconnectDelay = 1000;
    };

    this.ws.onmessage = (event: WebSocketMessage) => {
      this.handleMessage(event.data);
    };

    this.ws.onclose = () => {
      if (!this.isManualDisconnect) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // 错误时关闭连接，触发 onclose 进行重连
      this.ws?.close();
    };
  }

  /**
   * 构建连接 URL，重连时包含 after_sequence 参数
   */
  private buildConnectionUrl(): string {
    if (this.lastSequence > 0) {
      return `${this.wsUrl}?after_sequence=${this.lastSequence}`;
    }
    return this.wsUrl;
  }

  /**
   * 处理收到的消息
   */
  private handleMessage(data: string): void {
    try {
      const event = JSON.parse(data) as RalphEvent;

      // 验证事件格式
      if (typeof event.sequence !== 'number' || !event.event_id) {
        return;
      }

      // 处理 sequence_reset
      if (event.sequence_reset) {
        this.lastSequence = 0;
        this.notifyHandlers(event);
        return;
      }

      // 去重：忽略 sequence <= lastSequence 的事件
      if (event.sequence <= this.lastSequence) {
        return;
      }

      // 更新 sequence
      this.lastSequence = event.sequence;

      // 通知所有处理器
      this.notifyHandlers(event);
    } catch {
      // 忽略解析错误
    }
  }

  /**
   * 通知所有注册的事件处理器
   */
  private notifyHandlers(event: RalphEvent): void {
    for (const handler of this.handlers) {
      try {
        handler(event);
      } catch {
        // 忽略单个处理器的错误，不影响其他处理器
      }
    }
  }

  /**
   * 调度重连，使用指数退避
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectTimer = setTimeout(() => {
      this.connect();
      // 增加重连延迟（指数退避，最大 30 秒）
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    }, this.reconnectDelay);
  }

  /**
   * 断开 WebSocket 连接
   */
  disconnect(): void {
    this.isManualDisconnect = true;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * 注册事件监听器
   * @param handler 事件处理函数
   * @returns 取消订阅函数
   */
  on(handler: RalphEventHandler): () => void {
    this.handlers.add(handler);

    // 返回取消订阅函数
    return () => {
      this.handlers.delete(handler);
    };
  }
}
