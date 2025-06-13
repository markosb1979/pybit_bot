#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Create sample backtest results file for testing.
"""

import os
import json
import datetime

# Create results directory if it doesn't exist
os.makedirs('results', exist_ok=True)

# Sample backtest results
results = {
    'strategy': 'StrategyA',
    'symbol': 'BTCUSDT',
    'timeframe': '1m',
    'start_date': '2023-01-01',
    'end_date': '2023-01-31',
    'trades': [
        {
            'timestamp': '2023-01-05T08:30:15',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'entry_price': 16750.25,
            'exit_price': 16950.75,
            'quantity': 0.01,
            'pnl': 2.00,
            'pnl_pct': 1.20,
            'duration': '2h 15m',
            'exit_reason': 'TP_HIT'
        },
        {
            'timestamp': '2023-01-10T14:45:30',
            'symbol': 'BTCUSDT',
            'side': 'SELL',
            'entry_price': 17250.50,
            'exit_price': 17050.25,
            'quantity': 0.01,
            'pnl': 2.00,
            'pnl_pct': 1.16,
            'duration': '3h 30m',
            'exit_reason': 'TP_HIT'
        },
        {
            'timestamp': '2023-01-15T10:20:45',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'entry_price': 17500.75,
            'exit_price': 17300.50,
            'quantity': 0.01,
            'pnl': -2.00,
            'pnl_pct': -1.14,
            'duration': '1h 45m',
            'exit_reason': 'SL_HIT'
        },
        {
            'timestamp': '2023-01-20T16:15:00',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'entry_price': 17800.25,
            'exit_price': 18100.50,
            'quantity': 0.01,
            'pnl': 3.00,
            'pnl_pct': 1.69,
            'duration': '4h 30m',
            'exit_reason': 'TP_HIT'
        },
        {
            'timestamp': '2023-01-25T09:10:15',
            'symbol': 'BTCUSDT',
            'side': 'SELL',
            'entry_price': 18250.75,
            'exit_price': 18000.25,
            'quantity': 0.01,
            'pnl': 2.50,
            'pnl_pct': 1.37,
            'duration': '2h 45m',
            'exit_reason': 'TP_HIT'
        }
    ],
    'performance': {
        'total_trades': 5,
        'winning_trades': 4,
        'losing_trades': 1,
        'win_rate': 80.0,
        'profit_factor': 4.75,
        'total_pnl': 7.50,
        'max_drawdown': 2.00,
        'max_drawdown_pct': 1.14,
        'sharpe_ratio': 1.8,
        'sortino_ratio': 2.2
    }
}

# Save to file
results_file = 'results/backtest_20230101_20230131.json'
with open(results_file, 'w') as f:
    json.dump(results, f, indent=2)

print(f"Sample backtest results created: {results_file}")