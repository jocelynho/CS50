# online shopping budget list

import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, gbp

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///database.db")



@app.route("/")
@login_required
def index():
    """Show current budget"""

    # Store username of logged-in user
    user_id = int(session['user_id'])
    username = db.execute("SELECT username FROM users WHERE id = :id", id = user_id)[0]["username"]

    # Extract info from 'history' table of database
    info = db.execute("SELECT * FROM history WHERE id = :id", id = user_id)

    # List to add all totals
    total_spent = []

    # Iterate over the stocks list to append the faulty information needed in index.html table
    for row in info:
        if row['operation'] == '-':
            total_spent.append(float(row['price']))

    spending = sum(total_spent)

    # Extract budget left from users table
    balance = db.execute("SELECT budget FROM users WHERE id = :id", id = user_id)[0]["budget"]

    return render_template("list.html", spending = gbp(spending), balance = gbp(balance))



@app.route("/budget", methods=["GET", "POST"])
@login_required
def add():
    """Add budget"""

    # Store username of logged-in user
    user_id = int(session['user_id'])
    username = db.execute("SELECT username FROM users WHERE id = :id", id = user_id)[0]["username"]

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':

        # Save budget
        budget = int(request.form.get("budget"))

        # Ensure user inputs budget
        if not budget:
            return apology("please provide budget amount")

        # Ensure user inputs number of shares as positive integer
        if budget <= 0:
            return apology("please provide valid budget")

        # Add budget to user's balances
        db.execute("UPDATE users SET budget = budget + :budget WHERE username = :username", budget = budget, username = username)
        new_budget = db.execute("SELECT budget FROM users WHERE id = :id", id = user_id)[0]['budget']

        # Add transaction to user's history
        db.execute("INSERT INTO history (id, item, price, operation, balance, date) VALUES (:id, 'budget', :price, '+', :balance, :date)", \
                        id = user_id, price = budget, balance = new_budget, date = datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("budget.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Store username of logged-in user
    user_id = int(session['user_id'])
    username = db.execute("SELECT username FROM users WHERE id = :id", id = user_id)[0]["username"]

    # Extract user info from history table
    info = db.execute("SELECT * FROM history WHERE id = :id", id = user_id)

    return render_template("history.html", info = info)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("please provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("please provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")



@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        # Ensure username was submitted
        if not username:
            return apology("please provide username")

        # Ensure password was submitted
        elif not password or not password_confirm:
            return apology("please provide password")

        # Ensure password is at least 8 characters long
        elif len(password) < 8:
            return apology("password must contain 8 or more characters")

        # Ensure passwords are the same
        elif password != password_confirm:
            return apology("passwords do not match")

        # Hash password
        hash_pw = generate_password_hash(password)

        # Add user to database
        reg = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username = username, hash = hash_pw)

        # Error check
        if not reg:
            return apology("username already exists, please choose another", 403)

        # Remember which user has logged in
        session["user_id"] = reg

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('register.html')



@app.route("/spending", methods=["GET", "POST"])
@login_required
def spending():
    """Record spending details"""

    # Store username of logged-in user
    user_id = int(session['user_id'])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':

        # Save stock symbol entered by user
        item = request.form.get("item")

        # Ensure user inputs item
        if not item:
            return apology("please provide item details")

        # Ensure user inputs amount
        if not request.form.get("amount"):
            return apology("please provide amount of spending")

        amount = int(request.form.get("amount"))

        # Ensure amount is positive integer
        if amount <= 0:
            return apology("please provide valid amount of spending")


        # Check user has enough budget before spending
        result = db.execute("SELECT budget FROM users WHERE id = :id", id = user_id)
        curr_budget = result[0]["budget"]

        # If not enough budget
        if amount > curr_budget:
            return apology("insufficient budget")

       # If enough budget, proceed with spending
        else:

            # Subtract spending from users budget in users table
            db.execute("UPDATE users SET budget = budget - :amount WHERE id = :id", amount = amount, id = user_id)
            n_budget = db.execute("SELECT budget FROM users WHERE id = :id", id = user_id)[0]['budget']

            # Add spending to user's history
            db.execute("INSERT INTO history (id, item, price, operation, balance, date) VALUES (:id, :item, :price, '-', :balance, :date)", \
                        id = user_id, item = item, price = amount, balance = n_budget, date = datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("spending.html")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)



# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)



