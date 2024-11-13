from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import pandas as pd
import csv
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variables
price_history = []
MAX_HISTORY_LENGTH = 1
csv_filename = 'crude_oil_data.csv'
file_exists = os.path.exists(csv_filename)

def scrape_and_save_data():
    url = "https://fr.investing.com/commodities/crude-oil-commentary"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract data
            price = soup.find("div", {"data-test": "instrument-price-last"}).text.strip()
            change = soup.find("span", {"data-test": "instrument-price-change"}).text.strip()
            change_percent = soup.find("span", {"data-test": "instrument-price-change-percent"}).text.strip()
            time_label = soup.find("time", {"data-test": "trading-time-label"}).text.strip()
            
            # Get current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Save to CSV
            global file_exists
            with open(csv_filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                
                # Write header if file is new
                if not file_exists:
                    writer.writerow(["Timestamp", "Prix actuel", "Changement", "Changement (%)", "Heure de mise à jour"])
                    file_exists = True
                
                # Write data row
                writer.writerow([timestamp, price, change, change_percent, time_label])
            
            # Clean and convert data for API
            price_float = float(price.replace(',', ''))
            change_float = float(change.replace(',', ''))
            change_percent_float = float(change_percent.strip('()%').replace(',', ''))
            
            # Create data point for API
            data_point = {
                "timestamp": timestamp,
                "price": price_float,
                "change": change_float,
                "percentChange": change_percent_float,
                "updateTime": time_label
            }
            
            # Update price history for API
            global price_history
            price_history.append(data_point)
            if len(price_history) > MAX_HISTORY_LENGTH:
                price_history = price_history[-MAX_HISTORY_LENGTH:]
            
            # Print results to console
            print(f"Timestamp: {timestamp}")
            print(f"Prix actuel Pétrole brut : {price}")
            print(f"Changement : {change}")
            print(f"Changement en pourcentage : {change_percent}")
            print(f"Heure : {time_label}")
            print("-" * 40)
                
            return data_point
            
        else:
            print("Échec de la récupération de la page.")
            return {"error": "Failed to fetch data", "status_code": response.status_code}
            
    except Exception as e:
        print(f"Erreur: {str(e)}")
        return {"error": str(e)}

@app.route('/api/current-price', methods=['GET'])
def get_current_price():
    data = scrape_and_save_data()
    return jsonify(data)

@app.route('/api/price-history', methods=['GET'])
def get_price_history():
    return jsonify(price_history)

@app.route('/api/dashboard-data', methods=['GET'])
def get_dashboard_data():
    return jsonify({
        "current": price_history[-1] if price_history else None,
        "history": price_history
    })

def start_background_scraping():
    while True:
        scrape_and_save_data()
        time.sleep(10)

if __name__== '_main_':
    # Start background scraping in a separate thread
    import threading
    scraping_thread = threading.Thread(target=start_background_scraping)
    scraping_thread.daemon = True
    scraping_thread.start()
    
    # Start the Flask app
    app.run(debug=True, port=5000)