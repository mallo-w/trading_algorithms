import requests
import pandas as pd
import backtrader as bt
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Set your Alpha Vantage API key
api_key = 'CHWVXYLJ1M3KBV5Q'

# Function to fetch historical 60-minute data from Alpha Vantage and aggregate to daily data
def fetch_alpha_vantage_data(symbol, interval='60min'):
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=full'
    response = requests.get(url)
    data = response.json()

    # Debugging: Print the type and content of the response
    print(f"Type of data: {type(data)}")
    if 'Time Series (60min)' in data:
        df = pd.DataFrame.from_dict(data['Time Series (60min)'], orient='index')
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # Convert columns to numeric types
        df = df.apply(pd.to_numeric)

        # Aggregate to daily data
        df_daily = df.resample('D').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()

        return df_daily
    else:
        print(f"Error fetching data for {symbol}: {data}")
        raise ValueError(f"Error fetching data for {symbol} from Alpha Vantage")

# Define the strategy
class TSLA_Strategy(bt.Strategy):
    params = (
        ('rsi_period', 2),
        ('sar_af', 0.02),
        ('sar_max_af', 0.2),
    )

    def __init__(self):
        self.rsi = bt.indicators.RelativeStrengthIndex(period=self.params.rsi_period)
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
            if self.rsi[-1] < 10 and self.rsi[0] > 10:
                self.buy_price = self.data.close[0]
                self.stop_price = min(self.data.low.get(size=3))
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
data = fetch_alpha_vantage_data('TSLA', interval='60min')

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
cere