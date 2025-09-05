export interface MarketData {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  volume: number;
  timestamp: string;
}

export interface BarData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema9?: number;
}

export interface Position {
  symbol: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  unrealizedPnL: number;
  realizedPnL: number;
}

export interface Order {
  orderId: number;
  symbol: string;
  action: 'BUY' | 'SELL';
  orderType: 'MKT' | 'LMT' | 'STP';
  quantity: number;
  price?: number;
  status: 'PENDING' | 'SUBMITTED' | 'FILLED' | 'CANCELLED' | 'ERROR';
  timestamp: string;
  message?: string;
}

export interface AccountInfo {
  accountId: string;
  buyingPower: number;
  totalCashValue: number;
  totalPositionValue: number;
  netLiquidation: number;
  unrealizedPnL: number;
  realizedPnL: number;
}

export interface WebSocketMessage {
  type: 'market_data' | 'bar_data' | 'position_update' | 'order_status' | 'account_update' | 'error';
  data: any;
}