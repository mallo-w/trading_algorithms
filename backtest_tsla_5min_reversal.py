import requests
import pandas as pd
import backtrader as bt
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Set your Alpha Vantage API key
api_key = 'CHWVXYLJ1M3KBV5Q'

# Function to fetch historical 5-minute data from Alpha Vantage
def fetch_alpha_vantage_data(symbol, interval='5min'):
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=full'
    response = requests.get(url)
    data = response.json()

    # Debugging: Print the type and content of the response
    print(f"Type of data: {type(data)}")
    if 'Time Series (5min)' in data:
        df = pd.DataFrame.from_dict(data['Time Series (5min)'], orient='index')
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # Convert columns to numeric types
        df = df.apply(pd.to_numeric)

        return df
    else:
        print(f"Error fetching data for {symbol}: {data}")
        raise ValueError(f"Error fetching data for {symbol} from Alpha Vantage")

# Define the strategy
class TSLA_Strategy(bt.Strategy):
    params = (
        ('sar_af', 0.02),
        ('sar_max_af', 0.2),
    )

    def __init__(self):
        self.sar = bt.indicators.ParabolicSAR(self.data, af=self.params.sar_af, afmax=self.params.sar_max_af)
        self.order = None
        self.buy_price = None
        self.stop_price = None
        self.initial_stop = None
        self.trail_stop = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if len(self.data) >= 2:
                first_candle_close = self.data.close[-2]
                first_candle_open = self.data.open[-2]
                first_candle_high = self.data.high[-2]
                second_candle_close = self.data.close[-1]
                second_candle_open = self.data.open[-1]

                if first_candle_close < first_candle_open and second_candle_close > second_candle_open and second_candle_close > first_candle_high:
                    self.buy_price = self.data.close[0]
                    self.stop_price = min(self.data.low.get(size=len(self.data)))
                    risk_per_share = self.buy_price - self.stop_price
                    position_size = int((self.broker.cash * 0.015) / risk_per_share)
                    self.order = self.buy(size=position_size)
                    self.initial_stop = self.stop_price
                    self.trail_stop = self.stop_price
        else:
            if self.sar[0] > self.initial_stop:
                self.trail_stop = self.sar[0]
            self.order = self.sell(exectype=bt.Order.Stop, price=self.trail_stop)

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None

# Initialize Cerebro engine
cerebro = bt.Cerebro()

# Fetch data
start_date = '2020-01-01'
end_date = '2024-06-07'
data = fetch_alpha_vantage_data('TSLA')

# Filter data by date range
data = data[(data.index >= start_date) & (data.index <= end_date)]

# Load data
datafeed = bt.feeds.PandasData(dataname=data)

# Add data to Cerebro
cerebro.adddata(datafeed)

# Add strategy to Cerebro
cerebro.addstrategy(TSLA_Strategy)

# Set initial cash
initial_cash = 100000.0
cerebro.broker.set_cash(initial_cash)

# Set commission
cerebro.broker.setcommission(commission=0.001)

# Add analyzers
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')

# Print starting cash
print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

# Run backtest
results = cerebro.run()
strategy = results[0]

# Print final cash
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

# Get analyzers
drawdown = strategy.analyzers.drawdown.get_analysis()
trade_analyzer = strategy.analyzers.trade_analyzer.get_analysis()

# Print drawdown analysis
print('Max Drawdown: %.2f%%' % drawdown.max.drawdown)
print('Max Drawdown Duration: %s' % drawdown.max.len)

# Print trade analysis
print('Total Trades: %d' % trade_analyzer.total.closed)
print('Winning Trades: %d' % trade_analyzer.won.total)
print('Losing Trades: %d' % trade_analyzer.lost.total)

# Check for max losing streak
max_losing_streak = trade_analyzer.streak.losing.longest if 'streak' in trade_analyzer and 'losing' in trade_analyzer.streak and 'longest' in trade_analyzer.streak.losing else 0
print('Max Losing Streak: %d' % max_losing_streak)

# Plot results
cerebro.plot()

# Calculate relative performance
data['Returns'] = data['Close'].pct_change().cumsum()
strategy_returns = pd.Series([x[0] for x in strategy.analyzers.trade_analyzer.get_analysis().pnl.net], index=data.index).cumsum()

# Plot relative performance
plt.figure(figsize=(12, 6))
plt.plot(data['Returns'], label='TSLA')
plt.plot(strategy_returns, label='Strategy')
plt.legend()
plt.title('Relative Performance of Strategy vs TSLA')
plt.xlabel('Date')
plt.ylabel('Cumulative Returns')
plt.show()