from flask import Flask, render_template
from dotenv import load_dotenv
import csv
import requests
import os

load_dotenv()

app = Flask(__name__)

# # replace the "demo" apikey below with your own key from https://www.alphavantage.co/support/#api-key
# CSV_URL = 'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY_EXTENDED&symbol=IBM&interval=15min&slice=year8month1&apikey=demo'

# with requests.Session() as s:
#     download = s.get(CSV_URL)
#     decoded_content = download.content.decode('utf-8')
#     cr = csv.reader(decoded_content.splitlines(), delimiter=',')
#     my_list = list(cr)
#     for row in my_list:
#         print(row)


@app.route("/")
def home():
    return "<p>Hello World</p>"


app.run(debug=True)
