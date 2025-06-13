#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Monitoring Dashboard for PyBit Bot

A web-based dashboard for monitoring trading performance in real-time.
Provides visualizations for positions, orders, P&L, and strategy metrics.
"""

import os
import json
import logging
import time
import datetime
import threading
import webbrowser
from typing import Dict, List, Any, Optional

# Optional imports - will be skipped if not installed
try:
    import dash
    from dash import dcc, html
    from dash.dependencies import Input, Output
    import plotly.graph_objs as go
    import pandas as pd
    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False
    print("Dash not installed. Run 'pip install dash plotly pandas' to enable the dashboard.")

# Set up logging
logger = logging.getLogger(__name__)


class Dashboard:
    """Dashboard for monitoring PyBit Bot trading."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the dashboard.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config = self._load_config(config_path)
        self.port = self.config.get('dashboard', {}).get('port', 8050)
        self.host = self.config.get('dashboard', {}).get('host', '127.0.0.1')
        self.auto_open = self.config.get('dashboard', {}).get('auto_open', True)
        self.refresh_interval = self.config.get('dashboard', {}).get('refresh_interval_ms', 5000)
        
        # Data storage
        self.performance_data = []
        self.positions = []
        self.orders = []
        self.trades = []
        
        # App instance
        self.app = None
        self.server_thread = None
        self.is_running = False
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Configuration dictionary
        """
        default_config = {
            'dashboard': {
                'port': 8050,
                'host': '127.0.0.1',
                'auto_open': True,
                'refresh_interval_ms': 5000,
                'log_file': 'logs/dashboard.log'
            }
        }
        
        if not config_path:
            return default_config
            
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Merge with default config
            if 'dashboard' not in config:
                config['dashboard'] = default_config['dashboard']
            else:
                for key, value in default_config['dashboard'].items():
                    if key not in config['dashboard']:
                        config['dashboard'][key] = value
                        
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            return default_config

    def _create_app(self):
        """Create the Dash application."""
        if not DASH_AVAILABLE:
            print("Cannot create dashboard: Dash not installed")
            return
            
        app = dash.Dash(__name__, title="PyBit Bot Dashboard")
        
        # Define layout
        app.layout = html.Div([
            html.H1("PyBit Bot Trading Dashboard"),
            
            html.Div([
                html.H2("Performance Overview"),
                dcc.Graph(id='equity-curve'),
                
                html.Div(id='stats-container', children=[
                    html.Div([
                        html.H4("Total P&L"),
                        html.Div(id='total-pnl', className='stat-value'),
                    ], className='stat-box'),
                    
                    html.Div([
                        html.H4("Open Positions"),
                        html.Div(id='open-positions', className='stat-value'),
                    ], className='stat-box'),
                    
                    html.Div([
                        html.H4("Today's Trades"),
                        html.Div(id='todays-trades', className='stat-value'),
                    ], className='stat-box'),
                ], className='stats-row'),
            ], className='dashboard-section'),
            
            html.Div([
                html.H2("Active Positions"),
                html.Div(id='positions-table'),
            ], className='dashboard-section'),
            
            html.Div([
                html.H2("Recent Orders"),
                html.Div(id='orders-table'),
            ], className='dashboard-section'),
            
            dcc.Interval(
                id='interval-component',
                interval=self.refresh_interval,
                n_intervals=0
            )
        ])
        
        # Define callbacks
        @app.callback(
            [Output('equity-curve', 'figure'),
             Output('total-pnl', 'children'),
             Output('open-positions', 'children'),
             Output('todays-trades', 'children'),
             Output('positions-table', 'children'),
             Output('orders-table', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            # This is where we'd update with real data
            # For now, let's just return placeholders
            
            # Equity curve
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[datetime.datetime.now() - datetime.timedelta(minutes=i) for i in range(10)],
                y=[100 + i for i in range(10)],
                mode='lines',
                name='Equity'
            ))
            fig.update_layout(
                title='Equity Curve',
                xaxis_title='Time',
                yaxis_title='USD',
                height=400
            )
            
            # Stats
            total_pnl = "+$125.45"
            open_positions = "3"
            todays_trades = "8"
            
            # Positions table
            positions_table = html.Table([
                html.Thead(
                    html.Tr([
                        html.Th("Symbol"),
                        html.Th("Side"),
                        html.Th("Size"),
                        html.Th("Entry Price"),
                        html.Th("Current Price"),
                        html.Th("Unrealized P&L"),
                    ])
                ),
                html.Tbody([
                    html.Tr([
                        html.Td("BTCUSDT"),
                        html.Td("LONG"),
                        html.Td("0.01"),
                        html.Td("29250.50"),
                        html.Td("29375.25"),
                        html.Td("+$12.47"),
                    ]),
                    html.Tr([
                        html.Td("ETHUSDT"),
                        html.Td("SHORT"),
                        html.Td("0.1"),
                        html.Td("1845.75"),
                        html.Td("1830.25"),
                        html.Td("+$15.50"),
                    ]),
                ]),
            ])
            
            # Orders table
            orders_table = html.Table([
                html.Thead(
                    html.Tr([
                        html.Th("Time"),
                        html.Th("Symbol"),
                        html.Th("Type"),
                        html.Th("Side"),
                        html.Th("Size"),
                        html.Th("Price"),
                        html.Th("Status"),
                    ])
                ),
                html.Tbody([
                    html.Tr([
                        html.Td("14:25:36"),
                        html.Td("BTCUSDT"),
                        html.Td("LIMIT"),
                        html.Td("BUY"),
                        html.Td("0.01"),
                        html.Td("29250.50"),
                        html.Td("FILLED"),
                    ]),
                    html.Tr([
                        html.Td("14:10:22"),
                        html.Td("ETHUSDT"),
                        html.Td("LIMIT"),
                        html.Td("SELL"),
                        html.Td("0.1"),
                        html.Td("1845.75"),
                        html.Td("FILLED"),
                    ]),
                ]),
            ])
            
            return fig, total_pnl, open_positions, todays_trades, positions_table, orders_table
        
        return app

    def _run_server(self):
        """Run the dashboard server in a separate thread."""
        if self.app:
            # Fix: Using app.run() instead of app.run_server()
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False
            )
    
    def start(self):
        """Start the dashboard server."""
        if not DASH_AVAILABLE:
            print("Cannot start dashboard: Dash not installed. Run 'pip install dash plotly pandas'")
            return False
            
        if self.is_running:
            logger.warning("Dashboard is already running")
            return True
            
        try:
            # Create the app
            self.app = self._create_app()
            
            # Start server in a thread
            self.server_thread = threading.Thread(target=self._run_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            self.is_running = True
            
            # Open browser
            if self.auto_open:
                url = f"http://{self.host}:{self.port}"
                print(f"Opening dashboard in browser: {url}")
                webbrowser.open(url)
            
            print(f"Dashboard running at http://{self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start dashboard: {str(e)}")
            return False
    
    def stop(self):
        """Stop the dashboard server."""
        if not self.is_running:
            return
            
        self.is_running = False
        logger.info("Dashboard stopped")


def main():
    """Main function for running the dashboard directly."""
    import argparse
    
    parser = argparse.ArgumentParser(description='PyBit Bot Dashboard')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--port', type=int, default=8050, help='Dashboard port')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Dashboard host')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    
    args = parser.parse_args()
    
    # If Dash is not available, suggest installation
    if not DASH_AVAILABLE:
        print("Dashboard requires Dash. Please install with:")
        print("pip install dash plotly pandas")
        return
    
    # Create and start dashboard
    dashboard = Dashboard(args.config)
    
    # Override with command line arguments
    if args.port:
        dashboard.port = args.port
    if args.host:
        dashboard.host = args.host
    if args.no_browser:
        dashboard.auto_open = False
    
    dashboard.start()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping dashboard...")
        dashboard.stop()


if __name__ == "__main__":
    main()