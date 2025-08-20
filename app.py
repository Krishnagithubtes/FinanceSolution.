from flask import Flask, render_template, request, jsonify
from datetime import date

app = Flask(__name__)

# ---------- Utility functions ----------

def emi(principal, annual_rate_percent, months):
    if principal <= 0 or months <= 0:
        return 0.0
    r = (annual_rate_percent / 100) / 12.0
    if r == 0:
        return round(principal / months, 2)
    e = principal * r * (1 + r) ** months / ((1 + r) ** months - 1)
    return round(e, 2)

def loan_summary(principal, annual_rate_percent, months):
    e = emi(principal, annual_rate_percent, months)
    total_payment = round(e * months, 2)
    total_interest = round(total_payment - principal, 2)
    return {
        "emi": e,
        "total_payment": total_payment,
        "total_interest": total_interest
    }

def gst_breakup(amount, gst_rate_percent, mode="add"):
    """
    mode="add": given base amount -> adds GST
    mode="remove": given gross amount (incl. GST) -> removes GST
    """
    r = gst_rate_percent / 100.0
    if mode == "add":
        tax = round(amount * r, 2)
        gross = round(amount + tax, 2)
        return {"base": amount, "gst": tax, "gross": gross}
    else:
        base = round(amount / (1 + r), 2) if r != 0 else amount
        tax = round(amount - base, 2)
        return {"base": base, "gst": tax, "gross": amount}

def fd_maturity(principal, annual_rate_percent, years, comp_per_year=4):
    """Compound interest (e.g., quarterly compounding by default)."""
    r = annual_rate_percent / 100.0
    n = comp_per_year
    t = years
    maturity = principal * (1 + r / n) ** (n * t)
    interest = maturity - principal
    return {"maturity": round(maturity, 2), "interest": round(interest, 2)}

def rd_maturity(monthly_installment, annual_rate_percent, months, comp_per_year=4):
    """
    Commonly used RD approximation:
    M = R * [((1+i)^n - 1)/i] * (1+i)
    where i = r/12 (monthly rate), R is monthly installment, n is months.
    """
    if monthly_installment <= 0 or months <= 0:
        return {"maturity": 0.0, "interest": 0.0}
    r_annual = annual_rate_percent / 100.0
    i = r_annual / 12.0
    if i == 0:
        maturity = monthly_installment * months
        return {"maturity": round(maturity, 2), "interest": 0.0}
    factor = ((1 + i) ** months - 1) / i
    maturity = monthly_installment * factor * (1 + i)
    deposit = monthly_installment * months
    interest = maturity - deposit
    return {"maturity": round(maturity, 2), "interest": round(interest, 2)}

def estimate_credit_score(payment_history_pct, utilization_pct, credit_age_years, inquiries, dti_pct):
    """
    Lightweight heuristic for educational/demo use only. Outputs 300–850.
    """
    # Clamp inputs
    ph = max(0, min(100, payment_history_pct))
    util = max(0, min(100, utilization_pct))
    age = max(0.0, credit_age_years)
    inq = max(0, inquiries)
    dti = max(0, min(100, dti_pct))

    # Subscores (0–100)
    s_payment  = ph                                     # higher better
    s_util     = max(0, 100 - util)                     # lower util better
    s_age      = min(100, age * 10)                     # 10+ years ≈ 100
    s_inq      = max(0, 100 - inq * 10)                 # fewer inquiries better
    s_dti      = max(0, 100 - dti)                      # lower DTI better

    # Weighted average (roughly similar to common scoring weights)
    score_100 = (0.35*s_payment + 0.30*s_util + 0.15*s_age + 0.10*s_inq + 0.10*s_dti)
    # Map 0–100 -> 300–850
    score = 300 + (score_100 / 100.0) * (850 - 300)
    return int(round(score))

# Demo Bank Holidays (India) for 2025 – sample list (national/federal-style)
BANK_HOLIDAYS_2025_IN = [
    {"date": "2025-01-01", "name": "New Year’s Day"},
    {"date": "2025-01-26", "name": "Republic Day"},
    {"date": "2025-03-14", "name": "Holi"},
    {"date": "2025-03-31", "name": "Eid al-Fitr (Tentative)"},
    {"date": "2025-04-14", "name": "Dr. Ambedkar Jayanti"},
    {"date": "2025-04-18", "name": "Good Friday"},
    {"date": "2025-05-01", "name": "Maharashtra Day / Labour Day"},
    {"date": "2025-08-15", "name": "Independence Day"},
    {"date": "2025-10-02", "name": "Gandhi Jayanti"},
    {"date": "2025-10-20", "name": "Diwali (Tentative)"},
    {"date": "2025-12-25", "name": "Christmas Day"},
]

