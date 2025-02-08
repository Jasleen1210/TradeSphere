from flask import Flask, request, render_template, redirect, url_for, session,jsonify
from pymongo import MongoClient
import pandas as pd
import re
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
from sklearn.svm import SVR
from xgboost import XGBRegressor
from sklearn.preprocessing import MinMaxScaler, PolynomialFeatures
load_dotenv()

# Read MongoDB URI from environment

app = Flask(__name__)
app.secret_key = "your_secret_key"

mongo_uri = os.getenv("MONGO_URI")
data = pd.read_csv("energy_data.csv")
client = MongoClient(mongo_uri)
db = client["db"]  
users = db["user"]  
trades = db["trade"] 
print("✅ Connected to database:", db.name)
print("📂 Collections available:", db.list_collection_names())
def get_top_sellers_and_buyers(resource):
    supply_col = f"{resource}_supply (MWh)"
    demand_col = f"{resource}_demand (MWh)"
    sellers = data[supply_col].drop_duplicates().sort_values(ascending=False).head(5).tolist()
    buyers = data[demand_col].drop_duplicates().sort_values(ascending=False).head(5).tolist()
    return sellers, buyers
csv_file_path = "ledger.csv"
df = pd.read_csv(csv_file_path)

# Convert timestamp and extract features
df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s")
df["DayOfYear"] = df["Timestamp"].dt.dayofyear
df["Month"] = df["Timestamp"].dt.month
df["Weekday"] = df["Timestamp"].dt.weekday

# Filter Solar REC data
df_solar = df[df["Energy_Type"] == "Solar"].copy()

# Create Lag Features (Last 3 Days Prices)
df_solar["Prev_Day_Price"] = df_solar["Price (ETH)"].shift(1)
df_solar["Prev_2_Day_Price"] = df_solar["Price (ETH)"].shift(2)
df_solar["Prev_3_Day_Price"] = df_solar["Price (ETH)"].shift(3)

# 🔹 Fix: Fill NaN values properly
df_solar.fillna(method='ffill', inplace=True)  # Forward fill missing values
df_solar.fillna(df_solar["Price (ETH)"].mean(), inplace=True)  # If still NaN, replace with mean price

# Prepare dataset
features = ['DayOfYear', 'Quantity (MWh)', 'Month', 'Weekday', 
            'Prev_Day_Price', 'Prev_2_Day_Price', 'Prev_3_Day_Price']
X = df_solar[features].values
y = df_solar['Price (ETH)'].values

# Verify no NaNs exist
if np.isnan(X).any() or np.isnan(y).any():
    raise ValueError("Data still contains NaN values after preprocessing.")

# Apply Polynomial Features
poly = PolynomialFeatures(degree=2, include_bias=False)
X_poly = poly.fit_transform(X)

# Normalize data
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X_poly)

# Train XGBoost Model
model = XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=5)
model.fit(X_scaled, y)

# Predict the next 7 days
future_days = np.array(range(df["DayOfYear"].max() + 1, df["DayOfYear"].max() + 8)).reshape(-1, 1)
future_quantities = np.full((7, 1), np.mean(df_solar["Quantity (MWh)"]))  # Use avg quantity
future_months = np.full((7, 1), df["Month"].max())
future_weekdays = [(df["Timestamp"].max() + pd.Timedelta(days=i)).weekday() for i in range(1, 8)]

# Use last 3 real prices as initial guess
last_prices = df_solar["Price (ETH)"].iloc[-3:].values
future_prices_list = []

for i in range(7):
    prev_price_1 = last_prices[-1]
    prev_price_2 = last_prices[-2]
    prev_price_3 = last_prices[-3]
    
    future_X = np.array([[future_days[i][0], future_quantities[i][0], future_months[i][0], 
                          future_weekdays[i], prev_price_1, prev_price_2, prev_price_3]])
    
    future_X_poly = poly.transform(future_X)
    future_X_scaled = scaler.transform(future_X_poly)
    
    predicted_price = model.predict(future_X_scaled)[0]
    
    # Prevent negative prices & add slight variation to avoid constant values
    predicted_price = max(predicted_price + np.random.normal(0, 0.005), 0)
    
    # Append and shift prices
    future_prices_list.append(predicted_price)
    last_prices = np.roll(last_prices, -1)
    last_prices[-1] = predicted_price

# Convert predictions to JSON
@app.route("/solar_predictions")
def get_solar_predictions():
    last_date = df["Timestamp"].max()  # Last actual data point
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=7, freq="D")  # Continue from last date
    
    predictions = {
        "dates": future_dates.strftime("%Y-%m-%d").tolist(),
        "prices": [float(price) for price in future_prices_list]  # Convert float32 to Python float
    }
    return jsonify(predictions)

@app.route("/solar")
def solar():
    
    return render_template("solar.html")

@app.route('/')
def index():
    wind_sellers, wind_buyers = get_top_sellers_and_buyers('wind')
    solar_sellers, solar_buyers = get_top_sellers_and_buyers('solar')
    biogas_sellers, biogas_buyers = get_top_sellers_and_buyers('biogas')
    return render_template(
        'index.html',
        wind_sellers=wind_sellers,
        wind_buyers=wind_buyers,
        solar_sellers=solar_sellers,
        solar_buyers=solar_buyers,
        biogas_sellers=biogas_sellers,
        biogas_buyers=biogas_buyers,
    )

#@app.route('/solar')
#def solar():
 #   sellers, buyers = get_top_sellers_and_buyers('solar')
  #  return render_template('solar.html', sellers=sellers, buyers=buyers)
@app.route('/wind')
def wind():
    sellers, buyers = get_top_sellers_and_buyers('wind')
    return render_template('wind.html', sellers=sellers, buyers=buyers)
@app.route('/biogas')
def biogas():
    sellers, buyers = get_top_sellers_and_buyers('biogas')
    return render_template('biogas.html', sellers=sellers, buyers=buyers)

@app.route("/profile")
def profile():
    if "user_email" not in session:
        return redirect(url_for("login"))  # Redirect if not logged in

    user_email = session["user_email"]
    user = db["user"].find_one({"email": user_email})

    if user:
        profile_data = {
            "profileName": user.get("name", "Not Set"),
            "userName": user.get("username", "Not Set"),
            "userEmail": user.get("email", "Not Set"),
            "profileBio": user.get("bio", "Not Set"),
            "profileLocation": user.get("location", "Not Set"),
            "profileRECs": user.get("recs", "Not Set"),
            "profileWatt": user.get("watt_quantity", "Not Set"),
            "profileEnergy": user.get("energies_traded", "Not Set"),
        }
    else:
        # If the user is not found, set default values
        profile_data = {
            "profileName": "Not Set",
            "userName": "Not Set",
            "userEmail": "Not Set",
            "profileBio": "Not Set",
            "profileLocation": "Not Set",
            "profileRECs": "Not Set",
            "profileWatt": "Not Set",
            "profileEnergy": "Not Set",
        }

    return render_template("profile.html", profile=profile_data)


   

@app.route('/payment')
def payment():
    return render_template('payment.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/footprint')
def footprint():
    return render_template('footprint.html')

@app.route('/edit')
def edit():
    return render_template('edit.html')
@app.route("/get_profile", methods=["GET"])
def get_profile():
    if "user_email" not in session:
        return jsonify({"error": "User not logged in"}), 401

    user_email = session["user_email"]
    user = db["user"].find_one({"email": user_email})

    if not user:
        return jsonify({"error": "User not found"}), 404

    profile_data = {
        "profileName": user.get("name", ""),
        "userName": user.get("username", ""),
        "profileBio": user.get("bio", ""),
        "profileLocation": user.get("location", "")
    }

    return jsonify(profile_data)


