#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backtest Runner for PyBit Bot

Command-line tool for running backtests and generating performance reports.
"""

import os
import sys
import json
import logging
import argparse
import datetime
from typing import Dict, List, Any, Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BacktestRunner:
    """Command-line tool for running backtests."""
    
    def __init__(self):
        """Initialize the backtest runner."""
        self.config = {}
        self.results_dir = 'results'
        self.data_dir = 'data'
        
        # Create results directory if it doesn't exist
        os.makedirs(self.results_dir, exist_ok=True)
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            return {}
    
    def _parse_date(self, date_str: str) -> datetime.datetime:
        """
        Parse date string to datetime.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Datetime object
        """
        try:
            return datetime.datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            logger.error(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
            sys.exit(1)
    
    def _load_backtest_results(self, results_file: str) -> Dict[str, Any]:
        """
        Load backtest results from a JSON file.
        
        Args:
            results_file: Path to the results file
            
        Returns:
            Results dictionary
        """
        try:
            with open(results_file, 'r') as f:
                results = json.load(f)
            return results
        except FileNotFoundError:
            logger.error(f"Results file not found: {results_file}")
            sys.exit(1)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in results file: {results_file}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load results: {str(e)}")
            sys.exit(1)
    
    def run_backtest(self, args: argparse.Namespace) -> Optional[Dict[str, Any]]:
        """
        Run a backtest with the given arguments.
        
        Args:
            args: Command-line arguments
            
        Returns:
            Backtest results dictionary
        """
        # Print warning and exit if we're in report-only mode
        if args.report_only:
            print("Error: Cannot run backtest in report-only mode")
            print("Please specify a results file with --results-file or remove --report-only flag")
            return None
            
        logger.info("Starting backtest...")
        logger.info(f"Strategy: {args.strategy}")
        logger.info(f"Symbol: {args.symbol}")
        logger.info(f"Timeframe: {args.timeframe}")
        
        # Parse dates
        start_date = self._parse_date(args.start)
        end_date = self._parse_date(args.end)
        
        logger.info(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Load config if provided
        if args.config:
            self.config = self._load_config(args.config)
            logger.info(f"Loaded configuration from {args.config}")
        
        # This is where we'd actually run the backtest
        # For now, we'll just return a dummy result
        
        # In a real implementation, we'd import:
        # from pybit_bot.backtesting.engine import BacktestEngine
        # engine = BacktestEngine(self.config)
        # results = engine.run(args.strategy, args.symbol, args.timeframe, start_date, end_date)
        
        # Dummy results
        results = {
            'strategy': args.strategy,
            'symbol': args.symbol,
            'timeframe': args.timeframe,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'trades': [
                {
                    'timestamp': '2023-01-05T08:30:15',
                    'symbol': args.symbol,
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
                    'symbol': args.symbol,
                    'side': 'SELL',
                    'entry_price': 17250.50,
                    'exit_price': 17050.25,
                    'quantity': 0.01,
                    'pnl': 2.00,
                    'pnl_pct': 1.16,
                    'duration': '3h 30m',
                    'exit_reason': 'TP_HIT'
                }
            ],
            'performance': {
                'total_trades': 2,
                'winning_trades': 2,
                'losing_trades': 0,
                'win_rate': 100.0,
                'profit_factor': float('inf'),
                'total_pnl': 4.00,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'sharpe_ratio': 2.5,
                'sortino_ratio': 3.2
            }
        }
        
        # Save results
        results_file = f"{self.results_dir}/backtest_{args.strategy}_{args.symbol}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Backtest completed, results saved to {results_file}")
        
        return results
    
    def generate_report(self, results: Dict[str, Any], args: argparse.Namespace) -> None:
        """
        Generate a performance report from backtest results.
        
        Args:
            results: Backtest results dictionary
            args: Command-line arguments
        """
        # Here we'd generate a more detailed report
        # This could include charts, tables, and statistics
        
        # For now, just print some basic info
        
        print("\n" + "=" * 80)
        print(f"BACKTEST REPORT: {results['strategy']} on {results['symbol']} ({results['timeframe']})")
        print("-" * 80)
        print(f"Period: {results['start_date']} to {results['end_date']}")
        print("-" * 80)
        
        # Performance summary
        perf = results['performance']
        print(f"Total trades: {perf['total_trades']}")
        print(f"Win rate: {perf['win_rate']:.2f}%")
        print(f"Profit factor: {perf['profit_factor'] if perf['profit_factor'] != float('inf') else 'N/A'}")
        print(f"Total P&L: ${perf['total_pnl']:.2f}")
        print(f"Max drawdown: {perf['max_drawdown_pct']:.2f}%")
        print(f"Sharpe ratio: {perf['sharpe_ratio']:.2f}")
        print(f"Sortino ratio: {perf['sortino_ratio']:.2f}")
        
        print("-" * 80)
        print("TRADES:")
        
        # Print trades
        for i, trade in enumerate(results['trades'], 1):
            print(f"{i}. {trade['timestamp']} - {trade['side']} {trade['quantity']} {results['symbol']} @ {trade['entry_price']}")
            print(f"   Exit: {trade['exit_price']} | P&L: ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%) | Reason: {trade['exit_reason']}")
        
        print("=" * 80)
        
        # Here we'd generate visual reports if matplotlib is available
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            
            # Generate report directory
            report_dir = f"{self.results_dir}/reports"
            os.makedirs(report_dir, exist_ok=True)
            
            # Example of where we'd create charts
            # This is just placeholder code
            print(f"\nCharts would be saved to {report_dir}/")
            
        except ImportError:
            print("\nMatplotlib not installed. Install with 'pip install matplotlib' for visual reports.")


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(description='PyBit Bot Backtest Runner')
    
    # Mode flags
    parser.add_argument('--report-only', action='store_true', help='Generate report from existing results')
    
    # Backtest parameters
    parser.add_argument('--strategy', type=str, help='Strategy name')
    parser.add_argument('--symbol', type=str, help='Trading symbol')
    parser.add_argument('--timeframe', type=str, help='Timeframe')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    
    # Files
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--results-file', type=str, help='Path to results file for report generation')
    
    args = parser.parse_args()
    
    runner = BacktestRunner()
    
    # Report-only mode
    if args.report_only:
        if not args.results_file:
            print("Error: --results-file is required with --report-only")
            sys.exit(1)
            
        # Load existing results
        results = runner._load_backtest_results(args.results_file)
        
        # Generate report
        runner.generate_report(results, args)
    
    # Backtest mode
    else:
        # Validate required parameters
        if not all([args.strategy, args.symbol, args.timeframe, args.start, args.end]):
            print("Error: strategy, symbol, timeframe, start, and end are required for backtesting")
            parser.print_help()
            sys.exit(1)
            
        # Run backtest
        results = runner.run_backtest(args)
        
        if results:
            # Generate report
            runner.generate_report(results, args)


if __name__ == "__main__":
    main()