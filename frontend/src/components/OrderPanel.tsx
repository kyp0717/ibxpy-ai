import React, { useState } from 'react';
import { ShoppingCart, Send } from 'lucide-react';
import type { Order } from '../types/trading';
import websocketService from '../services/websocket';
import toast from 'react-hot-toast';

interface OrderPanelProps {
  symbol: string;
}

const OrderPanel: React.FC<OrderPanelProps> = ({ symbol }) => {
  const [action, setAction] = useState<'BUY' | 'SELL'>('BUY');
  const [orderType, setOrderType] = useState<'MKT' | 'LMT' | 'STP'>('MKT');
  const [quantity, setQuantity] = useState<string>('100');
  const [price, setPrice] = useState<string>('');
  const [stopPrice, setStopPrice] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!websocketService.isConnected()) {
      toast.error('Not connected to trading server');
      return;
    }

    const qty = parseInt(quantity);
    if (isNaN(qty) || qty <= 0) {
      toast.error('Invalid quantity');
      return;
    }

    if (orderType === 'LMT' && !price) {
      toast.error('Limit price required for limit orders');
      return;
    }

    if (orderType === 'STP' && !stopPrice) {
      toast.error('Stop price required for stop orders');
      return;
    }

    setIsSubmitting(true);

    const order: Omit<Order, 'orderId' | 'status' | 'timestamp'> = {
      symbol,
      action,
      orderType,
      quantity: qty,
      price: orderType === 'LMT' ? parseFloat(price) : undefined,
    };

    // Listen for order status
    const handleOrderStatus = (data: Order) => {
      if (data.symbol === symbol) {
        setIsSubmitting(false);
        
        if (data.status === 'FILLED') {
          toast.success(`Order filled: ${data.action} ${data.quantity} ${data.symbol}`);
        } else if (data.status === 'SUBMITTED') {
          toast.success(`Order submitted: ${data.action} ${data.quantity} ${data.symbol}`);
        } else if (data.status === 'ERROR') {
          toast.error(`Order error: ${data.message || 'Unknown error'}`);
        } else if (data.status === 'CANCELLED') {
          toast(`Order cancelled: ${data.symbol}`, { icon: '⚠️' });
        }
      }
    };

    websocketService.on('order_status', handleOrderStatus);

    // Place the order
    websocketService.placeOrder(order);

    // Remove listener after 30 seconds
    setTimeout(() => {
      websocketService.off('order_status', handleOrderStatus);
      setIsSubmitting(false);
    }, 30000);
  };

  const resetForm = () => {
    setQuantity('100');
    setPrice('');
    setStopPrice('');
    setOrderType('MKT');
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <ShoppingCart className="w-5 h-5 mr-2" />
        Place Order - {symbol}
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setAction('BUY')}
            className={`py-2 px-4 rounded font-medium transition-colors ${
              action === 'BUY'
                ? 'bg-green-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            BUY
          </button>
          <button
            type="button"
            onClick={() => setAction('SELL')}
            className={`py-2 px-4 rounded font-medium transition-colors ${
              action === 'SELL'
                ? 'bg-red-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            SELL
          </button>
        </div>

        {/* Order Type */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-1">
            Order Type
          </label>
          <select
            value={orderType}
            onChange={(e) => setOrderType(e.target.value as 'MKT' | 'LMT' | 'STP')}
            className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
          >
            <option value="MKT">Market</option>
            <option value="LMT">Limit</option>
            <option value="STP">Stop</option>
          </select>
        </div>

        {/* Quantity */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-1">
            Quantity
          </label>
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            min="1"
            step="1"
            className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
            required
          />
        </div>

        {/* Limit Price */}
        {orderType === 'LMT' && (
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Limit Price
            </label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              min="0.01"
              step="0.01"
              className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
              required
            />
          </div>
        )}

        {/* Stop Price */}
        {orderType === 'STP' && (
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Stop Price
            </label>
            <input
              type="number"
              value={stopPrice}
              onChange={(e) => setStopPrice(e.target.value)}
              min="0.01"
              step="0.01"
              className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
              required
            />
          </div>
        )}

        {/* Submit Buttons */}
        <div className="flex space-x-2">
          <button
            type="submit"
            disabled={isSubmitting || !websocketService.isConnected()}
            className={`flex-1 py-2 px-4 rounded font-medium transition-colors flex items-center justify-center ${
              isSubmitting || !websocketService.isConnected()
                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                : action === 'BUY'
                ? 'bg-green-600 hover:bg-green-700 text-white'
                : 'bg-red-600 hover:bg-red-700 text-white'
            }`}
          >
            <Send className="w-4 h-4 mr-2" />
            {isSubmitting ? 'Submitting...' : `${action} ${quantity} Shares`}
          </button>
          <button
            type="button"
            onClick={resetForm}
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors"
          >
            Reset
          </button>
        </div>
      </form>
    </div>
  );
};

export default OrderPanel;