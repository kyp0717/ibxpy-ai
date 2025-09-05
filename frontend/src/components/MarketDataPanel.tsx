import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import type { MarketData } from '../types/trading';
import websocketService from '../services/websocket';

interface MarketDataPanelProps {
  symbol: string;
  onSymbolChange: (symbol: string) => void;
}

const MarketDataPanel: React.FC<MarketDataPanelProps> = ({ symbol, onSymbolChange }) => {
  const [marketData, setMarketData] = useState<MarketData | null>(null);
  const [inputSymbol, setInputSymbol] = useState(symbol);
  const [priceChange, setPriceChange] = useState<number>(0);

  useEffect(() => {
    // Subscribe to market data for the current symbol
    websocketService.subscribeMarketData(symbol);

    const handleMarketData = (data: MarketData) => {
      if (data.symbol === symbol) {
        setMarketData(prevData => {
          if (prevData && prevData.last) {
            setPriceChange(data.last - prevData.last);
          }
          return data;
        });
      }
    };

    websocketService.on('market_data', handleMarketData);

    return () => {
      websocketService.off('market_data', handleMarketData);
      websocketService.unsubscribeMarketData(symbol);
    };
  }, [symbol]);

  const handleSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputSymbol && inputSymbol !== symbol) {
      onSymbolChange(inputSymbol.toUpperCase());
    }
  };

  const formatPrice = (price: number | undefined) => {
    return price?.toFixed(2) || '—';
  };

  const formatVolume = (volume: number | undefined) => {
    if (!volume) return '—';
    if (volume >= 1000000) return `${(volume / 1000000).toFixed(1)}M`;
    if (volume >= 1000) return `${(volume / 1000).toFixed(1)}K`;
    return volume.toString();
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-4">Market Data</h2>
      
      {/* Symbol Input */}
      <form onSubmit={handleSymbolSubmit} className="mb-4">
        <input
          type="text"
          value={inputSymbol}
          onChange={(e) => setInputSymbol(e.target.value)}
          className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
          placeholder="Enter symbol..."
        />
      </form>

      {/* Market Data Display */}
      {marketData ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold">{marketData.symbol}</span>
            <div className="flex items-center">
              {priceChange > 0 ? (
                <TrendingUp className="w-5 h-5 text-green-500 mr-1" />
              ) : priceChange < 0 ? (
                <TrendingDown className="w-5 h-5 text-red-500 mr-1" />
              ) : null}
              <span className={`text-xl font-semibold ${
                priceChange > 0 ? 'text-green-500' : 
                priceChange < 0 ? 'text-red-500' : 
                'text-gray-300'
              }`}>
                ${formatPrice(marketData.last)}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-gray-400">Bid:</span>
              <span className="ml-2 font-medium">${formatPrice(marketData.bid)}</span>
            </div>
            <div>
              <span className="text-gray-400">Ask:</span>
              <span className="ml-2 font-medium">${formatPrice(marketData.ask)}</span>
            </div>
            <div>
              <span className="text-gray-400">Volume:</span>
              <span className="ml-2 font-medium">{formatVolume(marketData.volume)}</span>
            </div>
            <div>
              <span className="text-gray-400">Spread:</span>
              <span className="ml-2 font-medium">
                ${formatPrice((marketData.ask || 0) - (marketData.bid || 0))}
              </span>
            </div>
          </div>

          {/* Timestamp */}
          <div className="text-xs text-gray-500 pt-2 border-t border-gray-700">
            Last update: {new Date(marketData.timestamp).toLocaleTimeString()}
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          Waiting for market data...
        </div>
      )}
    </div>
  );
};

export default MarketDataPanel;