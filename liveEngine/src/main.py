import requests
import json
import pyotp
from logzero import logger
import pandas as pd
import warnings
from SmartApi import SmartConnect
import datetime
import time
import os

# Suppress warnings
warnings.filterwarnings('ignore')

# List of stock names
name_list = ["NIFTY","BANKNIFTY", "ASIANPAINT", "BRITANNIA", "CIPLA", "EICHERMOT", "NESTLEIND", "GRASIM", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ITC", "LT", "M&M", "RELIANCE", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "WIPRO",
    "APOLLOHOSP", "DRREDDY", "TITAN", "SBIN", "SHRIRAMFIN", "BPCL", "KOTAKBANK", "INFY", "BAJFINANCE",
    "ADANIENT", "SUNPHARMA", "JSWSTEEL", "HDFCBANK", "TCS", "ICICIBANK", "POWERGRID", "MARUTI",
    "INDUSINDBK", "AXISBANK", "HCLTECH", "ONGC", "NTPC", "COALINDIA", "BHARTIARTL", "TECHM", "LTIM",
    "DIVISLAB", "ADANIPORTS", "HDFCLIFE", "SBILIFE", "ULTRACEMCO", "BAJAJ-AUTO", "BAJAJFINSV"
]

# Function to initialize the symbol token map and filter by stock names
def intializeSymbolTokenMap():
    url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
    response = requests.get(url)
    if response.status_code == 200:
        d = response.json()
        global token_df
        token_df = pd.DataFrame.from_dict(d)
        token_df['expiry'] = pd.to_datetime(token_df['expiry'], errors='coerce')  # Convert to datetime, handle errors
        token_df = token_df.dropna(subset=['expiry'])  # Drop rows where expiry is NaT
        token_df = token_df.astype({'strike': float})

        # Filter by stock names
        token_df = token_df[token_df['name'].isin(name_list)]  
        token_df.to_csv("data/memoryData/token_filtered.csv")
        logger.info("Filtered Token Map Downloaded")
    else:
        logger.error(f"Failed to download token map: {response.status_code}")

# Function to get valid expiry dates for each stock from the token map
def get_valid_expiry_dates(stock_name):
    global token_df
    # Filter expiry dates for the stock from the token dataframe
    valid_expiries = token_df[token_df['name'] == stock_name]['expiry'].unique()
    return valid_expiries

# Function to save the data to a JSON file
def save_to_json(stock, data):
    if data:  # Only save if there's data
        file_name = f'data/IVjsons/{stock}.json'
        with open(file_name, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Saved option Greeks for {stock} to {file_name}")

# Function to fetch option Greeks for a stock and its expiry dates
def fetch_option_greeks(obj, stock, expiry):
    params = {"name": stock, "expirydate": expiry.strftime("%d%b%Y").upper()}
    try:
        option_greeks_response = obj.optionGreek(params)

        if option_greeks_response and 'data' in option_greeks_response:
            optionGreek = pd.DataFrame(option_greeks_response['data'])

            # Check if the DataFrame is not empty
            if not optionGreek.empty:
                stock_greeks = []
                for _, row in optionGreek.iterrows():
                    stock_greeks.append({
                        "name": row['name'],
                        "expiry": row['expiry'],
                        "strikePrice": row['strikePrice'],
                        "optionType": row['optionType'],
                        "delta": row['delta'],
                        "gamma": row['gamma'],
                        "theta": row['theta'],
                        "vega": row['vega'],
                        "impliedVolatility": row['impliedVolatility'],
                        "tradeVolume": row['tradeVolume']
                    })
                logger.info(f"Fetched option Greeks for {stock} on {expiry}")
                return stock_greeks
            else:
                logger.error(f"Option Greeks DataFrame is empty for {stock} on {expiry}")
        else:
            logger.error(f"No data available for {stock} on {expiry}")

    except Exception as e:
        if "exceeding access rate" in str(e):
            logger.error(f"Rate limit exceeded for {stock} on {expiry}, retrying in 2 seconds...")
            time.sleep(2)  # Wait before retrying
            return fetch_option_greeks(obj, stock, expiry)  # Retry
        else:
            logger.error(f"Error fetching option Greeks for {stock} on {expiry}: {e}")

    return None

# Main function to handle login and fetch Greeks sequentially with a 1-second delay
def main():
    # Initialize credentials
    api_key = 'Wre9DhsK'  # Replace with your API key
    client_code = 'A53186177'  # Replace with your client code
    password = '4120'  # Replace with your password
    totp_secret = 'L5VV4FV2UZBEYWFAQYU3IGERKI'  # Replace with your TOTP secret

    # Initialize SmartConnect object
    obj = SmartConnect(api_key=api_key)

    # Generate TOTP for 2FA login
    token = pyotp.TOTP(totp_secret).now()

    # Authenticate and create a session
    try:
        data = obj.generateSession(client_code, password, token)
        print(data)
        if data["status"]:
            logger.info("Login Successful")
            now = datetime.datetime.now()
            tdate = now.strftime("%d-%m-%Y")
            logger.info(f"Current Date: {tdate}")

            # Initialize the symbol token map
            try:
                intializeSymbolTokenMap()
            except Exception as e:
                logger.error(f"Token Symbol Download error: {e}")

            # Run the loop indefinitely
            while True:
                intializeSymbolTokenMap()
                # Iterate over each stock in name_list
                for stock in name_list:
                    valid_expiries = get_valid_expiry_dates(stock)
                    stock_greeks = []  # To store all Greeks for this stock

                    # Iterate over all valid expiries for the stock
                    for expiry in valid_expiries:
                        greeks = fetch_option_greeks(obj, stock, expiry)
                        if greeks:
                            stock_greeks.extend(greeks)

                        # Introduce a 1-second delay to avoid exceeding the rate limit
                        time.sleep(1)

                    # Save the Greeks data to JSON for the current stock
                    save_to_json(stock, stock_greeks)

                # Delay between loops to avoid overloading the server
                logger.info("Completed one round of fetching. Waiting for 60 seconds before next run.")
                time.sleep(30)  # Wait 1 minute before fetching again

        else:
            logger.error("Login Error")
    except Exception as e:
        logger.error(f"Login not Done: {e}")

if __name__ == "__main__":
    main()
