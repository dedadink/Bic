#!/usr/bin/env python
# coding: utf-8

# In[1]:


import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
import logging
import time
import pytz

# Connect to MetaTrader 5
if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()
else:
    print("Connected")
    time.sleep(2)

# Create a timezone object for the GMT+2 timezone
gmt2 = pytz.timezone('Etc/GMT+2')

# Get the current time in the GMT+2 timezone
current_time = datetime.datetime.now(gmt2)

print(current_time)
# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(message)s', level=logging.INFO)

# Set your trading parameters
symbol = "GBPJPY.a"
stop_loss_pips = 0.035
take_profit_pips = 0.025
pip_scale = 1.00 # 1 pip equals 1 basis point for JPY pairs
magic_number = 88888
pip_conv = 100


def fetch_data(symbol, timeframe, years):
    # Request data
    rates = mt5.copy_rates_range(
        symbol,
        timeframe,
        pd.to_datetime(datetime.datetime.now(gmt2).date()) - pd.DateOffset(years=years),
        pd.to_datetime(datetime.datetime.now(gmt2).date())
    )
    return pd.DataFrame(rates)

def get_levels():

    """Get the highest and lowest prices within the most common bins."""
    # Fetch 10 years of weekly, daily, and 4-hourly data
    weekly_data = fetch_data(symbol, mt5.TIMEFRAME_W1, 10)
    daily_data = fetch_data(symbol, mt5.TIMEFRAME_D1, 5)
    hourly4_data = fetch_data(symbol, mt5.TIMEFRAME_H4, 1)

    # Concatenate the DataFrames
    df = pd.concat([weekly_data, daily_data, hourly4_data], ignore_index=True)

    # Get the latest 1 minute close price
    latest_price = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)['close'][0]

    # Define the ranges
    upper_range = latest_price + 0.45  # range above the latest price
    lower_range = latest_price - 0.45  # range below the latest price
    bin_size = 0.065 # each bin is 2 pips wide

    # Filter the data that falls within the defined ranges
    upper_df = df[(df['high'] >= latest_price) & (df['high'] <= upper_range)]
    lower_df = df[(df['low'] >= lower_range) & (df['low'] <= latest_price)]
    
    # Include close prices in the data
    upper_df = upper_df[['high', 'close']]
    lower_df = lower_df[['low', 'close']]

    # Create bins and count the number of highs, lows and closes within each bin
    upper_bins = np.arange(latest_price, upper_range, bin_size)
    lower_bins = np.arange(lower_range, latest_price, bin_size)

    high_counts, _ = np.histogram(upper_df.values.flatten(), bins=upper_bins)
    low_counts, _ = np.histogram(lower_df.values.flatten(), bins=lower_bins)

    # Get the bin with the highest count for both highs and lows
    top_high_index = high_counts.argmax()
    top_low_index = low_counts.argmax()

    # Define the price zones instead of exact levels
    upper_zone = (upper_bins[top_high_index], upper_bins[top_high_index] + bin_size)
    lower_zone = (lower_bins[top_low_index], lower_bins[top_low_index] + bin_size)

    # Return the calculated zones
    return upper_zone, lower_zone

## Get the SymbolInfo object
symbol_info = mt5.symbol_info(symbol)

if symbol_info is None:
    print("Failed to get symbol info for", symbol)
else:
    # Get the minimum tick size
    tick_size = float(symbol_info.point)  # Use .point instead of .min_step

# Calculate the pip value from the minimum tick size
pip_value = tick_size  # Use .point instead of .min_step

# Get the Bollinger bands levels
upper_zone, lower_zone = get_levels()
print(f"Calculated Bollinger Band Levels1: Lower Zone={lower_zone}, Upper Zone={upper_zone}")

# Initialize flags
trade_opened = False
position_closed = False

# Flags to keep track of whether the previous bar met the conditions
prev_lower_cond = False
prev_upper_cond = False

def move_sl_to(new_sl):
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "sl": new_sl,
        "tp": position.tp,  # Keep the original TP
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
        "volume": float(volume),
        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "price": price,
        "deviation": 30,
        "magic": magic_number,  # Use the variable passed into the function
        "comment": "Partial close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    return result.retcode == mt5.TRADE_RETCODE_DONE

