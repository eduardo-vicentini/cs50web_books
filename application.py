import os

from flask import Flask, session, request, render_template, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from passlib.hash import sha256_crypt
import requests

from functools import wraps

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

if not os.getenv("GOODREADS_API"):
    raise RuntimeError("GOODREADS_API is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# Set GoodReads API
GR_API = os.getenv("GOODREADS_API")


def lookup(isbn):
    """Look up book with the isbn."""

    # Contact API
    try:
        GR_API = os.getenv("GOODREADS_API")
        response = requests.get(f"https://www.goodreads.com/book/review_counts.json",
                        params={"key": GR_API, "isbns": isbn})
        
    except requests.RequestException:
        return None

    # Parse response
    try:
        book = response.json()["books"][0]
        return book
    except (KeyError, TypeError, ValueError):
        return None


def apology(message, code=400):
    """Render message as an apology to user."""
    try:
        message = message.capitalize()
    except AttributeError:
        pass
        

    return render_template("apology.html", message=message, code=code)

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """home page"""
    if request.method == "POST":
        search = request.form.get("search")

        if search.strip():
            rows = db.execute("SELECT * FROM books WHERE title LIKE :search or isbn LIKE :search or author LIKE :search",
                        {"search": "%{}%".format(search)}).fetchall()
            
            if search.isdecimal():
                rows += db.execute("SELECT * FROM books WHERE year = :search",
                        {"search": int(search)}).fetchall()

            return render_template("index.html", rows=rows)


        # Search is empty or just spaces
        else:
            redirect("/")


    else:
        return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        username = request.form.get("username")
        pwd = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        equal = db.execute("SELECT username FROM users WHERE username = :username",
                          {"username": username}).fetchone()

        if equal:
            return apology("username already in use", 403)

        # Ensure password was submitted
        elif not pwd:
            return apology("must provide password", 403)

        elif pwd != request.form.get("confpassword"):
            return apology("password and confirm password must be equal", 403)

        # Query database for username
        hash_pwd = sha256_crypt.encrypt(pwd)
        db.execute("INSERT INTO users (username, hash_pwd)  VALUES (:username, :hash_pwd)",
                          {"username": username, "hash_pwd": hash_pwd})
        
        db.commit()

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        pwd = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not pwd:
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username": username}).fetchone()

        # Ensure username exists and password is correct
        if not rows:
            return apology("invalid username and/or password", 403)
        if not sha256_crypt.verify(pwd, rows.hash_pwd):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows.id

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
    return index()

@app.route("/book/<string:isbn>", methods=["GET", "POST"])
@login_required
def books(isbn):
    """Books detail page"""
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn",
                          {"isbn": isbn}).fetchone()

    if request.method == "POST":
        review = request.form.get("review")
        rating = request.form.get("rating")


        if not rating.isdecimal():
            return apology("select a rating", 403)

        if not review:
            return apology("review can´t be empty", 403)
        
        rating = int(rating)
        
        db.execute("INSERT INTO reviews (user_id, book_id, review, rating) VALUES (:user_id, :book_id, :review, :rating)",
            {"user_id": session["user_id"], "book_id": book.id, "review": review, "rating": rating})

        db.commit()

        return redirect("/book/{}".format(isbn))

    else:

        if book:
            reviews = db.execute("SELECT * FROM reviews WHERE book_id = :id",
                        {"id": book.id}).fetchall()
            rating = db.execute("SELECT AVG(rating) as i FROM reviews WHERE book_id = :id GROUP BY book_id",
                        {"id": book.id}).fetchone()
            if rating:
                rating = round(rating.i, 1)
            d = []
            for review in reviews:
                username = db.execute("SELECT username FROM users WHERE id = :user_id",
                            {"user_id": review.user_id}).fetchone()

                review = dict(review)
                review["username"] = username.username

                d.append(review)
            
            not_posted = True
            if session["user_id"] in [review.user_id for review in reviews]:
                not_posted = False

            gr = lookup(isbn)

            return render_template("books.html", book=book, reviews=d, not_posted=not_posted, rating=rating, gr=gr)
        
        else:
            return apology("sorry, book don´t exists", 403)


@app.route("/api/<string:isbn>")
@login_required
def api(isbn):
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn",
                          {"isbn": isbn}).fetchone()
    
    if book is None:
        return  jsonify({"error": "Invalid book isbn"}), 422

    rating = db.execute("SELECT AVG(rating) as i FROM reviews WHERE book_id = :id GROUP BY book_id",
                        {"id": book.id}).fetchone()
    rating = round(rating.i, 1)

    count = db.execute("SELECT COUNT(rating) as i FROM reviews WHERE book_id = :id",
                        {"id": book.id}).fetchone().i                        

    return jsonify({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": isbn,
        "review_count": count,
        "average_score": str(rating)
    }), 200
    
