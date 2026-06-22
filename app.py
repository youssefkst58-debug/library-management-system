from flask import Flask, request, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta
from collections import Counter
from models import db, User, Book, BorrowTransaction, Reservation

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///library.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "library_secret_key"

db.init_app(app)


def get_reports_data():
    all_transactions = BorrowTransaction.query.all()
    borrowed_transactions = BorrowTransaction.query.filter_by(status="Borrowed").all()
    returned_transactions = BorrowTransaction.query.filter_by(status="Returned").all()

    overdue_transactions = BorrowTransaction.query.filter(
        BorrowTransaction.status == "Borrowed",
        BorrowTransaction.due_date < date.today()
    ).all()

    borrowed_isbns = [t.isbn for t in all_transactions]
    most_borrowed_counter = Counter(borrowed_isbns)
    active_user_counter = Counter([t.user_id for t in all_transactions])

    monthly_counter = Counter()
    for t in all_transactions:
        if t.borrow_date:
            month_key = str(t.borrow_date)[:7]
            monthly_counter[month_key] += 1

    return {
        "most_borrowed_books": [
            {
                "isbn": isbn,
                "title": Book.query.get(isbn).title if Book.query.get(isbn) else isbn,
                "borrow_count": count
            }
            for isbn, count in most_borrowed_counter.most_common()
        ],
        "active_users": [
            {
                "user_id": user_id,
                "username": User.query.get(user_id).username if User.query.get(user_id) else str(user_id),
                "transactions": count
            }
            for user_id, count in active_user_counter.most_common()
        ],
        "borrowed_books": [
            {
                "book": Book.query.get(t.isbn).title if Book.query.get(t.isbn) else t.isbn,
                "user": User.query.get(t.user_id).username if User.query.get(t.user_id) else str(t.user_id),
                "borrow_date": str(t.borrow_date),
                "due_date": str(t.due_date),
                "status": t.status
            }
            for t in borrowed_transactions
        ],
        "overdue_books": [
            {
                "book": Book.query.get(t.isbn).title if Book.query.get(t.isbn) else t.isbn,
                "user": User.query.get(t.user_id).username if User.query.get(t.user_id) else str(t.user_id),
                "due_date": str(t.due_date)
            }
            for t in overdue_transactions
        ],
        "monthly_borrowing_statistics": dict(monthly_counter),
        "returned_books": [
            {
                "book": Book.query.get(t.isbn).title if Book.query.get(t.isbn) else t.isbn,
                "return_date": str(t.return_date),
                "status": t.status
            }
            for t in returned_transactions
        ]
    }


@app.route("/")
def home():
    return """
    <h1>Library Management System</h1>

    <a href="/register">Register</a><br><br>
    <a href="/login">Login</a><br><br>
    <a href="/dashboard">Dashboard</a><br><br>
    <a href="/books">Books</a><br><br>
    <a href="/add_book">Add Book</a><br><br>
    <a href="/history">Transaction History</a><br><br>
    <a href="/reservations">Reservations</a><br><br>
    <a href="/reports">Reports</a><br><br>
    <a href="/users">REST API Users</a><br><br>
    <a href="/logout">Logout</a>
    """


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        new_user = User(
            username=request.form["username"],
            password=generate_password_hash(request.form["password"]),
            role=request.form["role"]
        )

        db.session.add(new_user)
        db.session.commit()

        return """
        <h2>User Registered Successfully!</h2>
        <a href="/login">Go To Login</a>
        """

    return """
    <h1>User Registration</h1>

    <form method="POST">
        Username:
        <input type="text" name="username"><br><br>

        Password:
        <input type="password" name="password"><br><br>

        Role:
        <select name="role">
            <option>Student</option>
            <option>Librarian</option>
            <option>Administrator</option>
        </select>

        <br><br>

        <input type="submit" value="Register">
    </form>
    """


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["role"] = user.role

            return """
            <h2>Login Successful!</h2>
            <a href="/dashboard">Go To Dashboard</a>
            """

        return "<h2>Invalid Username or Password</h2>"

    return """
    <h1>Login</h1>

    <form method="POST">
        Username:
        <input type="text" name="username"><br><br>

        Password:
        <input type="password" name="password"><br><br>

        <input type="submit" value="Login">
    </form>
    """


