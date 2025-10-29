import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import datetime
import os
import json
import logging
from dotenv import load_dotenv

# Import custom modules
from angel_api import AngelOneAPI
from nse_data import NSEDataFetcher
from strategy import NiftyIntradayStrategy

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
logger = logging.getLogger("app")

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'strategy' not in st.session_state:
    st.session_state.strategy = None
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'signals' not in st.session_state:
    st.session_state.signals = []
if 'auto_trading' not in st.session_state:
    st.session_state.auto_trading = False

# Page configuration
st.set_page_config(
    page_title="Nifty Intraday Trading Strategy",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #333;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .card {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    .buy-signal {
        color: #4CAF50;
        font-weight: bold;
    }
    .sell-signal {
        color: #F44336;
        font-weight: bold;
    }
    .neutral {
        color: #9E9E9E;
    }
    .metric-label {
        font-weight: bold;
        color: #555;
    }
    .metric-value {
        font-size: 1.2rem;
        font-weight: bold;
    }
    .footer {
        text-align: center;
        margin-top: 2rem;
        color: #666;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

def login_page():
    """Login page for authentication"""
    st.markdown('<div class="main-header">Nifty Intraday Trading Strategy</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Login</div>', unsafe_allow_html=True)
    
    # Check if credentials are already in environment variables
    api_key = os.getenv("API_KEY", "")
    client_id = os.getenv("CLIENT_ID", "")
    client_password = os.getenv("CLIENT_PASSWORD", "")
    totp_key = os.getenv("TOTP_KEY", "")
    
    # Input fields for credentials
    api_key_input = st.text_input("API Key", value=api_key, type="password")
    client_id_input = st.text_input("Client ID", value=client_id)
    client_password_input = st.text_input("Password", value=client_password, type="password")
    totp_key_input = st.text_input("TOTP Key", value=totp_key, type="password")
    
    save_credentials = st.checkbox("Save credentials for future use", value=True)
    
    if st.button("Login"):
        with st.spinner("Connecting to Angel One..."):
            # Initialize strategy
            strategy = NiftyIntradayStrategy()
            
            # Set credentials
            os.environ["API_KEY"] = api_key_input
            os.environ["CLIENT_ID"] = client_id_input
            os.environ["CLIENT_PASSWORD"] = client_password_input
            os.environ["TOTP_KEY"] = totp_key_input
            
            # Save credentials if checked
            if save_credentials:
                with open(".env", "w") as f:
                    f.write(f"API_KEY={api_key_input}\n")
                    f.write(f"CLIENT_ID={client_id_input}\n")
                    f.write(f"CLIENT_PASSWORD={client_password_input}\n")
                    f.write(f"TOTP_KEY={totp_key_input}\n")
            
            # Connect to Angel One API
            if strategy.connect():
                st.session_state.strategy = strategy
                st.session_state.authenticated = True
                st.success("Successfully connected to Angel One API!")
                st.experimental_rerun()
            else:
                st.error("Failed to connect to Angel One API. Please check your credentials.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def dashboard_page():
    """Main dashboard page after authentication"""
    st.markdown('<div class="main-header">Nifty Intraday Trading Strategy</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown('<div class="sub-header">Controls</div>', unsafe_allow_html=True)
        
        # Manual data refresh button
        if st.button("Refresh Data"):
            with st.spinner("Fetching data..."):
                refresh_data()
        
        # Auto-trading toggle
        auto_trading = st.checkbox("Enable Auto Trading", value=st.session_state.auto_trading)
        if auto_trading != st.session_state.auto_trading:
            st.session_state.auto_trading = auto_trading
            if auto_trading:
                st.success("Auto trading enabled!")
            else:
                st.warning("Auto trading disabled!")
        
        # Strategy parameters
        st.markdown('<div class="sub-header">Strategy Parameters</div>', unsafe_allow_html=True)
        
        delta_threshold = st.slider("Delta Threshold", 0.1, 1.0, float(os.getenv("DELTA_THRESHOLD", "0.5")), 0.1)
        gamma_threshold = st.slider("Gamma Threshold", 0.01, 0.5, float(os.getenv("GAMMA_THRESHOLD", "0.1")), 0.01)
        theta_threshold = st.slider("Theta Threshold", 0.01, 0.2, float(os.getenv("THETA_THRESHOLD", "0.05")), 0.01)
        vega_threshold = st.slider("Vega Threshold", 0.01, 0.5, float(os.getenv("VEGA_THRESHOLD", "0.1")), 0.01)
        
        if st.button("Update Parameters"):
            # Update environment variables
            os.environ["DELTA_THRESHOLD"] = str(delta_threshold)
            os.environ["GAMMA_THRESHOLD"] = str(gamma_threshold)
            os.environ["THETA_THRESHOLD"] = str(theta_threshold)
            os.environ["VEGA_THRESHOLD"] = str(vega_threshold)
            
            # Update .env file
            with open(".env", "a") as f:
                f.write(f"DELTA_THRESHOLD={delta_threshold}\n")
                f.write(f"GAMMA_THRESHOLD={gamma_threshold}\n")
                f.write(f"THETA_THRESHOLD={theta_threshold}\n")
                f.write(f"VEGA_THRESHOLD={vega_threshold}\n")
                
            st.success("Parameters updated!")
        
        # Logout button
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.strategy = None
            st.experimental_rerun()
    
    # Main content area - split into columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Market data and signals
        st.markdown('<div class="sub-header">Market Data & Signals</div>', unsafe_allow_html=True)
        
        if st.session_state.strategy:
            strategy_status = st.session_state.strategy.get_strategy_status()
            
            # Create metrics cards
            metrics_cols = st.columns(4)
            
            with metrics_cols[0]:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Current Price</div>', unsafe_allow_html=True)
                if 'current_price' in strategy_status:
                    st.markdown(f'<div class="metric-value">{strategy_status["current_price"]:.2f}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-value">N/A</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with metrics_cols[1]:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">RSI</div>', unsafe_allow_html=True)
                if 'current_rsi' in strategy_status:
                    rsi_value = strategy_status["current_rsi"]
                    rsi_color = "#4CAF50" if rsi_value > 50 else "#F44336"
                    st.markdown(f'<div class="metric-value" style="color: {rsi_color}">{rsi_value:.2f}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-value">N/A</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with metrics_cols[2]:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">India VIX</div>', unsafe_allow_html=True)
                if 'vix' in strategy_status:
                    vix_value = strategy_status["vix"]
                    vix_color = "#4CAF50" if vix_value < 20 else "#F44336" if vix_value > 30 else "#FF9800"
                    st.markdown(f'<div class="metric-value" style="color: {vix_color}">{vix_value:.2f}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-value">N/A</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with metrics_cols[3]:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Last Signal</div>', unsafe_allow_html=True)
                if 'last_signal' in strategy_status and strategy_status["last_signal"]:
                    signal = strategy_status["last_signal"]
                    signal_class = "buy-signal" if signal == "BUY" else "sell-signal"
                    st.markdown(f'<div class="metric-value {signal_class}">{signal}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-value neutral">NEUTRAL</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Greeks data
            st.markdown('<div class="sub-header">Option Greeks</div>', unsafe_allow_html=True)
            
            greeks_cols = st.columns(2)
            
            with greeks_cols[0]:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Call Option Greeks</div>', unsafe_allow_html=True)
                
                if all(k in strategy_status for k in ['call_delta', 'call_gamma', 'call_theta', 'call_vega']):
                    call_data = {
                        'Delta': strategy_status['call_delta'],
                        'Gamma': strategy_status['call_gamma'],
                        'Theta': strategy_status['call_theta'],
                        'Vega': strategy_status['call_vega']
                    }
                    
                    call_df = pd.DataFrame(list(call_data.items()), columns=['Greek', 'Value'])
                    st.dataframe(call_df, hide_index=True)
                else:
                    st.markdown('<div class="neutral">Data not available</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            with greeks_cols[1]:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Put Option Greeks</div>', unsafe_allow_html=True)
                
                if all(k in strategy_status for k in ['put_delta', 'put_gamma', 'put_theta', 'put_vega']):
                    put_data = {
                        'Delta': strategy_status['put_delta'],
                        'Gamma': strategy_status['put_gamma'],
                        'Theta': strategy_status['put_theta'],
                        'Vega': strategy_status['put_vega']
                    }
                    
                    put_df = pd.DataFrame(list(put_data.items()), columns=['Greek', 'Value'])
                    st.dataframe(put_df, hide_index=True)
                else:
                    st.markdown('<div class="neutral">Data not available</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Price chart
            if st.session_state.strategy.historical_data is not None and not st.session_state.strategy.historical_data.empty:
                st.markdown('<div class="sub-header">Price Chart</div>', unsafe_allow_html=True)
                
                df = st.session_state.strategy.historical_data.reset_index()
                
                fig = go.Figure()
                
                # Add candlestick chart
                fig.add_trace(go.Candlestick(
                    x=df['timestamp'],
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name='Price'
                ))
                
                # Add MA line
                fig.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=df['ma'],
                    line=dict(color='blue', width=1),
                    name=f'MA({int(os.getenv("MA_PERIOD", "20"))})'
                ))
                
                # Add buy/sell signals
                for signal in st.session_state.signals:
                    signal_time = signal['time']
                    signal_type = signal['type']
                    signal_price = signal['price']
                    
                    if signal_type == 'BUY':
                        fig.add_trace(go.Scatter(
                            x=[signal_time],
                            y=[signal_price],
                            mode='markers',
                            marker=dict(symbol='triangle-up', size=15, color='green'),
                            name='Buy Signal'
                        ))
                    else:
                        fig.add_trace(go.Scatter(
                            x=[signal_time],
                            y=[signal_price],
                            mode='markers',
                            marker=dict(symbol='triangle-down', size=15, color='red'),
                            name='Sell Signal'
                        ))
                
                # Update layout
                fig.update_layout(
                    title='Nifty Price Chart (15-min)',
                    xaxis_title='Time',
                    yaxis_title='Price',
                    height=500,
                    xaxis_rangeslider_visible=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Trading signals and positions
        st.markdown('<div class="sub-header">Trading Signals</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        if st.session_state.signals:
            signals_df = pd.DataFrame(st.session_state.signals)
            signals_df['time'] = pd.to_datetime(signals_df['time'])
            signals_df = signals_df.sort_values('time', ascending=False)
            
            for _, signal in signals_df.iterrows():
                signal_type = signal['type']
                signal_time = signal['time'].strftime('%Y-%m-%d %H:%M:%S')
                signal_price = signal['price']
                
                signal_class = "buy-signal" if signal_type == "BUY" else "sell-signal"
                
                st.markdown(f"""
                <div style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee;">
                    <span class="{signal_class}">{signal_type}</span> at {signal_price:.2f}
                    <br>
                    <small>{signal_time}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="neutral">No signals generated yet</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Current positions
        st.markdown('<div class="sub-header">Current Positions</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        if st.session_state.strategy:
            positions = st.session_state.strategy.angel_api.get_positions()
            
            if positions:
                positions_df = pd.DataFrame(positions)
                
                if not positions_df.empty:
                    # Filter and format positions data
                    display_cols = ['tradingsymbol', 'netqty', 'avgnetprice', 'ltp', 'pnl']
                    if all(col in positions_df.columns for col in display_cols):
                        positions_df = positions_df[display_cols]
                        positions_df.columns = ['Symbol', 'Quantity', 'Avg Price', 'LTP', 'P&L']
                        st.dataframe(positions_df, hide_index=True)
                    else:
                        st.markdown('<div class="neutral">Position data format not as expected</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="neutral">No open positions</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="neutral">No open positions</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="neutral">Strategy not initialized</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Manual trading controls
        st.markdown('<div class="sub-header">Manual Trading</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Buy", key="buy_button"):
                if st.session_state.strategy:
                    with st.spinner("Placing buy order..."):
                        order_id = st.session_state.strategy.angel_api.place_order(
                            "BUY",
                            os.getenv("SYMBOL", "NIFTY"),
                            os.getenv("EXCHANGE", "NSE"),
                            int(os.getenv("QUANTITY", "1"))
                        )
                        
                        if order_id:
                            st.success(f"Buy order placed! Order ID: {order_id}")
                            
                            # Add to signals
                            if st.session_state.strategy.historical_data is not None and not st.session_state.strategy.historical_data.empty:
                                current_price = st.session_state.strategy.historical_data.iloc[-1]['close']
                                
                                st.session_state.signals.append({
                                    'time': datetime.datetime.now(),
                                    'type': 'BUY',
                                    'price': current_price,
                                    'order_id': order_id
                                })
                        else:
                            st.error("Failed to place buy order")
        
        with col2:
            if st.button("Sell", key="sell_button"):
                if st.session_state.strategy:
                    with st.spinner("Placing sell order..."):
                        order_id = st.session_state.strategy.angel_api.place_order(
                            "SELL",
                            os.getenv("SYMBOL", "NIFTY"),
                            os.getenv("EXCHANGE", "NSE"),
                            int(os.getenv("QUANTITY", "1"))
                        )
                        
                        if order_id:
                            st.success(f"Sell order placed! Order ID: {order_id}")
                            
                            # Add to signals
                            if st.session_state.strategy.historical_data is not None and not st.session_state.strategy.historical_data.empty:
                                current_price = st.session_state.strategy.historical_data.iloc[-1]['close']
                                
                                st.session_state.signals.append({
                                    'time': datetime.datetime.now(),
                                    'type': 'SELL',
                                    'price': current_price,
                                    'order_id': order_id
                                })
                        else:
                            st.error("Failed to place sell order")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown('<div class="footer">Nifty Intraday Trading Strategy © 2023</div>', unsafe_allow_html=True)
    
    # Auto-refresh data every minute if auto-trading is enabled
    if st.session_state.auto_trading:
        if st.session_state.last_update is None or (datetime.datetime.now() - st.session_state.last_update).total_seconds() > 60:
            auto_refresh_data()

def refresh_data():
    """Manually refresh data"""
    if st.session_state.strategy:
        # Run strategy
        st.session_state.strategy.run_strategy()
        
        # Check for new signals
        signal = st.session_state.strategy.last_signal
        
        if signal and (not st.session_state.signals or 
                      st.session_state.signals[-1]['type'] != signal or 
                      (datetime.datetime.now() - st.session_state.signals[-1]['time']).total_seconds() > 900):  # 15 minutes
            
            # Add new signal
            if st.session_state.strategy.historical_data is not None and not st.session_state.strategy.historical_data.empty:
                current_price = st.session_state.strategy.historical_data.iloc[-1]['close']
                
                st.session_state.signals.append({
                    'time': datetime.datetime.now(),
                    'type': signal,
                    'price': current_price,
                    'order_id': None
                })
        
        st.session_state.last_update = datetime.datetime.now()

def auto_refresh_data():
    """Auto refresh data for auto-trading"""
    if st.session_state.strategy:
        with st.spinner("Auto-refreshing data..."):
            # Run strategy
            st.session_state.strategy.run_strategy()
            
            # Check for new signals and execute trades if auto-trading is enabled
            signal = st.session_state.strategy.last_signal
            
            if signal and (not st.session_state.signals or 
                          st.session_state.signals[-1]['type'] != signal or 
                          (datetime.datetime.now() - st.session_state.signals[-1]['time']).total_seconds() > 900):  # 15 minutes
                
                # Execute trade
                if st.session_state.auto_trading:
                    st.session_state.strategy.execute_trade(signal)
                
                # Add new signal
                if st.session_state.strategy.historical_data is not None and not st.session_state.strategy.historical_data.empty:
                    current_price = st.session_state.strategy.historical_data.iloc[-1]['close']
                    
                    st.session_state.signals.append({
                        'time': datetime.datetime.now(),
                        'type': signal,
                        'price': current_price,
                        'order_id': None
                    })
            
            st.session_state.last_update = datetime.datetime.now()

# Main app logic
def main():
    if not st.session_state.authenticated:
        login_page()
    else:
        dashboard_page()

if __name__ == "__main__":
    main()