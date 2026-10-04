"""
Part 3 - GenAI-powered insight narrator.

Run:   python narrator/generate_narrative.py
       python narrator/generate_narrative.py --save-sample   (also saves the Gemini output)

Reads narrator/findings.json (written by analysis/clean_and_eda.py), then:
  * with GEMINI_API_KEY set  -> asks Gemini for an SCR narrative
  * with no key / API failure -> falls back to a deterministic offline template
Either way it prints the narrative and a PASS/FAIL line for each of the 5 key figures.
"""
import calendar
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FINDINGS_PATH = os.path.join(HERE, "findings.json")
SAMPLE_PATH = os.path.join(HERE, "sample_output.txt")

SYSTEM_INSTRUCTION = (
    "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
    "Write a business narrative of about 250 words using exactly three labeled sections: "
    "Situation, Complication, Resolution. "
    "Every number in your output must come from the supplied findings and appear with the "
    "same value. Do not invent any statistics. "
    "Write months by name (for example March 2026) and copy rupee amounts exactly as supplied."
)


def month_name(year_month):
    """'2026-03' -> 'March 2026'"""
    year, month = year_month.split("-")
    return f"{calendar.month_name[int(month)]} {year}"


# ---------------------------------------------------------------- offline path
def generate_scr_narrative_offline(findings: dict) -> dict:
    """Fully deterministic: no network, no API key. Same return shape as the online path."""
    rev = findings["cleaned_total_revenue_inr"]
    raw = findings["raw_total_revenue_inr"]
    delta = findings["duplicate_reconciliation_delta_inr"]
    rates = findings["return_rate_by_payment"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    infl = findings["outlier_inflated_month"]

    narrative = f"""### Situation
Mamaearth's cleaned total revenue stands at Rs {rev:,.2f}, down from a raw figure of Rs {raw:,.2f} once duplicate orders were removed. Return rates differ sharply by payment method: COD {rates['COD']}%, UPI {rates['UPI']}% and Card {rates['CARD']}%.

### Complication
The Rs {delta:,.2f} gap between raw and cleaned revenue comes entirely from duplicate order submissions. Returns are concentrated in one segment: {seg['payment_method']} orders in Tier-{seg['city_tier']} cities return at {seg['return_rate_pct']}%. Separately, {month_name(infl['month'])} looked like the strongest month at Rs {infl['apparent_revenue_inr']:,.2f}, but that was inflated by bulk orders.

### Resolution
Report revenue using the deduplicated figure of Rs {rev:,.2f}. Focus return-reduction effort on {seg['payment_method']} orders in Tier-{seg['city_tier']} cities. Treat {month_name(peak['month'])} as the true peak month at Rs {peak['revenue_inr']:,.2f}; once bulk orders are excluded, {month_name(infl['month'])} falls to Rs {infl['corrected_revenue_inr']:,.2f}."""
    return {"status": "success", "narrative": narrative, "tokens": 0}


# ----------------------------------------------------------------- online path
def call_gemini_narrative(findings: dict) -> dict:
    # The user prompt is built FROM the findings argument - nothing is hardcoded.
    user_prompt = f"""Write the SCR narrative using only these verified findings:

- Cleaned total revenue: Rs {findings['cleaned_total_revenue_inr']}
- Raw total revenue (before cleaning): Rs {findings['raw_total_revenue_inr']}
- Revenue difference caused by removing duplicate orders: Rs {findings['duplicate_reconciliation_delta_inr']}
- Return rate by payment method (%): {findings['return_rate_by_payment']}
- Highest-risk segment: {findings['highest_risk_segment']}
- True peak month: {month_name(findings['true_peak_month']['month'])}, revenue Rs {findings['true_peak_month']['revenue_inr']}
- Outlier-inflated month: {month_name(findings['outlier_inflated_month']['month'])}, apparent revenue Rs {findings['outlier_inflated_month']['apparent_revenue_inr']}, corrected revenue Rs {findings['outlier_inflated_month']['corrected_revenue_inr']}
"""
    try:
        from google import genai            # imported here so the offline path needs no library
        from google.genai import types

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,   # role + rules kept separate from the data
                # temperature=0.0: this is a factual business report, not creative writing,
                # so we want the most deterministic output the model can give.
                temperature=0.0,
                max_output_tokens=1024,                  # explicit (>= 300 required)
                thinking_config=types.ThinkingConfig(thinking_budget=0),  # keep tokens for the text
                http_options=types.HttpOptions(timeout=30000),            # milliseconds = 30 s
            ),
        )
        return {"status": "success", "narrative": response.text,
                "tokens": response.usage_metadata.total_token_count}
    except Exception as err:                              # the caller never sees a raw exception
        return {"status": "error", "narrative": None, "message": str(err)}


# ------------------------------------------------------- public entry function
def generate_scr_narrative(findings: dict) -> dict:
    """Try Gemini; fall back to the offline template if there is no key or the call fails."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("[info] No GEMINI_API_KEY found - using the offline fallback.")
        return generate_scr_narrative_offline(findings)
    result = call_gemini_narrative(findings)
    if result["status"] == "error":
        print(f"[info] Gemini call failed ({result['message']}) - using the offline fallback.")
        return generate_scr_narrative_offline(findings)
    return result


# ------------------------------------------------------- numeric accuracy check
def check_numbers(text: str) -> bool:
    """Assert the five key figures appear in the narrative (commas ignored)."""
    t = text.replace(",", "")
    checks = [
        ("Cleaned total revenue (97358.3)",        ["97358.3"]),
        ("COD return rate (44.4)",                 ["44.4"]),
        ("Highest-risk segment rate (54.5)",       ["54.5"]),
        ("Duplicate reconciliation delta (2501.9)", ["2501.9"]),
        ("True peak month (March + 20318.9)",      ["March", "20318.9"]),
    ]
    all_ok = True
    for label, needed in checks:
        ok = all(n in t for n in needed)
        print(("PASS" if ok else "FAIL"), "-", label)
        all_ok = all_ok and ok
    return all_ok


if __name__ == "__main__":
    with open(FINDINGS_PATH) as f:
        findings = json.load(f)

    result = generate_scr_narrative(findings)
    print(result["narrative"], "\n")

    if "--save-sample" in sys.argv and result["tokens"]:   # tokens > 0 means it came from Gemini
        with open(SAMPLE_PATH, "w") as f:
            f.write(result["narrative"])
        print(f"[info] Saved Gemini output to {os.path.relpath(SAMPLE_PATH, HERE)}\n")

    print("Numeric accuracy checklist:")
    check_numbers(result["narrative"])

    if os.path.exists(SAMPLE_PATH):
        print("\nChecklist on the saved Gemini sample (narrator/sample_output.txt):")
        with open(SAMPLE_PATH) as f:
            check_numbers(f.read())
