import random
import uuid

# =========================
# Generate 13-digit account number
# =========================
def generate_account_number():
    return "".join([str(random.randint(0, 9)) for _ in range(13)])


# =========================
# Generate transaction ID
# =========================
def generate_transaction_id():
    return str(uuid.uuid4())[:20]