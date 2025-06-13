#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Indicator Visualization Charts

Creates interactive charts for custom indicators.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union

# Optional imports for visualization
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

logger = logging.getLogger(__name__)


class IndicatorCharts:
    """
    Creates interactive charts for custom indicators.
    
    Visualizes LuxFVGtrend, TVA, CVD, VFI, and ATR indicators
    along with price data and trading signals.
    """
    
    def __init__(self):
        """Initialize the indicator charts."""
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly not installed, visualization will not be available")
    
    def create_indicator_chart(self, df: pd.DataFrame, indicators: Dict[str, Any],
                              trades: Optional[List[Dict[str, Any]]] = None,
                              title: str = "Indicator Chart") -> Optional[go.Figure]:
        """
        Create a chart with price data, indicators, and trades.
        
        Args:
            df: DataFrame with OHLCV data
            indicators: Dictionary of indicator values
            trades: List of trade dictionaries
            title: Chart title
            
        Returns:
            Plotly figure object
        """
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly not installed, cannot create chart")
            return None
            
        # Create figure with subplots
        fig = make_subplots(
            rows=4, 
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=("Price", "Indicators", "Volume", "Trades"),
            row_heights=[0.5, 0.2, 0.15, 0.15]
        )
        
        # Add price data
        self._add_price_chart(fig, df, 1, 1)
        
        # Add indicators
        self._add_indicators(fig, df, indicators, 2, 1)
        
        # Add volume
        self._add_volume(fig, df, 3, 1)
        
        # Add trades if available
        if trades:
            self._add_trades(fig, df, trades, 4, 1)
            
            # Also mark trades on price chart
            self._mark_trades_on_price(fig, df, trades, 1, 1)
        
        # Update layout
        fig.update_layout(
            title=title,
            xaxis_rangeslider_visible=False,
            height=900,
            width=1200,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
    
    def _add_price_chart(self, fig: go.Figure, df: pd.DataFrame, row: int, col: int):
        """
        Add price chart to figure.
        
        Args:
            fig: Plotly figure
            df: DataFrame with OHLCV data
            row: Subplot row
            col: Subplot column
        """
        # Add candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df['timestamp'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name="Price"
            ),
            row=row, col=col
        )
        
        # Update axes
        fig.update_yaxes(title_text="Price", row=row, col=col)
    
    def _add_indicators(self, fig: go.Figure, df: pd.DataFrame, 
                       indicators: Dict[str, Any], row: int, col: int):
        """
        Add indicators to figure.
        
        Args:
            fig: Plotly figure
            df: DataFrame with OHLCV data
            indicators: Dictionary of indicator values
            row: Subplot row
            col: Subplot column
        """
        # Add each indicator based on what's available
        
        # LuxFVGtrend
        if 'luxfvgtrend' in indicators:
            luxfvg = indicators['luxfvgtrend']
            if isinstance(luxfvg, pd.Series) or isinstance(luxfvg, np.ndarray):
                fig.add_trace(
                    go.Scatter(