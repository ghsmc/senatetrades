from dateutil.parser import parse as parse_date
from decimal import Decimal
from datetime import date, datetime, timedelta
import requests
import re
from dotenv import load_dotenv
import os
from diskcache import Cache
from tqdm import tqdm
from heapq import nlargest
import json

load_dotenv()


def loadopensecrets(id):
    opensecrets_data = requests.get(
        "https://www.opensecrets.org/api/?method=candSummary",
        params={
            "cid": id,
            "apikey": os.getenv("OPEN_SECRETS_API_KEY"),
            "output": "json",
        },
    ).json()

    attributes = opensecrets_data["response"]["summary"]

    senator_open_secrets = {
        "next_election": attributes["next_election"],
        "total_raised": attributes["total"],
        "total_spent": attributes["spent"],
        "cash_on_hand": attributes["cash_on_hand"],
    }

    return senator_open_secrets


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


@stock_data_cache.memoize(expire=60 * 60 * 24)
def load_alphavantage_data(ticker):
    tqdm.write(f"Stock data for {ticker} not loaded yet... getting now...")
    r = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "apikey": os.getenv("ALPHAVANTAGE_API_KEY"),
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "full",
        },
    )
    tqdm.write(f"    ...done and cached!")
    return r.json()


def stock_price(ticker, date):
    stock_data = load_alphavantage_data(ticker)

    if "Time Series (Daily)" not in stock_data:
        tqdm.write(f"{ticker} is invalid, {stock_data}")
        return None

    date_str = date.strftime("%Y-%m-%d")

    if date_str not in stock_data["Time Series (Daily)"]:
        i = 0
        while i < 5:
            parse_date(date_str) - timedelta(days=i)
            if str(date_str) in stock_data["Time Series (Daily)"]:
                return float(
                    stock_data["Time Series (Daily)"][date_str]["5. adjusted close"]
                )
            if str(date_str) not in stock_data["Time Series (Daily)"]:
                for j in range(4):
                    time_delta = timedelta(days=j) 
                    if str(parse_date(date_str) - time_delta) in stock_data["Time Series (Daily)"]:
                        return float(
                            stock_data["Time Series (Daily)"][date_str]["5. adjusted close"]                        
                        )
                i += 1
            i += 1
        return None

    return float(stock_data["Time Series (Daily)"][date_str]["5. adjusted close"])


def parse_ticker(ticker):
    return re.sub("<[^<]+?>", "", ticker)


def preprocess_data():
    for senator in tqdm(senator_data, "Preprocessing data"):
        for transaction in senator["transactions"]:
            if "amount" not in transaction:
                transaction[
                    "ignored"
                ] = "ignored because no amount was specified in the transaction"
                continue
            elif "transaction_date" not in transaction:
                transaction[
                    "ignored"
                ] = "ignored because the transaction was missing a transaction date"
                continue

            if "type" in transaction and transaction["type"] == "Exchange":
                tickers = parse_ticker(transaction["ticker"]).strip().split()
                purchased_ticker = tickers[0]

                senator["transactions"].append(
                    {
                        "transaction_date": transaction["transaction_date"],
                        "owner": transaction["owner"],
                        "ticker": purchased_ticker,
                        "asset_description": transaction["asset_description"],
                        "asset_type": transaction["asset_type"],
                        "type": "Purchase",
                        "amount": transaction["amount"],
                        "comment": transaction["comment"],
                        "ptr_link": transaction["ptr_link"],
                    }
                )
                continue

            if "ticker" not in transaction or transaction["ticker"] == "--":
                transaction["ignored"] = "ignored because there was no ticker"
                continue

            # Clean the ticker (strip HTML)
            transaction["ticker"] = parse_ticker(transaction["ticker"])
            amount = estimate_transaction_amount(transaction["amount"])

            price = stock_price(
                transaction["ticker"], parse_date(transaction["transaction_date"])
            )
            if price is None:
                transaction[
                    "ignored"
                ] = "ignored because AlphaVantage could not retrieve a stock price at this point in time"
                continue
            shares = amount / price
            transaction["shares"] = shares


