"""
Configuration loader module to centralize config loading logic
"""

import json
import os
import glob
from typing import Dict, Any, List

from .logger import Logger

class ConfigLoader:
    """
    Centralized configuration loading class
    Loads and validates configuration from JSON files
    """
    
    def __init__(self, config_dir: str = None, logger=None):
        """
        Initialize with config directory path
        
        Args:
            config_dir: Path to configuration directory
            logger: Optional logger instance
        """
        self.logger = logger or Logger("ConfigLoader")
        self.logger.debug(f"→ __init__(config_dir={config_dir})")
        
        # Use the known Google Drive directory path as our primary choice
        primary_config_dir = r"G:\My Drive\MyBotFolder\Bybit\pybit_bot\pybit_bot\configs"
        
        if os.path.exists(primary_config_dir) and os.path.isdir(primary_config_dir):
            # Use the primary directory that we know contains the config files
            self.config_dir = primary_config_dir
            self.logger.info(f"Using primary config directory: {self.config_dir}")
        elif config_dir and os.path.exists(config_dir) and os.path.isdir(config_dir):
            # If that fails, use the provided directory if it exists
            self.config_dir = config_dir
            self.logger.info(f"Using provided config directory: {self.config_dir}")
        else:
            # If all else fails, try to find the configs in a few common locations
            fallback_locations = [
                os.path.join(os.getcwd(), "pybit_bot", "configs"),
                os.path.join(os.getcwd(), "configs"),
                os.path.dirname(os.path.abspath(__file__)).replace("utils", "configs")
            ]
            
            for location in fallback_locations:
                if os.path.exists(location) and os.path.isdir(location):
                    self.config_dir = location
                    self.logger.info(f"Using fallback config directory: {self.config_dir}")
                    break
            else:
                # Last resort - create a configs directory in the current directory
                self.config_dir = os.path.join(os.getcwd(), "configs")
                os.makedirs(self.config_dir, exist_ok=True)
                self.logger.warning(f"Created new config directory: {self.config_dir}")
        
        self.logger.info(f"Using config from: {self.config_dir}")
        
        # Initialize empty config store
        self.config = {}
        self.config_files = []
        
        self.logger.debug(f"← __init__ completed")
    
    def load_configs(self) -> Dict[str, Any]:
        """
        Load all configuration files from the config directory
        
        Returns:
            Dictionary with all configurations merged
        """
        self.logger.debug(f"→ load_configs()")
        
        try:
            # Find all JSON files in the config directory
            config_files = glob.glob(os.path.join(self.config_dir, "*.json"))
            self.config_files = [os.path.basename(f) for f in config_files]
            self.logger.info(f"Found config files: {self.config_files}")
            print(f"Loading configs from: {self.config_dir}")
            print(f"Config files found: {self.config_files}")
            
            # Track if we've loaded all required files
            required_files = ['general.json', 'indicators.json', 'strategy.json', 'execution.json']
            loaded_required_files = []
            
            # Load each config file
            for config_file in config_files:
                # Skip config.json if it exists (not needed)
                if os.path.basename(config_file) == 'config.json':
                    continue
                    
                config_name = os.path.basename(config_file).split('.')[0]  # Get filename without extension
                
                try:
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                        
                    # Add to config under the file's name
                    self.config[config_name] = config_data
                    
                    # Log detailed config content at debug level
                    self.logger.debug(f"Loaded {config_name}.json: {json.dumps(config_data, indent=2)}")
                    
                    # Log at info level
                    self.logger.info(f"Loaded config from {config_name}.json")
                    
                    # Check if this is a required file
                    if f"{config_name}.json" in required_files:
                        loaded_required_files.append(f"{config_name}.json")
                except Exception as e:
                    self.logger.error(f"Error loading {config_file}: {str(e)}")
            
            # Check if all required files were loaded
            missing_files = [f for f in required_files if f not in loaded_required_files]
            if missing_files:
                self.logger.warning(f"Missing required config files: {missing_files}")
            
            if not self.config:
                raise RuntimeError(f"No configuration files found in {self.config_dir}")
            
            self.logger.debug(f"← load_configs returned config with {len(self.config)} sections")
            return self.config
            
        except Exception as e:
            self.logger.error(f"Failed to load configurations: {str(e)}")
            print(f"ERROR loading configs: {str(e)}")
            self.logger.debug(f"← load_configs returned empty config (error)")
            raise RuntimeError(f"Failed to load configurations: {str(e)}")
    
    def get(self, section: str = None, subsection: str = None, key: str = None, default: Any = None) -> Any:
        """
        Get configuration value with dot notation and fallback
        
        Args:
            section: Main config section (general, strategy, etc.)
            subsection: Optional subsection
            key: Optional specific key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        self.logger.debug(f"→ get(section={section}, subsection={subsection}, key={key}, default={default})")
        
        if not self.config:
            self.load_configs()
            
        try:
            # Get section
            if section is None:
                self.logger.debug(f"← get returned full config")
                return self.config
                
            section_data = self.config.get(section, {})
            
            # Get subsection if requested
            if subsection is not None:
                section_data = section_data.get(subsection, {})
                
                # Get key if requested
                if key is not None:
                    result = section_data.get(key, default)
                    self.logger.debug(f"← get returned {result} for {section}.{subsection}.{key}")
                    return result
                else:
                    self.logger.debug(f"← get returned subsection {section}.{subsection}")
                    return section_data
            else:
                # No subsection, return section or key in section
                if key is not None:
                    result = section_data.get(key, default)
                    self.logger.debug(f"← get returned {result} for {section}.{key}")
                    return result
                else:
                    self.logger.debug(f"← get returned section {section}")
                    return section_data
                    
        except Exception as e:
            self.logger.error(f"Error getting config value: {str(e)}")
            self.logger.debug(f"← get returned default {default} (error)")
            return default