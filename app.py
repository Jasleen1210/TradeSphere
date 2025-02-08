from flask import Flask, request, render_template, redirect, url_for, session,jsonify
from pymongo import MongoClient
import pandas as pd
import re
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os

load_dotenv()

# Read MongoDB URI from environment

app = Flask(__name__)
app.secret_key = "your_secret_key"

mongo_uri = os.getenv("MONGO_URI")
data = pd.read_csv("energy_data.csv")
client = MongoClient(mongo_uri)
db = client["tradesphere"]  
users = db["users"]  
trades = db["trades"] 
def get_top_sellers_and_buyers(resource):
    supply_col = f"{resource}_supply (kWh)"
    demand_col = f"{resource}_demand (kWh)"
    sellers = data[supply_col].drop_duplicates().sort_values(ascending=False).head(5).tolist()
    buyers = data[demand_col].drop_duplicates().sort_values(ascending=False).head(5).tolist()
    return sellers, buyers

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

@app.route('/solar')
def solar():
    sellers, buyers = get_top_sellers_and_buyers('solar')
    return render_template('solar.html', sellers=sellers, buyers=buyers)
@app.route('/wind')
def wind():
    sellers, buyers = get_top_sellers_and_buyers('wind')
    return render_template('wind.html', sellers=sellers, buyers=buyers)
@app.route('/biogas')
def biogas():
    sellers, buyers = get_top_sellers_and_buyers('biogas')
    return render_template('biogas.html', sellers=sellers, buyers=buyers)


@app.route('/profile')
def profile():
    return render_template('profile.html')  # Serve profile.html at /profile
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



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if the email already exists in the database
        existing_user = users.find_one({"email": email})
        if existing_user:
            return render_template('register.html', error="Email already registered. Try another email.")
        hashed_password = generate_password_hash(password)
        # Insert user into MongoDB
        users.insert_one({
            "name": name,
            "email": email,
            "password": hashed_password # Store hashed password in production
        })

        return redirect(url_for('login', email=email))  # Redirect to profile page

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