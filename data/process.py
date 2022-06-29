from dateutil.parser import parse as parse_date
from decimal import Decimal
from datetime import date, datetime, timedelta
import requests
import re
from dotenv import load_dotenv
import os
from diskcache import Cache
from tqdm import tqdm
import heapq
import operator
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


stock_data_cache = Cache(".cache", size_limit=int(10e9))


@stock_data_cache.memoize(expire=60 * 60 * 24, name="load_alphavantage_data")
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


@stock_data_cache.memoize(expire=60 * 60 * 24, name="stock_price")
def stock_price(ticker, date):
    stock_data = load_alphavantage_data(ticker)

    if "Time Series (Daily)" not in stock_data:
        tqdm.write(f"{ticker} is invalid, {stock_data}")
        return None

    for j in range(4):
        time_delta = timedelta(days=j)
        date_str = (date - time_delta).strftime("%Y-%m-%d")
        if date_str in stock_data["Time Series (Daily)"]:
            return float(
                stock_data["Time Series (Daily)"][date_str]["5. adjusted close"]
            )
    return None


def parse_ticker(ticker):
    return re.sub("<[^<]+?>", "", ticker)


daily_senator_data = requests.get(
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
).json()


@stock_data_cache.memoize(expire=60 * 60 * 24, name="get_preprocessed_data")
def get_preprocessed_data():
    tqdm.write("Preprocessed data not cached -- pulling...")

    senator_data = requests.get(
        "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions_for_senators.json"
    ).json()

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

    return senator_data


@stock_data_cache.memoize(expire=60 * 60 * 24, name="portfolio_breakdown")
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
                if positions[ticker] > 0:
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
        "value": value, #ADDED "value + cash", but correct change
        "purchases": purchases,
        "sales": sales,
        "cash": cash,
        "name": senatordata["first_name"] + " " + senatordata["last_name"],
    }


def get_index():
    index_returns = {}

    spy_start_price = stock_price("SPY", parse_date("Jan 1 2020"))
    spy_data = load_alphavantage_data("SPY")
    start_date = parse_date("Jan 1 2020")
    end_date = datetime.now()
    delta = timedelta(days=1)

    while start_date <= end_date:
        if start_date in spy_data:
            index_returns[start_date] = stock_price["SPY", start_date] / spy_start_price
        else:
            for j in range(4):
                time_delta = timedelta(days=j)
                date_str = (start_date - time_delta).strftime("%Y-%m-%d")
                if date_str in spy_data["Time Series (Daily)"]:
                    index_returns[start_date.isoformat()] = (
                        float(
                            spy_data["Time Series (Daily)"][date_str][
                                "5. adjusted close"
                            ]
                        )
                        / spy_start_price
                    )
        start_date += delta
    return index_returns


senator_data = get_preprocessed_data()
processed_data = {}

total_returns = 0
total_values = 0
total_sales = 0
total_purchases = 0
senator_names = []

for senator in tqdm(senator_data, "Calculating returns"):
    start_date = parse_date("Jan 1 2020")
    end_date = datetime.now()
    delta = timedelta(days=1)
    returns = {}

    while start_date <= end_date:
        portfolio = portfolio_breakdown(senator, start_date)
        if portfolio["total"] == 0:
            returns[start_date.isoformat()] = portfolio["value"] / 1
        else:
            returns[start_date.isoformat()] = portfolio["value"] / portfolio["total"]
        start_date += delta

    # opensecretsinformation = loadopensecrets("N00027658")

    stockpositions = portfolio["positions"]
    top_positions = {}
    for (ticker, amount) in stockpositions.items():
        if stock_price(ticker, datetime.now()) is not None:
            top_positions[ticker] = amount * stock_price(ticker, datetime.now())
        else:
            continue
    top_five_stocks = {
        stock: value
        for (stock, value) in sorted(
            top_positions.items(), key=operator.itemgetter(1), reverse=True
        )[:5]
    }

    transactions = []

    for transaction in senator["transactions"][:100]:
        if "ignored" in transaction:
            continue
        else:
            transactions.append(
                {
                    "ticker": parse_ticker(transaction["ticker"]),
                    "type": transaction["type"],
                    "date": transaction["transaction_date"],
                    "amount": transaction["amount"],
                    "ptr_link": transaction["ptr_link"],
                }
            )
    
    percentage_return = list(returns.values())[-1]

    if percentage_return == 0: 
        percentage_return = 0

    if percentage_return < 1  and percentage_return != 0:
        percentage_return = percentage_return - 1
        percentage_return = percentage_return * 100
    
    if percentage_return > 1:
        percentage_return = percentage_return - 1
        percentage_return = percentage_return * 100

    senator_dict = {
        "name": portfolio["name"],
        "estimated_return": list(returns.values())[-1],
        "percentage_return": round(percentage_return, 2),
        "portfolio_value": portfolio["value"],
        "sales": portfolio["sales"],
        "purchases": portfolio["purchases"],
        "returns": returns,
        "positions": portfolio["positions"],
        "top_five_stocks": top_five_stocks,
        "transactions": transactions,
    }

    total_values += senator_dict["portfolio_value"]
    total_sales += senator_dict["sales"]
    total_purchases += senator_dict["purchases"]

    senator_dict["estimated return"] = "{:,}".format(
        round(list(returns.values())[-1]), 2
    )
    senator_dict["portfolio_value"] = "{:,}".format(round(portfolio["value"]))

    tqdm.write(f"Processed {portfolio['name']}!")
    processed_data[portfolio["name"]] = senator_dict

    senator_names.append(portfolio["name"])
    senators_with_returns = len(senator_names)

    if senator_dict["estimated_return"] == 0:
        senators_with_returns -= 1
        continue
    else:
        total_returns += senator_dict["estimated_return"]


