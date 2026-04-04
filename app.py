from flask import Flask, request, jsonify, render_template, redirect, session
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
        cur.execute("""
            INSERT INTO users (name, email, password, account_number, amount, role)
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
    if request.method == "GET":
        return render_template("login.html")

    account_number = request.form["account_number"]
    password = request.form["password"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, account_number, password, role
        FROM users
        WHERE account_number=%s
    """, (account_number,))

    user = cur.fetchone()

    cur.close()
    put_conn(conn)

    if not user:
        return "Account not found ❌"

    user_id, acc, stored_password, role = user

    if stored_password == password:
        session["user_id"] = user_id
        session["account_number"] = acc
        session["role"] = role

        if role == "admin":
            return redirect("/admin_dashboard")

        return redirect("/dashboard")

    return "Invalid password ❌"


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return render_template("logout.html")


# =========================
# USER DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if "account_number" not in session:
        return redirect("/login")

    if session.get("role") != "user":
        return "Access denied 🚫"

    acc = session["account_number"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT name, amount FROM users WHERE account_number=%s", (acc,))
    row = cur.fetchone()

    name = row[0]
    balance = row[1]

    cur.execute("""
        SELECT sender_account, receiver_account, amount, transaction_id
        FROM transactions
        WHERE sender_account=%s OR receiver_account=%s
        ORDER BY id DESC
    """, (acc, acc))

    transactions = cur.fetchall()

    cur.close()
    put_conn(conn)

    return render_template("dashboard.html",
                           balance=balance,
                           transactions=transactions,
                           account=acc,
                           name=name)


# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin_dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        return "Access denied 🚫"

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, email, password, account_number, amount, role
        FROM users
    """)
    users = cur.fetchall()

    cur.close()
    put_conn(conn)

    return render_template("admin_dashboard.html", users=users)


# =========================
# TRANSFER MONEY
# =========================
@app.route("/transfer", methods=["POST"])
def transfer():
    if "account_number" not in session:
        return redirect("/login")

    sender = session["account_number"]
    receiver = request.form["receiver"]
    amount = float(request.form["amount"])

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("SELECT amount FROM users WHERE account_number=%s", (sender,))
        s = cur.fetchone()

        if not s or s[0] < amount:
            return "Insufficient balance"

        cur.execute("SELECT amount FROM users WHERE account_number=%s", (receiver,))
        r = cur.fetchone()

        if not r:
            return "Receiver not found"

        # update balances
        cur.execute("""
            UPDATE users SET amount = amount - %s WHERE account_number=%s
        """, (amount, sender))

        cur.execute("""
            UPDATE users SET amount = amount + %s WHERE account_number=%s
        """, (amount, receiver))

        # transaction record
        cur.execute("""
            INSERT INTO transactions (sender_account, receiver_account, amount, transaction_id)
            VALUES (%s, %s, %s, %s)
        """, (sender, receiver, amount, generate_transaction_id()))

        conn.commit()

        return redirect("/dashboard")

    except Exception as e:
        conn.rollback()
        return str(e)

    finally:
        cur.close()
        put_conn(conn)


# =========================
# ADMIN DEPOSIT (FIXED 🔥)
# =========================
@app.route("/admin/deposit", methods=["POST"])
def deposit():
    if session.get("role") != "admin":
        return "Forbidden", 403

    acc = request.form["account_number"]
    amount = float(request.form["amount"])

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE users SET amount = amount + %s WHERE account_number=%s
        """, (amount, acc))

        # 🔥 transaction record
        cur.execute("""
            INSERT INTO transactions (sender_account, receiver_account, amount, transaction_id)
            VALUES (%s, %s, %s, %s)
        """, (
            "ADMIN",
            acc,
            amount,
            generate_transaction_id()
        ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return str(e)

    finally:
        cur.close()
        put_conn(conn)

    return redirect("/admin_dashboard")


# =========================
# ADMIN WITHDRAW (FIXED 🔥)
# =========================
@app.route("/admin/withdraw", methods=["POST"])
def withdraw():
    if session.get("role") != "admin":
        return "Forbidden", 403

    acc = request.form["account_number"]
    amount = float(request.form["amount"])

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("SELECT amount FROM users WHERE account_number=%s", (acc,))
        row = cur.fetchone()

        if not row:
            return "Account not found"

        if row[0] < amount:
            return "Insufficient balance"

        cur.execute("""
            UPDATE users SET amount = amount - %s WHERE account_number=%s
        """, (amount, acc))

        # 🔥 transaction record
        cur.execute("""
            INSERT INTO transactions (sender_account, receiver_account, amount, transaction_id)
            VALUES (%s, %s, %s, %s)
        """, (
            acc,
            "ADMIN",
            amount,
            generate_transaction_id()
        ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return str(e)

    finally:
        cur.close()
        put_conn(conn)

    return redirect("/admin_dashboard")


# =========================
# DELETE USER
# =========================
@app.route("/admin/delete_user", methods=["POST"])
def delete_user():
    if session.get("role") != "admin":
        return "Forbidden", 403

    user_id = request.form["user_id"]

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()

    except Exception as e:
        conn.rollback()
        return str(e)

    finally:
        cur.close()
        put_conn(conn)

    return redirect("/admin_dashboard")


# =========================
# CHANGE USER'S PASSWORD
# =========================
@app.route("/admin/change_password", methods=["POST"])
def change_password():
    if session.get("role") != "admin":
        return "Forbidden", 403

    user_id = request.form["user_id"]
    new_password = request.form["new_password"]

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE users
            SET password = %s
            WHERE id = %s
        """, (new_password, user_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return str(e)

    finally:
        cur.close()
        put_conn(conn)

    return redirect("/admin_dashboard")

# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)