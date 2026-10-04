"""
Part 2, Task 11 - two visualizations.

Run AFTER clean_and_eda.py (or on its own - it rebuilds the numbers from the raw CSVs):
    python analysis/visualize.py

Saves:
    visualizations/return_rate_by_payment.png
    visualizations/monthly_revenue_trend.png
"""
import calendar
import os

import matplotlib
matplotlib.use("Agg")  # draw to files, no screen needed
import matplotlib.pyplot as plt

from clean_and_eda import ROOT, run

OUT_DIR = os.path.join(ROOT, "visualizations")
os.makedirs(OUT_DIR, exist_ok=True)

results = run(verbose=False)  # recompute from the raw CSVs every time

# ---- Chart 1: return rate by (cleaned) payment method, descending ----------
rates = results["return_rates"]["return_rate_pct"].sort_values(ascending=False)
cod = rates["COD"]
card = rates["CARD"]

fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(rates.index, rates.values, color=["#d62728", "#1f77b4", "#2ca02c"])
for bar, pct in zip(bars, rates.values):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.6, f"{pct}%",
            ha="center", fontweight="bold")
ax.set_title(f"COD Returns at {cod}% - {cod / card:.0f}x Card")
ax.set_xlabel("Payment method")
ax.set_ylabel("Return rate (%)")
ax.set_ylim(0, max(rates.values) + 8)
fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "return_rate_by_payment.png"), dpi=150)
plt.close(fig)

# ---- Chart 2: outlier-corrected monthly revenue -----------------------------
monthly = results["monthly_without"]  # the corrected series, not the inflated one
peak_month = monthly.idxmax()
year, month = peak_month.split("-")
peak_label = f"{calendar.month_name[int(month)]} {year}"
peak_idx = list(monthly.index).index(peak_month)

fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(monthly.index, monthly.values, marker="o", linewidth=2, color="#1f77b4")
ax.annotate(f"Peak: Rs {monthly.max():,.2f}", xy=(peak_idx, monthly.max()),
            xytext=(peak_idx, monthly.max() + 1800), ha="center", fontweight="bold",
            arrowprops=dict(arrowstyle="->"))
ax.set_title(f"Outlier-Corrected Monthly Revenue - True Peak: {peak_label}")
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (Rs)")
ax.set_ylim(0, monthly.max() + 5000)
fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "monthly_revenue_trend.png"), dpi=150)
plt.close(fig)

print("Saved visualizations/return_rate_by_payment.png and visualizations/monthly_revenue_trend.png")
