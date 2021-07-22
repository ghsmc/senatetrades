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



senatordata = requests.get(
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions_for_senators.json"
).json()


for senator in senatordata:
    senatorname = senator["first_name"] + "_" + senator["last_name"]
    senatorspent = 0
    senatortransactionnum = 0

    for transaction in senator["transactions"]:
        if(transaction["transaction_date"][7:10] == "2020" and transaction["ticker"] != "--" and transaction["type"] == "Purchase"):
            currentticker = transaction["ticker"]
            transactiondate = fixdate(transaction["transaction_date"])
            initialstockprice = cr["transactiondate"]
            amount  = str(transaction["amount"]) / 2
            senatorspent = senatorspent + amount
            senatortransactionnum = senatortransactionnum + 1

            saledate = "12-31-2020"

            for transaction in senator["transactions"]:
                if(transaction["ticker"] == currentticker and transaction["type"] == "Sale (Full)"):
                    saledate = transaction["transaction_date"]
                    break
                
                if(transaction["ticker"] == currentticker and transaction["type"] == "Sale (Partial"):
                    saledate = transaction["transaction_date"]
                    amountsold = transaction["amount"] / 2
                    remaining = amount - amountsold
                    # check return on remaining amount, and see if any of it was sold again

            finalstockprice = cr[str(saledate)]
            percentreturn = (finalstockprice - initialstockprice) / initialstockprice       
            moneyreturn = (percentreturn + 1) * amount

            #add moneyreturn to array

            # how to calculate day by day


def fixdate(date):
    #fix date formatting





        
@app.route("/")
def home():
    return "<p>Hello World</p>"


app.run(debug=True)

Richard_Shelby  = []
Tommy_Tuberville = []
Lisa_Murkowski = []
Dan_Sullivan = []
Kyrsten_Sinema = []
Mark_Kelly = []
John_Boozman = []
Tom_Cotton = []
Dianne_Feinstein = []
Alex_Padilla = []
Micheal_Bennet = []
John_Hickenlooper = []
Richard_Blumenthal = []
Chris_Murphy = []
Tom_Carper = []
Chris_Coons = []
Marco_Rubio = []
Rick_Scott = []
Raphael_Warnock = []
Jon_Ossoff = []
Brian_Schatz =  []
Mazie_Hirono = [ ]
Mike_Crapo = [] 
Jim_Risch = [] 
Dick_Durbin =  []
Tammy_Duckworth  = []
Todd_Young = [] 
Mike_Braun = [ ]
Chuck_Grassley  = []
Joni_Ernst = [] 
Jerry_Moran  = []
Roger_Marshall = []
Mitch_McConnell = []
Rand_Paul = []
Bill_Cassidy = []
John_Kennedy = []
Susan_Collins = []
Angus_King = []
Ben_Cardin = []
Chris_Van_Hollen = []
Elizabeth_Warren = []
Ed_Markey = []
Debble_Stabenow = []
Gary_Peters = []
Amy_Klobuchar = []
Tina_Smith = []
Roger_Wicker  = []
Cindy_Hyde_Smith = []
Roy_Blunt = []
Josh_Hawley = []
Jon_Tester = []
Steve_Daines = []
Deb_Fischer = []
Ben_Sasse = []
Catherine_Cortez_Masto = []
Jacky_Rosen = []
Jeanne_Shaheen = []
Maggie_Hassan = []
Bob_Menendez = []
Cory_Booker = []
Martin_Heinrich  = []
Ben_Ray_Luján = []
Chuck_Schumer = []
Kirsten_Gillibrand = []
Richard_Burr = []
Thom_Tillis = []
John_Hoeven = []
Kevin_Cramer = []
Sherrod_Brown = []
Rob_Portman = []
Jim_Inhofe = []
James_Lankford = []
Ron_Wyden = []
Jeff_Merkley = []
Bob_Casey = []
Pat_Toomey = []
Jack_Reed = []
Sheldon_Whitehouse = []
Lindsey_Graham = []
Tim_Scott = []
John_Thune = []
Mike_Rounds = []
Marsha_Blackburn  = []
Bill_Hagerty = []
John_Cornyn = []
Ted_Cruz = []
Mike_Lee = []
Mitt_Romney = []
Patrick_Leahy = []
Bernie_Sanders = []
Mark_Warner = []
Tim_Kaine = []
Patty_Murray = []
Maria_Cantwell = []
Joe_Manchin = []
Shelley_Moore_Capito = []
Ron_Johnson = []
Tammy_Baldwin = []
John_Barrasso = []
Cynthia_Lummis = []