import React, { useState, useEffect } from 'react';
import { Package, TrendingUp, TrendingDown } from 'lucide-react';
import type { Position } from '../types/trading';
import websocketService from '../services/websocket';

interface PositionsPanelProps {
  onSelectSymbol: (symbol: string) => void;
}

const PositionsPanel: React.FC<PositionsPanelProps> = ({ onSelectSymbol }) => {
  const [positions, setPositions] = useState<Position[]>([]);

  useEffect(() => {
    // Request initial positions
    if (websocketService.isConnected()) {
      websocketService.requestPositions();
    }

    const handlePositionUpdate = (data: Position) => {
      setPositions(prevPositions => {
        const index = prevPositions.findIndex(p => p.symbol === data.symbol);
        if (index >= 0) {
          const newPositions = [...prevPositions];
          newPositions[index] = data;
          return newPositions;
        } else if (data.quantity !== 0) {
          return [...prevPositions, data];
        }
        return prevPositions;
      });
    };

    const handleConnection = (data: { status: string }) => {
      if (data.status === 'connected') {
        websocketService.requestPositions();
      }
    };

    websocketService.on('position_update', handlePositionUpdate);
    websocketService.on('connection', handleConnection);

    // Request positions every 10 seconds
    const interval = setInterval(() => {
      if (websocketService.isConnected()) {
        websocketService.requestPositions();
      }
    }, 10000);

    return () => {
      websocketService.off('position_update', handlePositionUpdate);
      websocketService.off('connection', handleConnection);
      clearInterval(interval);
    };
  }, []);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const calculatePnLPercent = (position: Position) => {
    if (position.avgCost === 0) return 0;
    return ((position.currentPrice - position.avgCost) / position.avgCost) * 100;
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <Package className="w-5 h-5 mr-2" />
        Positions
      </h2>

      {positions.length > 0 ? (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {positions.map((position) => {
            const pnlPercent = calculatePnLPercent(position);
            const isProfit = position.unrealizedPnL >= 0;

            return (
              <div
                key={position.symbol}
                className="bg-gray-700 rounded p-3 cursor-pointer hover:bg-gray-600 transition-colors"
                onClick={() => onSelectSymbol(position.symbol)}
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="font-semibold text-lg">{position.symbol}</span>
                    <div className="text-sm text-gray-400">
                      {position.quantity} shares @ {formatCurrency(position.avgCost)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium">
                      {formatCurrency(position.currentPrice)}
                    </div>
                    <div className={`text-sm ${isProfit ? 'text-green-500' : 'text-red-500'}`}>
                      {formatPercent(pnlPercent)}
                    </div>
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2 border-t border-gray-600">
                  <div className="flex items-center">
                    {isProfit ? (
                      <TrendingUp className="w-4 h-4 text-green-500 mr-1" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-red-500 mr-1" />
                    )}
                    <span className="text-sm text-gray-400">Unrealized P&L</span>
                  </div>
                  <span className={`font-medium ${isProfit ? 'text-green-500' : 'text-red-500'}`}>
                    {formatCurrency(position.unrealizedPnL)}
                  </span>
                </div>

                {position.realizedPnL !== 0 && (
                  <div className="flex justify-between items-center mt-1">
                    <span className="text-sm text-gray-400">Realized P&L</span>
                    <span className={`text-sm ${position.realizedPnL >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {formatCurrency(position.realizedPnL)}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          No open positions
        </div>
      )}
    </div>
  );
};

export default PositionsPanel;