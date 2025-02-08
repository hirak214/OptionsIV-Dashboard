from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Assign variables
api_key = os.getenv("API_KEY")
client_code = os.getenv("CLIENT_CODE")
password = os.getenv("PASSWORD")
totp_secret = os.getenv("TOTP_SECRET")