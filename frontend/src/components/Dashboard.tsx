import React, { useState, useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import MarketDataPanel from './MarketDataPanel';
import ChartPanel from './ChartPanel';
import PositionsPanel from './PositionsPanel';
import OrderPanel from './OrderPanel';
import AccountInfoPanel from './AccountInfoPanel';
import ConnectionStatus from './ConnectionStatus';
import websocketService from '../services/websocket';

const Dashboard: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('AAPL');
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Connect to WebSocket
    websocketService.connect();

    // Listen for connection status
    const handleConnection = (data: { status: string }) => {
      setIsConnected(data.status === 'connected');
    };

    websocketService.on('connection', handleConnection);

    return () => {
      websocketService.off('connection', handleConnection);
      websocketService.disconnect();
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <Toaster position="top-right" />
      
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">TWS Trading Dashboard</h1>
            <ConnectionStatus isConnected={isConnected} />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column - Market Data & Order Entry */}
          <div className="col-span-3 space-y-6">
            <MarketDataPanel 
              symbol={selectedSymbol} 
              onSymbolChange={setSelectedSymbol} 
            />
            <OrderPanel symbol={selectedSymbol} />
          </div>

          {/* Center Column - Chart */}
          <div className="col-span-6">
            <ChartPanel symbol={selectedSymbol} />
          </div>

          {/* Right Column - Positions & Account */}
          <div className="col-span-3 space-y-6">
            <AccountInfoPanel />
            <PositionsPanel onSelectSymbol={setSelectedSymbol} />
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;