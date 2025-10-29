import logging
import pyotp
import os
# Mock SmartConnect class for development
class SmartConnect:
    def __init__(self, api_key=None):
        self.api_key = api_key
        
    def generateSession(self, clientCode, password, totp):
        return {"status": True, "message": "SUCCESS", "data": {"jwtToken": "mock_token", "refreshToken": "mock_refresh"}}
        
    def getProfile(self, refreshToken):
        return {"status": True, "data": {"name": "Test User", "email": "test@example.com"}}
        
    def generateToken(self, refreshToken):
        return {"status": True, "data": {"jwtToken": "mock_token"}}
        
    def terminateSession(self, clientCode):
        return {"status": True, "message": "User logged out successfully"}
import pandas as pd
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "trading_app.log")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=LOG_FILE
)
logger = logging.getLogger("angel_api")

class AngelOneAPI:
    def __init__(self):
        self.api = None
        self.session_id = None
        self.refresh_token = None
        self.feed_token = None
        self.is_connected = False
    
    def connect(self, api_key=None, client_id=None, password=None, totp_key=None):
        """Connect to Angel One API using credentials from config or parameters"""
        try:
            # Use provided credentials or get from environment variables
            api_key = api_key or os.getenv("API_KEY", "")
            client_id = client_id or os.getenv("CLIENT_ID", "")
            client_password = password or os.getenv("CLIENT_PASSWORD", "")
            totp_key = totp_key or os.getenv("TOTP_KEY", "")
            
            # Generate TOTP
            totp = pyotp.TOTP(totp_key)
            totp_token = totp.now()
            
            # Initialize SmartConnect
            self.api = SmartConnect(api_key=api_key)
            
            # Login to Angel One
            data = self.api.generateSession(client_id, client_password, totp_token)
            self.refresh_token = data['data']['refreshToken']
            self.session_id = data['data']['sessionId']
            self.feed_token = self.api.getfeedToken()
            
            if self.session_id:
                self.is_connected = True
                logger.info("Successfully connected to Angel One API")
                return True
            else:
                logger.error("Failed to connect to Angel One API")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to Angel One API: {str(e)}")
            return False
    
    def get_profile(self):
        """Get user profile information"""
        if not self.is_connected:
            logger.error("Not connected to Angel One API")
            return None
        
        try:
            profile = self.api.getProfile()
            return profile
        except Exception as e:
            logger.error(f"Error getting profile: {str(e)}")
            return None
    
    def get_ltp(self, symbol, exchange):
        """Get Last Traded Price for a symbol"""
        if not self.is_connected:
            logger.error("Not connected to Angel One API")
            return None
        
        try:
            ltp_data = self.api.ltpData(exchange, symbol, "")
            return ltp_data
        except Exception as e:
            logger.error(f"Error getting LTP for {symbol}: {str(e)}")
            return None
    
    def place_order(self, transaction_type, symbol, exchange, quantity, price=0, order_type="MARKET"):
        """Place an order
        
        Args:
            transaction_type: "BUY" or "SELL"
            symbol: Trading symbol
            exchange: Exchange (NSE, BSE, etc.)
            quantity: Number of shares/contracts
            price: Price (for limit orders)
            order_type: "MARKET" or "LIMIT"
        """
        if not self.is_connected:
            logger.error("Not connected to Angel One API")
            return None
        
        try:
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": self._get_token(symbol, exchange),
                "transactiontype": transaction_type,
                "exchange": exchange,
                "ordertype": order_type,
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": quantity
            }
            
            if order_type == "LIMIT":
                order_params["price"] = price
                
            order_id = self.api.placeOrder(order_params)
            logger.info(f"Placed {transaction_type} order for {symbol}, Order ID: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return None
    
    def get_order_status(self, order_id):
        """Get status of an order"""
        if not self.is_connected:
            logger.error("Not connected to Angel One API")
            return None
        
        try:
            orders = self.api.orderBook()
            for order in orders:
                if order['orderid'] == order_id:
                    return order
            return None
        except Exception as e:
            logger.error(f"Error getting order status: {str(e)}")
            return None
    
    def get_positions(self):
        """Get current positions"""
        if not self.is_connected:
            logger.error("Not connected to Angel One API")
            return None
        
        try:
            positions = self.api.position()
            return positions
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            return None
    
    def get_historical_data(self, symbol, exchange, interval, from_date, to_date):
        """Get historical candle data
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (NSE, BSE, etc.)
            interval: Candle interval (ONE_MINUTE, FIFTEEN_MINUTE, etc.)
            from_date: Start date (format: "YYYY-MM-DD HH:MM:SS")
            to_date: End date (format: "YYYY-MM-DD HH:MM:SS")
        """
        if not self.is_connected:
            logger.error("Not connected to Angel One API")
            return None
        
        try:
            token = self._get_token(symbol, exchange)
            if not token:
                return None
                
            historical_data = self.api.getCandleData({
                "exchange": exchange,
                "symboltoken": token,
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            })
            
            if historical_data and 'data' in historical_data:
                df = pd.DataFrame(historical_data['data'], 
                                 columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                return df
            return None
            
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return None
    
    def _get_token(self, symbol, exchange):
        """Get token for a symbol"""
        try:
            search_results = self.api.searchscrip(exchange, symbol)
            if search_results and 'data' in search_results:
                for item in search_results['data']:
                    if item['tradingsymbol'] == symbol:
                        return item['token']
            return None
        except Exception as e:
            logger.error(f"Error getting token for {symbol}: {str(e)}")
            return None
    
    def disconnect(self):
        """Disconnect from Angel One API"""
        if self.api:
            try:
                self.api.terminateSession(os.getenv("CLIENT_ID", ""))
                self.is_connected = False
                logger.info("Disconnected from Angel One API")
            except Exception as e:
                logger.error(f"Error disconnecting from Angel One API: {str(e)}")