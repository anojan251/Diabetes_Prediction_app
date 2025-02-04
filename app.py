import sqlite3
from datetime import datetime

import joblib
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_bcrypt import Bcrypt


app = Flask(__name__)
app.secret_key = "your_secret_key"  # Set a secret key for session management
bcrypt = Bcrypt(app)  # Initialize bcrypt for password hashing

# Load the pre-trained model
model = joblib.load('diabetes_model.pkl')


# Database setup
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    # Create predictions table
    c.execute('''CREATE TABLE IF NOT EXISTS predictions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  prediction_message TEXT,
                  confidence_score TEXT,
                  time TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()


init_db()  # Initialize the database tables


# Define the route for the home page
@app.route('/')
def home():
    return render_template('index.html')


# User Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_password))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Email already exists. Try a different one."
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')


# User Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['email'] = user[1]
            return redirect(url_for('home'))
        else:
            return "Invalid email or password"
    return render_template('login.html')


# User Logout Route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('email', None)
    return redirect(url_for('login'))


# Define the route for making predictions
@app.route('/predict', methods=['POST'])
def predict():
    # Collect input data from the form
    try:
        input_data = [
            float(request.form['Pregnancies']),
            float(request.form['Glucose']),
            float(request.form['BloodPressure']),
            float(request.form['SkinThickness']),
            float(request.form['Insulin']),
            float(request.form['BMI']),
            float(request.form['DiabetesPedigreeFunction']),
            float(request.form['Age'])
        ]
    except KeyError:
        # Handle missing form fields gracefully
        return jsonify({"error": "Missing field: {e}"}), 400

    # Make a prediction using the loaded model
    prediction = model.predict([input_data])[0]
    var = model.predict_proba([input_data])[0][prediction] * 100

    # Custom prediction message based on result
    if prediction == 1:
        prediction_message = "Sorry, you are likely to get diabetes. Please seek professional advice."
    else:
        prediction_message = "Great! You are less likely to get diabetes. Keep maintaining a healthy lifestyle!"

    # Store the prediction in the session history
    prediction_entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prediction_message": prediction_message,
        "confidence_score": "{confidence_score:.2f}%"
    }
    prediction_history = session.get("prediction_history", [])
    prediction_history.insert(0, prediction_entry)  # Add latest prediction to the start of the list
    session["prediction_history"] = prediction_history  # Save updated history back to session

    # Generate health tips based on specific input values
    health_tips = []
    bmi = input_data[5]
    glucose = input_data[1]
    blood_pressure = input_data[2]

    # Check BMI
    if bmi >= 25:
        health_tips.append("Consider a balanced diet and regular exercise to lower BMI.")
    elif bmi < 18.5:
        health_tips.append("Your BMI is low. A nutritionist can help you with a balanced diet plan.")

    # Check Glucose Level
    if glucose >= 140:
        health_tips.append("High glucose levels detected. Limit sugar intake and consider regular exercise.")
    elif glucose < 70:
        health_tips.append("Your glucose level is low. Ensure you have regular meals and monitor sugar intake.")

    # Check Blood Pressure
    if blood_pressure >= 130:
        health_tips.append("High blood pressure detected. Consider reducing salt intake and managing stress.")

    # Return the result, confidence score, and tips as a JSON response
    return jsonify(predictionMessage=prediction_message, confidenceScore="{confidence_score:.2f}%",
                   healthTips=health_tips)


# Define the route for the prediction history page
@app.route('/prediction_history')
def prediction_history():
    # Retrieve history from the session
    prediction_history = session.get("prediction_history", [])
    return render_template('prediction_history.html', prediction_history=prediction_history)


# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