def handle_partial_closure(percentage, price, symbol, magic_number):
    global cumulative_profit_pips
    global remaining_volume
    
    close_volume = remaining_volume * percentage
    result = close_partial_position(order_ticket, close_volume, price, symbol, magic_number)
    if result:
        print(f"{percentage * 100}% of the position closed successfully at price {price}!")
        
        # Calculate profit or loss in pips for this partial closure
        partial_profit_pips = (price - order_price) * pip_conv * close_volume if order_type == mt5.ORDER_TYPE_BUY else (order_price - price) * pip_conv * close_volume
        
        # Update the global cumulative_profit_pips
        cumulative_profit_pips += partial_profit_pips

        remaining_volume -= close_volume
    else:
        print(f"Failed to close {percentage * 100}% of the position")

def on_trade_close():
    global cumulative_profit_pips
    cumulative_profit_pips = 0


# Add a flag to track whether you have already executed a 50% partial closure

partial_closure_done = False
cumulative_profit_pips = 0
new_order_flag = False

# Main program loop
while not position_closed:
    current_time = datetime.datetime.now(gmt2)
    print(datetime.datetime.now())
    
    # Initialize the variable outside the block
    profit_in_pips = 0  
    partial_profit_pips = 0
        
    # At the beginning of your trading loop, check if there is an open position
    positions = mt5.positions_get(symbol=symbol)
    if len(positions) > 0:
        position = positions[0]
        order_type = position.type
        order_price = position.price_open
        order_ticket = position.ticket
        order_volume = position.volume
        remaining_volume = order_volume
        
        if new_order_flag:
            remaining_volume = position.volume
            new_order_flag = False
            
        print(f"Profit in pips: {profit_in_pips}")
        print(f"Remaining volume: {remaining_volume}")    
        
        close_to_lower_pips = (close - lower_zone[0]) * pip_conv
        lower_to_close_pips = (lower_zone[1] - close) * pip_conv
        close_to_upper_pips = (close - upper_zone[0]) * pip_conv
        upper_to_close_pips = (upper_zone[1] - close) * pip_conv
    
        # Get the latest tick data
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            print("Error retrieving tick data:", mt5.last_error())
        else:
            print(f"Latest tick data: {tick}")
            latest_tick_price = tick.last
                                
        # Calculate the stop loss price based on the formula
        stop_loss_price = upper_zone[1] + pip_value * pip_scale * 20
        
        # Calculate partial_profit_pips based on the order type
        if order_type == mt5.ORDER_TYPE_BUY:
            half_way_to_stop_loss = order_price + (stop_loss_price - order_price) * 0.5
            partial_profit_pips = (latest_tick_price - order_price) * pip_conv
        elif order_type == mt5.ORDER_TYPE_SELL:
            half_way_to_stop_loss = order_price - (order_price - stop_loss_price) * 0.5
            partial_profit_pips = (order_price - latest_tick_price) * pip_conv
        
        # Update cumulative_profit_pips
        cumulative_profit_pips += partial_profit_pips
        
        # Handle partial and full closures
        if not partial_closure_done and latest_tick_price >= half_way_to_stop_loss:
            handle_partial_closure(0.5, latest_tick_price, symbol, magic_number)
            partial_closure_done = True
        
        # Check if the latest close price is at 50% of the way to the stop loss
        if order_type == mt5.ORDER_TYPE_BUY:
            cumulative_profit_pips += partial_profit_pips

        elif order_type == mt5.ORDER_TYPE_SELL:
            half_way_to_stop_loss = order_price - (order_price - stop_loss_price) * 0.5
        
        # When closing 50% of the position
        if not partial_closure_done and latest_tick_price >= half_way_to_stop_loss:
            handle_partial_closure(0.5, latest_tick_price, symbol, magic_number)
            partial_closure_done = True
            # Update cumulative_profit_pips
            portion_of_trade_closed = 0.5
            partial_profit_pips = profit_in_pips * portion_of_trade_closed
            cumulative_profit_pips += partial_profit_pips
            
        if profit_in_pips >= 6 and profit_in_pips < 10:
            close_volume = order_volume * 0.3
            if close_partial_position(order_ticket, close_volume, latest_tick_price, symbol, magic_number):
                print("30% of the position closed successfully!")
                remaining_volume -= close_volume  # Update remaining_volume
                print(f"Remaining Volume2: {remaining_volume}")
                
                # Update cumulative_profit_pips
                portion_of_trade_closed = 0.3
                partial_profit_pips = profit_in_pips * portion_of_trade_closed
                cumulative_profit_pips += partial_profit_pips
                
            else:
                print("Failed to close 30% of the position")

            # Move the SL to the break-even point
            move_sl_to(order_price)

        elif profit_in_pips >= 10 and profit_in_pips < 20:
            close_volume = order_volume * 0.3
            if close_partial_position(order_ticket, close_volume, latest_tick_price, symbol, magic_number):
                print("Another 30% of the position closed successfully!")
                remaining_volume -= close_volume  # Update remaining_volume
                print(f"Remaining Volume3: {remaining_volume}")
                
                # Update cumulative_profit_pips
                portion_of_trade_closed = 0.3
                partial_profit_pips = profit_in_pips * portion_of_trade_closed
                cumulative_profit_pips += partial_profit_pips              
                
                # Move the SL to +3 pips
                new_sl = order_price + 3 * pip_value if order_type == mt5.ORDER_TYPE_BUY else order_price - 3 * pip_value
                move_sl_to(new_sl)
                           
            else:
                print("Failed to close 30% of the position")

        elif profit_in_pips >= 20:
            # Move the SL to +10 pips
            new_sl = order_price + 10 * pip_value if order_type == mt5.ORDER_TYPE_BUY else order_price - 10 * pip_value
            move_sl_to(new_sl)
        
        # Handle trade closures
        if remaining_volume == 0:
            final_profit_pips = (latest_tick_price - order_price) * pip_conv if order_type == mt5.ORDER_TYPE_BUY else (order_price - latest_tick_price) * pip_conv
            cumulative_profit_pips += final_profit_pips  # Add the final pips to the cumulative total
           
            print(f"Remaining Volume final: {remaining_volume}")
            print(f"Cumulative profit in pips: {cumulative_profit_pips}")
            
            if cumulative_profit_pips < 0:
                print("Last trade was a loss in pips, waiting for 30 minutes...")
                time.sleep(1800)  # Wait for 30 minutes
            else:
                print("Last trade was a gain in pips, proceeding...")
            
            # Reset for the next trade
            cumulative_profit_pips = 0
            partial_closure_done = False

    time.sleep(5)  # waits for 5 seconds before the next iteration

    # Calculate time in seconds since the last 5-minute mark
    time_since_5min_mark = (current_time.minute % 5) * 60 + current_time.second
    # Check if the time is within 5 seconds after the 5-minute mark
    if time_since_5min_mark < 5:
        print("Within 5 seconds after the 5-minute mark, executing code...")
        wait_time = 300 - time_since_5min_mark  # 300 seconds = 5 minutes
        print(f'Sleeping for {wait_time} seconds until the next 5-minute mark.')
        time.sleep(wait_time)  # Sleep for the calculated wait time

    # Get the latest 5-minute bar data
    print("Fetching latest 5-minute bar data...")
    rates_5m = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1)
    if rates_5m is None:
        print("Error retrieving 5-minute rates:", mt5.last_error())
    else:
        latest_bar_5m = rates_5m[-1]
        
        # Get the latest 1-minute bar data
        print("Fetching latest 1-minute bar data...")
        rates_1m = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
        if rates_1m is None:
            print("Error retrieving 1-minute rates:", mt5.last_error())
        else:
            latest_bar_1m = rates_1m[-1]

        # Analyze the latest close price and its relation with Bollinger Band
        close = latest_bar_1m['close']
        print(f"Latest bar close price: {close}")
    
    if lower_zone[0] <= latest_bar_5m['close'] <= lower_zone[1]:
        print("Close price3 is within the Lower Zone.")
    elif upper_zone[0] <= latest_bar_5m['close'] <= upper_zone[1]:
        print("Close price4 is within the Upper Zone.")
    else:
        print("Close price5 is in the Middle Zone.")
    
    # Sleep for 3 seconds
    time.sleep(5)
    
    # If the latest bar is within the lower Bollinger Band zone
    lower_cond = lower_zone[0] <= latest_bar_5m['close'] <= lower_zone[1]
    if lower_cond and prev_lower_cond:
        print("First condition met. Waiting for 5 minutes...")
        time.sleep(5 * 60)  # Wait for 5 minutes
        
        # Get the latest 5-minute bar data
        print("Fetching latest 5-minute bar data...")
        rates_5m = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1)
        if rates_5m is None:
            print("Error retrieving 5-minute rates:", mt5.last_error())
        else:
            latest_bar_5m = rates_5m[-1]
            
            positions = mt5.positions_get(symbol=symbol)
            # Second condition check
            if lower_cond and prev_lower_cond and len(positions) == 0:
                print("Second condition also met. Executing trade...")
                print("No open position found. Placing buy order...")
                # Open a buy position
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": 1.0,
                    "type": mt5.ORDER_TYPE_BUY,
                    "price": latest_bar_5m['close'],
                    "sl": lower_zone[0] - pip_value * pip_scale * 60,  # stop loss 2 pips below the lower Bollinger band level
                    "tp": upper_zone[1] + pip_value * pip_scale * 20,  # take profit 2 pips above the upper Bollinger band level
                    "deviation": 30,
                    "magic": magic_number,
                    "comment": "Bollinger Buy Signal",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(request)
                
                order_volume = 1.0  # lots
                remaining_volume = order_volume  # Initialize remaining_volume here
                new_order_flag = True
                
                # Check if the order went through
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print("Buy order placed successfully!")
                    trade_opened = True
                    order_type = mt5.ORDER_TYPE_BUY  # Order type
                    order_price = latest_bar_5m['close']  # Entry price
                    order_ticket = result.order  # Order ticket
                else:
                    print("Position opening failed, error code:", result.retcode)
            else:
                print("Second condition not met. Aborting trade...")
    else:
        print("First condition not met. Aborting trade...")
        prev_lower_cond = lower_cond  # Update the flag for the next iteration
    
        
    # If the latest bar is within the upper Bollinger Band zone
    upper_cond = upper_zone[0] <= latest_bar_5m['close'] <= upper_zone[1]
    if upper_cond and prev_upper_cond:
        print("First condition met. Waiting for 5 minutes...")
        time.sleep(5 * 60)  # Wait for 5 minutes
 
        # Get the latest 5-minute bar data
        print("Fetching latest 5-minute bar data...")
        rates_5m = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1)
        if rates_5m is None:
            print("Error retrieving 5-minute rates:", mt5.last_error())
        else:
            latest_bar_5m = rates_5m[-1]
            
            positions = mt5.positions_get(symbol=symbol)
            # Second condition check
            if upper_cond and prev_upper_cond and len(positions) == 0:
                print("Second condition also met. Executing trade...")
                print("No open position found. Placing sell order...")
                request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": 1.0,
                "type": mt5.ORDER_TYPE_SELL,
                "price": latest_bar_5m['close'],
                "sl": upper_zone[1] + pip_value * pip_scale * 60,  # stop loss 2 pips above the upper Bollinger band level
                "tp": lower_zone[0] - pip_value * pip_scale * 20,  # take profit 2 pips below the lower Bollinger band level
                "deviation": 30,
                "magic": magic_number,
                "comment": "Sell order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
                }

                result = mt5.order_send(request)
            
                order_volume = 1.0  # lots
                remaining_volume = order_volume  # Initialize remaining_volume here
                new_order_flag = True
            
                # Check if the order went through
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print("Buy order placed successfully!")
                    trade_opened = True
                    order_type = mt5.ORDER_TYPE_BUY  # Order type
                    order_price = latest_bar_5m['close']  # Entry price
                    order_ticket = result.order  # Order ticket
                else:
                    print("Order Failed, Error Code:", result.retcode)
            else:
                print("Second condition not met. Aborting trade...")
    else:
        print("First condition not met. Aborting trade...")
        prev_upper_cond = upper_cond  # Update the flag for the next iteration
    
    # If the close price is within Bollinger Band range but not close enough to levels
    if lower_zone[1] < latest_bar_5m['close'] < upper_zone[0]:
        # Calculate the difference in pips
        pips_to_lower = (latest_bar_5m['close'] - lower_zone[1]) * pip_conv
        pips_to_upper = (upper_zone[0] - latest_bar_5m['close']) * pip_conv

        print(f"Close price8 is {pips_to_lower} pips above lower zone and {pips_to_upper} pips below upper zone.")
        current_time = datetime.datetime.now(gmt2)
        if current_time.minute not in [0, 5]:
            wait_time = 5 - (current_time.minute % 5)
            print('sleeptime 3:', wait_time)
            time.sleep(wait_time * 60 + 3)  # Sleep for the calculated wait time
            print(f"Close is within range but not close enough to levels. Waiting for {wait_time} minutes until the next bar.")
            
    # At the end of the loop, check if levels need to be recalculated
    if latest_bar_5m['close'] < lower_zone[0] or latest_bar_5m['close'] > upper_zone[1]:
        print("Latest bar close price9 is outside the Bollinger band zones, recalculating levels.")
        upper_zone, lower_zone = get_levels()
        print(f"Calculated Bollinger Band Levels2: Lower Zone2={lower_zone}, Upper Zone2={upper_zone}")
        
    # Sleep for 1 second    
    time.sleep(5)

                            
                            


# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:




 


# In[ ]:





# In[ ]:






# In[ ]:




