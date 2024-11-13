from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import csv
import os
from sklearn.linear_model import LinearRegression
import numpy as np

app = Flask(__name__)  # Fixed _name_ to __name__
CORS(app)

# Global variables
price_history = []
MAX_HISTORY_LENGTH = 6
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
            price = soup.find("div", {"data-test": "instrument-price-last"}).text.strip()
            change = soup.find("span", {"data-test": "instrument-price-change"}).text.strip()
            change_percent = soup.find("span", {"data-test": "instrument-price-change-percent"}).text.strip()
            time_label = soup.find("time", {"data-test": "trading-time-label"}).text.strip()

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            global file_exists
            with open(csv_filename, mode='a', newline='') as file:
                writer = csv.writer(file)

                if not file_exists:
                    writer.writerow(["Timestamp", "Prix actuel", "Changement", "Changement (%)", "Heure de mise à jour", "Prix prédit"])
                    file_exists = True

                # Write the new data point with None for the predicted price
                writer.writerow([timestamp, price, change, change_percent, time_label, None])  # Temporarily set None for predicted price

            price_float = float(price.replace(',', ''))
            change_float = float(change.replace(',', ''))
            change_percent_float = float(change_percent.strip('()%').replace(',', ''))

            data_point = {
                "timestamp": timestamp,
                "price": price_float,
                "change": change_float,
                "percentChange": change_percent_float,
                "updateTime": time_label
            }

            global price_history
            price_history.append(data_point)
            if len(price_history) > MAX_HISTORY_LENGTH:
                price_history = price_history[-MAX_HISTORY_LENGTH:]

            calculate_predictions()  # Call function to update predictions for each data point
            return data_point

        else:
            return {"error": "Failed to fetch data", "status_code": response.status_code}

    except Exception as e:
        return {"error": str(e)}

def remove_empty_rows_from_csv():
    with open(csv_filename, mode='r') as file:
        reader = csv.reader(file)
        rows = [row for row in reader if row[0].strip()]  # Keep only non-empty rows

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    print(f"Nombre de lignes après nettoyage: {len(rows)}")  # Optional: Display remaining row count

def calculate_predictions():
    if len(price_history) < 2:
        for data in price_history:
            data['predictedPrice'] = None
        return

    with open(csv_filename, mode='r+', newline='') as file:
        reader = csv.reader(file)
        rows = list(reader)

    empty_row_index = len(rows)  # Default to append at the end
    for index, row in enumerate(rows):
        if len(row) > 0 and row[-1] == '':
            empty_row_index = index
            break

    final_predictions = []
    for i in range(1, len(price_history) + 1):
        prices = [data['price'] for data in price_history[:i]]
        timestamps = list(range(len(prices)))

        X = np.array(timestamps).reshape(-1, 1)
        y = np.array(prices)

        model = LinearRegression()
        model.fit(X, y)

        predicted_price = model.predict([[i]])[0]
        price_history[i - 1]['predictedPrice'] = predicted_price
        final_predictions.append(predicted_price)

        if empty_row_index < len(rows):
            rows[empty_row_index][-1] = predicted_price
        else:
            new_row = [''] * len(rows[0])
            new_row[-1] = predicted_price
            rows.append(new_row)

        empty_row_index += 1

    if final_predictions:
        final_prediction = final_predictions[-1]
        rows[-1][-1] = final_prediction

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    remove_empty_rows_from_csv()

@app.route('/api/current-price', methods=['GET'])
def get_current_price():
    data = scrape_and_save_data()
    return jsonify(data)

@app.route('/api/predicted-price', methods=['GET'])
def get_predicted_price():
    if not price_history:
        return jsonify({"predictedPrice": None})
    return jsonify({"predictedPrice": price_history[-1].get('predictedPrice')})

@app.route('/api/price-history', methods=['GET'])
def get_price_history():
    return jsonify(price_history)

@app.route('/api/dashboard-data', methods=['GET'])
def get_dashboard_data():
    dashboard_data = []
    for entry in price_history:
        dashboard_entry = {
            "timestamp": entry["timestamp"],
            "currentPrice": entry["price"],
            "predictedPrice": entry.get("predictedPrice")
        }
        dashboard_data.append(dashboard_entry)

    return jsonify({
        "current": dashboard_data[-1] if dashboard_data else None,
        "history": dashboard_data
    })
@app.route('/api/last-prices', methods=['GET'])
def get_last_prices():
    count = request.args.get('count', default=10, type=int)
    if count not in [10, 50, 100, 1000]:
        return jsonify({"error": "Invalid count value. Please use 10, 50, 100, or 1000."}), 400

    try:
        with open(csv_filename, mode='r') as file:
            rows = list(csv.reader(file))
            header, data_rows = rows[0], rows[1:]  # La première ligne est l'en-tête, les lignes suivantes sont les données

            # Récupérer les 'count' dernières lignes
            last_rows = data_rows[-count:]

            # Préparer les données pour l'affichage
            result = []
            for row in last_rows:
                result.append({
                    "timestamp": row[0],
                    "price": row[1],
                    "change": row[2],
                    "percentChange": row[3],
                    "updateTime": row[4],
                    "predictedPrice": row[5]
                })

            return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




def start_background_scraping():
    while True:
        scrape_and_save_data()
        time.sleep(10)

if __name__ == '__main__':  # Fixed _name_ to __name__
    import threading
    scraping_thread = threading.Thread(target=start_background_scraping)
    scraping_thread.daemon = True
    scraping_thread.start()

    app.run(debug=True, port=5000)
