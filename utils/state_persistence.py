"""
State persistence utilities for storing and loading strategy and order state.
Uses SQLite for robust, atomic storage of state data.
"""

import os
import json
import sqlite3
import logging
import time
from typing import Dict, Optional, Any, List, Union
from contextlib import contextmanager


class StatePersistence:
    """
    Handles persistence of application state using SQLite.
    """
    
    def __init__(self, db_path: str = "state.db"):
        """
        Initialize the state persistence manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Initialize the database
        self._init_db()
    
    def _init_db(self) -> None:
        """
        Initialize the database schema if it doesn't exist.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Create state table if it doesn't exist
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS state (
                    component TEXT PRIMARY KEY,
                    data TEXT,
                    timestamp INTEGER
                )
                ''')
                
                # Create audit log table if it doesn't exist
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS state_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component TEXT,
                    data TEXT,
                    timestamp INTEGER
                )
                ''')
                
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {str(e)}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections.
        
        Yields:
            SQLite connection object
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            yield conn
        except sqlite3.Error as e:
            self.logger.error(f"Database connection error: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def save_state(self, component: str, state: Dict) -> bool:
        """
        Save state data for a component.
        
        Args:
            component: Component identifier (e.g., 'strategy_manager')
            state: Dictionary containing state data
            
        Returns:
            Boolean indicating success
        """
        try:
            # Convert state to JSON
            state_json = json.dumps(state)
            timestamp = int(time.time())
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Insert or replace state
                cursor.execute(
                    "INSERT OR REPLACE INTO state (component, data, timestamp) VALUES (?, ?, ?)",
                    (component, state_json, timestamp)
                )
                
                # Also log to audit table
                cursor.execute(
                    "INSERT INTO state_audit (component, data, timestamp) VALUES (?, ?, ?)",
                    (component, state_json, timestamp)
                )
                
                conn.commit()
                
            self.logger.debug(f"Saved state for component: {component}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving state for {component}: {str(e)}")
            return False
    
    def load_state(self, component: str) -> Optional[Dict]:
        """
        Load state data for a component.
        
        Args:
            component: Component identifier (e.g., 'strategy_manager')
            
        Returns:
            Dictionary containing state data, or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Query the state
                cursor.execute(
                    "SELECT data FROM state WHERE component = ?",
                    (component,)
                )
                
                row = cursor.fetchone()
                if row is None:
                    return None
                
                # Parse JSON
                state = json.loads(row[0])
                return state
                
        except Exception as e:
            self.logger.error(f"Error loading state for {component}: {str(e)}")
            return None
    
    def delete_state(self, component: str) -> bool:
        """
        Delete state data for a component.
        
        Args:
            component: Component identifier (e.g., 'strategy_manager')
            
        Returns:
            Boolean indicating success
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Delete the state
                cursor.execute(
                    "DELETE FROM state WHERE component = ?",
                    (component,)
                )
                
                conn.commit()
                
            self.logger.debug(f"Deleted state for component: {component}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting state for {component}: {str(e)}")
            return False
    
    def get_all_components(self) -> List[str]:
        """
        Get a list of all components with saved state.
        
        Returns:
            List of component identifiers
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Query all components
                cursor.execute("SELECT component FROM state")
                
                components = [row[0] for row in cursor.fetchall()]
                return components
                
        except Exception as e:
            self.logger.error(f"Error getting components: {str(e)}")
            return []
    
    def get_state_history(self, component: str, limit: int = 10) -> List[Dict]:
        """
        Get the history of state changes for a component.
        
        Args:
            component: Component identifier
            limit: Maximum number of history entries to return
            
        Returns:
            List of dictionaries with state history
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Query the state history
                cursor.execute(
                    "SELECT data, timestamp FROM state_audit WHERE component = ? ORDER BY timestamp DESC LIMIT ?",
                    (component, limit)
                )
                
                history = []
                for row in cursor.fetchall():
                    state = json.loads(row[0])
                    timestamp = row[1]
                    history.append({
                        'state': state,
                        'timestamp': timestamp
                    })
                
                return history
                
        except Exception as e:
            self.logger.error(f"Error getting state history for {component}: {str(e)}")
            return []
    
    def clear_all(self) -> bool:
        """
        Clear all state data.
        
        Returns:
            Boolean indicating success
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Clear state table
                cursor.execute("DELETE FROM state")
                
                # Don't clear audit table to maintain history
                
                conn.commit()
                
            self.logger.info("Cleared all state data")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing all state data: {str(e)}")
            return False