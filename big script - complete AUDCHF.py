#!/usr/bin/env python
# coding: utf-8

# In[1]:


import logging
import MetaTrader5 as mt5
import pandas as pd #pip install pandas
import plotly.express as px #pip install plotly
from datetime import datetime
from datetime import timedelta
import time

# Set up logging
logging.basicConfig(filename='trading_log.txt', level=logging.INFO)

        #strategy parameters
SYMBOL = "AUDCHF.a"
VOLUME = 2.0
TIMEFRAME = mt5.TIMEFRAME_M1
DEVIATION = 20
        
# Connect to MetaTrader 5
mt5.initialize()

# login to Trade Account with login()
# make sure that trade server is enabled in MT5 client terminal

Login = 51214935
password = '6ZpDgMcq'
server = 'ICMarkets-Demo'

# attempt to enable the display of the AUDCHF.a in MarketWatch
selected = mt5.symbol_select("AUDCHF.a", True)

# get account info
account_info = mt5.account_info()
print(account_info)

# getting specific account data
login_number = account_info.login
balance = account_info.balance
equity = account_info.equity

print()
print('balance: ', balance)

# display the last AUDCHF.a tick
lasttick = mt5.symbol_info_tick("AUDCHF.a")
print(lasttick)
# display tick field values in the form of a list
print("Show symbol_info_tick(\"AUDCHF.a\")._asdict():")
symbol_info_tick_dict = mt5.symbol_info_tick("AUDCHF.a")._asdict()
for prop in symbol_info_tick_dict:
    print("  {}={}".format(prop, symbol_info_tick_dict[prop]))
    
symbol_info = mt5.symbol_info ("AUDCHF.a")._asdict()
symbol_info    

# Calculate the start time as 4 hours ago from the current time
end_time = datetime.now()
start_time = end_time - timedelta(hours=4)

# ohlc_data, changing to 1 minute below changes suport and resistnace significantly
ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))

fig = px.line(ohlc_data, x='time', y='close')
ohlc_data

#using this same OHLC data, we can code 

# Tick volume check
#check 10 most recent Tick Volumes, 
#if 10 most recent tick volumes are <10, wait one hour and loop back to # Calculate the start time as 4 hours ago from the current time
#if 10 most recent are >10, continue.


# Calculate support and resistance levels
close = ohlc_data['close']
SUPPORT_LEVEL = close.min()
resistance_level = close.max()

# Check if support and resistance levels can be set
if SUPPORT_LEVEL is None or resistance_level is None:
    logging.info("Support and resistance levels cannot be set.")
else:
    logging.info("Support and resistance levels set at {} and {}.".format(SUPPORT_LEVEL, resistance_level))
print('support_level: ', SUPPORT_LEVEL)
print('resistance_level: ', resistance_level)

time.sleep(900)  # Wait for 15 minutes

       
# Trade rules for selling

# Initial request for the most recent tick data
close = ohlc_data['close']
logging.info("New Close: {}".format(close))

end_time = datetime.now()
start_time = end_time - timedelta(minutes=15)

ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))

