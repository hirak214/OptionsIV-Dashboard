
import os
import json
import pyotp
import threading
from logzero import logger
import pandas as pd
import warnings
from SmartApi import SmartConnect
import datetime
import time
import requests
from flask import Flask, render_template, request, jsonify
import keys

# Suppress warnings
warnings.filterwarnings('ignore')

# Flask app initialization
app = Flask(__name__)

# Folder for saving fetched JSON files
DATA_FOLDER = 'data/IVjsons'

# Ensure the data folder exists
os.makedirs(DATA_FOLDER, exist_ok=True)

# Global variables for user-selected stock and expiry
selected_stock = None
selected_expiry = None

# List of stock names
name_list = ["NIFTY", "BANKNIFTY", "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC", "ADANIENT", "ADANIPORTS", "ALKEM", "AMBUJACEM", "APOLLOHOSP", "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "ATUL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA", "BATAINDIA", "BEL", "BERGEPAINT", "BHARATFORG", "BHARTIARTL", "BHEL", "BIOCON", "BOSCHLTD", "BPCL", "BRITANNIA", "BSOFT", "CANBK", "CANFINHOME", "CHAMBLFERT", "CHOLAFIN", "CIPLA", "COALINDIA", "COFORGE", "COLPAL", "CONCOR", "COROMANDEL", "CROMPTON", "CUB", "CUMMINSIND", "DABUR", "DALBHARAT", "DEEPAKNTR", "DIVISLAB", "DIXON", "DLF", "DRREDDY", "EICHERMOT", "ESCORTS", "EXIDEIND", "FEDERALBNK", "FINNIFTY", "GAIL", "GLENMARK", "GMRINFRA", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES", "GRASIM", "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDCOPPER", "HINDPETRO", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDEA", "IDFC", "IDFCFIRSTB", "IEX", "IGL", "INDHOTEL", "INDIAMART", "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFY", "IOC", "IPCALAB", "IRCTC", "ITC", "JINDALSTEL", "JKCEMENT", "JSWSTEEL", "JUBLFOOD", "KOTAKBANK", "LALPATHLAB", "LAURUSLABS", "LICHSGFIN", "LT", "LTF", "LTIM", "LTTS", "LUPIN", "M&M", "M&MFIN", "MANAPPURAM", "MARICO", "MARUTI", "MCX", "METROPOLIS", "MFSL", "MGL", "MIDCPNIFTY", "MOTHERSON", "MPHASIS", "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI", "NAVINFLUOR", "NESTLEIND", "NIFTYNXT50", "NMDC", "NTPC", "OBEROIRLTY", "OFSS", "ONGC", "PAGEIND", "PEL", "PERSISTENT", "PETRONET", "PFC", "PIDILITIND", "PIIND", "PNB", "POLYCAB", "POWERGRID", "PVRINOX", "RAMCOCEM", "RBLBANK", "RECLTD", "RELIANCE", "SAIL", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SRF", "SUNPHARMA", "SUNTV", "SYNGENE", "TATACHEM", "TATACOMM", "TATACONSUM", "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM", "TRENT", "TVSMOTOR", "UBL", "ULTRACEMCO", "UNITDSPR", "UPL", "VEDL", "VOLTAS", "WIPRO", "ZYDUSLIFE"]
#sort name list by 1st letter
name_list.sort()

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

# Function to get valid expiry dates for the selected stock from the token map
def get_valid_expiry_dates(stock_name):
    global token_df
    valid_expiries = token_df[token_df['name'] == stock_name]['expiry'].unique()

    if stock_name not in ["NIFTY", "BANKNIFTY","MIDCPNIFTY","NIFTYNXT50","FINNIFTY"]:
        # Group expiries by year and month, and get the last expiry of each month
        df = pd.DataFrame({'expiry': valid_expiries})
        df['year'] = df['expiry'].dt.year
        df['month'] = df['expiry'].dt.month
        last_expiries = df.groupby(['year', 'month'])['expiry'].max().values
        return pd.to_datetime(last_expiries)
    return pd.to_datetime(valid_expiries)

