from flask import Flask, render_template, request, redirect, url_for, session
from flask_bcrypt import Bcrypt, check_password_hash
from flask_pymongo import PyMongo
from bson import ObjectId
from dotenv import load_dotenv
import os
import io
import base64
from datetime import datetime, timedelta

from virtual_trade import get_latest_price, buy_stock, sell_stock, can_sell_stock, can_buy_stock, get_user_balance, get_watchlist_data, is_symbol_valid
from risk_return_analysis import generate_risk_return_plot, sort_watchlist
from day3_trade import get_stock_data, plot_signals, get_trade_data, calculate_cumulative_percentage_gain


app = Flask(__name__, static_url_path='/static')
load_dotenv()
bcrypt = Bcrypt(app)

# Configure MongoDB
app.config['MONGO_URI'] = os.getenv('MONGODB_URI')
mongo = PyMongo(app)

# Secret key for session management
app.secret_key = os.getenv('SECRET_KEY')

# Define user schema
users_collection = mongo.db.users
admin_collection = mongo.db.admin


@app.route('/')
def home():
    user_id = session.get('user_id')
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    return render_template('home.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = users_collection.find_one({'username': username})

        # Store in session if login success
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            return redirect(url_for('portfolio'))

        # Handle login failure
        return render_template('login.html', error='Invalid username or password. Please try again.')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the username already exists
        existing_user = users_collection.find_one({'username': username})
        if existing_user:
            return render_template('signup.html', error='Username already exists. Please choose a different one.')

        # Hash the password before storing it
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        initial_cash_value = 100000
        new_user = {
            'username': username,
            'password': hashed_password,
            'cash_value': initial_cash_value,
            'stocks': {},
            'watchlist': [],
            'three_day_rule': {
                'first_day_change': 4,
                'second_day_change': 3
            },
            'max_percentage': 40
        }
        user_id = users_collection.insert_one(new_user).inserted_id

        # Log in the new user
        session['user_id'] = str(user_id)
        return redirect(url_for('portfolio'))
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/portfolio')
def portfolio():
    user_id = session.get('user_id')
    if user_id:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        user_balance = get_user_balance(user)
        return render_template('portfolio.html', user=user, user_balance=user_balance)  
    else:
        return redirect(url_for('home'))

@app.route('/get_stock_info', methods=['POST'])
def get_stock_info():
    if request.method == 'POST':
        stock_symbol = request.form.get('stock_symbol').upper()
        user_id = session.get('user_id')
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        user_balance = get_user_balance(user)
        if is_symbol_valid(stock_symbol):          
            latest_price = get_latest_price(stock_symbol)
            session['stock_info'] = {
                'symbol': stock_symbol,
                'latest_price': latest_price,
            }
            return render_template('portfolio.html', user=user, stock_info=session.get('stock_info'), user_balance=user_balance)
        else:
            return render_template('portfolio.html', user=user, user_balance=user_balance, 
                                   symbol_valid_message="Please enter a valid symbol in US market")

@app.route('/watchlist')
def watchlist():
    # Fetch user data from the session or database
    user_id = session.get('user_id')
    if user_id:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        user_balance = get_user_balance(user)
        watchlist_info, non_watchlist_holding = get_watchlist_data(user, admin_collection)
        return render_template('watchlist.html', user=user, user_balance=user_balance, watchlist_info=watchlist_info, non_watchlist_holding=non_watchlist_holding)
    else:
        # Redirect to home if the user is not logged in
        return redirect(url_for('home'))

@app.route('/add_to_watchlist', methods=['POST'])
def add_to_watchlist():
    symbol = request.form.get('symbol').upper()
    user_id = session.get('user_id')
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    user_balance = get_user_balance(user)
    if is_symbol_valid(symbol):
        users_collection.update_one({'_id': ObjectId(user_id)}, {'$addToSet': {'watchlist': symbol}})
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        watchlist_info, non_watchlist_holding = get_watchlist_data(user, admin_collection)
        redirect_url = request.form.get('redirect_url')
        if redirect_url == 'risk_return':
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            watchlist = user.get('watchlist', [])
            risk_return_plot = generate_risk_return_plot(watchlist, start_date, end_date)
            sorted_watchlist = sort_watchlist(watchlist, start_date, end_date)
            return render_template('risk_return.html', user=user, user_balance=user_balance, sorted_watchlist=sorted_watchlist,
                                    risk_return_plot=risk_return_plot, start_date=start_date, end_date=end_date)
        else:
            return render_template('watchlist.html', user=user, user_balance=user_balance, watchlist_info=watchlist_info, non_watchlist_holding=non_watchlist_holding)
    else:
        watchlist_info, non_watchlist_holding = get_watchlist_data(user, admin_collection)
        redirect_url = request.form.get('redirect_url')
        if redirect_url == 'risk_return':
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            watchlist = user.get('watchlist', [])
            risk_return_plot = generate_risk_return_plot(watchlist, start_date, end_date)
            sorted_watchlist = sort_watchlist(watchlist, start_date, end_date)
            return render_template('risk_return.html', user=user, user_balance=user_balance, sorted_watchlist=sorted_watchlist,
                                    risk_return_plot=risk_return_plot, start_date=start_date, end_date=end_date,
                                    symbol_valid_message="Please enter a valid symbol in US market")
        else:
             return render_template('watchlist.html', user=user, user_balance=user_balance, watchlist_info=watchlist_info,
                                    symbol_valid_message="Please enter a valid symbol in US market", non_watchlist_holding=non_watchlist_holding)

@app.route('/delete_from_watchlist', methods=['POST'])
def delete_from_watchlist():
    user_id = session.get('user_id')
    symbol_to_delete = request.form.get('symbol')
    redirect_url = request.form.get('redirect_url')
    users_collection.update_one(
        {'_id': ObjectId(user_id)},
        {'$pull': {'watchlist': symbol_to_delete}}
    )

    user = users_collection.find_one({'_id': ObjectId(user_id)})
    user_balance = get_user_balance(user)
    watchlist_info, non_watchlist_holding = get_watchlist_data(user, admin_collection)

    if redirect_url == 'risk_return':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        watchlist = user.get('watchlist', [])
        risk_return_plot = generate_risk_return_plot(watchlist, start_date, end_date)
        sorted_watchlist = sort_watchlist(watchlist, start_date, end_date)
        return render_template('risk_return.html', user=user, user_balance=user_balance, sorted_watchlist=sorted_watchlist,
                                risk_return_plot=risk_return_plot, start_date=start_date, end_date=end_date)
    else:
        return render_template('watchlist.html', user=user, user_balance=user_balance, watchlist_info=watchlist_info, non_watchlist_holding=non_watchlist_holding)

@app.route('/buy_sell', methods=['POST'])
def buy_sell():
    if request.method == 'POST':
        symbol = request.form.get('symbol')
        quantity = int(request.form.get('quantity'))
        action = request.form.get('action')
        user_id = session.get('user_id')
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        user_balance = get_user_balance(user)
        
        if action == 'buy':
            if not can_buy_stock(user, symbol, quantity):
                return render_template('portfolio.html', user=user, stock_info=session.get('stock_info'), error='Not enough money to buy.', user_balance=user_balance)
            buy_stock(user, symbol, quantity)

        elif action == 'sell':
            if not can_sell_stock(user, symbol, quantity):
                return render_template('portfolio.html', user=user, stock_info=session.get('stock_info'), error='Not enough quantity to sell.', user_balance=user_balance)
            sell_stock(user, symbol, quantity)

        users_collection.update_one({'_id': ObjectId(user['_id'])}, {'$set': user})
        new_user_balance = get_user_balance(user)
        return render_template('portfolio.html', user=user, stock_info=session.get('stock_info'), user_balance=new_user_balance)

@app.route('/execute_trades', methods=['POST'])
def execute_trades():
    user_id = session.get('user_id')
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    watchlist_info, non_watchlist_holding = get_watchlist_data(user, admin_collection)
    
    for item in watchlist_info:
        symbol = item['symbol']
        action = item['suggested_action']
        quantity = int(item['suggested_quantity'])
        
        if action == 'buy' and quantity!= 0 :
            buy_stock(user, symbol, quantity)
        elif action == 'sell' and quantity!= 0 :
            sell_stock(user, symbol, quantity)

    new_watchlist_info, non_watchlist_holding = get_watchlist_data(user, admin_collection)
    users_collection.update_one({'_id': ObjectId(user['_id'])}, {'$set': user})
    user_balance = get_user_balance(user)
    return render_template('watchlist.html', user=user, user_balance=user_balance, watchlist_info=new_watchlist_info, non_watchlist_holding=non_watchlist_holding)


@app.route('/setting', methods=['GET', 'POST'])
def settings():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    return render_template('setting.html', user=user)

@app.route('/setting/change_password', methods=['POST'])
def change_password():
    user_id = session.get('user_id')
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    user_id = session.get('user_id')
    user = users_collection.find_one({'_id': ObjectId(user_id)})

    # Check if old password is correct
    if bcrypt.check_password_hash(user['password'], old_password):
        if new_password == confirm_password:
            # Hash the new password and update user data
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'password': hashed_password}})
            return render_template('setting.html', user=user, success_password=True)
        else:
            return render_template('setting.html', user=user, wrong_password=False, password_mismatch=True)
    else:
        return render_template('setting.html', user=user, wrong_password=True, password_mismatch=False)

