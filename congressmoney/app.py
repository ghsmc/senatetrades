from flask import Flask, render_template, send_from_directory
from dotenv import load_dotenv
import csv
import requests
import os

load_dotenv()

app = Flask(__name__, static_url_path='/static')

@app.route('/')
def home():
   value = "Kirsten Gillibrand"
   return render_template('home.html')

@app.route('/dashboard')
def dashboard():
   return render_template('dashboard.html')


@app.route('/base')
def base():
   return render_template('base.html')


app.run()