@app.route("/dashboard")
def dashboard():
    if "role" not in session:
        return "<h2>Please Login First</h2>"

    if session["role"] == "Administrator":
        return """
        <h1>Administrator Dashboard</h1>
        <p>Can manage users, books, reports, and system operations.</p>
        <a href="/books">View Books</a><br><br>
        <a href="/add_book">Add Book</a><br><br>
        <a href="/history">Transaction History</a><br><br>
        <a href="/reservations">Reservations</a><br><br>
        <a href="/reports">Reports</a>
        """

    if session["role"] == "Librarian":
        return """
        <h1>Librarian Dashboard</h1>
        <p>Can manage books, borrowing records, reservations, and reports.</p>
        <a href="/books">View Books</a><br><br>
        <a href="/add_book">Add Book</a><br><br>
        <a href="/history">Transaction History</a><br><br>
        <a href="/reservations">Reservations</a><br><br>
        <a href="/reports">Reports</a>
        """

    return """
    <h1>Student Dashboard</h1>
    <p>Can search, borrow, reserve, and view personal transaction history.</p>
    <a href="/books">View Books</a><br><br>
    <a href="/history">Transaction History</a><br><br>
    <a href="/reservations">Reservations</a>
    """


@app.route("/books", methods=["GET", "POST"])
def books():
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form

        new_book = Book(
            isbn=data["isbn"],
            title=data["title"],
            author=data.get("author", ""),
            publisher=data.get("publisher", ""),
            publication_year=int(data.get("publication_year", 0)),
            available=True
        )

        db.session.add(new_book)
        db.session.commit()

        return jsonify({"message": "Book added successfully", "isbn": new_book.isbn}), 201

    all_books = Book.query.all()

    if request.args.get("format") == "json":
        return jsonify([
            {
                "isbn": book.isbn,
                "title": book.title,
                "author": book.author,
                "publisher": book.publisher,
                "publication_year": book.publication_year,
                "available": book.available
            }
            for book in all_books
        ])

    output = """
    <h1>Books</h1>

    <form method="GET" action="/search_books">
        Search:
        <input type="text" name="q">
        <input type="submit" value="Search">
    </form>

    <br>
    <a href="/">Home</a><br><br>
    """

    if not all_books:
        output += "<p>No books added yet.</p>"

    for book in all_books:
        status = "Available" if book.available else "Not Available"

        output += f"""
        <p>
            <b>{book.title}</b><br>
            ISBN: {book.isbn}<br>
            Author: {book.author}<br>
            Publisher: {book.publisher}<br>
            Year: {book.publication_year}<br>
            Status: {status}<br>
            <a href="/borrow/{book.isbn}">Borrow</a><br>
            <a href="/reserve/{book.isbn}">Reserve</a><br>
            <a href="/delete_book/{book.isbn}">Delete</a>
        </p>
        <hr>
        """

    return output


@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    if "role" not in session:
        return "<h2>Please Login First</h2>"

    if session["role"] not in ["Administrator", "Librarian"]:
        return "<h2>Access Denied</h2>"

    if request.method == "POST":
        new_book = Book(
            isbn=request.form["isbn"],
            title=request.form["title"],
            author=request.form["author"],
            publisher=request.form["publisher"],
            publication_year=int(request.form["publication_year"]),
            available=True
        )

        db.session.add(new_book)
        db.session.commit()

        return """
        <h2>Book Added Successfully!</h2>
        <a href="/books">View Books</a>
        """

    return """
    <h1>Add Book</h1>

    <form method="POST">
        ISBN:
        <input type="text" name="isbn"><br><br>

        Title:
        <input type="text" name="title"><br><br>

        Author:
        <input type="text" name="author"><br><br>

        Publisher:
        <input type="text" name="publisher"><br><br>

        Publication Year:
        <input type="number" name="publication_year"><br><br>

        <input type="submit" value="Add Book">
    </form>
    """


@app.route("/delete_book/<isbn>")
def delete_book(isbn):
    if "role" not in session:
        return "<h2>Please Login First</h2>"

    if session["role"] not in ["Administrator", "Librarian"]:
        return "<h2>Access Denied</h2>"

    book = Book.query.get(isbn)

    if not book:
        return "<h2>Book Not Found</h2>"

    db.session.delete(book)
    db.session.commit()

    return """
    <h2>Book Deleted Successfully!</h2>
    <a href="/books">Back To Books</a>
    """