@app.route('/setting/set_three_day_rule', methods=['POST'])
def set_three_day_rule():
    first_day_change = float(request.form.get('first_day_change'))
    second_day_change = float(request.form.get('second_day_change'))

    user_id = session.get('user_id')
    users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'three_day_rule': {'first_day_change': first_day_change, 'second_day_change': second_day_change}}})
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    return render_template('setting.html', user=user, success_three_day=True)

@app.route('/setting/set_max_percentage', methods=['POST'])
def set_max_percentage():
    max_percentage = float(request.form.get('max_percentage'))

    user_id = session.get('user_id')
    users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'max_percentage': max_percentage}})
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    return render_template('setting.html', user=user, success_max=True)

@app.route('/day3_trade', methods=['GET', 'POST'])
def day3_trade():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if request.method == 'POST':

        stock_symbol = request.form.get('stock_symbol')
        if is_symbol_valid(stock_symbol):
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            change1day = float(request.form.get('change1day'))
            change2day = float(request.form.get('change2day'))

            stock_data = get_stock_data(stock_symbol, start_date, end_date, change2day, change1day)
            img_buf = io.BytesIO()
            plot_signals(stock_data, img_buf)

            trade_data = get_trade_data(stock_data)
            num_trades = len(trade_data)
            cumulative_percentage_gain = calculate_cumulative_percentage_gain(trade_data)

            img_base64 = base64.b64encode(img_buf.getvalue()).decode('utf-8')

            return render_template('day3_trade.html', user=user, result=True,
                                num_trades=num_trades, cumulative_percentage_gain=cumulative_percentage_gain,
                                day3_chart=img_base64, trade_data=trade_data)
        else:
            return render_template('day3_trade.html', user=user, result=False,
                                    symbol_valid_message="Please enter a valid stock symbol")

    return render_template('day3_trade.html', user=user, result=False)

@app.route('/risk_return', methods=['GET', 'POST'])
def risk_return():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        return redirect(url_for('risk_return', start_date=start_date, end_date=end_date))
 
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if start_date is None or end_date is None:
        start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d')
        end_date = datetime.today().strftime('%Y-%m-%d')

    user = users_collection.find_one({'_id': ObjectId(user_id)})
    user_balance = get_user_balance(user)
    watchlist = user.get('watchlist', [])
    sorted_watchlist = sort_watchlist(watchlist, start_date, end_date)
    risk_return_plot = generate_risk_return_plot(watchlist, start_date, end_date)
    
    return render_template('risk_return.html', user=user, user_balance=user_balance, sorted_watchlist=sorted_watchlist,
                           risk_return_plot=risk_return_plot, start_date=start_date, end_date=end_date)

if __name__ == '__main__':
    app.run(debug=True)