#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
import logging
import time
import pytz


def initialize_mt5():
    if not mt5.initialize():
        print("initialize() failed")
        mt5.shutdown()
    else:
        print("Connected")
        time.sleep(2)

def setup_logging():
    logger = logging.getLogger(__name__)
    logging.basicConfig(format='%(message)s', level=logging.INFO)

def set_trading_params():
    global symbol, stop_loss_pips, take_profit_pips, pip_scale, magic_number, pip_conv
    symbol = "GBPJPY.a"
    stop_loss_pips = 0.035
    take_profit_pips = 0.025
    pip_scale = 1.00
    magic_number = 88888
    pip_conv = 100

def fetch_data(symbol, timeframe, years):
    rates = mt5.copy_rates_range(
        symbol,
        timeframe,
        pd.to_datetime(datetime.datetime.now(gmt2).date()) - pd.DateOffset(years=years),
        pd.to_datetime(datetime.datetime.now(gmt2).date())
    )
    return pd.DataFrame(rates)

def get_levels():
    weekly_data = fetch_data(symbol, mt5.TIMEFRAME_W1, 10)
    daily_data = fetch_data(symbol, mt5.TIMEFRAME_D1, 5)
    hourly4_data = fetch_data(symbol, mt5.TIMEFRAME_H4, 1)
    df = pd.concat([weekly_data, daily_data, hourly4_data], ignore_index=True)
    latest_price = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)['close'][0]
    upper_range = latest_price + 0.45
    lower_range = latest_price - 0.45
    bin_size = 0.065
    upper_df = df[(df['high'] >= latest_price) & (df['high'] <= upper_range)]
    lower_df = df[(df['low'] >= lower_range) & (df['low'] <= latest_price)]
    upper_df = upper_df[['high', 'close']]
    lower_df = lower_df[['low', 'close']]
    upper_bins = np.arange(latest_price, upper_range, bin_size)
    lower_bins = np.arange(lower_range, latest_price, bin_size)
    high_counts, _ = np.histogram(upper_df.values.flatten(), bins=upper_bins)
    low_counts, _ = np.histogram(lower_df.values.flatten(), bins=lower_bins)
    top_high_index = high_counts.argmax()
    top_low_index = low_counts.argmax()
    upper_zone = (upper_bins[top_high_index], upper_bins[top_high_index] + bin_size)
    lower_zone = (lower_bins[top_low_index], lower_bins[top_low_index] + bin_size)
    return upper_zone, lower_zone

def get_symbol_info():
    global tick_size, pip_value
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print("Failed to get symbol info for", symbol)
    else:
        tick_size = float(symbol_info.point)
        pip_value = tick_size

def move_sl_to(new_sl, order_ticket, position):
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "sl": new_sl,
        "tp": position.tp,
        "position": order_ticket,
        "deviation": 30,
    }
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"Stop loss moved to {new_sl} successfully!")
    else:
        print("Failed to move stop loss, error code:", result.retcode)
        
