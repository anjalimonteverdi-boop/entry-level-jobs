"""Decide whether a posting's location is in scope, and label its area and
work mode (Remote / Hybrid / On-site). Driven entirely by config/regions.yaml."""

import re

from .text import phrase_regex

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

_US = re.compile(
    r"united states|\busa\b|\bu\.s\.a?\.?|\bus\b|\bus-|north america|\bamericas\b|nationwide"
    r"|anywhere in the us|" + "|".join(re.escape(n.lower()) for n in US_STATES.values())
    + r"|,\s*(?:" + "|".join(US_STATES) + r")\b",
    re.I,
)
_FOREIGN = phrase_regex([
    "canada", "toronto", "vancouver", "montreal", "mexico", "brazil", "argentina", "colombia",
    "uk", "united kingdom", "england", "london", "ireland", "dublin, ireland", "europe", "emea",
    "germany", "berlin", "france", "paris", "netherlands", "amsterdam", "spain", "portugal",
    "poland", "sweden", "switzerland", "italy", "india", "bangalore", "bengaluru", "apac",
    "asia", "singapore", "japan", "tokyo", "korea", "china", "australia", "sydney",
    "new zealand", "israel", "philippines", "latam", "worldwide", "global",
])
_REMOTE = re.compile(r"\bremote\b|work from home|\bwfh\b|anywhere in the us", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)
_SEGMENT_SPLIT = re.compile(r";|\||/| or |\n", re.I)


class LocationMatcher:
    def __init__(self, regions_cfg):
        self.include_remote_us = regions_cfg.get("include_remote_us", True)
        self.regions = []
        for key in regions_cfg.get("active_regions", []):
            r = regions_cfg["regions"][key]
            state_re = re.compile(
                rf",\s*{re.escape(r['state'])}\b|{re.escape(r['state_name'])}", re.I
            )
            areas = []
            for name, a in (r.get("areas") or {}).items():
                areas.append((
                    name,
                    phrase_regex(a.get("places") or []),
                    phrase_regex(a.get("ambiguous_places") or []),
                ))
            self.regions.append(dict(
                key=key, label=r.get("label", key), state_re=state_re, areas=areas,
                phrases=phrase_regex(r.get("region_phrases") or []),
                default_area=r.get("region_default_area", r.get("label", key)),
            ))

    def _match_region(self, text):
        for seg in _SEGMENT_SPLIT.split(text):
            for r in self.regions:
                for name, places, ambiguous in r["areas"]:
                    if places.search(seg):
                        return r, name
                    if ambiguous.search(seg) and r["state_re"].search(seg):
                        return r, name
                if r["phrases"].search(seg):
                    return r, r["default_area"]
        return None, None

    def _is_remote_us(self, p, text):
        remote = p.get("workplace") == "remote" or bool(_REMOTE.search(text))
        if not remote:
            return False
        if _US.search(text):
            return True
        if _FOREIGN.search(text):
            return False
        country = (p.get("country") or "").strip().upper()
        return country in ("", "US", "USA", "UNITED STATES")

    def classify(self, p):
        """Returns dict(region, area, remote, work_mode) or None if out of scope."""
        loc_text = " ; ".join(l for l in p.get("locations") or [] if l)
        text = f"{loc_text} ; {p.get('title', '')}"
        region, area = self._match_region(loc_text)
        remote_us = self.include_remote_us and self._is_remote_us(p, text)
        if not region and not remote_us:
            return None
        if remote_us:
            mode = "Remote"
        elif p.get("workplace") == "hybrid" or _HYBRID.search(text):
            mode = "Hybrid"
        else:
            mode = "On-site"
        return dict(
            region=region["key"] if region else "remote_us",
            area=area if region else "Remote (US)",
            remote=remote_us,
            work_mode=mode,
            location_display=_display(loc_text, remote_us),
        )


def _display(loc_text, remote):
    parts = [s.strip() for s in loc_text.split(";") if s.strip()]
    seen, uniq = set(), []
    for s in parts:
        if s.lower() not in seen:
            seen.add(s.lower())
            uniq.append(s)
    shown = "; ".join(uniq[:3]) + (f" +{len(uniq) - 3} more" if len(uniq) > 3 else "")
    if remote and shown.lower() in ("remote", "remote - us", "remote, us", "remote (us)"):
        shown = "Remote (US)"
    elif remote and "remote" not in shown.lower():
        shown = f"Remote (US){'; ' + shown if shown else ''}"
    return shown or ("Remote (US)" if remote else "")
