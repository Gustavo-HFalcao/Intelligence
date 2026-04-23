
import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_KEY")

def check_table():
    headers = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    # Query one row to see columns
    resp = httpx.get(f"{URL}/rest/v1/login?limit=1", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data:
            print(f"COLUMNS: {list(data[0].keys())}")
        else:
            print("Table 'login' is empty.")
    else:
        print(f"ERROR {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    check_table()