# Flask route for the web UI
@app.route('/', methods=['GET', 'POST'])
def index():
    global selected_stock, selected_expiry

    if request.method == 'POST':
        # Reset expiry when a new stock is selected
        new_stock = request.form.get('stock')
        if new_stock != selected_stock:
            selected_expiry = None  # Reset expiry selection if new stock is selected
        selected_stock = new_stock
        selected_expiry = request.form.get('expiry')

    # Load expiry dates if a stock is selected
    expiry_dates = []
    if selected_stock and selected_stock != '--selected stock--':
        expiry_dates = sorted(get_valid_expiry_dates(selected_stock))

    # Render the template with default values if nothing is selected
    return render_template(
        'index.html',
        stock_names=name_list,
        selected_stock=selected_stock or "--selected stock--",
        expiry_dates=expiry_dates,
        selected_expiry=selected_expiry or "--selected expiry--"
    )

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

# Flask API endpoint to serve option Greeks data
@app.route('/get_data')
def get_data():
    global selected_stock, selected_expiry
    stock_greeks = []
    message = ""
    data_found = False

    if selected_stock and selected_expiry and selected_expiry != "--selected expiry--":
        expiry_dt = pd.to_datetime(selected_expiry).date()
        file_name = f'{DATA_FOLDER}/{selected_stock}.json'
        if os.path.exists(file_name):
            with open(file_name, 'r') as f:
                stock_greeks = json.load(f)
            if stock_greeks:  # Check if the file contains data
                data_found = True
                message = f"Data for {selected_stock} and {expiry_dt.strftime('%d-%b-%Y')} found."
            else:
                message = f"No data available for {selected_stock} and {expiry_dt.strftime('%d-%b-%Y')}."
        else:
            message = f"No data found for {selected_stock} and {expiry_dt.strftime('%d-%b-%Y')}."
    else:
        message = "No stock or expiry selected."

    return jsonify({'data': stock_greeks, 'data_found': data_found, 'message': message})

# Main function to handle login and fetch Greeks sequentially with a 1-second delay
def main():
    # Initialize credentials
    api_key = keys.api_key # Replace with your API key
    client_code = keys.client_code  # Replace with your client code
    password = keys.password
    totp_secret = keys.totp_secret

    # Initialize SmartConnect object
    obj = SmartConnect(api_key=api_key)

    # Generate TOTP for 2FA login
    token = pyotp.TOTP(totp_secret).now()

    # Authenticate and create a session
    try:
        data = obj.generateSession(client_code, password, token)
        if data["status"]:
            logger.info("Login Successful")

            # Initialize the symbol token map
            intializeSymbolTokenMap()

            # Start Flask app in a separate thread
            flask_thread = threading.Thread(target=lambda: app.run(use_reloader=False, host='0.0.0.0', port=5006))
            flask_thread.start()

            # Run the loop indefinitely
            while True:
                # Fetch the selected stock and expiry from global variables
                if selected_stock and selected_expiry and selected_expiry != "--selected expiry--":
                    logger.info(f"Fetching data for {selected_stock} with expiry {selected_expiry}")
                    stock_greeks = fetch_option_greeks(obj, selected_stock, pd.to_datetime(selected_expiry))

                    if stock_greeks:
                        # Save the fetched data
                        file_name = f'{DATA_FOLDER}/{selected_stock}.json'
                        with open(file_name, 'w') as f:
                            json.dump(stock_greeks, f, indent=4)
                        logger.info(f"Saved option Greeks for {selected_stock} to {file_name}")

                    # Introduce a 1-second delay to avoid exceeding the rate limit
                    time.sleep(1)

                # Introduce a delay to avoid overloading the server
                time.sleep(1)

        else:
            logger.error("Login Error")
    except Exception as e:
        logger.error(f"Login not Done: {e}")

if __name__ == "__main__":
    main()
