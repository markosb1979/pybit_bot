#!/usr/bin/env python3
"""
Environment setup script for Bybit Trading Bot
"""

import os
import sys
from pathlib import Path


def create_directory_structure():
    """Create the required directory structure"""
    directories = [
        "pybit_bot",
        "pybit_bot/core",
        "pybit_bot/trading", 
        "pybit_bot/strategies",
        "pybit_bot/indicators",
        "pybit_bot/websocket",
        "pybit_bot/utils",
        "logs",
        "data",
        "backups"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")


def create_env_template():
    """Create .env template if it doesn't exist"""
    env_template = """# Bybit API Credentials (TESTNET)
BYBIT_API_KEY=your_testnet_api_key_here
BYBIT_API_SECRET=your_testnet_api_secret_here
BYBIT_TESTNET=true

# Trading Configuration
TRADING_SYMBOL=BTCUSDT
POSITION_SIZE=0.01
STOP_LOSS_PCT=0.02
TAKE_PROFIT_PCT=0.04

# Risk Management
MAX_DAILY_LOSS=0.05
MAX_OPEN_POSITIONS=3
MIN_BALANCE_THRESHOLD=100.0
"""
    
    env_file = Path('.env')
    if not env_file.exists():
        with open(env_file, 'w') as f:
            f.write(env_template)
        print("✅ Created .env template")
        print("🔒 Please edit .env with your API credentials")
    else:
        print("⚠️  .env file already exists")


def check_python_version():
    """Check Python version compatibility"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} is not compatible")
        print("   Please use Python 3.8 or higher")
        return False


def check_required_packages():
    """Check if required packages can be imported"""
    required_packages = [
        'requests',
        'json',
        'asyncio',
        'pathlib',
        'datetime',
        'time',
        'logging',
        'hmac',
        'hashlib'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} (missing)")
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("   Run: pip install -r requirements.txt")
        return False
    
    return True


def main():
    """Main setup function"""
    print("Bybit Trading Bot - Environment Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create directory structure
    print("\nCreating directory structure...")
    create_directory_structure()
    
    # Create .env template
    print("\nSetting up configuration...")
    create_env_template()
    
    # Check packages
    print("\nChecking required packages...")
    packages_ok = check_required_packages()
    
    # Final status
    print("\n" + "=" * 40)
    if packages_ok:
        print("✅ Environment setup complete!")
        print("\nNext steps:")
        print("1. Edit .env with your Bybit testnet API credentials")
        print("2. Run: python test_bot_comprehensive.py")
    else:
        print("⚠️  Environment setup incomplete")
        print("1. Install missing packages: pip install -r requirements.txt")
        print("2. Edit .env with your API credentials")
        print("3. Run: python test_bot_comprehensive.py")


if __name__ == "__main__":
    main()