@app.route("/search_books")
def search_books():
    q = request.args.get("q", "")

    results = Book.query.filter(
        (Book.title.contains(q)) |
        (Book.isbn.contains(q)) |
        (Book.author.contains(q)) |
        (Book.publisher.contains(q))
    ).all()

    output = f"<h1>Search Results for: {q}</h1>"
    output += '<a href="/books">Back To Books</a><br><br>'

    if not results:
        output += "<p>No books found.</p>"

    for book in results:
        status = "Available" if book.available else "Not Available"

        output += f"""
        <p>
            <b>{book.title}</b><br>
            ISBN: {book.isbn}<br>
            Author: {book.author}<br>
            Publisher: {book.publisher}<br>
            Year: {book.publication_year}<br>
            Status: {status}<br>
            <a href="/borrow/{book.isbn}">Borrow</a><br>
            <a href="/reserve/{book.isbn}">Reserve</a>
        </p>
        <hr>
        """

    return output


@app.route("/borrow/<isbn>")
def borrow_book(isbn):
    if "user_id" not in session:
        return "<h2>Please Login First</h2>"

    book = Book.query.get(isbn)

    if not book:
        return "<h2>Book Not Found</h2>"

    if not book.available:
        return f"""
        <h2>Book is not available</h2>
        <a href="/reserve/{isbn}">Reserve This Book</a><br>
        <a href="/books">Back To Books</a>
        """

    transaction = BorrowTransaction(
        user_id=session["user_id"],
        isbn=isbn,
        borrow_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        return_date=None,
        status="Borrowed"
    )

    book.available = False

    db.session.add(transaction)
    db.session.commit()

    return """
    <h2>Book Borrowed Successfully!</h2>
    <p>Due date is 14 days from today.</p>
    <a href="/history">View Transaction History</a><br><br>
    <a href="/books">Back To Books</a>
    """


@app.route("/borrow", methods=["POST"])
def api_borrow_book():
    data = request.get_json() if request.is_json else request.form
    isbn = data["isbn"]
    user_id = int(data.get("user_id", session.get("user_id", 0)))

    book = Book.query.get(isbn)

    if not book:
        return jsonify({"error": "Book not found"}), 404

    if not book.available:
        return jsonify({"error": "Book is not available"}), 400

    transaction = BorrowTransaction(
        user_id=user_id,
        isbn=isbn,
        borrow_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        return_date=None,
        status="Borrowed"
    )

    book.available = False

    db.session.add(transaction)
    db.session.commit()

    return jsonify({
        "message": "Book borrowed successfully",
        "transaction_id": transaction.transaction_id,
        "due_date": str(transaction.due_date)
    }), 201


@app.route("/return_book/<int:transaction_id>")
def return_book(transaction_id):
    if "user_id" not in session:
        return "<h2>Please Login First</h2>"

    transaction = BorrowTransaction.query.get(transaction_id)

    if not transaction:
        return "<h2>Transaction Not Found</h2>"

    book = Book.query.get(transaction.isbn)

    transaction.return_date = date.today()
    transaction.status = "Returned"

    if book:
        book.available = True

    db.session.commit()

    return """
    <h2>Book Returned Successfully!</h2>
    <a href="/history">Back To History</a>
    """


@app.route("/return", methods=["POST"])
def api_return_book():
    data = request.get_json() if request.is_json else request.form
    transaction_id = int(data["transaction_id"])

    transaction = BorrowTransaction.query.get(transaction_id)

    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404

    book = Book.query.get(transaction.isbn)

    transaction.return_date = date.today()
    transaction.status = "Returned"

    if book:
        book.available = True

    db.session.commit()

    return jsonify({"message": "Book returned successfully"}), 200


@app.route("/history")
def history():
    if "user_id" not in session:
        return "<h2>Please Login First</h2>"

    transactions = BorrowTransaction.query.filter_by(
        user_id=session["user_id"]
    ).all()

    output = """
    <h1>Transaction History</h1>
    <a href="/">Home</a><br><br>
    """

    if not transactions:
        output += "<p>No transactions yet.</p>"

    for t in transactions:
        book = Book.query.get(t.isbn)

        output += f"""
        <p>
            Book: {book.title if book else t.isbn}<br>
            Borrow Date: {t.borrow_date}<br>
            Due Date: {t.due_date}<br>
            Return Date: {t.return_date}<br>
            Status: {t.status}<br>
        """

        if t.status == "Borrowed":
            output += f'<a href="/return_book/{t.transaction_id}">Return Book</a>'

        output += "</p><hr>"

    return output