if (close < SUPPORT_LEVEL).all():
    logging.info("Close value fell below the support level. Waiting for 15 minutes.")
    time.sleep(900)  # Wait for 15 minutes

    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=15)
    ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))

    if (close < SUPPORT_LEVEL).all():
        logging.info("Close value fell below the support level. Waiting for 30 minutes.")
        time.sleep(1800)  # Wait for 30 minutes

    if (close > SUPPORT_LEVEL).any():
        for _ in range(10):
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=15)
            ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))
            if (close >= SUPPORT_LEVEL).any():
                logging.info("Close value is above the support level. Waiting for it to go below again.")
                time.sleep(900)  # Wait for 15 minutes
            else:
                break
        else:
            logging.info("Close value is still above the support level after multiple checks. Checking trade rules for buying.")

            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=15)        
            ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))
            if (close <= 0.050 * SUPPORT_LEVEL).any():
                logging.info("Close value is below or equal to 0.050 times the support level. Waiting for 30 minutes.")
                time.sleep(1800)  # Wait for 30 minutes

            if (close <= 0.050 * SUPPORT_LEVEL).any():
                # Send order to the market code here
                symbol = "AUDCHF.a"
                symbol_info = mt5.symbol_info(symbol)
                lot = 0.1
                point = mt5.symbol_info(symbol).point
                price = mt5.symbol_info_tick(symbol).bid  # Use bid price for sell trade
                deviation = 20
                
                # Calculate SL and TP levels
                sl_price = price + 100 * point  # Set SL level 100 points above the current bid price
                tp_price = price - 100 * point  # Set TP level 100 points below the current bid price
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot,
                    "type": mt5.ORDER_TYPE_SELL,
                    "price": price,   
                    "sl": sl_price,
                    "tp": tp_price,    
                    "deviation": deviation,
                    "magic": 5,    
                    "comment": "python script open",    
                    "type_time": mt5.ORDER_TIME_GTC,    
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }                
                # send a trading request
                result = mt5.order_send(request)                  
                # check the execution result
                print("1. order_send(): by {} {} lots at {} with deviation={} points".format(symbol, lot, price, deviation))
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print("2. order_send failed, retcode={}".format(result.retcode))
                    # request the result as a dictionary and display it element by element
                    result_dict = result._asdict()
                    for field in result_dict.keys():
                        print("   {}={}".format(field, result_dict[field]))
                        # if this is a trading request structure, display it element by element as well
                        if field == "request":
                            traderequest_dict = result_dict[field]._asdict()
                            for tradereq_field in traderequest_dict:
                                print("       traderequest: {}={}".format(tradereq_field, traderequest_dict[tradereq_field]))
                                print("2. order_send done, ", result)
                                print("   opened position with POSITION_TICKET={}".format(result.order))
                                print("   sleep 2 seconds before closing position #{}".format(result.order))  
    
            if (close >= 0.050 * SUPPORT_LEVEL).all():
                for _ in range(300):
                    end_time = datetime.now()
                    start_time = end_time - timedelta(minutes=1)
                    ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M1, start_time, end_time))
                    if (close >= 0.050 * SUPPORT_LEVEL).all():
                        logging.info("Close value is above the support level. Waiting for it to go below again.")
                        time.sleep(60)  # Wait for 1 minute
                    if (close <= 0.050 * SUPPORT_LEVEL).all():
                        # Send order to the market code here
                        symbol = "AUDCHF.a"
                        symbol_info = mt5.symbol_info(symbol)
                        
                        lot = 0.1
                        point = mt5.symbol_info(symbol).point
                        price = mt5.symbol_info_tick(symbol).bid  # Use bid price for sell trade
                        deviation = 20
                        
                        # Calculate SL and TP levels
                        sl_price = price + 100 * point  # Set SL level 100 points above the current bid price
                        tp_price = price - 100 * point  # Set TP level 100 points below the current bid price
                        
                        request = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": symbol,
                            "volume": lot,
                            "type": mt5.ORDER_TYPE_SELL,
                            "price": price,   
                            "sl": sl_price,
                            "tp": tp_price,    
                            "deviation": deviation,
                            "magic": 5,    
                            "comment": "python script open",    
                            "type_time": mt5.ORDER_TIME_GTC,    
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }
                    
                        # send a trading request
                        result = mt5.order_send(request)
                    
                        # check the execution result
                        print("1. order_send(): by {} {} lots at {} with deviation={} points".format(symbol, lot, price, deviation))
                        if result.retcode != mt5.TRADE_RETCODE_DONE:
                            print("2. order_send failed, retcode={}".format(result.retcode))
                            # request the result as a dictionary and display it element by element
                            result_dict = result._asdict()
                            for field in result_dict.keys():
                                print("   {}={}".format(field, result_dict[field]))
                            
                                # if this is a trading request structure, display it element by element as well
                                if field == "request":
                                    traderequest_dict = result_dict[field]._asdict()
                                    for tradereq_field in traderequest_dict:
                                        print("       traderequest: {}={}".format(tradereq_field, traderequest_dict[tradereq_field]))
                                        print("2. order_send done, ", result)
                                        print("   opened position with POSITION_TICKET={}".format(result.order))
                                        print("   sleep 2 seconds before closing position #{}".format(result.order))  


    #buying code:
    # Initial request for the most recent tick data
close = ohlc_data['close']
logging.info("New Close: {}".format(close))

end_time = datetime.now()
start_time = end_time - timedelta(minutes=15)

ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))

# Trade rules for selling
if (close < resistance_level).all():
    logging.info("Close value fell below the support level. Waiting for 15 minutes.")
    time.sleep(900)  # Wait for 15 minutes
    
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=15)
    ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))
    
    if (close < resistance_level).all():
        logging.info("Close value fell below the support level. Waiting for 30 minutes.")
        time.sleep(1800)  # Wait for 30 minutes

    if (close > resistance_level).any():
        for _ in range(10):
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=15)
            ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))
            
            if (close > resistance_level).any():
                logging.info("Close value is above the support level. Waiting for it to go below again.")
                time.sleep(900)  # Wait for 15 minutes
            else:
                break
    else:
        logging.info("Close value is still above the support level after multiple checks. Checking trade rules for buying.")

