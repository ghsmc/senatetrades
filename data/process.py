from dateutil.parser import parse as parse_date
from decimal import Decimal
import requests
import re

senator_data = requests.get(
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions_for_senators.json"
).json()


# replace the "demo" apikey below with your own key from https://www.alphavantage.co/support/#api-key
# url = 'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=IBM&apikey=demo'
# r = requests.get(url)
# data = r.json()


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


def parse_ticker(ticker):
    return re.sub("<[^<]+?>", "", ticker)


def preprocess_data():
    for senator in senator_data:
        for transaction in senator["transactions"]:
            if "ticker" not in transaction:
                continue
            
            # Clean the ticker (strip HTML)
            transaction["ticker"] = parse_ticker(transaction["ticker"])
            amount = estimate_transaction_amount(transaction["amount"])
            stockprice = 100
            shares = amount / stockprice

            transaction["shares"] = shares


def portfolio_breakdown(transactions, date):
    portfolio = {
        "_total": 0,
        "_unaccounted": []
    }
    print("well, the function ran.")

    for transaction in sorted(transactions, key=lambda k: parse_date(k["transaction_date"])):
        transaction_date = parse_date(transaction["transaction_date"])

        if transaction_date > date:
            break
        print(transaction)
        ticker = transaction["ticker"]
        if ticker == "--":
            continue

        if transaction["type"] == "Purchase":
            if ticker in portfolio:
                portfolio[ticker] += transaction["shares"]
            else:
                portfolio[ticker] = transaction["shares"]
            portfolio["_total"] += estimate_transaction_amount(transaction["amount"])
        elif transaction["type"] == "Sale (Partial)":
            if ticker in portfolio:
                portfolio[ticker] -= transaction["shares"]
                portfolio["_total"] -= estimate_transaction_amount(transaction["amount"])
            else:
                # Unaccounted for sale!
                portfolio["_unaccounted"].append(transaction)
        elif transaction["type"] == "Sale (Full)":
            if ticker in portfolio:
                portfolio[ticker] = 0
                portfolio["_total"] -= estimate_transaction_amount(transaction["amount"])
            else:
                # Unaccounted for sale!
                portfolio["_unaccounted"].append(transaction)
        else:
            raise RuntimeError("unknown transaction type: " + transaction["type"])
    return portfolio

preprocess_data()
print(senator_data[0]["transactions"])
print(portfolio_breakdown(senator_data[0]["transactions"], parse_date("11/12/21")))
