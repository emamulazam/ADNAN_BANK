from flask import Flask, request, jsonify, render_template, redirect, session

from werkzeug.security import check_password_hash

from db import get_conn, put_conn
from utils import generate_account_number, generate_transaction_id

app = Flask(__name__)
app.secret_key = "super_secret_key"


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return render_template("index.html")


# =========================
# SIGNUP
# =========================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    name = request.form["name"]
    email = request.form["email"]
    password = request.form["password"]

    account_number = generate_account_number()

    conn = get_conn()
    cur = conn.cursor()

    try:
        # NOTE: storing plain password (as you wanted)
        cur.execute("""
            INSERT INTO users (name, email, password, account_number, amount, user_type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, email, password, account_number, 0.0, "user"))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)})

    finally:
        cur.close()
        put_conn(conn)

    return render_template("success.html",
                           name=name,
                           account_number=account_number)


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        account_number = request.form["account_number"]
        password = request.form["password"]

        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, account_number, password, role FROM users WHERE account_number = %s",
            (account_number,)
        )
        user = cur.fetchone()

        cur.close()
        conn.close()

        # check user exists + password match
        if user and user[2] == password:
            session["user_id"] = user[0]
            session["account_number"] = user[1]
            session["role"] = user[3]

            # 🔥 ROLE REDIRECTION
            if user[3] == "admin":
                return redirect("/admin_dashboard")
            else:
                return redirect("/dashboard")

        return "Invalid credentials ❌"

    return render_template("login.html")


# =========================
# USER DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "user":
        return "Access denied 🚫 (User only)"

    return render_template("dashboard.html")


# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        return "Access denied 🚫 (Admin only)"

    return render_template("dashboard.html")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# BALANCE
# =========================
@app.route("/balance")
def balance():
    if "account_number" not in session:
        return redirect("/login")

    acc = session["account_number"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT amount FROM users WHERE account_number=%s", (acc,))
    row = cur.fetchone()

    cur.close()
    put_conn(conn)

    if not row:
        return jsonify({"error": "Account not found"}), 404

    return jsonify({"balance": float(row[0])})


# =========================
# TRANSFER MONEY
# =========================
@app.route("/transfer", methods=["POST"])
def transfer():
    if "account_number" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    sender = session["account_number"]
    receiver = request.form["receiver_account"]
    amount = float(request.form["amount"])

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    conn = get_conn()
    cur = conn.cursor()

    try:
        # sender check
        cur.execute("SELECT amount FROM users WHERE account_number=%s", (sender,))
        s = cur.fetchone()

        if not s:
            return jsonify({"error": "Sender not found"}), 400

        if s[0] < amount:
            return jsonify({"error": "Insufficient balance"}), 400

        # receiver check
        cur.execute("SELECT amount FROM users WHERE account_number=%s", (receiver,))
        r = cur.fetchone()

        if not r:
            return jsonify({"error": "Receiver not found"}), 400

        # update balances
        cur.execute("""
            UPDATE users SET amount = amount - %s
            WHERE account_number=%s
        """, (amount, sender))

        cur.execute("""
            UPDATE users SET amount = amount + %s
            WHERE account_number=%s
        """, (amount, receiver))

        tx_id = generate_transaction_id()

        cur.execute("""
            INSERT INTO transactions (
                sender_account,
                receiver_account,
                amount,
                transaction_id
            )
            VALUES (%s, %s, %s, %s)
        """, (sender, receiver, amount, tx_id))

        conn.commit()

        return jsonify({
            "message": "Transfer successful",
            "transaction_id": tx_id
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)})

    finally:
        cur.close()
        put_conn(conn)


# =========================
# ADMIN CHECK
# =========================
def admin_required():
    return session.get("role") == "admin"


# =========================
# ADMIN DEPOSIT
# =========================
@app.route("/admin/deposit", methods=["POST"])
def deposit():
    if not admin_required():
        return "Forbidden", 403

    acc = request.form["account_number"]
    amount = float(request.form["amount"])

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET amount = amount + %s
        WHERE account_number=%s
    """, (amount, acc))

    conn.commit()
    cur.close()
    put_conn(conn)

    return jsonify({"message": "Deposit successful"})


# =========================
# ADMIN WITHDRAW
# =========================
@app.route("/admin/withdraw", methods=["POST"])
def withdraw():
    if not admin_required():
        return "Forbidden", 403

    acc = request.form["account_number"]
    amount = float(request.form["amount"])

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT amount FROM users WHERE account_number=%s", (acc,))
    row = cur.fetchone()

    if not row:
        return jsonify({"error": "Account not found"}), 404

    if row[0] < amount:
        return jsonify({"error": "Insufficient funds"}), 400

    cur.execute("""
        UPDATE users
        SET amount = amount - %s
        WHERE account_number=%s
    """, (amount, acc))

    conn.commit()
    cur.close()
    put_conn(conn)

    return jsonify({"message": "Withdraw successful"})


# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    app.run(debug=True)