@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "user_email" not in session:
        return jsonify({"success": False, "error": "User not logged in"}), 401

    user_email = session["user_email"]
    data = request.get_json()

    # Debug: Print received data
    print("🔍 Received profile update request:", data)

    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400

    update_data = {
        "name": data.get("name", ""),
        "username": data.get("username", ""),
        "bio": data.get("bio", ""),
        "location": data.get("location", "")
    }

    result = db["user"].update_one({"email": user_email}, {"$set": update_data})

    if result.modified_count > 0:
        print("✅ Profile updated successfully in MongoDB!")
        return jsonify({"success": True})
    else:
        print("⚠ No changes were made to the profile.")
        return jsonify({"success": False, "error": "No changes made"}), 400


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

       
        existing_user = users.find_one({"email": email})  # Check if user exists
        print("🔍 Checking if email exists in DB:", existing_user)  # Debugging

        if existing_user:
            print("❌ User already exists! Redirecting back to register.")
            return render_template('register.html', error="Email already registered. Try another email.")

        hashed_password = generate_password_hash(password)
        users.insert_one({"name": name, "email": email, "password": hashed_password})

        print("✅ User registered successfully!")
        return redirect(url_for('login', email=email))  # Redirect to login

       #if existing_user:
            #return render_template('register.html', error="Email already registered. Try another email.")
            #hashed_password = generate_password_hash(password)
        # Insert user into MongoDB

    return render_template('register.html')


@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

# Route to handle the login form submission
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()  # Receiving JSON from frontend
        email = data.get("email")
        password = data.get("password")
    
    # Find the user by email in MongoDB
        user = users.find_one({"email": email})
        print(f"Login attempt for email: {email}")
        print(f"User found: {user}")
        if user and check_password_hash(user["password"], password):
                session["user_email"] = email 
                return jsonify({"success": True})
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    
@app.route('/trade')
def trade():
    # Ensure user is logged in
    if "user_email" not in session:
        return redirect(url_for('login_page'))  # Redirect to login page if not logged in
    return render_template('trade.html')

@app.route("/submit_trade", methods=["POST"])
def submit_trade():
    if "user_email" not in session:
        return jsonify({"error": "User not logged in"}), 401  # Unauthorized response

    data = request.get_json()
    energy_type = data.get("energyType")
    quantity = data.get("quantity")
    price = data.get("price")
    user_email = session["user_email"]  # Get the logged-in user's email

    if not energy_type or not quantity or not price:
        return jsonify({"error": "All fields are required"}), 400  # Bad request
 # Store trade in MongoDB
    trades.insert_one({
        "email": user_email,  # Automatically link trade to user
        "energyType": energy_type,
        "quantity": quantity,
        "price": price
    })


@app.route("/buy")
def buy():
    if "user_email" not in session:
        return redirect(url_for("login_page"))  # Redirect if not logged in
    return render_template("buy.html")

@app.route("/get_trades")
def get_trades():
    try:
        trades = db["trades"].find()
        trade_list = []
        for trade in trades:
            trade_list.append({
                "_id": str(trade["_id"]),
                "email": trade["email"],
                "energyType": trade["energyType"],
                "quantity": trade["quantity"],
                "price": trade["price"]
            })
        
        # Debugging output
        print("Fetched trades:", trade_list)  

        return jsonify(trade_list)

    except Exception as e:
        print(f"❌ Error fetching trades: {e}")
        return jsonify({"error": "Failed to fetch trades"}), 500

@app.route("/buy_rec", methods=["POST"])
def buy_rec():
    if "user_email" not in session:
        return jsonify({"error": "User not logged in"}), 401

    data = request.get_json()
    trade_id = data.get("tradeId")
    buyer_email = session["user_email"]  # Logged-in buyer
    quantity = data.get("quantity")
    price = data.get("price")

    trade = db["trades"].find_one({"_id": ObjectId(trade_id)})
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    # Record purchase in MongoDB
    purchases_collection = db["purchases"]
    purchases_collection.insert_one({
        "buyer_email": buyer_email,
        "seller_email": trade["email"],
        "energyType": trade["energyType"],
        "quantity": quantity,
        "price": price
    })

    # Remove the purchased REC from available trades
    db["trades"].delete_one({"_id": ObjectId(trade_id)})

    return jsonify({"success": True})
if __name__ == '__main__':
    app.run(debug=True)
