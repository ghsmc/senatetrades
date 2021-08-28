from flask import Flask, render_template, send_from_directory, request
from dotenv import load_dotenv
import csv
import requests
import os
import json

load_dotenv()

app = Flask(__name__, static_url_path="/static")

with open("processed_senators.json", "r") as infile:
    data = json.load(infile)
    

@app.route("/")
def home():
    return render_template("pages/dailysummary.html", data=data)


@app.route("/official")
def dashboard():
    official = request.args.get("official")
    return render_template("pages/dashboard.html", official=official, data=data)

@app.route("/research")
def research():
    return render_template("pages/research.html")

@app.route("/about")
def about():
    return render_template("pages/about.html")

if __name__ == "__main__":
    app.run(debug=True)
