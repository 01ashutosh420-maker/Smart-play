import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
import json
from dotenv import load_dotenv
from angel_api import AngelOneAPI
from nse_data import NSEDataFetcher
from strategy import NiftyIntradayStrategy

# Load environment variables
load_dotenv()

class Backtester:
    def __init__(self, start_date, end_date, symbol="NIFTY", timeframe="15minute"):
        """
        Initialize the backtester with date range and symbol
        
        Args:
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            symbol (str): Symbol to backtest (default: NIFTY)
            timeframe (str): Timeframe for candles (default: 15minute)
        """
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.symbol = symbol
        self.timeframe = timeframe
        self.api = AngelOneAPI()
        self.nse_data = NSEDataFetcher()
        self.strategy = NiftyIntradayStrategy(self.api)
        
        # Strategy parameters
        self.strategy_params = {
            'DELTA_THRESHOLD': float(os.getenv('DELTA_THRESHOLD', '0.5')),
            'GAMMA_THRESHOLD': float(os.getenv('GAMMA_THRESHOLD', '0.1')),
            'THETA_THRESHOLD': float(os.getenv('THETA_THRESHOLD', '0.05')),
            'VEGA_THRESHOLD': float(os.getenv('VEGA_THRESHOLD', '0.1')),
            'RSI_PERIOD': int(os.getenv('RSI_PERIOD', '14')),
            'RSI_OVERSOLD': 30,
            'RSI_OVERBOUGHT': 70,
            'MA_PERIOD': int(os.getenv('MA_PERIOD', '20')),
            'VIX_THRESHOLD': float(os.getenv('VIX_THRESHOLD', '25'))
        }
        
        # Risk management parameters
        self.risk_management = {
            'STOP_LOSS_PERCENT': float(os.getenv('STOP_LOSS_PERCENT', '1.0')),
            'TAKE_PROFIT_PERCENT': float(os.getenv('TAKE_PROFIT_PERCENT', '2.0'))
        }
        
        # Results storage
        self.trades = []
        self.equity_curve = []
        self.metrics = {}
        
        # Create results directory if it doesn't exist
        os.makedirs("backtest_results", exist_ok=True)
    
    def fetch_historical_data(self):
        """
        Fetch historical price data for the specified symbol and date range
        """
        print(f"Fetching historical data for {self.symbol} from {self.start_date.date()} to {self.end_date.date()}...")
        
        # Connect to Angel One API
        self.api.connect()
        
        # Get historical data
        historical_data = self.api.get_historical_data(
            symbol=self.symbol,
            exchange="NSE",
            from_date=self.start_date.strftime("%Y-%m-%d"),
            to_date=self.end_date.strftime("%Y-%m-%d"),
            interval=self.timeframe
        )
        
        # Convert to DataFrame
        self.price_data = pd.DataFrame(historical_data)
        
        # Process data
        if not self.price_data.empty:
            self.price_data['timestamp'] = pd.to_datetime(self.price_data['timestamp'])
            self.price_data.set_index('timestamp', inplace=True)
            self.price_data.sort_index(inplace=True)
            
            # Calculate RSI and MA
            self.price_data['rsi'] = self._calculate_rsi(self.price_data['close'], self.strategy_params['RSI_PERIOD'])
            self.price_data['ma'] = self.price_data['close'].rolling(window=self.strategy_params['MA_PERIOD']).mean()
            
            print(f"Successfully fetched {len(self.price_data)} candles")
            return True
        else:
            print("Failed to fetch historical data")
            return False
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def simulate_option_greeks(self):
        """
        Simulate option Greeks data based on price movements
        This is a simplified simulation since we can't get historical Greeks data
        """
        print("Simulating option Greeks data...")
        
        # Base values
        atm_price = self.price_data['close'].iloc[0]
        vix_base = 15.0  # Base VIX value
        
        # Create simulated Greeks data
        self.price_data['call_delta'] = 0.5
        self.price_data['put_delta'] = -0.5
        self.price_data['call_gamma'] = 0.05
        self.price_data['put_gamma'] = 0.05
        self.price_data['call_theta'] = -0.1
        self.price_data['put_theta'] = -0.1
        self.price_data['call_vega'] = 0.2
        self.price_data['put_vega'] = 0.2
        self.price_data['india_vix'] = vix_base
        
        # Adjust Greeks based on price movements
        for i in range(1, len(self.price_data)):
            price_change = (self.price_data['close'].iloc[i] / self.price_data['close'].iloc[i-1]) - 1
            
            # Delta changes with price (increases for calls, decreases for puts)
            self.price_data.loc[self.price_data.index[i], 'call_delta'] = min(0.95, self.price_data['call_delta'].iloc[i-1] + price_change * 0.5)
            self.price_data.loc[self.price_data.index[i], 'put_delta'] = max(-0.95, self.price_data['put_delta'].iloc[i-1] - price_change * 0.5)
            
            # Gamma decreases as option moves deeper ITM/OTM
            delta_change = abs(self.price_data['call_delta'].iloc[i] - 0.5)
            self.price_data.loc[self.price_data.index[i], 'call_gamma'] = max(0.01, 0.05 - delta_change * 0.1)
            self.price_data.loc[self.price_data.index[i], 'put_gamma'] = max(0.01, 0.05 - delta_change * 0.1)
            
            # Theta increases as time passes
            self.price_data.loc[self.price_data.index[i], 'call_theta'] = self.price_data['call_theta'].iloc[i-1] * 1.01
            self.price_data.loc[self.price_data.index[i], 'put_theta'] = self.price_data['put_theta'].iloc[i-1] * 1.01
            
            # Vega decreases with time
            self.price_data.loc[self.price_data.index[i], 'call_vega'] = self.price_data['call_vega'].iloc[i-1] * 0.99
            self.price_data.loc[self.price_data.index[i], 'put_vega'] = self.price_data['put_vega'].iloc[i-1] * 0.99
            
            # VIX changes (simulated)
            vix_change = np.random.normal(0, 0.5)
            self.price_data.loc[self.price_data.index[i], 'india_vix'] = max(10, min(30, self.price_data['india_vix'].iloc[i-1] + vix_change))
    
    def run_backtest(self):
        """
        Run the backtest using the strategy logic
        """
        print("Running backtest...")
        
        # Initial capital
        capital = 100000
        position = 0  # 0: no position, 1: long, -1: short
        entry_price = 0
        
        # Track equity and trades
        self.equity_curve = [{'timestamp': self.price_data.index[0], 'equity': capital}]
        
        # Iterate through each candle
        for i in range(1, len(self.price_data)):
            current_data = self.price_data.iloc[i]
            current_time = self.price_data.index[i]
            
            # Skip if outside trading hours (9:15 AM to 3:15 PM)
            if current_time.time() < datetime.strptime("09:15:00", "%H:%M:%S").time() or \
               current_time.time() > datetime.strptime("15:15:00", "%H:%M:%S").time():
                continue
            
            # Check for signal
            signal = self._check_strategy_signal(i)
            
            # Process exit for existing position
            if position != 0:
                # Check stop loss and take profit
                current_price = current_data['close']
                pnl_percent = ((current_price / entry_price) - 1) * 100 * position
                
                # Exit on stop loss or take profit
                if (pnl_percent <= -self.risk_management['STOP_LOSS_PERCENT']) or \
                   (pnl_percent >= self.risk_management['TAKE_PROFIT_PERCENT']):
                    # Close position
                    trade_pnl = (current_price - entry_price) * position
                    capital += trade_pnl
                    
                    # Record trade
                    self.trades.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'position': 'LONG' if position == 1 else 'SHORT',
                        'pnl': trade_pnl,
                        'pnl_percent': pnl_percent,
                        'exit_reason': 'SL' if pnl_percent < 0 else 'TP'
                    })
                    
                    position = 0
            
            # Process entry signal
            if position == 0 and signal != 0:
                position = signal
                entry_price = current_data['close']
                entry_time = current_time
            
            # Update equity curve
            current_equity = capital
            if position != 0:
                unrealized_pnl = (current_data['close'] - entry_price) * position
                current_equity += unrealized_pnl
            
            self.equity_curve.append({
                'timestamp': current_time,
                'equity': current_equity
            })
        
        # Close any open position at the end
        if position != 0:
            final_price = self.price_data['close'].iloc[-1]
            trade_pnl = (final_price - entry_price) * position
            capital += trade_pnl
            
            self.trades.append({
                'entry_time': entry_time,
                'exit_time': self.price_data.index[-1],
                'entry_price': entry_price,
                'exit_price': final_price,
                'position': 'LONG' if position == 1 else 'SHORT',
                'pnl': trade_pnl,
                'pnl_percent': ((final_price / entry_price) - 1) * 100 * position,
                'exit_reason': 'END'
            })
        
        # Calculate performance metrics
        self._calculate_performance_metrics(capital)
        
        print(f"Backtest completed. Final capital: {capital:.2f}")
        return self.metrics
    
    def _check_strategy_signal(self, index):
        """
        Check for strategy signals based on current data
        Returns: 1 for long, -1 for short, 0 for no signal
        """
        current = self.price_data.iloc[index]
        
        # Check Delta-Gamma filter for long
        delta_gamma_long = (current['call_delta'] > self.strategy_params['DELTA_THRESHOLD']) and \
                           (current['call_gamma'] > self.strategy_params['GAMMA_THRESHOLD'])
        
        # Check Delta-Gamma filter for short
        delta_gamma_short = (current['put_delta'] < -self.strategy_params['DELTA_THRESHOLD']) and \
                            (current['put_gamma'] > self.strategy_params['GAMMA_THRESHOLD'])
        
        # Check Theta-Vega confirmation for long
        theta_vega_long = (current['call_theta'] < -self.strategy_params['THETA_THRESHOLD']) and \
                          (current['call_vega'] > self.strategy_params['VEGA_THRESHOLD'])
        
        # Check Theta-Vega confirmation for short
        theta_vega_short = (current['put_theta'] < -self.strategy_params['THETA_THRESHOLD']) and \
                           (current['put_vega'] > self.strategy_params['VEGA_THRESHOLD'])
        
        # Check RSI filter
        rsi_long = current['rsi'] < self.strategy_params['RSI_OVERSOLD']
        rsi_short = current['rsi'] > self.strategy_params['RSI_OVERBOUGHT']
        
        # Check MA filter
        ma_long = current['close'] > current['ma']
        ma_short = current['close'] < current['ma']
        
        # Check VIX filter
        vix_filter = current['india_vix'] < self.strategy_params['VIX_THRESHOLD']
        
        # Generate signals
        long_signal = delta_gamma_long and theta_vega_long and rsi_long and ma_long and vix_filter
        short_signal = delta_gamma_short and theta_vega_short and rsi_short and ma_short and vix_filter
        
        if long_signal:
            return 1
        elif short_signal:
            return -1
        else:
            return 0
    
    def _calculate_performance_metrics(self, final_capital):
        """
        Calculate performance metrics from backtest results
        """
        # Convert equity curve to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
        equity_df.set_index('timestamp', inplace=True)
        
        # Calculate returns
        equity_df['returns'] = equity_df['equity'].pct_change()
        
        # Convert trades to DataFrame
        trades_df = pd.DataFrame(self.trades)
        
        # Basic metrics
        initial_capital = self.equity_curve[0]['equity']
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        # Calculate metrics
        self.metrics = {
            'initial_capital': initial_capital,
            'final_capital': final_capital,
            'total_return_percent': total_return,
            'total_trades': len(self.trades),
            'winning_trades': sum(1 for trade in self.trades if trade['pnl'] > 0),
            'losing_trades': sum(1 for trade in self.trades if trade['pnl'] <= 0),
        }
        
        # Calculate win rate
        if self.metrics['total_trades'] > 0:
            self.metrics['win_rate'] = self.metrics['winning_trades'] / self.metrics['total_trades'] * 100
        else:
            self.metrics['win_rate'] = 0
        
        # Calculate average profit/loss
        if self.metrics['winning_trades'] > 0:
            self.metrics['avg_profit'] = sum(trade['pnl'] for trade in self.trades if trade['pnl'] > 0) / self.metrics['winning_trades']
        else:
            self.metrics['avg_profit'] = 0
            
        if self.metrics['losing_trades'] > 0:
            self.metrics['avg_loss'] = sum(trade['pnl'] for trade in self.trades if trade['pnl'] <= 0) / self.metrics['losing_trades']
        else:
            self.metrics['avg_loss'] = 0
        
        # Calculate profit factor
        total_profit = sum(trade['pnl'] for trade in self.trades if trade['pnl'] > 0)
        total_loss = abs(sum(trade['pnl'] for trade in self.trades if trade['pnl'] <= 0))
        
        if total_loss > 0:
            self.metrics['profit_factor'] = total_profit / total_loss
        else:
            self.metrics['profit_factor'] = float('inf') if total_profit > 0 else 0
        
        # Calculate max drawdown
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax'] * 100
        self.metrics['max_drawdown'] = abs(equity_df['drawdown'].min())
        
        # Calculate Sharpe ratio (assuming 252 trading days)
        if len(equity_df) > 1:
            daily_returns = equity_df['returns'].dropna()
            if len(daily_returns) > 0:
                sharpe_ratio = np.sqrt(252) * daily_returns.mean() / daily_returns.std()
                self.metrics['sharpe_ratio'] = sharpe_ratio
            else:
                self.metrics['sharpe_ratio'] = 0
        else:
            self.metrics['sharpe_ratio'] = 0
    
    def save_results(self, filename=None):
        """
        Save backtest results to files
        """
        if filename is None:
            filename = f"backtest_{self.symbol}_{self.start_date.strftime('%Y%m%d')}_{self.end_date.strftime('%Y%m%d')}"
        
        # Save metrics
        with open(f"backtest_results/{filename}_metrics.json", 'w') as f:
            json.dump(self.metrics, f, indent=4, default=str)
        
        # Save trades
        trades_df = pd.DataFrame(self.trades)
        if not trades_df.empty:
            trades_df.to_csv(f"backtest_results/{filename}_trades.csv", index=False)
        
        # Save equity curve
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.to_csv(f"backtest_results/{filename}_equity.csv", index=False)
        
        print(f"Results saved to backtest_results/{filename}_*.json/csv")
    
    def plot_results(self):
        """
        Plot backtest results
        """
        if not self.trades or not self.equity_curve:
            print("No results to plot")
            return
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot price data
        ax1.plot(self.price_data.index, self.price_data['close'], label='Price', color='blue', alpha=0.7)
        
        # Plot entry and exit points
        for trade in self.trades:
            if trade['position'] == 'LONG':
                ax1.scatter(trade['entry_time'], trade['entry_price'], color='green', marker='^', s=100)
                ax1.scatter(trade['exit_time'], trade['exit_price'], color='red', marker='v', s=100)
            else:
                ax1.scatter(trade['entry_time'], trade['entry_price'], color='red', marker='v', s=100)
                ax1.scatter(trade['exit_time'], trade['exit_price'], color='green', marker='^', s=100)
        
        # Plot equity curve
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
        ax2.plot(equity_df['timestamp'], equity_df['equity'], label='Equity', color='green')
        
        # Add labels and title
        ax1.set_title(f"{self.symbol} Backtest Results ({self.start_date.date()} to {self.end_date.date()})")
        ax1.set_ylabel("Price")
        ax1.legend()
        ax1.grid(True)
        
        ax2.set_xlabel("Date")
        ax2.set_ylabel("Equity")
        ax2.legend()
        ax2.grid(True)
        
        # Format x-axis
        fig.autofmt_xdate()
        
        # Add metrics as text
        metrics_text = (
            f"Total Return: {self.metrics['total_return_percent']:.2f}%\n"
            f"Win Rate: {self.metrics['win_rate']:.2f}%\n"
            f"Profit Factor: {self.metrics['profit_factor']:.2f}\n"
            f"Max Drawdown: {self.metrics['max_drawdown']:.2f}%\n"
            f"Sharpe Ratio: {self.metrics['sharpe_ratio']:.2f}"
        )
        
        plt.figtext(0.01, 0.01, metrics_text, fontsize=10, bbox=dict(facecolor='white', alpha=0.8))
        
        # Save plot
        plt.tight_layout()
        plt.savefig(f"backtest_results/backtest_{self.symbol}_{self.start_date.strftime('%Y%m%d')}_{self.end_date.strftime('%Y%m%d')}.png")
        plt.close()
        
        print(f"Plot saved to backtest_results/backtest_{self.symbol}_{self.start_date.strftime('%Y%m%d')}_{self.end_date.strftime('%Y%m%d')}.png")


def run_backtest_from_cli():
    """
    Run backtest from command line
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Run backtest for Nifty Intraday Strategy')
    parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--symbol', type=str, default='NIFTY', help='Symbol to backtest')
    parser.add_argument('--timeframe', type=str, default='15minute', help='Timeframe for candles')
    
    args = parser.parse_args()
    
    # Create and run backtester
    backtester = Backtester(
        start_date=args.start,
        end_date=args.end,
        symbol=args.symbol,
        timeframe=args.timeframe
    )
    
    # Fetch data and run backtest
    if backtester.fetch_historical_data():
        backtester.simulate_option_greeks()
        backtester.run_backtest()
        backtester.save_results()
        backtester.plot_results()
        
        # Print summary
        print("\nBacktest Summary:")
        for key, value in backtester.metrics.items():
            if isinstance(value, float):
                print(f"{key}: {value:.2f}")
            else:
                print(f"{key}: {value}")


if __name__ == "__main__":
    run_backtest_from_cli()