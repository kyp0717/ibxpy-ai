import React, { useState, useEffect } from 'react';
import { DollarSign, TrendingUp, TrendingDown } from 'lucide-react';
import type { AccountInfo } from '../types/trading';
import websocketService from '../services/websocket';

const AccountInfoPanel: React.FC = () => {
  const [accountInfo, setAccountInfo] = useState<AccountInfo | null>(null);

  useEffect(() => {
    // Request initial account info
    if (websocketService.isConnected()) {
      websocketService.requestAccountInfo();
    }

    const handleAccountUpdate = (data: AccountInfo) => {
      setAccountInfo(data);
    };

    const handleConnection = (data: { status: string }) => {
      if (data.status === 'connected') {
        websocketService.requestAccountInfo();
      }
    };

    websocketService.on('account_update', handleAccountUpdate);
    websocketService.on('connection', handleConnection);

    // Request account info every 30 seconds
    const interval = setInterval(() => {
      if (websocketService.isConnected()) {
        websocketService.requestAccountInfo();
      }
    }, 30000);

    return () => {
      websocketService.off('account_update', handleAccountUpdate);
      websocketService.off('connection', handleConnection);
      clearInterval(interval);
    };
  }, []);

  const formatCurrency = (value: number | undefined) => {
    if (value === undefined) return '—';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatPnL = (value: number | undefined) => {
    if (value === undefined) return '—';
    const formatted = formatCurrency(value);
    const color = value >= 0 ? 'text-green-500' : 'text-red-500';
    return <span className={color}>{formatted}</span>;
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <DollarSign className="w-5 h-5 mr-2" />
        Account Info
      </h2>

      {accountInfo ? (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">Net Liquidation</span>
            <span className="font-semibold">
              {formatCurrency(accountInfo.netLiquidation)}
            </span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">Buying Power</span>
            <span className="font-medium">
              {formatCurrency(accountInfo.buyingPower)}
            </span>
          </div>

          <div className="border-t border-gray-700 pt-3">
            <div className="flex justify-between items-center mb-2">
              <span className="text-gray-400 text-sm">Cash</span>
              <span>{formatCurrency(accountInfo.totalCashValue)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Positions</span>
              <span>{formatCurrency(accountInfo.totalPositionValue)}</span>
            </div>
          </div>

          <div className="border-t border-gray-700 pt-3">
            <div className="flex justify-between items-center mb-2">
              <span className="text-gray-400 text-sm flex items-center">
                <TrendingUp className="w-4 h-4 mr-1" />
                Unrealized P&L
              </span>
              {formatPnL(accountInfo.unrealizedPnL)}
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm flex items-center">
                <TrendingDown className="w-4 h-4 mr-1" />
                Realized P&L
              </span>
              {formatPnL(accountInfo.realizedPnL)}
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          Loading account info...
        </div>
      )}
    </div>
  );
};

export default AccountInfoPanel;