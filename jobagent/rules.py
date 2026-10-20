"""Entry-level filtering and category tagging, driven by config/rules.yaml."""

import re

from .text import phrase_regex

NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15,
}
_NUM = r"(?:\d{1,2}|" + "|".join(NUM_WORDS) + r")"
_YEARS = re.compile(
    rf"(?P<a>{_NUM})\s*(?:\(\d+\)\s*)?(?:\+|plus)?\s*(?:(?:-|–|—|to|or)\s*(?P<b>{_NUM})\s*\+?\s*)?"
    rf"(?:\+\s*)?(?:years?|yrs?)(?:'|’)?",
    re.I,
)
_EXP_NEAR = re.compile(r"experience|exp\b|working in|work in|track record|background in", re.I)
_NOT_EXP = re.compile(r"years? (?:old|of age|ago)|anniversary|founded|in business", re.I)
_NO_EXP = re.compile(
    r"no (?:prior |previous |professional )?(?:work )?experience (?:is )?(?:required|necessary|needed)"
    r"|no experience required|entry[- ]level|new grad|recent (?:college )?grad|"
    r"(?:0|zero)\s*(?:-|–|to)\s*[12]\s*years|less than (?:1|one|2|two) years?",
    re.I,
)
_DEGREE = re.compile(
    r"bachelor'?s|bachelor’s|\bB\.?A\.?\b|\bB\.?S\.?\b|undergraduate degree|"
    r"(?:4|four)[- ]year (?:college )?degree|college degree|university degree",
    re.I,
)
_INTERN = re.compile(r"\bintern(?:ship)?s?\b|\bco-?op\b", re.I)


def _num(s):
    s = s.lower()
    return NUM_WORDS[s] if s in NUM_WORDS else int(s)


def years_required(text):
    """Smallest 'N years of experience' number mentioned, or None."""
    found = []
    for m in _YEARS.finditer(text):
        after = text[m.end(): m.end() + 80]
        before = text[max(0, m.start() - 60): m.start()]
        if _NOT_EXP.search(m.group(0) + after[:20]):
            continue
        if not (_EXP_NEAR.search(after) or _EXP_NEAR.search(before)):
            continue
        try:
            found.append(_num(m.group("a")))
        except (KeyError, ValueError):
            continue
    return min(found) if found else None


class EntryLevelRules:
    def __init__(self, cfg):
        e = cfg["entry_level"]
        self.include = phrase_regex(e["include_title"])
        self.exclude = phrase_regex(e["exclude_title"])
        self.override = phrase_regex(e.get("override_exclude") or [])
        self.max_years = e.get("max_years_required", 2)
        self.internships = e.get("internships", "paid_only")
        self.include_vague = e.get("include_vague", True)
        self.bad = {k: phrase_regex(v) for k, v in (e.get("exclude_phrases") or {}).items()}

    def evaluate(self, p):
        """Returns (keep: bool, reason: str, flags: list[str])."""
        title = p.get("title") or ""
        desc = p.get("description") or ""
        both = f"{title}\n{desc}"

        for reason, rx in self.bad.items():
            if rx.search(both):
                return False, reason, []

        if _INTERN.search(title) or _INTERN.search(p.get("employment_type") or ""):
            if self.internships == "exclude":
                return False, "internship", []
            if self.internships == "paid_only" and not p.get("salary"):
                return False, "internship_unpaid_or_pay_unstated", []

        if self.exclude.search(title) and not self.override.search(title):
            return False, "senior_title", []

        signals = []
        if self.include.search(title):
            signals.append("title")

        extra = p.get("extra") or {}
        if extra.get("pay_plan") in ("GS", "GL") and extra.get("low_grade") is not None:
            if extra["low_grade"] <= extra.get("max_entry_gs_grade", 7):
                signals.append("gs_grade")
            elif "graduates" not in (extra.get("hiring_paths") or []):
                return False, "gs_grade_too_high", []

        yrs = years_required(desc)
        if yrs is not None and yrs > self.max_years:
            return False, "too_many_years", []
        if yrs is not None:
            signals.append("years")
        if _NO_EXP.search(desc):
            signals.append("no_experience_needed")
        experience_stated = bool(set(signals) & {"years", "no_experience_needed", "gs_grade"})
        if yrs is None and _DEGREE.search(desc):
            signals.append("degree_only")

        flags = [] if experience_stated else ["Experience not stated"]
        if signals:
            return True, "+".join(signals), flags
        if self.include_vague:
            return True, "vague", flags
        return False, "no_entry_level_signal", []


class Categorizer:
    def __init__(self, cfg):
        self.cats = [(c["name"], phrase_regex(c["words"])) for c in cfg["categories"]]

    def categorize(self, p):
        sector = (p.get("sector") or "").lower()
        if sector == "government":
            return "Government"
        if sector == "nonprofit":
            return "Nonprofit"
        for field in ("title", "department"):
            text = p.get(field) or ""
            for name, rx in self.cats:
                if rx.search(text):
                    return name
        return "Other"
