import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt

def get_stock_data(stock_symbol, start_date, end_date, change2day, change1day):

    stock_data = yf.download(stock_symbol, start=start_date, end=end_date)

    stock_data['PercentageChange'] = stock_data['Close'].pct_change() * 100
    stock_data['PercentageChangeYesterday'] = stock_data['PercentageChange'].shift(1)
    stock_data['PercentageChange2DayAgo'] = stock_data['PercentageChange'].shift(2)
    stock_data['DayChange'] = stock_data['Close'] - stock_data['Open']
    stock_data['PrevClose'] = stock_data['Close'].shift(1)
    stock_data['factor'] = np.where(
        ((stock_data['PercentageChangeYesterday'] > change1day) & (stock_data['PercentageChange2DayAgo'] > change2day)),
        -1,
        np.where(
        ((stock_data['PercentageChangeYesterday'] < -change1day) & (stock_data['PercentageChange2DayAgo'] < -change2day)),
        1,
        0  # If none of the conditions are met, set 'factor' to 0
        )
    )
    stock_data['profit'] = (stock_data['Close'] - stock_data['Open']) * stock_data['factor']
    stock_data['profitPrevCloseBuy'] = (stock_data['Close'] - stock_data['PrevClose']) * stock_data['factor']

    return stock_data[['Open', 'Close', 'PrevClose', 'PercentageChange', 'PercentageChangeYesterday', 'PercentageChange2DayAgo', 'DayChange', 'factor', 'profit', 'profitPrevCloseBuy']]

def plot_signals(stock_data, img_buf):

    plt.switch_backend('Agg')
    plt.figure(figsize=(12, 6))
    plt.plot(stock_data['Close'], label='Close Price', linewidth=2)

    # Plotting buy signals (factor=1) with green triangle up markers
    plt.plot(stock_data[stock_data['factor'] == 1].index,
             stock_data['Close'][stock_data['factor'] == 1],
             '^', markersize=10, color='g', label='Buy Signal')

    # Plotting sell signals (factor=-1) with red triangle down markers
    plt.plot(stock_data[stock_data['factor'] == -1].index,
             stock_data['Close'][stock_data['factor'] == -1],
             'v', markersize=10, color='r', label='Sell Signal')

    plt.title('Stock Price with Buy/Sell Signals')
    plt.xlabel('Date')
    plt.ylabel('Stock Price')
    plt.legend()

    # Save the plot to the provided BytesIO buffer
    plt.savefig(img_buf, format='png')
    plt.close()

def get_trade_data(stock_data):
    trade_data = stock_data[stock_data['factor'] != 0].copy()
    return trade_data

def calculate_cumulative_percentage_gain(trade_data):
    cumulative_percentage_gain = 100 * (1 + trade_data['PercentageChange'] * trade_data['factor'] / 100).cumprod()
    cumulative_percentage_gain = (cumulative_percentage_gain.iloc[-1]-100)
    return cumulative_percentage_gain.round(4)