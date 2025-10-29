import pandas as pd
import numpy as np
import logging
import datetime
import os
from dotenv import load_dotenv
from angel_api import AngelOneAPI
from nse_data import NSEDataFetcher

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
logger = logging.getLogger("strategy")

class NiftyIntradayStrategy:
    def __init__(self, angel_api=None):
        self.angel_api = angel_api or AngelOneAPI()
        self.nse_data = NSEDataFetcher()
        self.historical_data = None
        self.greeks_data = None
        self.vix = None
        self.current_position = None
        self.last_signal = None
        self.last_signal_time = None
        
        # Strategy parameters from environment variables
        self.delta_threshold = float(os.getenv("DELTA_THRESHOLD", "0.5"))
        self.gamma_threshold = float(os.getenv("GAMMA_THRESHOLD", "0.1"))
        self.theta_threshold = float(os.getenv("THETA_THRESHOLD", "0.05"))
        self.vega_threshold = float(os.getenv("VEGA_THRESHOLD", "0.1"))
        self.rsi_period = int(os.getenv("RSI_PERIOD", "14"))
        self.ma_period = int(os.getenv("MA_PERIOD", "20"))
        self.vix_buy_threshold = float(os.getenv("VIX_BUY_THRESHOLD", "20"))
        self.vix_sell_threshold = float(os.getenv("VIX_SELL_THRESHOLD", "30"))
        self.stop_loss_percent = float(os.getenv("STOP_LOSS_PERCENT", "1.0"))
        self.take_profit_percent = float(os.getenv("TAKE_PROFIT_PERCENT", "2.0"))
    
    def connect(self):
        """Connect to Angel One API"""
        return self.angel_api.connect()
    
    def is_trading_hours(self):
        """Check if current time is within trading hours"""
        now = datetime.datetime.now()
        start_time = now.replace(
            hour=int(os.getenv("TRADING_START_HOUR", "9")),
            minute=int(os.getenv("TRADING_START_MINUTE", "15")),
            second=0,
            microsecond=0
        )
        end_time = now.replace(
            hour=int(os.getenv("TRADING_END_HOUR", "15")),
            minute=int(os.getenv("TRADING_END_MINUTE", "30")),
            second=0,
            microsecond=0
        )
        
        return start_time <= now <= end_time
    
    def fetch_data(self):
        """Fetch all required data for strategy execution"""
        try:
            # Fetch option Greeks data
            symbol = os.getenv("SYMBOL", "NIFTY")
            self.greeks_data = self.nse_data.get_option_greeks(symbol)
            
            if not self.greeks_data:
                logger.error("Failed to fetch Greeks data")
                return False
            
            # Extract VIX
            self.vix = self.greeks_data.get('vix', 0)
            
            # Fetch historical price data for technical indicators
            now = datetime.datetime.now()
            from_date = (now - datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            to_date = now.strftime("%Y-%m-%d %H:%M:%S")
            
            self.historical_data = self.angel_api.get_historical_data(
                symbol,
                os.getenv("EXCHANGE", "NSE"),
                "FIFTEEN_MINUTE",
                from_date,
                to_date
            )
            
            if self.historical_data is None or self.historical_data.empty:
                logger.error("Failed to fetch historical data")
                return False
            
            logger.info("Successfully fetched all required data")
            return True
            
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            return False
    
    def calculate_indicators(self):
        """Calculate technical indicators"""
        if self.historical_data is None or self.historical_data.empty:
            logger.error("Historical data not available")
            return False
        
        try:
            # Calculate RSI
            delta = self.historical_data['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=self.rsi_period).mean()
            avg_loss = loss.rolling(window=self.rsi_period).mean()
            
            rs = avg_gain / avg_loss
            self.historical_data['rsi'] = 100 - (100 / (1 + rs))
            
            # Calculate Moving Average
            self.historical_data['ma'] = self.historical_data['close'].rolling(window=self.ma_period).mean()
            
            logger.info("Successfully calculated technical indicators")
            return True
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            return False
    
    def generate_signal(self):
        """Generate trading signal based on strategy conditions"""
        if not self.is_trading_hours():
            logger.info("Outside trading hours, no signal generated")
            return None
        
        if not self.greeks_data or not self.historical_data.iloc[-1].notna().all():
            logger.error("Data not available for signal generation")
            return None
        
        try:
            # Get latest price and indicators
            latest_data = self.historical_data.iloc[-1]
            current_price = latest_data['close']
            current_rsi = latest_data['rsi']
            current_ma = latest_data['ma']
            
            # Get Greeks data
            call_delta = self.greeks_data['call']['delta']
            call_gamma = self.greeks_data['call']['gamma']
            call_theta = self.greeks_data['call']['theta']
            call_vega = self.greeks_data['call']['vega']
            
            put_delta = self.greeks_data['put']['delta']
            put_gamma = self.greeks_data['put']['gamma']
            put_theta = self.greeks_data['put']['theta']
            put_vega = self.greeks_data['put']['vega']
            
            # Check buy conditions
            # Delta-Gamma Filter: Buy Call options when Delta > 0.5 && Gamma > 0.1 && RSI > 50 && Price > MA(20)
            delta_gamma_buy = (call_delta > self.delta_threshold and 
                              call_gamma > self.gamma_threshold and 
                              current_rsi > 50 and 
                              current_price > current_ma)
            
            # Theta-Vega Confirmation: Confirm trade when Theta < 0.05 && Vega > 0.1 (for Buy)
            theta_vega_buy = (call_theta < self.theta_threshold and 
                             call_vega > self.vega_threshold)
            
            # Volatility Filter: Trade only when India VIX < 20 (for Buy)
            vix_buy = self.vix < self.vix_buy_threshold
            
            # Check sell conditions
            # Delta-Gamma Filter: Sell Put options when Delta < -0.5 && Gamma < -0.1 && RSI < 50 && Price < MA(20)
            delta_gamma_sell = (put_delta < -self.delta_threshold and 
                               put_gamma < -self.gamma_threshold and 
                               current_rsi < 50 and 
                               current_price < current_ma)
            
            # Theta-Vega Confirmation: Confirm trade when Theta > 0.05 && Vega < -0.1 (for Sell)
            theta_vega_sell = (put_theta > self.theta_threshold and 
                              put_vega < -self.vega_threshold)
            
            # Volatility Filter: Trade only when India VIX > 30 (for Sell)
            vix_sell = self.vix > self.vix_sell_threshold
            
            # Generate signal
            if delta_gamma_buy and theta_vega_buy and vix_buy:
                signal = "BUY"
                logger.info(f"BUY signal generated: Delta={call_delta}, Gamma={call_gamma}, Theta={call_theta}, Vega={call_vega}, RSI={current_rsi}, VIX={self.vix}")
            elif delta_gamma_sell and theta_vega_sell and vix_sell:
                signal = "SELL"
                logger.info(f"SELL signal generated: Delta={put_delta}, Gamma={put_gamma}, Theta={put_theta}, Vega={put_vega}, RSI={current_rsi}, VIX={self.vix}")
            else:
                signal = None
                logger.info("No signal generated")
            
            # Update last signal
            if signal:
                self.last_signal = signal
                self.last_signal_time = datetime.datetime.now()
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating signal: {str(e)}")
            return None
    
    def execute_trade(self, signal):
        """Execute trade based on signal"""
        if not signal:
            return False
        
        try:
            # Check current positions
            positions = self.angel_api.get_positions()
            has_position = False
            symbol = os.getenv("SYMBOL", "NIFTY")
            exchange = os.getenv("EXCHANGE", "NSE")
            quantity = int(os.getenv("QUANTITY", "1"))
            
            if positions:
                for position in positions:
                    if position['tradingsymbol'] == symbol:
                        has_position = True
                        self.current_position = position
                        break
            
            # Execute trade based on signal
            if signal == "BUY" and (not has_position or self.current_position['netqty'] <= 0):
                # Place buy order
                order_id = self.angel_api.place_order(
                    "BUY",
                    symbol,
                    exchange,
                    quantity
                )
                
                if order_id:
                    logger.info(f"Buy order placed successfully, Order ID: {order_id}")
                    return True
                else:
                    logger.error("Failed to place buy order")
                    return False
                    
            elif signal == "SELL" and (not has_position or self.current_position['netqty'] >= 0):
                # Place sell order
                order_id = self.angel_api.place_order(
                    "SELL",
                    symbol,
                    exchange,
                    quantity
                )
                
                if order_id:
                    logger.info(f"Sell order placed successfully, Order ID: {order_id}")
                    return True
                else:
                    logger.error("Failed to place sell order")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            return False
    
    def run_strategy(self):
        """Run the complete strategy workflow"""
        try:
            # Connect to Angel One API
            if not self.angel_api.is_connected:
                if not self.connect():
                    logger.error("Failed to connect to Angel One API")
                    return False
            
            # Fetch data
            if not self.fetch_data():
                logger.error("Failed to fetch required data")
                return False
            
            # Calculate indicators
            if not self.calculate_indicators():
                logger.error("Failed to calculate indicators")
                return False
            
            # Generate signal
            signal = self.generate_signal()
            
            # Execute trade if signal is generated
            if signal:
                if self.execute_trade(signal):
                    logger.info(f"Successfully executed {signal} trade")
                    return True
                else:
                    logger.error(f"Failed to execute {signal} trade")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error running strategy: {str(e)}")
            return False
    
    def get_strategy_status(self):
        """Get current strategy status"""
        status = {
            "connected": self.angel_api.is_connected,
            "last_signal": self.last_signal,
            "last_signal_time": self.last_signal_time,
            "current_position": self.current_position,
            "vix": self.vix
        }
        
        if self.historical_data is not None and not self.historical_data.empty:
            latest_data = self.historical_data.iloc[-1]
            status.update({
                "current_price": latest_data['close'],
                "current_rsi": latest_data['rsi'],
                "current_ma": latest_data['ma']
            })
        
        if self.greeks_data:
            status.update({
                "call_delta": self.greeks_data['call']['delta'],
                "call_gamma": self.greeks_data['call']['gamma'],
                "call_theta": self.greeks_data['call']['theta'],
                "call_vega": self.greeks_data['call']['vega'],
                "put_delta": self.greeks_data['put']['delta'],
                "put_gamma": self.greeks_data['put']['gamma'],
                "put_theta": self.greeks_data['put']['theta'],
                "put_vega": self.greeks_data['put']['vega']
            })
        
        return status