# Optional: a tiny, static currency rate table (for demo). In production, use a live API.
STATIC_RATES_BASE_USD = {
    "INR": 84.0,
    "USD": 1.0,
    "EUR": 0.91,
    "GBP": 0.76,
    "JPY": 155.0,
    "AUD": 1.45,
    "CAD": 1.34,
}

# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/emi", methods=["POST"])
def api_emi():
    data = request.json
    p = float(data.get("principal", 0))
    r = float(data.get("annual_rate_percent", 0))
    m = int(data.get("months", 0))
    return jsonify(loan_summary(p, r, m))

@app.route("/api/loan-compare", methods=["POST"])
def api_loan_compare():
    data = request.json
    a = loan_summary(float(data["p1"]), float(data["r1"]), int(data["m1"]))
    b = loan_summary(float(data["p2"]), float(data["r2"]), int(data["m2"]))
    return jsonify({"loanA": a, "loanB": b})

@app.route("/api/gst", methods=["POST"])
def api_gst():
    data = request.json
    amount = float(data["amount"])
    gst_rate = float(data["gst_rate"])
    mode = data.get("mode", "add")
    return jsonify(gst_breakup(amount, gst_rate, mode))

@app.route("/api/fd", methods=["POST"])
def api_fd():
    data = request.json
    principal = float(data["principal"])
    rate = float(data["annual_rate"])
    years = float(data["years"])
    comp = int(data.get("comp_per_year", 4))
    return jsonify(fd_maturity(principal, rate, years, comp))

@app.route("/api/rd", methods=["POST"])
def api_rd():
    data = request.json
    monthly = float(data["monthly_installment"])
    rate = float(data["annual_rate"])
    months = int(data["months"])
    return jsonify(rd_maturity(monthly, rate, months))

@app.route("/api/currency", methods=["POST"])
def api_currency():
    """
    Simple converter using STATIC_RATES_BASE_USD; client can also pass custom rate.
    Request JSON:
      - amount
      - from_code
      - to_code
      - custom_rate (optional): rate of 1 from_code in to_code
    """
    data = request.json
    amount = float(data["amount"])
    from_code = data["from_code"].upper()
    to_code = data["to_code"].upper()
    custom_rate = data.get("custom_rate")

    if custom_rate is not None:
        rate = float(custom_rate)
        return jsonify({"converted": round(amount * rate, 4), "rate_used": rate, "note": "Custom rate"})
    # Convert via USD base
    if from_code not in STATIC_RATES_BASE_USD or to_code not in STATIC_RATES_BASE_USD:
        return jsonify({"error": "Unsupported currency in static table. Provide custom_rate or update server rates."}), 400
    # amount (from) -> USD -> to
    amount_usd = amount / STATIC_RATES_BASE_USD[from_code]
    converted = amount_usd * STATIC_RATES_BASE_USD[to_code]
    return jsonify({"converted": round(converted, 4), "rate_used": STATIC_RATES_BASE_USD[to_code] / STATIC_RATES_BASE_USD[from_code], "note": "Static demo rates"})

@app.route("/api/bank-holidays")
def api_bank_holidays():
    return jsonify({
        "country": "India",
        "year": 2025,
        "today": date.today().isoformat(),
        "holidays": BANK_HOLIDAYS_2025_IN
    })

@app.route("/api/credit-score", methods=["POST"])
def api_credit_score():
    data = request.json
    score = estimate_credit_score(
        float(data["payment_history_pct"]),
        float(data["utilization_pct"]),
        float(data["credit_age_years"]),
        int(data["inquiries"]),
        float(data["dti_pct"]),
    )
    # Basic bands
    band = (
        "Excellent" if score >= 750 else
        "Good" if score >= 700 else
        "Fair" if score >= 650 else
        "Poor"
    )
    return jsonify({"score": score, "band": band})

if __name__ == "__main__":
    app.run(debug=True)
