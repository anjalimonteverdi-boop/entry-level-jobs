"""Small text helpers shared across modules."""

import html
import re
from datetime import datetime, timezone

_TAG = re.compile(r"<[^>]+>")
_BLOCK_TAGS = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr|section)[^>]*>", re.I)
_WS = re.compile(r"[ \t\r\f\v]+")


def html_to_text(s):
    """HTML (possibly entity-escaped, as Greenhouse sends it) to plain text."""
    if not s:
        return ""
    s = html.unescape(s)
    if "&lt;" in s or "&amp;" in s:  # double-escaped
        s = html.unescape(s)
    s = _BLOCK_TAGS.sub("\n", s)
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    lines = [_WS.sub(" ", ln).strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def phrase_regex(phrases):
    """One case-insensitive regex matching any phrase as whole words."""
    parts = sorted({p.strip().lower() for p in phrases if p.strip()}, key=len, reverse=True)
    if not parts:
        return re.compile(r"(?!x)x")
    alt = "|".join(re.escape(p) for p in parts)
    return re.compile(rf"(?<![\w]){'(?:' + alt + ')'}(?![\w])", re.I)


def norm_key(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def parse_date(value):
    """Best-effort parse to an aware datetime (UTC). Accepts ISO strings,
    RFC 822 strings, and epoch milliseconds."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        v = value / 1000 if value > 10**11 else value
        return datetime.fromtimestamp(v, tz=timezone.utc)
    s = str(value).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None


_MONEY = r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\$\s?\d+(?:\.\d+)?\s?[kK]|\$\s?\d+(?:\.\d{2})?"
_RANGE = re.compile(
    rf"({_MONEY})\s*(?:-|–|—|to)\s*({_MONEY})(\s*(?:/|per|an|a)\s*(?:hour|hr|year|yr|annum|annually))?",
    re.I,
)
_SINGLE = re.compile(rf"({_MONEY})(\s*(?:/|per|an|a)\s*(?:hour|hr|year|yr))", re.I)


def _money_value(s):
    s = s.replace("$", "").replace(",", "").strip()
    mult = 1000 if s.lower().endswith("k") else 1
    return float(s.rstrip("kK").strip()) * mult


def find_salary(text):
    """Find a pay range like '$70,000 - $85,000' or '$25/hour' in text.
    Returns (display_string, min, max) or (None, None, None)."""
    if not text:
        return None, None, None
    for m in _RANGE.finditer(text):
        lo, hi = _money_value(m.group(1)), _money_value(m.group(2))
        if hi < lo or lo < 10:
            continue
        hourly = bool(m.group(3) and re.search(r"hour|hr", m.group(3), re.I)) or hi < 300
        if not hourly and lo < 15000:
            continue  # probably not a salary (e.g. a sign-on bonus)
        return format_salary(lo, hi, "hour" if hourly else "year"), lo, hi
    m = _SINGLE.search(text)
    if m:
        v = _money_value(m.group(1))
        unit = "hour" if re.search(r"hour|hr", m.group(2), re.I) else "year"
        return format_salary(v, v, unit), v, v
    return None, None, None


def format_salary(lo, hi, unit="year"):
    def fmt(v):
        if unit == "hour":
            return f"${v:,.2f}".replace(".00", "")
        return f"${v / 1000:,.0f}K" if v >= 1000 else f"${v:,.0f}"
    suffix = "/hr" if unit == "hour" else "/yr"
    if lo == hi or not hi:
        return f"{fmt(lo)}{suffix}"
    return f"{fmt(lo)}–{fmt(hi)}{suffix}"