end_time = datetime.now()
start_time = end_time - timedelta(minutes=15)        
ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M15, start_time, end_time))

if (close >= 0.050 * resistance_level).any():
    logging.info("Close value is below or equal to 0.050 times the support level. Waiting for 30 minutes.")
    time.sleep(1800)  # Wait for 30 minutes
    
    if (close >= 0.050 * resistance_level).any():
        # Send order to the market code here
        symbol = "AUDCHF.a"
        symbol_info = mt5.symbol_info(symbol)
        lot = 0.1
        point = mt5.symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).bid  # Use bid price for sell trade
        deviation = 20                
        # Calculate SL and TP levels
        sl_price = price + 100 * point  # Set SL level 100 points above the current bid price
        tp_price = price - 100 * point  # Set TP level 100 points below the current bid price   
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": price,   
            "sl": sl_price,
            "tp": tp_price,    
            "deviation": deviation,
            "magic": 5,    
            "comment": "python script open",    
            "type_time": mt5.ORDER_TIME_GTC,    
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        # send a trading request
        result = mt5.order_send(request)
        # check the execution result
        print("1. order_send(): by {} {} lots at {} with deviation={} points".format(symbol, lot, price, deviation))
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("2. order_send failed, retcode={}".format(result.retcode))
            # request the result as a dictionary and display it element by element
            result_dict = result._asdict()
            for field in result_dict.keys():
                print("   {}={}".format(field, result_dict[field]))
                # if this is a trading request structure, display it element by element as well
                if field == "request":
                    traderequest_dict = result_dict[field]._asdict()
                    for tradereq_field in traderequest_dict:
                        print("       traderequest: {}={}".format(tradereq_field, traderequest_dict[tradereq_field]))
                        print("2. order_send done, ", result)
                        print("   opened position with POSITION_TICKET={}".format(result.order))
                        print("   sleep 2 seconds before closing position #{}".format(result.order))  
                        if (close < 0.050 * resistance_level).any():
                            for _ in range(300):
                                end_time = datetime.now()
                                start_time = end_time - timedelta(minutes=1)
                                ohlc_data = pd.DataFrame(mt5.copy_rates_range("AUDCHF.a", mt5.TIMEFRAME_M1, start_time, end_time))
                                if (close <= 0.050 * resistance_level).any():
                                    logging.info("Close value is above the support level. Waiting for it to go below again.")
                                    time.sleep(60)  # Wait for 1 minute
                                    if (close >= 0.050 * resistance_level).any():
                                        # Send order to the market code here
                                        symbol = "AUDCHF.a"
                                        symbol_info = mt5.symbol_info(symbol)                                     
                                        lot = 0.1
                                        point = mt5.symbol_info(symbol).point
                                        price = mt5.symbol_info_tick(symbol).bid  # Use bid price for sell trade
                                        deviation = 20 
                                        # Calculate SL and TP levels
                                        sl_price = price + 100 * point  # Set SL level 100 points above the current bid price
                                        tp_price = price - 100 * point  # Set TP level 100 points below the current bid price                                    
                                        request = {
                                            "action": mt5.TRADE_ACTION_DEAL,
                                            "symbol": symbol,
                                            "volume": lot,
                                            "type": mt5.ORDER_TYPE_SELL,
                                            "price": price,   
                                            "sl": sl_price,
                                            "tp": tp_price,    
                                            "deviation": deviation,
                                            "magic": 5,    
                                            "comment": "python script open",    
                                            "type_time": mt5.ORDER_TIME_GTC,    
                                            "type_filling": mt5.ORDER_FILLING_IOC,
                                        } 
                                        # send a trading request
                                        result = mt5.order_send(request)                    
                                        # check the execution result
                                        print("1. order_send(): by {} {} lots at {} with deviation={} points".format(symbol, lot, price, deviation))
                                        if result.retcode != mt5.TRADE_RETCODE_DONE:
                                            print("2. order_send failed, retcode={}".format(result.retcode))
                                            # request the result as a dictionary and display it element by element
                                            result_dict = result._asdict()
                                            for field in result_dict.keys():
                                                print("   {}={}".format(field, result_dict[field]))
                                                # if this is a trading request structure, display it element by element as well
                                                if field == "request":
                                                    traderequest_dict = result_dict[field]._asdict()
                                                    for tradereq_field in traderequest_dict:
                                                        print("       traderequest: {}={}".format(tradereq_field, traderequest_dict[tradereq_field]))
                                                        print("2. order_send done, ", result)
                                                        print("   opened position with POSITION_TICKET={}".format(result.order))
                                                        print("   sleep 2 seconds before closing position #{}".format(result.order))  
                                


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




