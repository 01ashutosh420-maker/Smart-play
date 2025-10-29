# Nifty Intraday Trading Strategy Software

A complete trading solution that integrates with Angel One's SmartAPI to fetch NSE option Greeks data and execute trades based on a sophisticated strategy using Delta-Gamma and Theta-Vega filters.

## Features

- **Real-time Data Fetching**: Fetches option Greeks data (Delta, Gamma, Theta, Vega) from NSE and integrates with Angel One's API for market data
- **Advanced Trading Strategy**: Implements Delta-Gamma filter, Theta-Vega confirmation, RSI, Moving Average, and VIX filters
- **Interactive Dashboard**: Streamlit-based UI with real-time market data visualization, option Greeks display, and trading controls
- **Secure Authentication**: Login system with Angel One credentials and optional TOTP-based 2FA
- **Backtesting Module**: Test your strategy on historical data with detailed performance metrics
- **Risk Management**: Configurable stop-loss and take-profit parameters

## Installation

### Prerequisites

- Python 3.8 or higher
- Angel One trading account with API access
- NSE market data access
- Git installed on your system

### Setup

1. Clone the repository from GitLab:
```
git clone https://gitlab.com/your-username/nifty-intraday-strategy.git
cd nifty-intraday-strategy
```

2. Install the required packages:
```
pip install -r requirements.txt
```

3. Create a `.env` file in the project root directory with your Angel One credentials:
```
API_KEY=your_api_key
CLIENT_ID=your_client_id
CLIENT_PASSWORD=your_password
TOTP_KEY=your_totp_key
```

## GitLab Repository Setup

To add this project to GitLab:

1. Create a new repository on GitLab
2. Install Git on your system if not already installed
3. Open a terminal/command prompt in your project directory
4. Run the following commands:
```
git init
git add .
git commit -m "Initial commit"
git remote add origin https://gitlab.com/your-username/your-repository-name.git
git push -u origin master
```

## Configuration

The `config.py` file contains all the configurable parameters for the trading strategy:

- **API Settings**: Angel One API credentials
- **Trading Parameters**: Symbol, exchange, product type, order type
- **Strategy Parameters**: Delta, Gamma, Theta, Vega thresholds, RSI levels, MA period, VIX threshold
- **Risk Management**: Stop-loss and take-profit percentages
- **Trading Hours**: Start and end times for trading
- **NSE URLs**: URLs for fetching option chain data and India VIX

Modify these parameters according to your trading preferences.

## Usage

### Running the Application

Start the application with:
```
streamlit run app.py
```

This will launch the Streamlit web interface, accessible at `http://localhost:8501` in your browser.

### Authentication

1. If you're a new user, register with your Angel One credentials
2. Login with your username and password
3. If 2FA is enabled, enter the TOTP code

### Dashboard

The dashboard displays:
- Current market data for Nifty
- Option Greeks (Delta, Gamma, Theta, Vega) for selected strike prices
- Price chart with strategy signals
- Current positions and P&L
- Trading signals based on the strategy

### Trading

You can trade in two modes:

1. **Manual Trading**: Execute trades manually based on the signals
2. **Automated Trading**: Enable auto-trading to execute trades automatically when signals are generated

### Backtesting

Run backtests to evaluate the strategy performance:

```
python backtesting.py --start 2023-01-01 --end 2023-12-31 --symbol NIFTY --timeframe 15minute
```

This will generate performance metrics and charts in the `backtest_results` directory.

## Project Structure

- `app.py`: Main Streamlit application and UI
- `angel_api.py`: Angel One SmartAPI integration
- `nse_data.py`: NSE data fetching for option Greeks
- `strategy.py`: Trading strategy implementation
- `auth.py`: Authentication system
- `backtesting.py`: Backtesting module
- `config.py`: Configuration settings
- `requirements.txt`: Required Python packages

## Strategy Logic

The trading strategy is based on the following filters:

1. **Delta-Gamma Filter**:
   - For long: Call Delta > threshold AND Call Gamma > threshold
   - For short: Put Delta < -threshold AND Put Gamma > threshold

2. **Theta-Vega Confirmation**:
   - For long: Call Theta < -threshold AND Call Vega > threshold
   - For short: Put Theta < -threshold AND Put Vega > threshold

3. **Technical Indicators**:
   - RSI filter: < oversold level for long, > overbought level for short
   - MA filter: Price > MA for long, Price < MA for short

4. **Volatility Filter**:
   - India VIX < threshold

5. **Time Filter**:
   - Only trade during specified trading hours

## Risk Management

The strategy includes the following risk management features:

- Stop-loss: Exit position when loss exceeds the specified percentage
- Take-profit: Exit position when profit exceeds the specified percentage
- Position sizing: Based on available capital and risk per trade

## Security

- Passwords are stored as SHA-256 hashes
- Optional TOTP-based two-factor authentication
- Secure storage of API credentials

## Troubleshooting

### Common Issues

1. **Connection Error**:
   - Check your internet connection
   - Verify your Angel One API credentials
   - Ensure the Angel One servers are operational

2. **Data Fetching Issues**:
   - NSE website structure may change, requiring updates to the scraping logic
   - Check if you have access to the NSE option chain data

3. **Order Placement Failures**:
   - Verify you have sufficient funds in your trading account
   - Check if the symbol is available for trading
   - Ensure you're trading during market hours

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This software is for educational and informational purposes only. Trading in financial markets involves risk, and you should never trade with money you cannot afford to lose. The creators of this software are not responsible for any financial losses incurred from using this system.

Always consult with a qualified financial advisor before making investment decisions.