def portfolio_breakdown(senatordata, date):
    total = 0
    cash = 0
    sales = 0
    purchases = 0
    unaccounted = []
    positions = {}

    transactions = senatordata["transactions"]

    transactions = filter(lambda k: "ignored" not in k, transactions)

    for transaction in sorted(
        transactions, key=lambda k: parse_date(k["transaction_date"])
    ):
        transaction_date = parse_date(transaction["transaction_date"])

        if transaction_date > date:
            break
        ticker = transaction["ticker"]

        if transaction["type"] == "Purchase":
            total += estimate_transaction_amount(transaction["amount"])
            purchases += 1
            if ticker in positions:
                positions[ticker] += transaction["shares"]
            else:
                positions[ticker] = transaction["shares"]
        elif transaction["type"] == "Sale (Partial)":
            if ticker in positions:
                sales += 1
                positions[ticker] -= transaction["shares"]
                cash += estimate_transaction_amount(transaction["amount"])
            else:
                # Unaccounted for sale!
                unaccounted.append(transaction)
        elif transaction["type"] == "Exchange":
            if ticker in positions:
                positions[ticker] += transaction["shares"]
                total += estimate_transaction_amount(transaction["amount"])
        elif transaction["type"] == "Sale (Full)":
            sales += 1
            if ticker in positions:
                positions[ticker] = 0
                cash += estimate_transaction_amount(transaction["amount"])
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
        "value": value + cash,
        "purchases": purchases,
        "sales": sales,
        "cash": cash,
        "name": senatordata["first_name"] + " " + senatordata["last_name"],
    }


preprocess_data()
processed_data = {}

total_returns=0
total_values=0
total_sales = 0
total_purchases = 0
average_daily_returns = []

for senator in tqdm(senator_data, "Calculating returns"):
    start_date = parse_date("Jan 1 2020")
    end_date = datetime.now()
    delta = timedelta(days=1)
    returns = {}
    senator_names = []

    while start_date <= end_date:
        portfolio = portfolio_breakdown(senator, start_date)
        if portfolio["total"] == 0:
            returns[start_date.isoformat()] = portfolio["value"] / 1
        else:
            returns[start_date.isoformat()] = portfolio["value"] / portfolio["total"]
        start_date += delta

    # opensecretsinformation = loadopensecrets("N00027658")

    stockpositions = portfolio["positions"]
    top4 = nlargest(4, stockpositions, key=stockpositions.get)

    totalshares = 0
    othershares = 0

    # # TODO: is this what I want?
    # for position, shares in stockpositions.items():
    #     totalshares += shares
    #     for i in range(4):
    #         totalshares - stockpositions[top4[i]]["shares"]
    #     othershares = totalshares

    senator_dict = {
        "name": portfolio["name"],
        "estimated_return": list(returns.values())[-1],
        "portfolio_value": portfolio["value"],
        "sales": portfolio["sales"],
        "purchases": portfolio["purchases"],
        "returns": returns,
        "positions": portfolio["positions"]
        # "top_positions": {
        #     "ticker1": {"shares": stockpositions[top4[0]]},
        #     "ticker2": {"shares": stockpositions[top4[1]]},
        #     "ticker3": {"shares": stockpositions[top4[2]]},
        #     "ticker4": {"shares": stockpositions[top4[3]]},
        #     "other": {"shares": othershares},
        # }
        # "total_raised": opensecretsinformation["total_raised"],
        # "total_spent": opensecretsinformation["total_spent"],
        # "cash_on_hand": opensecretsinformation["cash_on_hand"],
        # "next_election": opensecretsinformation["next_election"],
    }

    senator_names.append(senator_dict["name"])
    total_returns += senator_dict["estimated_return"] 
    total_values += senator_dict["portfolio_value"]
    total_sales += senator_dict["sales"]
    total_purchases += senator_dict["purchases"]


    tqdm.write(f"Processed {portfolio['name']}!")
    processed_data[portfolio["name"]] = senator_dict
    processed_data["senator_names"] = senator_names
    processed_data["daily_summary"] = daily_summary

daily_summary = {
    "estimated_return": total_returns/len(senator_names),
    "portfolio_value": total_values/len(senator_names),
    "sales": total_sales/len(senator_names),
    "purchases": total_purchases/len(senator_names),
    "average_daily_returns": average_daily_returns,
    "positions": portfolio["positions"]
}
tqdm.write("Writing output...!")
with open("processed_senators.json", "w") as outfile:
    json.dump(processed_data, outfile, indent=2, sort_keys=True)
tqdm.write("Done!")
