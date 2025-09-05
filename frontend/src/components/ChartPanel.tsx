import React, { useEffect, useRef, useState } from 'react';
import { createChart, type IChartApi, type ISeriesApi, type CandlestickData, type LineData } from 'lightweight-charts';
import type { BarData } from '../types/trading';
import websocketService from '../services/websocket';

interface ChartPanelProps {
  symbol: string;
}

const ChartPanel: React.FC<ChartPanelProps> = ({ symbol }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const [, setBarData] = useState<BarData[]>([]);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 500,
      layout: {
        background: { color: '#1f2937' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#374151',
      },
      timeScale: {
        borderColor: '#374151',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Create candlestick series
    const candleSeries = (chart as any).addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    // Create EMA line series
    const emaSeries = (chart as any).addLineSeries({
      color: '#3b82f6',
      lineWidth: 2,
      title: 'EMA9',
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    emaSeriesRef.current = emaSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    // Subscribe to bar data
    websocketService.subscribeBars(symbol, '1m');

    const handleBarData = (data: BarData & { symbol?: string }) => {
      if (data.symbol && data.symbol !== symbol) return;

      setBarData(prevData => {
        const newData = [...prevData];
        const existingIndex = newData.findIndex(
          bar => bar.timestamp === data.timestamp
        );

        if (existingIndex >= 0) {
          newData[existingIndex] = data;
        } else {
          newData.push(data);
          // Keep only last 500 bars
          if (newData.length > 500) {
            newData.shift();
          }
        }

        // Update chart
        if (candleSeriesRef.current && emaSeriesRef.current) {
          const candleData: CandlestickData[] = newData.map(bar => ({
            time: (new Date(bar.timestamp).getTime() / 1000) as any,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
          }));

          const emaData: LineData[] = newData
            .filter(bar => bar.ema9 !== undefined)
            .map(bar => ({
              time: (new Date(bar.timestamp).getTime() / 1000) as any,
              value: bar.ema9!,
            }));

          candleSeriesRef.current.setData(candleData);
          emaSeriesRef.current.setData(emaData);
        }

        return newData;
      });
    };

    websocketService.on('bar_data', handleBarData);

    return () => {
      websocketService.off('bar_data', handleBarData);
      websocketService.unsubscribeBars(symbol);
    };
  }, [symbol]);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Price Chart - {symbol}</h2>
        <div className="flex items-center space-x-4 text-sm">
          <span className="text-gray-400">1 Minute</span>
          <span className="text-blue-500">EMA9</span>
        </div>
      </div>
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
};

export default ChartPanel;