from dateutil.parser import parse as parse_date
from decimal import Decimal
from datetime import date, timedelta
import requests
import re
from dotenv import load_dotenv
import os
from diskcache import Cache

load_dotenv()

senator_data = requests.get(
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions_for_senators.json"
).json()


def parse_transaction_amount(amount):
    ranges = {
        "$1,001 - $15,000": (1001, 15000),
        "$15,001 - $50,000": (15001, 50000),
        "$50,001 - $100,000": (50001, 100000),
        "$100,001 - $250,000": (100001, 250000),
        "$250,001 - $500,000": (250001, 500000),
        "$500,001 - $1,000,000": (500001, 1000000),
        "$1,000,001 - $5,000,000": (1000001, 5000000),
        "$5,000,001 - $25,000,000": (5000001, 25000000),
        "$25,000,001 - $50,000,000": (25000001, 50000000),
        "Over $50,000,000": (50000000, 50000000),
    }
    return ranges[amount]


def estimate_transaction_amount(amount):
    return sum(parse_transaction_amount(amount)) / 2


stock_data_cache = Cache(".cache")

@stock_data_cache.memoize(expire=60*60*24)
def load_alphavantage_data(ticker):
    print(f"Stock data for {ticker} not loaded yet... getting now...")
    r = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "apikey": os.getenv("ALPHAVANTAGE_API_KEY"),
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "full",
        },
    )
    print(f"    ...done and cached!")
    return r.json()


def stock_price(ticker, date):
    stock_data = load_alphavantage_data(ticker)

    if "Time Series (Daily)" not in stock_data:
        print(f"{ticker} has no known timeseries")
        return None
    
    date_str = date.strftime("%Y-%m-%d")
    
    if date_str not in stock_data["Time Series (Daily)"]:
        print(f"{ticker} has no known timeseries")
        return None
    
    return float(stock_data["Time Series (Daily)"][date_str][
        "5. adjusted close"
    ])


def parse_ticker(ticker):
    return re.sub("<[^<]+?>", "", ticker)


def preprocess_data():
    for senator in senator_data:
        for transaction in senator["transactions"]:
            if "type" in transaction and transaction["type"] == "Exchange":
                tickers = parse_ticker(transaction["ticker"]).strip().split()
                purchased_ticker = tickers[0]

                senator["transactions"].append({
                    "transaction_date": transaction["transaction_date"],
                    "owner": transaction["owner"],
                    "ticker": purchased_ticker,
                    "asset_description": transaction["asset_description"],
                    "asset_type": transaction["asset_type"],
                    "type": "Purchase",
                    "amount": transaction["amount"],
                    "comment": transaction["comment"],
                    "ptr_link": transaction["ptr_link"]
                })
                continue

            if "ticker" not in transaction or transaction["ticker"] == "--":
                continue

            # Clean the ticker (strip HTML)
            transaction["ticker"] = parse_ticker(transaction["ticker"])
            amount = estimate_transaction_amount(transaction["amount"])

            price = stock_price(
                transaction["ticker"], parse_date(transaction["transaction_date"])
            )
            if price is None:
                continue
            shares = amount / price
            transaction["shares"] = shares


def portfolio_breakdown(transactions, date):
    total = 0
    unaccounted = []
    positions = {}

    for transaction in sorted(
        transactions, key=lambda k: parse_date(k["transaction_date"])
    ):
        transaction_date = parse_date(transaction["transaction_date"])

        if transaction_date > date:
            break
        print(transaction)
        ticker = transaction["ticker"]
        if ticker == "--":
            continue

        if transaction["type"] == "Purchase":
            if ticker in positions:
                positions[ticker] += transaction["shares"]
            else:
                positions[ticker] = transaction["shares"]
            total += estimate_transaction_amount(transaction["amount"])
        elif transaction["type"] == "Sale (Partial)":
            if ticker in positions:
                positions[ticker] -= transaction["shares"]
                total -= estimate_transaction_amount(transaction["amount"])
            else:
                # Unaccounted for sale!
                unaccounted.append(transaction)
        elif transaction["type"] == "Exchange":
            if ticker in positions:
                positions[ticker] += transaction["shares"]
                total -= estimate_transaction_amount(transaction["amount"])
        elif transaction["type"] == "Sale (Full)":
            if ticker in positions:
                positions[ticker] = 0
                total -= estimate_transaction_amount(transaction["amount"])
            else:
                # Unaccounted for sale!
                unaccounted.append(transaction)
        else:
            raise RuntimeError("unknown transaction type: " + transaction["type"])
            
    # value = sum(
    #     amount * stock_price(ticker, date) 
    # )

    value = 0

    for (ticker, amount) in positions.items():
        if amount <= 0:
            continue
        price = stock_price(ticker, date)
        if price is None:
            continue
        value += amount * price
        
    
    return {
        "positions": positions,
        "unaccounted": unaccounted,
        "total": total,
        "value": value,
    }


preprocess_data()
# print(senator_data[0]["transactions"])

portfolio = portfolio_breakdown(senator_data[0]["transactions"], parse_date("5/7/19"))
print(portfolio["value"])
print(portfolio["total"])
print(portfolio["positions"])

start_date = parse_date("Jan 1 2020")
end_date = parse_date("Dec 31, 2020")
delta = timedelta(days=1)
value = []

while start_date <= end_date:
    print(start_date)
    portfolio = portfolio_breakdown(senator_data[0]["transactions"], start_date)
    value.append(portfolio["value"] / portfolio["total"])
    start_date += delta

print(value)

# figure out 0.0 issue
# plot against spy, compare to senatestockwatch
# start on website



