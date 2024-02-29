from alpaca_trade_api.rest import REST
import yfinance as yf
from dotenv import load_dotenv
import os

load_dotenv()
alpaca_api_key = os.getenv("alpaca_api_key")
alpaca_api_secret = os.getenv("alpaca_api_secret")
alpaca_base_url = os.getenv("alpaca_base_url")
alpaca_api = REST(alpaca_api_key, alpaca_api_secret, alpaca_base_url)

def get_latest_price(symbol):
    return alpaca_api.get_latest_trade(symbol).price

def get_yesterday_close_price(symbol):
    return yf.download(symbol, start='2024-01-01').iloc[-1]['Close']

# Get latest price in stock list and calculate latest stock_balance
def calculate_stock_balance(user):
    total_stock_value = 0

    for symbol, stock_data in user['stocks'].items():
        latest_price = get_latest_price(symbol)
        stock_data['latest_price'] = latest_price
        stock_value = stock_data['quantity'] * latest_price
        total_stock_value += stock_value

    return total_stock_value

def buy_stock(user, symbol, quantity):
    latest_price = get_latest_price(symbol)
    transaction_value = quantity * latest_price

    if symbol in user['stocks']:
        old_quantity = user['stocks'][symbol]['quantity']
        old_average_price = user['stocks'][symbol]['average_price']
        new_quantity = old_quantity + quantity
        new_average_price = ((old_quantity * old_average_price) + (quantity * latest_price)) / new_quantity
        user['stocks'][symbol]['quantity'] = new_quantity
        user['stocks'][symbol]['average_price'] = new_average_price
    else:
            # User is buying the stock for the first time
            user['stocks'][symbol] = {
                'quantity': quantity,
                'average_price': latest_price
            }

    user['cash_value'] -=  transaction_value

def sell_stock(user, symbol, quantity):
    latest_price = get_latest_price(symbol)
    sale_value = quantity * latest_price
    new_quantity = user['stocks'][symbol]['quantity'] - quantity
    if new_quantity == 0:
        del user['stocks'][symbol]
    else:
        user['stocks'][symbol]['quantity'] = new_quantity

    user['cash_value'] += sale_value

# Check if the user has enough quantity to sell
def can_sell_stock(user, symbol, quantity):
    return symbol in user['stocks'] and user['stocks'][symbol]['quantity'] >= quantity

# Check if the user has enough cash to buy
def can_buy_stock(user, symbol, quantity):
    latest_price = get_latest_price(symbol)
    return user['cash_value'] >= quantity * latest_price

# Return user cash_balance, stock_balance and total_balance
def get_user_balance(user):
    cash_balance = user['cash_value']
    stock_balance = calculate_stock_balance(user)
    user_balance = {
        'cash_balance': cash_balance,
        'stock_balance': stock_balance,
        'total_balance': cash_balance + stock_balance,
    }
    return user_balance

def is_day3_apply(user,admin_record):
    is_day3_apply_result = "No"
    first_day_max = 1 + (user['three_day_rule']['first_day_change'] / 100)
    first_day_min = 1 - (user['three_day_rule']['first_day_change'] / 100)
    second_day_max = 1 + (user['three_day_rule']['second_day_change'] / 100)
    second_day_min = 1 - (user['three_day_rule']['second_day_change'] / 100)
    if ((admin_record['pct_1day'] < first_day_min) or (admin_record['pct_1day'] > first_day_max)):
        if ((admin_record['pct_today'] < second_day_min) or (admin_record['pct_today']> second_day_max)):
            is_day3_apply_result = 'Yes'
    return is_day3_apply_result

