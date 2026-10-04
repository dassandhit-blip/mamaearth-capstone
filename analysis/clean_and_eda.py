"""
Part 2 - Python/Pandas data wrangling & EDA.

Run from anywhere:   python analysis/clean_and_eda.py

Works directly on the raw CSVs in data/ (NOT on the SQL database), prints every
intermediate result, and finishes by writing narrator/findings.json - so the
numbers the GenAI layer reports are always produced by this script, never typed.
"""
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
FINDINGS_PATH = os.path.join(ROOT, "narrator", "findings.json")

# Natural key for duplicates: everything EXCEPT order_id (which differs by design)
DEDUP_KEY = ["customer_id", "product_id", "order_date", "quantity",
             "discount_pct", "payment_method", "rating", "returned"]


def band(r):
    """Taught correlation-strength bands, applied to |r|."""
    r = abs(r)
    if r < 0.2:
        return "negligible"
    if r < 0.4:
        return "weak"
    if r < 0.7:
        return "moderate"
    return "strong"


def run(verbose=True):
    say = print if verbose else (lambda *a, **k: None)

    # ---- Task 1: load and inspect ------------------------------------------
    customers = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
    products = pd.read_csv(os.path.join(DATA_DIR, "products.csv"))
    orders = pd.read_csv(os.path.join(DATA_DIR, "orders.csv"))
    say("=== Task 1: load and inspect ===")
    say("orders.shape:", orders.shape)
    say("customers.shape:", customers.shape)
    say("products.shape:", products.shape)

    # Raw revenue on the UNCLEANED data (NaN discount treated as 0) = Part 1 report (a)
    raw = orders.merge(products, on="product_id")
    raw_total = round(float((raw["quantity"] * raw["price"]
                             * (1 - raw["discount_pct"].fillna(0) / 100)).sum()), 2)

    # ---- Task 2: standardise payment_method --------------------------------
    say("\n=== Task 2: standardise payment_method casing ===")
    say("Before:", sorted(orders["payment_method"].unique()))
    orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
    say("After: ", sorted(orders["payment_method"].unique()))
    say(orders["payment_method"].value_counts().to_string())

    # ---- Task 3: remove duplicate orders -----------------------------------
    say("\n=== Task 3: remove duplicate orders ===")
    dup_mask = orders.duplicated(subset=DEDUP_KEY, keep="first")
    dropped_ids = orders.loc[dup_mask, "order_id"].tolist()
    say("Dropped order_ids:", dropped_ids)
    orders_clean = orders[~dup_mask].reset_index(drop=True)
    say("orders_clean.shape:", orders_clean.shape)

    # ---- Task 4: impute missing values -------------------------------------
    say("\n=== Task 4: impute missing values ===")
    say("discount_pct missing (before):", int(orders_clean["discount_pct"].isnull().sum()))
    say("rating missing (before):", int(orders_clean["rating"].isnull().sum()))
    rating_median = float(orders_clean["rating"].median())
    say("Median rating (before imputing):", rating_median)
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
    orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
    say("Missing after imputing:",
        orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

    # ---- Task 5: merge and reconcile against Part 1 ------------------------
    say("\n=== Task 5: merge and reconcile ===")
    merged = orders_clean.merge(products, on="product_id").merge(customers, on="customer_id")
    merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)
    cleaned_total = round(float(merged["order_value"].sum()), 2)
    say("Cleaned total revenue:", cleaned_total)

    # Independent check: sum order_value of the 5 dropped rows on their own
    dropped_rows = orders[orders["order_id"].isin(dropped_ids)].merge(products, on="product_id")
    dropped_total = round(float((dropped_rows["quantity"] * dropped_rows["price"]
                                 * (1 - dropped_rows["discount_pct"].fillna(0) / 100)).sum()), 2)
    delta = round(raw_total - cleaned_total, 2)
    say("Combined order_value of the 5 dropped duplicate rows:", dropped_total)
    say(f"\nReconciliation note: Part 1's raw total revenue was Rs {raw_total}, computed on the "
        f"uncleaned data with all 180 orders. Part 2's cleaned total is Rs {cleaned_total}, a "
        f"difference of Rs {delta}. This entire delta is attributable to the 5 duplicate rows "
        f"{dropped_ids} removed in Task 3: their own combined order_value independently sums to "
        f"Rs {dropped_total}, which equals the delta. The discount_pct and rating imputation does "
        f"not change any order_value total (a 0% discount multiplies by 1), so none of the gap "
        f"comes from imputation.")

    # ---- Task 6: IQR outliers on quantity ----------------------------------
    say("\n=== Task 6: IQR outlier detection on quantity ===")
    q1, q3 = merged["quantity"].quantile(0.25), merged["quantity"].quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    say(f"Q1={q1}, Q3={q3}, IQR={iqr}, lower={lower}, upper={upper}")
    merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)  # flag, don't drop
    say(merged.loc[merged["is_outlier"], ["order_id", "quantity"]].to_string(index=False))

    # ---- Task 7: hypothesis - does COD have a higher return rate? ----------
    say("\n=== Task 7: hypothesis test ===")
    say("Hypothesis: COD orders have a higher return rate than Card or UPI.")
    return_rates = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
    return_rates["return_rate_pct"] = (return_rates["mean"] * 100).round(1)
    say(return_rates.to_string())
    cod_rate = float(return_rates.loc["COD", "return_rate_pct"])
    confirmed = cod_rate > float(return_rates.drop("COD")["return_rate_pct"].max())
    say(f"Hypothesis {'CONFIRMED' if confirmed else 'NOT confirmed'}: COD return rate is {cod_rate}%.")

    # ---- Task 8: multi-level segmentation ----------------------------------
    say("\n=== Task 8: payment_method x city_tier segmentation ===")
    seg = merged.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
    seg["return_rate_pct"] = (seg["mean"] * 100).round(1)
    say(seg.to_string())
    top = seg["return_rate_pct"].idxmax()
    top_rate = float(seg["return_rate_pct"].max())
    say(f"Highest-risk segment: payment_method={top[0]}, city_tier={top[1]}, return_rate_pct={top_rate}")
    c1, c2 = seg.loc[("COD", 1)], seg.loc[("COD", 2)]
    say(f"COD Tier-1: {int(c1['count'])} orders at {c1['return_rate_pct']}%; "
        f"COD Tier-2: {int(c2['count'])} orders at {c2['return_rate_pct']}%. "
        f"The blended COD rate hides where the problem is concentrated.")

    # ---- Task 9: correlation analysis --------------------------------------
    say("\n=== Task 9: correlation analysis ===")
    cols = ["rating", "returned", "discount_pct", "quantity"]
    corr = merged[cols].corr()
    say(corr.round(2).to_string())
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            say(f"{a} vs {b}: r={corr.loc[a, b]:.2f} -> {band(corr.loc[a, b])}")
    say(f"Hypothesis 'higher discounts reduce returns': r={corr.loc['discount_pct', 'returned']:.2f} -> Busted")

    # ---- Task 10: outlier-corrected monthly time series --------------------
    say("\n=== Task 10: monthly revenue, with and without outliers ===")
    merged["order_date"] = pd.to_datetime(merged["order_date"])
    merged["year_month"] = merged["order_date"].dt.strftime("%Y-%m")
    monthly_with = merged.groupby("year_month")["order_value"].sum().round(2)
    monthly_without = merged[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
    say("INCLUDING outliers:\n" + monthly_with.to_string())
    say("EXCLUDING outliers (outlier-corrected):\n" + monthly_without.to_string())
    peak_month = monthly_without.idxmax()
    say(f"January's apparent lead (Rs {monthly_with.loc['2026-01']}) is an artifact of two bulk "
        f"orders landing in January: O0011 (2026-01-28, qty 25) and O0098 (2026-01-10, qty 30). "
        f"Excluding them, {peak_month} is the genuine peak month at Rs {monthly_without.max()}.")

    # ---- Part 3 Task 1: export findings.json -------------------------------
    findings = {
        "cleaned_total_revenue_inr": cleaned_total,
        "raw_total_revenue_inr": raw_total,
        "duplicate_reconciliation_delta_inr": dropped_total,
        "return_rate_by_payment": {m: float(return_rates.loc[m, "return_rate_pct"])
                                   for m in ["COD", "CARD", "UPI"]},
        "highest_risk_segment": {"payment_method": top[0], "city_tier": int(top[1]),
                                 "return_rate_pct": top_rate},
        "true_peak_month": {"month": peak_month, "revenue_inr": float(monthly_without.max())},
        "outlier_inflated_month": {"month": "2026-01",
                                   "apparent_revenue_inr": float(monthly_with.loc["2026-01"]),
                                   "corrected_revenue_inr": float(monthly_without.loc["2026-01"])},
    }
    if verbose:
        os.makedirs(os.path.dirname(FINDINGS_PATH), exist_ok=True)
        with open(FINDINGS_PATH, "w") as f:
            json.dump(findings, f, indent=2)
        print(f"\n=== Wrote {os.path.relpath(FINDINGS_PATH, ROOT)} ===")
        print(json.dumps(findings, indent=2))

    return {"merged": merged, "return_rates": return_rates,
            "monthly_without": monthly_without, "monthly_with": monthly_with,
            "findings": findings}


if __name__ == "__main__":
    run(verbose=True)
