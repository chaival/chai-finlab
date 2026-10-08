import os
import time
import json
import yfinance as yf
import streamlit as st
from pymongo import MongoClient
from google import genai

if not os.path.exists("api_outputs"):
    os.makedirs("api_outputs")

# An expanded market scan including high-debt and low-ROCE traps
tickers = ["RELIANCE", "TCS", "INFY", "ZOMATO", "SUZLON", "YESBANK", "ITC", "HDFCBANK"]

# PASTE YOUR GEMINI API KEY INSIDE THE QUOTES BELOW
# Pulls the secure key from Streamlit's secrets
api_key = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=api_key)
# Connect to MongoDB Cloud
mongo_client = MongoClient(st.secrets["MONGO_URI"])
db = mongo_client["chai_finlab"]       # This creates a database named 'chai_finlab'
collection = db["alpha_reports"]       # This creates a collection (like a folder) for your reports

print(f"\n[+] Initializing Chai FinLab Algorithmic Funnel...\n")

for ticker_input in tickers:
    try:
        full_ticker = f"{ticker_input}.NS"
        print(f"[*] Scanning {ticker_input}...")

        stock = yf.Ticker(full_ticker)
        info = stock.info

        market_cap = info.get("marketCap", "N/A")
        pe_ratio = info.get("trailingPE", "N/A")
        current_price = info.get("currentPrice", "N/A")
        promoter_holding = info.get("heldPercentInsiders", "N/A")
        
        raw_de = info.get("debtToEquity", "N/A")
        debt_to_equity = round(raw_de / 100, 2) if isinstance(raw_de, (int, float)) else raw_de

        try:
            cf = stock.cashflow
            fcf = float(cf.loc['Operating Cash Flow'].iloc[0] + cf.loc['Capital Expenditure'].iloc[0])
        except Exception:
            fcf = "N/A"

        try:
            bs = stock.balance_sheet
            inc = stock.financials
            roce = float((inc.loc['EBIT'].iloc[0] / (bs.loc['Total Assets'].iloc[0] - bs.loc['Current Liabilities'].iloc[0])) * 100)
        except Exception:
            roce = info.get("returnOnEquity", "N/A")
            if isinstance(roce, (int, float)):
                roce = float(roce * 100)

        # --- THE CHAI FORMULA GATEKEEPER ---
        # 1. Reject high leverage
        if isinstance(debt_to_equity, (int, float)) and debt_to_equity > 1.0:
            print(f"    [-] REJECTED: D/E ({debt_to_equity}x) exceeds 1.0x limit. Skipping AI compute.")
            continue
            
        # 2. Reject low capital efficiency
        if isinstance(roce, (int, float)) and roce < 15.0:
            print(f"    [-] REJECTED: ROCE ({roce:.2f}%) is below 15% threshold. Skipping AI compute.")
            continue

        print(f"    [+] PASSED FILTERS: Sending to AI Reasoning Engine...")

        prompt = f"""
        Evaluate {ticker_input} (NSE India) based on:
        Price: {current_price}, P/E: {pe_ratio}, Market Cap: {market_cap}, FCF: {fcf}, D/E: {debt_to_equity}, Promoter Holding: {promoter_holding}, ROCE: {roce}.
        
        Provide a 4-sentence strict fundamental analysis verdict.
        
        CRITICAL INSTRUCTION: You must respond ONLY with a valid, raw JSON object. Do not include markdown formatting, code blocks (like ```json), or any other text.
        Use this exact schema:
        {{
            "ticker": "{ticker_input}",
            "metrics": {{
                "current_price": {current_price},
                "pe_ratio": {pe_ratio if isinstance(pe_ratio, float) else f'"{pe_ratio}"'},
                "free_cash_flow": {fcf if isinstance(fcf, float) else f'"{fcf}"'},
                "debt_to_equity": {debt_to_equity if isinstance(debt_to_equity, float) else f'"{debt_to_equity}"'},
                "roce_percent": {round(roce, 2) if isinstance(roce, float) else f'"{roce}"'}
            }},
            "chai_formula_verdict": "Your 4-sentence evaluation goes here."
        }}
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        raw_output = response.text.strip()
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:-3].strip()
            
        json_data = json.loads(raw_output)

        filename = f"api_outputs/{ticker_input}_data.json"
        # Push the AI synthesis directly to MongoDB
        collection.insert_one(json_data)
        print(f"    [SUCCESS] JSON API payload generated: {filename}")
        time.sleep(3)

    except Exception as e:
        print(f"    [-] Failed to process {ticker_input}: {e}")

print("\n[SUCCESS] Algorithmic Funnel execution complete!\n")