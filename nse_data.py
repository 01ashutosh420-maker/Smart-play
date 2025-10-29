import requests
import pandas as pd
import json
import logging
import time
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

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
logger = logging.getLogger("nse_data")

class NSEDataFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.cookies = {}
        self.option_chain_data = None
        self.vix_data = None
    
    def _get_cookies(self):
        """Get cookies from NSE website"""
        try:
            response = self.session.get("https://www.nseindia.com/", headers=self.headers, timeout=10)
            if response.status_code == 200:
                self.cookies = response.cookies
                logger.info("Successfully obtained cookies from NSE website")
                return True
            else:
                logger.error(f"Failed to get cookies. Status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error getting cookies: {str(e)}")
            return False
    
    def fetch_option_chain(self, symbol="NIFTY"):
        """Fetch option chain data from NSE website"""
        if not self.cookies:
            if not self._get_cookies():
                return None
        
        try:
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            response = self.session.get(
                url,
                headers=self.headers,
                cookies=self.cookies,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.option_chain_data = data
                logger.info(f"Successfully fetched option chain data for {symbol}")
                return data
            else:
                logger.error(f"Failed to fetch option chain. Status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching option chain: {str(e)}")
            return None
    
    def fetch_india_vix(self):
        """Fetch India VIX data from NSE website"""
        if not self.cookies:
            if not self._get_cookies():
                return None
        
        try:
            url = "https://www.nseindia.com/api/marketStatus"
            response = self.session.get(
                url,
                headers=self.headers,
                cookies=self.cookies,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                for index in data.get('marketState', []):
                    if index.get('index') == 'India VIX':
                        self.vix_data = float(index.get('last', 0))
                        logger.info(f"Successfully fetched India VIX: {self.vix_data}")
                        return self.vix_data
                
                logger.error("India VIX data not found in response")
                return None
            else:
                logger.error(f"Failed to fetch India VIX. Status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching India VIX: {str(e)}")
            return None
    
    def extract_greeks_data(self, expiry_date=None, strike_price=None):
        """Extract option Greeks data from option chain
        
        Args:
            expiry_date: Option expiry date (format: "DD-MM-YYYY")
            strike_price: Strike price to filter
            
        Returns:
            Dictionary with call and put option Greeks
        """
        if not self.option_chain_data:
            logger.error("Option chain data not available")
            return None
        
        try:
            records = self.option_chain_data.get('records', {})
            data = records.get('data', [])
            
            # If expiry date is not provided, use the nearest expiry
            if not expiry_date:
                expiry_dates = records.get('expiryDates', [])
                if expiry_dates:
                    expiry_date = expiry_dates[0]
                else:
                    logger.error("No expiry dates found in option chain data")
                    return None
            
            # Filter by expiry date
            filtered_data = [item for item in data if item.get('expiryDate') == expiry_date]
            
            # If strike price is provided, filter by strike price
            if strike_price:
                filtered_data = [item for item in filtered_data if item.get('strikePrice') == strike_price]
            
            # If no strike price is provided, use ATM option
            if not strike_price and filtered_data:
                underlying_value = records.get('underlyingValue', 0)
                filtered_data.sort(key=lambda x: abs(x.get('strikePrice', 0) - underlying_value))
                filtered_data = [filtered_data[0]]
            
            if not filtered_data:
                logger.error("No data found for the specified filters")
                return None
            
            # Extract Greeks data
            greeks_data = {}
            for item in filtered_data:
                call_option = item.get('CE', {})
                put_option = item.get('PE', {})
                
                greeks_data = {
                    'call': {
                        'delta': call_option.get('delta', 0),
                        'gamma': call_option.get('gamma', 0),
                        'theta': call_option.get('theta', 0),
                        'vega': call_option.get('vega', 0),
                        'iv': call_option.get('impliedVolatility', 0),
                        'ltp': call_option.get('lastPrice', 0),
                        'change': call_option.get('change', 0),
                        'oi': call_option.get('openInterest', 0),
                        'volume': call_option.get('totalTradedVolume', 0)
                    },
                    'put': {
                        'delta': put_option.get('delta', 0),
                        'gamma': put_option.get('gamma', 0),
                        'theta': put_option.get('theta', 0),
                        'vega': put_option.get('vega', 0),
                        'iv': put_option.get('impliedVolatility', 0),
                        'ltp': put_option.get('lastPrice', 0),
                        'change': put_option.get('change', 0),
                        'oi': put_option.get('openInterest', 0),
                        'volume': put_option.get('totalTradedVolume', 0)
                    },
                    'strike_price': item.get('strikePrice', 0),
                    'expiry_date': item.get('expiryDate', '')
                }
                
                # Only return the first match
                break
            
            return greeks_data
            
        except Exception as e:
            logger.error(f"Error extracting Greeks data: {str(e)}")
            return None
    
    def get_option_greeks(self, symbol="NIFTY", expiry_date=None, strike_price=None):
        """Get option Greeks data
        
        Args:
            symbol: Index symbol (NIFTY, BANKNIFTY, etc.)
            expiry_date: Option expiry date (format: "DD-MM-YYYY")
            strike_price: Strike price to filter
            
        Returns:
            Dictionary with call and put option Greeks
        """
        # Fetch option chain data
        self.fetch_option_chain(symbol)
        
        # Extract Greeks data
        greeks_data = self.extract_greeks_data(expiry_date, strike_price)
        
        # Fetch India VIX
        vix = self.fetch_india_vix()
        if vix:
            if greeks_data:
                greeks_data['vix'] = vix
        
        return greeks_data