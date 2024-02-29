# risk_return_analysis.py
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64

def calculate_risk_return(stock_symbol, start_date, end_date):
    stock_data = yf.download(stock_symbol, start=start_date, end=end_date)

    if stock_data.empty:
        return None, None
    
    daily_returns = stock_data['Adj Close'].pct_change()
    avg_return = daily_returns.mean() * 252 
    risk = daily_returns.std() * (252 ** 0.5)  
    return avg_return, risk

def generate_risk_return_plot(stock_symbols, start_date, end_date):
    risk_return_data = []

    for stock_symbol in stock_symbols:
        avg_return, risk = calculate_risk_return(stock_symbol, start_date, end_date)
        risk_return_data.append({'symbol': stock_symbol, 'avg_return': avg_return, 'risk': risk})

    df = pd.DataFrame(risk_return_data)
    plt.switch_backend('Agg')

    plt.figure(figsize=(10, 6))
    plt.scatter(df['risk'], df['avg_return'])
    for i, txt in enumerate(df['symbol']):
        plt.annotate(txt, (df['risk'][i], df['avg_return'][i]))
    plt.xlabel('Risk (Standard Deviation)')
    plt.ylabel('Average Return')
    plt.title('Risk-Return Profile')
    plt.grid(True)

    # Save the plot to a BytesIO object
    img_bytes_io = io.BytesIO()
    plt.savefig(img_bytes_io, format='png')
    img_bytes_io.seek(0)
    plt.close()

    # Convert the image to base64 for embedding in HTML
    img_base64 = base64.b64encode(img_bytes_io.read()).decode('utf-8')

    return img_base64

def sort_watchlist(watchlist, start_date, end_date):
    risk_return_data = []
    for stock_symbol in watchlist:
        avg_return, risk = calculate_risk_return(stock_symbol, start_date= start_date, end_date= end_date)
        return_risk_ratio = avg_return / risk if risk != 0 else 0

        risk_return_data.append({
            'symbol': stock_symbol,
            'avg_return': avg_return,
            'risk': risk,
            'return_risk_ratio': return_risk_ratio
        })

    df = pd.DataFrame(risk_return_data)
    sorted_watchlist = df.sort_values(by='return_risk_ratio', ascending=False)
    
    return sorted_watchlist
