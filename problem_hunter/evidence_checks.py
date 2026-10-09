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


def loss_quote(content):
    for quote in passages(content):
        if re.search(CONDITIONAL, quote, re.I):
            continue
        if not re.search(SELF, quote, re.I):
            continue
        if re.search(r"\b(?:wast\w*|los(?:t|ing)|unpaid|underpaid|overdue|short.?paid|haven't been paid|not been paid|not paid|refus\w* to pay|missing invoice|can't find)\b", quote, re.I):
            return quote
        if re.search(r"\b(?:spend|spent|takes?|taking)\b.{0,60}\b(?:hours?|minutes?|days?)\b", quote, re.I):
            return quote
        if re.search(r"\b(?:I|we)\s+invoice\b.{0,80}[$€£]\s?\d", quote, re.I) and re.search(r"\b(?:send|sent|receive|received|pay|paid)\b.{0,40}[$€£]\s?\d", quote, re.I):
            return quote
    return None


def support_quotes(content):
    result = {"pain": loss_quote(content), "workaround_burden": None, "replacement_motivation": None}
    for quote in passages(content):
        if re.search(CONDITIONAL, quote, re.I):
            continue
        if result["pain"] is None and re.search(SELF, quote, re.I) and re.search(r"\b(?:frustrat\w*|inefficient|tedious|nightmare|trouble|struggl\w*|confus\w*|cannot|can't|difficult|error\w*)\b", quote, re.I):
            result["pain"] = quote
        if result["workaround_burden"] is None and re.search(SELF, quote, re.I) and re.search(r"\b(?:manually|spreadsheet\w*|excel|workaround|copy.?past\w*|script\w*|reminder\w*|chasing|hired|hire|tried|trying)\b", quote, re.I):
            result["workaround_burden"] = quote
        if result["replacement_motivation"] is None and re.search(r"\b(?:looking for|seeking|I'd like|I would like|I'd love|I want|we want|I need|I tried|I've tried|we tried|switch\w*|alternatives?|better way|what software|what tool|how can I)\b", quote, re.I):
            result["replacement_motivation"] = quote
    return result


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


def complaint_excerpt(content):
    quotes = support_quotes(content)
    return quotes["pain"] or quotes["workaround_burden"] or quotes["replacement_motivation"] or next(iter(passages(content)), content)