def close_partial_position(ticket, volume, price, symbol, magic_number):
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        print("Position not found")
        return False
    position = None;
    for pos in positions:
        if pos.ticket == ticket and pos.magic == magic_number:
            position = pos
            break
    if position is None:
        print("Position not found")
        return False
    request = {
        "action": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "symbol": position.symbol,
        "volume": float(0.30*),
        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "price": price,
        "deviation": 30,
        "magic": magic_number,
        "comment": "Partial close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    return result.retcode == mt5.TRADE_RETCODE_DONE

def handle_partial_closure(percentage, price, symbol, magic_number, order_ticket, order_type, order_price, order_volume, remaining_volume, pip_conv):
    global cumulative_profit_pips
    close_volume = remaining_volume * percentage
    result = close_partial_position(order_ticket, close_volume, price, symbol, magic_number)
    if result:
        print(f"{percentage * 100}% of the position closed successfully at price {price}!")
        partial_profit_pips = (price - order_price) * pip_conv * close_volume if order_type == mt5.ORDER_TYPE_BUY else (order_price - price) * pip_conv * close_volume
        cumulative_profit_pips += partial_profit_pips
        remaining_volume -= close_volume
    else:
        print(f"Failed to close {percentage * 100}% of the position")

def on_trade_close():
    global cumulative_profit_pips
    cumulative_profit_pips = 0

def main():
    initialize_mt5()
    setup_logging()
    set_trading_params()
    get_symbol_info()
    upper_zone, lower_zone = get_levels()
    print(f"Calculated Bollinger Band Levels1: Lower Zone={lower_zone}, Upper Zone={upper_zone}")
    trade_opened = False
    position_closed = False
    prev_lower_cond = False
    prev_upper_cond = False
    partial_closure_done = False
    cumulative_profit_pips = 0
    new_order_flag = False
    while not position_closed:
        # Main trading logic here
        pass  # Replace with your trading logic

if __name__ == '__main__':
    main()

# Function to fetch account information
def fetch_account_info():
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to fetch account information.")
        return None
    return {
        'balance': account_info.balance,
        'equity': account_info.equity,
        'margin': account_info.margin,
        'free_margin': account_info.margin_free,
        'margin_level': account_info.margin_level,
    }


def trade_management(account_info, upper_zone, order_price, latest_tick_price, pip_value, pip_scale, partial_closure_done):
    # Risk Management: Calculate the lot size based on account balance (assuming 'account_info' contains the balance)
    account_balance = account_info['balance']
    risk_percent = 0.01  # Assuming 1% risk per trade
    lot_size = (account_balance * risk_percent) / 1000  # Replace 1000 with appropriate value based on your risk calculation

    # Stop Loss and Take Profit in pips
    stop_loss_pips = 0.035
    take_profit_pips = 0.025

    # Calculate the Stop Loss Price
    stop_loss_price = upper_zone[1] + pip_value * pip_scale * 20

    # Calculate the price level for partial closure (trailing stop)
    half_way_to_stop_loss = order_price + (stop_loss_price - order_price) * 0.5
    if not partial_closure_done and latest_tick_price >= half_way_to_stop_loss:
        # Here, you can add the logic to partially close the trade, modify the stop loss, etc.
        pass

    # Return the calculated values for use in other functions
    return lot_size, stop_loss_pips, take_profit_pips, stop_loss_price


def manage_wait_times(last_trade_result, time_since_5min_mark, current_time):
    # Short Wait (2 seconds)
    time.sleep(2)

    # Long Wait (30 minutes) after a losing trade (assuming 'last_trade_result' contains this info)
    if last_trade_result == 'loss':
        print("Last trade was a loss in pips, waiting for 30 minutes...")
        time.sleep(1800)

    # General Short Wait (5 seconds)
    time.sleep(5)

    # Wait until the next 5-minute mark (assuming 'time_since_5min_mark' contains the time since the last 5-minute mark)
    wait_time = 300 - time_since_5min_mark
    print(f'Sleeping for {wait_time} seconds until the next 5-minute mark.')
    time.sleep(wait_time)

    # Another Wait Time Calculation (assuming 'current_time' contains the current time)
    wait_time = 5 - (current_time.minute % 5)
    print(f'sleeptime 3: {wait_time}')
    time.sleep(wait_time * 60 + 3)


def execute_trade(trade_type, request):
    # Sending the trade order (assuming 'request' contains the necessary order parameters)
    result = mt5.order_send(request)
    
    # Console feedback based on the trade type (assuming 'trade_type' is either 'buy' or 'sell')
    if trade_type == 'buy':
        print("Placing buy order...")
    elif trade_type == 'sell':
        print("Placing sell order...")
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print("Trade execution failed, error code:", result.retcode)
    
    # Return the result for further processing or logging
    return result


check_counter = 0  # Initialize a counter to keep track of consecutive condition checks

def check_entry_conditions(latest_bar_5m, lower_zone, upper_zone):
    global check_counter  # Use the global counter variable
    # Evaluate conditions
    lower_cond = lower_zone[0] <= latest_bar_5m['close'] <= lower_zone[1]
    upper_cond = upper_zone[0] <= latest_bar_5m['close'] <= upper_zone[1]
    
    if lower_cond or upper_cond:
        check_counter += 1  # Increment the counter
        if check_counter >= 2:  # Check if conditions held true twice
            check_counter = 0  # Reset the counter
            return True  # Conditions met, eligible for trade entry
    else:
        check_counter = 0  # Reset the counter if conditions are not met
    
    return False  # Conditions not met, not eligible for trade entry

# Function to check if a trade is active
def trade_is_active():
    positions = mt5.positions_get(symbol=symbol)
    return positions is not None and len(positions) > 0

def manage_partial_closures(profit_in_pips, order_volume):
    close_volume = 0  # Initialize the volume to close
    
    # Evaluate conditions for partial closures
    if profit_in_pips >= 6 and profit_in_pips < 10:
        close_volume = order_volume * 0.3
    elif profit_in_pips >= 10 and profit_in_pips < 20:
        close_volume = order_volume * 0.3
    
    # Here, you can add the logic to actually close the trade based on close_volume
    # For example, call a function that sends a close order with the calculated close_volume
    
    return close_volume  # Return the calculated close_volume for logging or further processing


# Initialize variables (Replace these initializations with actual data fetching and calculations)
latest_bar_5m = {'close': 1.2000}
lower_zone = [1.1990, 1.1995]
upper_zone = [1.2005, 1.2010]
last_trade_result = 'win'  # This should be set based on actual trading logic
time_since_5min_mark = 120  # This should be calculated based on data
current_time = None  # This should be set to the current time
profit_in_pips = 8  # This should be calculated based on open trades
order_volume = 1.0  # This should be set based on trading logic
trade_type = 'buy'  # This should be set based on trading logic
request = None  # This should be prepared based on trading conditions


# Main trading loop
while True:
    main
    # Fetch latest data, update indicators, etc.
    latest_bar_5m = fetch_data(symbol, mt5.TIMEFRAME_M5, 1).iloc[-1]
    account_info = fetch_account_info()

    # Check trade entry conditions
    eligible_for_trade = check_entry_conditions(latest_bar_5m, lower_zone, upper_zone)
    
    if eligible_for_trade or trade_is_active():
        # Calculate trading parameters
        lot_size, stop_loss_pips, take_profit_pips, stop_loss_price = trade_management(account_info, upper_zone, latest_bar_5m['close'], latest_bar_5m['close'], pip_value, pip_scale, partial_closure_done)
        
        if eligible_for_trade:
            positions = mt5.positions_get(symbol=symbol)
            if positions is None:
                
                # Determine trade direction based on some condition (replace with your actual logic)
                trade_direction = 'buy' if some_buy_condition else 'sell'
                request = {
                    "action": mt5.ORDER_TYPE_BUY if trade_direction == 'buy' else mt5.ORDER_TYPE_SELL,
                    "symbol": symbol,
                    "volume": 1,
                    "price": latest_bar_5m['close'],
                    "deviation": 30,
                    "magic": magic_number,
                    "comment": "Opening trade",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                result = execute_trade(trade_direction, request)

    
         # If a trade is active, manage the trade
        if trade_is_active():  
           # Fetch the latest price data (you can use either tick data or 1-second bars)
            one_second_data = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_S1, datetime.datetime.now()
            # Calculate trading parameters
            lot_size, stop_loss_pips, take_profit_pips, stop_loss_price = trade_management(account_info, upper_zone, mt5.TIMEFRAME_S1['close'], pip_value, pip_scale, partial_closure_done)
                                          
            # Manage partial closures
            close_volume = manage_partial_closures(profit_in_pips, order_volume)
            
            if close_volume > 0:
                # Prepare and execute the partial closure
                request = {
                    # ... (your request parameters here, using close_volume)
                }
                execute_trade('handle_partial_closure', request)
                move_sl_to
            time.sleep(1)  # Sleep for one second before the next iteration
                                     
    # Manage wait times
    manage_wait_times(last_trade_result, time_since_5min_mark, current_time)

