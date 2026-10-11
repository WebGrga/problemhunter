"""Conservative literal checks. These are auditable rules, not market validation.

JEV cannot return free-form quotes. Select exact source sentences in code and
never accept a payment classification based on model confidence alone.
"""
import re

CHECK_VERSION = "literal-v1"
SELF = r"\b(?:I|we|my|our)\b"
CONDITIONAL = r"\b(?:let's say|suppose|assuming|if I (?:were|had|lost)|if we (?:were|had))\b"


def passages(content):
    # Boundaries do not change characters, so returned text is always a substring.
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", content) if s.strip()]


def payment_quote(content, signal):
    if signal == "unknown":
        return None
    for quote in passages(content):
        if re.search(CONDITIONAL, quote, re.I):
            continue
        # The speaker must pay for a remedy, not collect payment or run payroll.
        remedy = bool(re.search(r"\b(?:software|tool|app|automation|solution|subscription|office manager|accountant|bookkeeper|debt collect\w*|invoice service)\b", quote, re.I))
        refusal = bool(re.search(r"\b(?:I|we)\s+(?:won't|wouldn't|will not|do not|don't|refuse to)\s+pay\b", quote, re.I))
        if signal == "explicit_refusal" and refusal and remedy:
            return quote
        if refusal or re.search(r"\b(?:free|no cost|nothing|not paying)\b", quote, re.I):
            continue
        if signal == "explicit_intent" and remedy and re.search(r"\b(?:I|we)(?:'d| would| will| am willing to| are willing to)\s+pay\b", quote, re.I):
            return quote
        paid = bool(re.search(r"\b(?:I|we)\s+(?:already\s+)?(?:pay|paid|spend|spent)\b", quote, re.I))
        if signal == "paid_solution" and paid and remedy and not re.search(r"\b(?:office manager|accountant|bookkeeper|debt collect\w*)\b", quote, re.I):
            return quote
        if signal == "spending_workaround" and remedy and (paid or re.search(r"\b(?:I|we)\s+(?:have\s+)?hired\s+(?:an?\s+)?(?:office manager|accountant|bookkeeper|debt collect\w*)\b", quote, re.I)):
            return quote
    return None


def ground_payment(content, signal):
    quote = payment_quote(content, signal)
    return {"signal": signal, "quote": quote, "verification": "literal_rule_check", "check_version": CHECK_VERSION} if quote else None