# Calculate best stock allocation, get all information to watchlist_info for display
def get_watchlist_data(user, admin_collection):
    total_balance = get_user_balance(user)['total_balance']
    non_watchlist_holding_balance = 0

    # Create a list to store information that user are holding but not in watchlist
    non_watchlist_holding = []
    for symbol, stock_data in user['stocks'].items():
        if symbol not in user['watchlist']:
            latest_price = get_latest_price(symbol)
            stock_balance = stock_data['quantity'] * latest_price
            existing_allocation =  stock_balance / total_balance * 100
            non_watchlist_holding_balance += stock_balance
            non_watchlist_holding.append({
                'symbol': symbol,
                'latest_price': latest_price,
                'holding_shares': stock_data['quantity'],
                'existing_allocation': existing_allocation
            })
    
    # Calculate adjusted_balance and total_sharpe_ratio for further suggested allocation calculation
    total_score = 0
    total_est_pct_close = 0
    count_symbols = 0
    for symbol in user['watchlist']:
        if symbol:
            admin_record = admin_collection.find_one({'symbol': symbol})
            if admin_record:
                if is_day3_apply(user, admin_record) == 'Yes':
                    total_score += 1
                total_score += admin_record['score']
                total_est_pct_close += admin_record['last_est_pct_close']
                count_symbols += 1
    
    # Adjust total investment amount
    non_watchlist_holding_factor = (total_balance - non_watchlist_holding_balance) / total_balance
    average_est_pct_close = total_est_pct_close / count_symbols if count_symbols > 0 else 0
    if average_est_pct_close > 2:
        adjusted_balance = 0.9
    elif average_est_pct_close > 1.5:
        adjusted_balance = 0.8
    elif average_est_pct_close < 0:
        adjusted_balance = 0.5
    else:
        adjusted_balance = 0.7

    # Create a watchlist_info to store all the data that will display in watchlist.html
    watchlist_info = []
    for symbol in user['watchlist']:
        if symbol:
            latest_price = get_latest_price(symbol)
            admin_record = admin_collection.find_one({'symbol': symbol})
            if admin_record:
                yesterday_close_price = admin_record['price']
                news_sentiment = admin_record['sentiment']
                est_close_price = admin_record['last_est_tmr_close']
                est_pct_close = admin_record['last_est_pct_close']
                mse_tmr = admin_record['mse_tmr']
                risk_return = admin_record['risk_return']
                is_day3_apply_result = is_day3_apply(user, admin_record)
                if is_day3_apply_result == 'Yes':
                    day3_factor = 1
                day3_factor = 0
                suggested_allocation = (admin_record['score'] + day3_factor) / total_score * 100 * adjusted_balance * non_watchlist_holding_factor
                
                # Calculate existing allocation percentage
                if symbol in user['stocks']:
                    holding_shares = user['stocks'][symbol]['quantity']
                    existing_allocation = (holding_shares * latest_price) / total_balance * 100
                else:
                    existing_allocation = 0
                    holding_shares = 0

                max_percentage = user.get('max_percentage', 100)  # Get the max_percentage from user, default to 100 if not set
                # Calculate suggested allocation
                if existing_allocation > suggested_allocation:
                    suggested_action = 'sell'
                    suggested_quantity = int(((existing_allocation - suggested_allocation) / 100 * total_balance) / latest_price)
                elif existing_allocation < suggested_allocation:
                    suggested_action = 'buy'
                    # Adjust suggested_allocation if it exceeds max_percentage
                    suggested_allocation = min(suggested_allocation, max_percentage)
                    suggested_quantity = int(((suggested_allocation - existing_allocation) / 100 * total_balance) / latest_price)
                else:
                    suggested_action = None
                    suggested_quantity = None

            else:
                yesterday_close_price = get_yesterday_close_price(symbol)
                news_sentiment = None
                est_close_price = None
                est_pct_close = None
                mse_tmr = None
                risk_return = None
                is_day3_apply_result = None
                holding_shares = 0
                existing_allocation = 0
                suggested_allocation = 0
                suggested_quantity = 0
                suggested_action = None

            percentage_change = ((latest_price - yesterday_close_price) / yesterday_close_price) * 100 if yesterday_close_price != 0 else 0

            watchlist_info.append({
                'symbol': symbol,
                'latest_price': latest_price,
                'yesterday_close_price': yesterday_close_price,
                'percentage_change': percentage_change,
                'news_sentiment': news_sentiment,
                'holding_shares': holding_shares,
                'est_close_price': est_close_price,
                'est_pct_close': est_pct_close,
                'mse_tmr': mse_tmr,
                'risk_return': risk_return,
                'is_day3_apply': is_day3_apply_result,
                'existing_allocation': existing_allocation,
                'suggested_allocation': suggested_allocation,
                'suggested_quantity': suggested_quantity,
                'suggested_action': suggested_action
            })  
    return watchlist_info, non_watchlist_holding

def is_symbol_valid(symbol):
    try:
        latest_price = get_latest_price(symbol)
        if latest_price is not None:
            return True
        else:
            return False
    except Exception as e:
        return False
