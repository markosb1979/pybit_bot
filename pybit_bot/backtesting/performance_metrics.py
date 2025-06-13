#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Performance Metrics Calculator

Calculates trading performance metrics from backtest results.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple


class PerformanceMetrics:
    """Calculate and analyze trading performance metrics."""
    
    @staticmethod
    def calculate_metrics(trades: List[Dict[str, Any]], initial_capital: float = 1000.0) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics from a list of trades.
        
        Args:
            trades: List of trade dictionaries with pnl, entry_price, etc.
            initial_capital: Initial trading capital
            
        Returns:
            Dictionary of performance metrics
        """
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'avg_profit_per_trade': 0.0,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'calmar_ratio': 0.0,
                'avg_trade_duration': 0.0,
                'expectancy': 0.0
            }
        
        # Extract PnL values
        pnl_values = [trade['pnl'] for trade in trades]
        
        # Calculate basic metrics
        total_trades = len(trades)
        winning_trades = sum(1 for pnl in pnl_values if pnl > 0)
        losing_trades = sum(1 for pnl in pnl_values if pnl < 0)
        break_even_trades = total_trades - winning_trades - losing_trades
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        # PnL metrics
        total_pnl = sum(pnl_values)
        gross_profit = sum(pnl for pnl in pnl_values if pnl > 0)
        gross_loss = sum(pnl for pnl in pnl_values if pnl < 0)
        
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')
        
        # Average metrics
        avg_profit_per_trade = total_pnl / total_trades if total_trades > 0 else 0.0
        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0
        
        # Calculate equity curve and drawdown
        equity = [initial_capital]
        for pnl in pnl_values:
            equity.append(equity[-1] + pnl)
        
        # Calculate drawdown
        max_equity = initial_capital
        drawdowns = []
        
        for eq in equity:
            if eq > max_equity:
                max_equity = eq
            drawdown = max_equity - eq
            drawdowns.append(drawdown)
        
        max_drawdown = max(drawdowns)
        max_drawdown_pct = (max_drawdown / max_equity) * 100 if max_equity > 0 else 0.0
        
        # Calculate risk-adjusted returns
        pnl_returns = np.diff(equity) / np.array(equity[:-1])
        avg_return = np.mean(pnl_returns)
        std_return = np.std(pnl_returns)
        
        risk_free_rate = 0.0  # Assuming 0% risk-free rate
        
        # Sharpe ratio
        sharpe_ratio = (avg_return - risk_free_rate) / std_return if std_return > 0 else 0.0
        
        # Sortino ratio (using only negative returns for denominator)
        negative_returns = [r for r in pnl_returns if r < 0]
        downside_deviation = np.std(negative_returns) if negative_returns else 0.0
        sortino_ratio = (avg_return - risk_free_rate) / downside_deviation if downside_deviation > 0 else 0.0
        
        # Calmar ratio
        annual_return = avg_return * 252  # Assuming 252 trading days
        calmar_ratio = annual_return / (max_drawdown_pct / 100) if max_drawdown_pct > 0 else 0.0
        
        # Expectancy
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss)) if total_trades > 0 else 0.0
        
        # Average trade duration
        # This assumes trades have a 'duration' field in seconds or as a timedelta
        if 'duration' in trades[0]:
            try:
                # If duration is already in hours
                avg_trade_duration = sum(float(trade.get('duration', 0)) for trade in trades) / total_trades
            except (ValueError, TypeError):
                # If duration is a string like "2h 15m", extract hours
                avg_trade_duration = 0.0
                for trade in trades:
                    duration_str = trade.get('duration', '0h 0m')
                    if 'h' in duration_str and 'm' in duration_str:
                        hours = float(duration_str.split('h')[0])
                        minutes = float(duration_str.split('h')[1].split('m')[0])
                        avg_trade_duration += hours + (minutes / 60)
                avg_trade_duration /= total_trades
        else:
            avg_trade_duration = 0.0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'break_even_trades': break_even_trades,
            'win_rate': win_rate * 100,  # as percentage
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / initial_capital) * 100,
            'avg_profit_per_trade': avg_profit_per_trade,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'avg_trade_duration': avg_trade_duration,
            'expectancy': expectancy
        }

    @staticmethod
    def create_equity_curve(trades: List[Dict[str, Any]], initial_capital: float = 1000.0) -> pd.DataFrame:
        """
        Create an equity curve DataFrame from trades.
        
        Args:
            trades: List of trade dictionaries
            initial_capital: Initial capital
            
        Returns:
            DataFrame with equity curve data
        """
        if not trades:
            return pd.DataFrame({
                'timestamp': [pd.Timestamp.now()],
                'equity': [initial_capital],
                'drawdown': [0.0],
                'drawdown_pct': [0.0]
            })
        
        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda x: x['timestamp'])
        
        # Create DataFrame
        equity_curve = pd.DataFrame({
            'timestamp': [pd.to_datetime(trade['timestamp']) for trade in sorted_trades],
            'pnl': [trade['pnl'] for trade in sorted_trades]
        })
        
        # Calculate cumulative equity
        equity_curve['equity'] = initial_capital + equity_curve['pnl'].cumsum()
        
        # Calculate drawdown
        equity_curve['peak'] = equity_curve['equity'].cummax()
        equity_curve['drawdown'] = equity_curve['peak'] - equity_curve['equity']
        equity_curve['drawdown_pct'] = (equity_curve['drawdown'] / equity_curve['peak']) * 100
        
        return equity_curve