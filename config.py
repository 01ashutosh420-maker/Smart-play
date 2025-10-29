import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Angel One API credentials
API_KEY = os.getenv("API_KEY", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_PASSWORD = os.getenv("CLIENT_PASSWORD", "")
TOTP_KEY = os.getenv("TOTP_KEY", "")

# Trading parameters
SYMBOL = "NIFTY"
EXCHANGE = "NSE"
TIMEFRAME = 15  # minutes
QUANTITY = 50  # Number of shares/contracts to trade

# Strategy parameters
DELTA_THRESHOLD = 0.5
GAMMA_THRESHOLD = 0.1
THETA_THRESHOLD = 0.05
VEGA_THRESHOLD = 0.1
RSI_PERIOD = 14
MA_PERIOD = 20
VIX_BUY_THRESHOLD = 20
VIX_SELL_THRESHOLD = 30

# Risk management
STOP_LOSS_PERCENT = 1.0
TAKE_PROFIT_PERCENT = 2.0

# Trading hours
TRADING_START_HOUR = 9
TRADING_START_MINUTE = 30
TRADING_END_HOUR = 14
TRADING_END_MINUTE = 45

# NSE website URLs
NSE_OPTION_CHAIN_URL = "https://www.nseindia.com/option-chain"
NSE_INDIA_VIX_URL = "https://www.nseindia.com/market-data/india-vix"

# Database settings
DB_PATH = "trading_data.db"

# Logging settings
LOG_LEVEL = "INFO"
LOG_FILE = "trading_app.log"