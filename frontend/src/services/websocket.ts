import { io, type Socket } from 'socket.io-client';
import type { MarketData, BarData, Position, Order, AccountInfo } from '../types/trading';

class WebSocketService {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private listeners: Map<string, Set<Function>> = new Map();

  connect(url: string = 'http://localhost:8000'): void {
    if (this.socket?.connected) {
      console.log('WebSocket already connected');
      return;
    }

    this.socket = io(url, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    });

    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.emit('connection', { status: 'connected' });
    });

    this.socket.on('disconnect', (reason: string) => {
      console.log('WebSocket disconnected:', reason);
      this.emit('connection', { status: 'disconnected', reason });
    });

    this.socket.on('connect_error', (error: Error) => {
      console.error('WebSocket connection error:', error);
      this.reconnectAttempts++;
      this.emit('connection', { status: 'error', error: error.message });
    });

    // Trading event handlers
    this.socket.on('market_data', (data: MarketData) => {
      this.emit('market_data', data);
    });

    this.socket.on('bar_data', (data: BarData) => {
      this.emit('bar_data', data);
    });

    this.socket.on('position_update', (data: Position) => {
      this.emit('position_update', data);
    });

    this.socket.on('order_status', (data: Order) => {
      this.emit('order_status', data);
    });

    this.socket.on('account_update', (data: AccountInfo) => {
      this.emit('account_update', data);
    });

    this.socket.on('error', (data: { message: string; code?: string }) => {
      console.error('WebSocket error:', data);
      this.emit('error', data);
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  // Subscribe to market data
  subscribeMarketData(symbol: string): void {
    if (!this.socket?.connected) {
      console.error('WebSocket not connected');
      return;
    }
    this.socket.emit('subscribe_market_data', { symbol });
  }

  unsubscribeMarketData(symbol: string): void {
    if (!this.socket?.connected) return;
    this.socket.emit('unsubscribe_market_data', { symbol });
  }

  // Subscribe to bar data
  subscribeBars(symbol: string, interval: '5s' | '1m' = '1m'): void {
    if (!this.socket?.connected) {
      console.error('WebSocket not connected');
      return;
    }
    this.socket.emit('subscribe_bars', { symbol, interval });
  }

  unsubscribeBars(symbol: string): void {
    if (!this.socket?.connected) return;
    this.socket.emit('unsubscribe_bars', { symbol });
  }

  // Order management
  placeOrder(order: Omit<Order, 'orderId' | 'status' | 'timestamp'>): void {
    if (!this.socket?.connected) {
      console.error('WebSocket not connected');
      return;
    }
    this.socket.emit('place_order', order);
  }

  cancelOrder(orderId: number): void {
    if (!this.socket?.connected) return;
    this.socket.emit('cancel_order', { orderId });
  }

  // Request current positions
  requestPositions(): void {
    if (!this.socket?.connected) return;
    this.socket.emit('request_positions');
  }

  // Request account info
  requestAccountInfo(): void {
    if (!this.socket?.connected) return;
    this.socket.emit('request_account_info');
  }

  // Event listener management
  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(callback);
  }

  off(event: string, callback: Function): void {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data: any): void {
    this.listeners.get(event)?.forEach(callback => callback(data));
  }

  isConnected(): boolean {
    return this.socket?.connected || false;
  }
}

export default new WebSocketService();