def get_average_returns():
    average_daily_returns = {}
    
    start_date = parse_date("Jan 1 2020")
    end_date = datetime.now()
    delta = timedelta(days=1)

    while start_date <= end_date:
        temporary_average = []
        for senator in processed_data.values():
            if senator["returns"][start_date.isoformat()] == 0.0:
                continue
            if senator["purchases"] + senator["sales"] < 10:
                continue
            if senator["name"] == "Susan M Collins" or senator["name"] == "Kelly Loeffler":
                continue
            else:
                temporary_average.append(senator["returns"][start_date.isoformat()])
        average_daily_returns[start_date.isoformat()] = sum(temporary_average) / len(
            temporary_average
        )
        start_date += delta
    return average_daily_returns


def get_top_positions():
    overall_positions = {}
    overall_top_positions = {}

    for senator in processed_data.values():
        for (ticker, amount) in senator["positions"].items():
            if ticker in overall_positions:
                overall_positions[ticker] += amount
            else:
                overall_positions[ticker] = amount
    for (ticker, amount) in overall_positions.items():
        if stock_price(ticker, datetime.now()) is not None: 
            overall_top_positions[ticker] = amount * stock_price(ticker, datetime.now())
        else:
            continue

    top_five_stocks = {
        stock: value
        for (stock, value) in sorted(
            overall_top_positions.items(), key=operator.itemgetter(1), reverse=True
        )[:5]
    }

    for (ticker, amount) in top_five_stocks.items():
        if amount < 0:
            top_five_stocks[ticker] = 0

    return top_five_stocks


daily_transactions = []
for transaction in daily_senator_data[:100]:
    if "ticker" not in transaction:
        continue
    if "--" in transaction:
        continue
    if "type" not in transaction:
        continue
    if "transaction_date" not in transaction:
        continue
    if "amount" not in transaction:
        continue

    daily_transactions.append(
        {
            "ticker": parse_ticker(transaction["ticker"]),
            "senator": transaction["senator"],
            "type": transaction["type"],
            "date": transaction["transaction_date"],
            "amount": transaction["amount"],
            "ptr_link": transaction["ptr_link"],
        }
    )

for transaction in daily_transactions:
    if transaction["ticker"] == "--":
        daily_transactions.remove(transaction)

daily_summary = {
    "estimated_return": round(list(get_average_returns().values())[-1], 4),
    "portfolio_value": "{:,}".format(round(total_values)),
    "sales": total_sales,
    "purchases": total_purchases,
    "average_daily_returns": get_average_returns(),
    "positions": get_top_positions(),
    "daily_transactions": daily_transactions,
    "index_returns": get_index(),
    "senators_tracked": len(senator_names)
}

processed_data["senator_names"] = senator_names
processed_data["daily_summary"] = daily_summary

if "Christopher A Coons" in processed_data["senator_names"]:
    processed_data["senator_names"].remove("Christopher A Coons")

if "Ronald L Wyden" in processed_data["senator_names"]:
    processed_data["senator_names"].remove("Ronald L Wyden")

if "Ladda Tammy Duckworth" in processed_data["senator_names"]:
    processed_data["senator_names"].remove("Ladda Tammy Duckworth")

if "Ron Wydenn" in processed_data["senator_names"]:
    processed_data["senator_names"].remove("Ron Wyden")

if "Angus S King" in processed_data["senator_names"]:
    processed_data["senator_names"].remove("Angus S King")

tqdm.write("Writing output...!")
with open("processed_senators.json", "w") as outfile:
    json.dump(processed_data, outfile, indent=2, sort_keys=True)
tqdm.write("Done!")
