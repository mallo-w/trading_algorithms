import requests
import pandas as pd
import numpy as np
import streamlit as st
import base64
from datetime import datetime, timedelta

# Set your API key
api_key = 'lg0Ac0SKhk44RhMPB2a7Bp0ANg3eI8nl'

# Function to fetch historical data from FMP
def fetch_fmp_historical_data(symbol, api_key, start_date, end_date):
    url = f'https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?apikey={api_key}'
    response = requests.get(url)
    data = response.json()
    if 'historical' in data:
        df = pd.DataFrame(data['historical'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df.sort_index()
        df = df[(df.index >= start_date) & (df.index <= end_date)]  # Filter data by date range
        return df
    else:
        raise ValueError(f"Error fetching data for {symbol} from FMP")

# Function to fetch fundamental data from FMP
def fetch_fmp_fundamental_data(symbol, api_key):
    url = f'https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={api_key}'
    response = requests.get(url)
    data = response.json()
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    else:
        raise ValueError(f"Error fetching fundamental data for {symbol} from FMP")

# Function to calculate RSI
def calculate_rsi(data, window=14):
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Function to calculate moving averages
def calculate_moving_averages(data):
    data['SMA_20'] = data['close'].rolling(window=20).mean()
    data['SMA_50'] = data['close'].rolling(window=50).mean()
    data['SMA_100'] = data['close'].rolling(window=100).mean()
    return data

# Function to screen stocks based on criteria
def screen_stocks(symbols, api_key, start_date, end_date):
    screened_stocks = []
    for symbol in symbols:
        try:
            # Fetch historical data
            data = fetch_fmp_historical_data(symbol, api_key, start_date, end_date)
            data = calculate_moving_averages(data)
            data['RSI_14'] = calculate_rsi(data)

            # Fetch fundamental data
            fundamental_data = fetch_fmp_fundamental_data(symbol, api_key)

            # Apply screening criteria
            if (data['RSI_14'].iloc[-1] > 60 and
                data['close'].iloc[-1] > data['SMA_20'].iloc[-1] > data['SMA_50'].iloc[-1] > data['SMA_100'].iloc[-1] and
                float(fundamental_data['quarterlyEarningsGrowthYOY']) > 0.25 and
                float(fundamental_data['quarterlyRevenueGrowthYOY']) > 0.25 and
                float(fundamental_data['netProfitMargin']) > 0.15):
                
                screened_stocks.append({
                    'Symbol': symbol,
                    'Company Name': fundamental_data['companyName'],
                    'Current Price': data['close'].iloc[-1],
                    'RSI(14)': data['RSI_14'].iloc[-1],
                    'SMA(20)': data['SMA_20'].iloc[-1],
                    'SMA(50)': data['SMA_50'].iloc[-1],
                    'SMA(100)': data['SMA_100'].iloc[-1],
                    'EPS Growth QoQ': fundamental_data['quarterlyEarningsGrowthYOY'],
                    'Sales Growth QoQ': fundamental_data['quarterlyRevenueGrowthYOY'],
                    'Net Profit Margin': fundamental_data['netProfitMargin']
                })
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    return pd.DataFrame(screened_stocks)

# Function to download the screened stocks as a CSV file
def filedownload(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="screened_stocks.csv">Download CSV File</a>'
    return href

# Streamlit app
st.sidebar.header('Settings')
min_volume = st.sidebar.text_input("Minimum Volume", 1e6)
min_price = st.sidebar.slider('Minimum Price ($)', 0, 5000, 0)
days = st.sidebar.slider('Max Period (days)', 14, 730, 365)

with st.container():
    st.title('US Market Stock Screener')
    st.write('''
        This app screens for stocks in the US market based on the following criteria:
        - RSI(14) > 60
        - Price > SMA(20) > SMA(50) > SMA(100)
        - EPS growth quarter over quarter > 25%
        - Sales growth quarter over quarter > 25%
        - Net Profit Margin > 15%
    ''')

    if st.button('Start screening'):
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        # Fetch the list of all US stocks
        url = f'https://financialmodelingprep.com/api/v3/stock/list?apikey={api_key}'
        response = requests.get(url)
        all_stocks = response.json()

        # Debugging: Print the type and structure of all_stocks
        print(f"Type of all_stocks: {type(all_stocks)}")
        if isinstance(all_stocks, list):
            print(f"First 5 entries: {all_stocks[:5]}")
            symbols = [stock['symbol'] for stock in all_stocks]
        else:
            print(f"all_stocks content: {all_stocks}")
            raise ValueError("Error fetching the list of US stocks from FMP")

        # Screen stocks
        final_df = screen_stocks(symbols, api_key, start_date, end_date)
        st.dataframe(final_df)
        st.markdown(filedownload(final_df), unsafe_allow_html=True)
        st.set_option('deprecation.showPyplotGlobalUse', False)