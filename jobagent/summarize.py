"""Rule-based 1–2 sentence plain-English summaries (free, no API needed).

Strategy: find the part of the description that talks about the role (not
the company), then take its first one or two sentences."""

import re

_ROLE_HEADINGS = re.compile(
    r"^(?:about (?:the|this) (?:role|position|job|opportunity)|the role|the position|"
    r"role overview|position (?:summary|overview)|job (?:summary|description)|"
    r"what you(?:'|’)ll do|what you will do|your role|in this role|the opportunity|"
    r"overview|summary|duties|responsibilities)\s*:?\s*$",
    re.I,
)
_COMPANY_HEADINGS = re.compile(r"^(?:about (?:us|the company|[A-Z][\w&.\- ]{0,40})|who we are|our mission)\s*:?\s*$", re.I)
_ROLE_CUES = re.compile(
    r"\b(?:you will|you(?:'|’)ll|this role|the role|this position|in this position|"
    r"we(?:'|’)re (?:looking|seeking|hiring)|we are (?:looking|seeking|hiring)|"
    r"is responsible for|will be responsible|responsible for|join (?:our|the) .{0,40}team)\b",
    re.I,
)
_ABOUT_COMPANY = re.compile(r"^(?:we|we're|we are|our|at |founded|since|headquartered)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“(])")
_BOILER = re.compile(r"equal opportunity|accommodation|e-verify|privacy|benefits|salary range|pay range|\$\d", re.I)

MAX_CHARS = 280


def _sentences(text):
    out = []
    for para in text.split("\n"):
        para = para.strip(" •*-–\t")
        if len(para) < 25:
            continue
        out.extend(s.strip() for s in _SENTENCE.split(para) if len(s.strip()) > 20)
    return out


def _pick(sentences):
    picked = []
    for s in sentences:
        if _BOILER.search(s):
            continue
        picked.append(s)
        if len(picked) == 2 or len(" ".join(picked)) > 160:
            break
    text = " ".join(picked)
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(",;:")
        text = cut + "…"
    if text and text[-1] not in ".!?…":
        text += "."
    return text


def summarize(p):
    desc = p.get("description") or ""
    lines = [ln.strip() for ln in desc.split("\n") if ln.strip()]

    # 1. Text under a "the role" style heading.
    for i, ln in enumerate(lines):
        if _ROLE_HEADINGS.match(ln):
            body = []
            for nxt in lines[i + 1:]:
                if _COMPANY_HEADINGS.match(nxt) or (len(nxt) < 40 and nxt.endswith(":")):
                    break
                body.append(nxt)
            s = _pick(_sentences("\n".join(body)))
            if s:
                return s

    # 2. Sentences that describe the role ("you will", "this role"...).
    sents = _sentences(desc)
    cued = [s for s in sents if _ROLE_CUES.search(s)]
    if cued:
        return _pick(cued)

    # 3. Opening sentences, skipping ones that are about the company.
    company = (p.get("company") or "").lower()
    plain = [s for s in sents if not _ABOUT_COMPANY.match(s)
             and not (company and company in s.lower())]
    if plain:
        return _pick(plain)

    # 4. Fallback that's always true.
    where = p.get("location_display") or "the listed location"
    return f"{p.get('title')} role at {p.get('company')} ({where}). See the posting for details."