@app.route("/reserve/<isbn>")
def reserve_book(isbn):
    if "user_id" not in session:
        return "<h2>Please Login First</h2>"

    book = Book.query.get(isbn)

    if not book:
        return "<h2>Book Not Found</h2>"

    if book.available:
        return """
        <h2>Book is available. No need to reserve.</h2>
        <a href="/books">Back To Books</a>
        """

    existing = Reservation.query.filter_by(
        user_id=session["user_id"],
        isbn=isbn,
        status="Pending"
    ).first()

    if existing:
        return """
        <h2>You already reserved this book.</h2>
        <a href="/books">Back To Books</a>
        """

    reservation = Reservation(
        user_id=session["user_id"],
        isbn=isbn,
        reservation_date=date.today(),
        status="Pending"
    )

    db.session.add(reservation)
    db.session.commit()

    return """
    <h2>Book Reserved Successfully!</h2>
    <a href="/reservations">View Reservations</a>
    """


@app.route("/reservations")
def reservations():
    if "user_id" not in session:
        return "<h2>Please Login First</h2>"

    user_reservations = Reservation.query.filter_by(
        user_id=session["user_id"]
    ).all()

    output = """
    <h1>Reservations</h1>
    <a href="/">Home</a><br><br>
    """

    if not user_reservations:
        output += "<p>No reservations yet.</p>"

    for r in user_reservations:
        book = Book.query.get(r.isbn)

        output += f"""
        <p>
            Book: {book.title if book else r.isbn}<br>
            Reservation Date: {r.reservation_date}<br>
            Status: {r.status}
        </p>
        <hr>
        """

    return output


@app.route("/reports")
def reports():
    if request.args.get("format") == "json":
        return jsonify(get_reports_data())

    if "role" not in session:
        return "<h2>Please Login First</h2>"

    if session["role"] not in ["Administrator", "Librarian"]:
        return "<h2>Access Denied</h2>"

    data = get_reports_data()

    output = """
    <h1>Reports and Analytics</h1>
    <a href="/">Home</a><br><br>
    """

    output += "<h2>Most Borrowed Books</h2>"
    if not data["most_borrowed_books"]:
        output += "<p>No borrowed books yet.</p>"
    for item in data["most_borrowed_books"]:
        output += f"<p>{item['title']} - Borrowed {item['borrow_count']} time(s)</p>"

    output += "<h2>Active Users</h2>"
    if not data["active_users"]:
        output += "<p>No active users yet.</p>"
    for item in data["active_users"]:
        output += f"<p>{item['username']} - {item['transactions']} transaction(s)</p>"

    output += "<h2>Currently Borrowed Books</h2>"
    if not data["borrowed_books"]:
        output += "<p>No books are currently borrowed.</p>"
    for item in data["borrowed_books"]:
        output += f"""
        <p>
        Book: {item['book']}<br>
        User: {item['user']}<br>
        Borrow Date: {item['borrow_date']}<br>
        Due Date: {item['due_date']}<br>
        Status: {item['status']}
        </p>
        """

    output += "<h2>Overdue Books</h2>"
    if not data["overdue_books"]:
        output += "<p>No overdue books.</p>"
    for item in data["overdue_books"]:
        output += f"""
        <p>
        Book: {item['book']}<br>
        User: {item['user']}<br>
        Due Date: {item['due_date']}
        </p>
        """

    output += "<h2>Monthly Borrowing Statistics</h2>"
    if not data["monthly_borrowing_statistics"]:
        output += "<p>No monthly data yet.</p>"
    for month, count in data["monthly_borrowing_statistics"].items():
        output += f"<p>{month}: {count} borrowing transaction(s)</p>"

    output += "<h2>Returned Books</h2>"
    if not data["returned_books"]:
        output += "<p>No returned books yet.</p>"
    for item in data["returned_books"]:
        output += f"""
        <p>
        Book: {item['book']}<br>
        Return Date: {item['return_date']}<br>
        Status: {item['status']}
        </p>
        """

    return output


@app.route("/users")
def users():
    all_users = User.query.all()

    return jsonify([
        {
            "id": user.id,
            "username": user.username,
            "role": user.role
        }
        for user in all_users
    ])


@app.route("/logout")
def logout():
    session.clear()

    return """
    <h2>Logged Out Successfully!</h2>
    <a href="/login">Login Again</a>
    """


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5000, debug=True)