"""One fetch function per source type. Each returns a list of raw postings in a
common shape (see `posting()`), or raises on failure."""

import os
import urllib.parse
import xml.etree.ElementTree as ET

from .text import find_salary, format_salary, html_to_text, parse_date


def posting(**kw):
    base = dict(
        id=None, source=None, source_type=None, sector=None, company=None,
        title="", locations=[], workplace=None, country=None, department="",
        employment_type="", description="", posted_at=None, closes_at=None,
        url=None, salary=None, salary_min=None, salary_max=None, extra={},
    )
    base.update(kw)
    if base["salary"] is None:
        base["salary"], base["salary_min"], base["salary_max"] = find_salary(base["description"])
    return base


# ---------------------------------------------------------------- Greenhouse
def fetch_greenhouse(src, http, ctx):
    board = src["board"]
    data = http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        offices = [o.get("name") for o in j.get("offices") or [] if o.get("name")]
        depts = [d.get("name") for d in j.get("departments") or [] if d.get("name")]
        out.append(posting(
            id=f"gh:{board}:{j.get('id')}",
            company=src.get("name") or j.get("company_name") or board,
            title=j.get("title", ""),
            locations=[loc] + [o for o in offices if o != loc],
            department=", ".join(depts),
            description=html_to_text(j.get("content")),
            posted_at=parse_date(j.get("first_published") or j.get("updated_at")),
            url=j.get("absolute_url"),
        ))
    return out


# ---------------------------------------------------------------- Lever
def fetch_lever(src, http, ctx):
    board = src["board"]
    data = http.get_json(f"https://api.lever.co/v0/postings/{board}?mode=json")
    out = []
    for j in data:
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
        lists = "\n".join(
            f"{li.get('text', '')}\n{html_to_text(li.get('content'))}" for li in j.get("lists") or []
        )
        desc = "\n".join(filter(None, [j.get("descriptionPlain"), lists, j.get("additionalPlain")]))
        salary = smin = smax = None
        sr = j.get("salaryRange") or {}
        if sr.get("min"):
            unit = "hour" if "hour" in (sr.get("interval") or "") else "year"
            smin, smax = float(sr["min"]), float(sr.get("max") or sr["min"])
            salary = format_salary(smin, smax, unit)
        out.append(posting(
            id=f"lever:{board}:{j.get('id')}",
            company=src.get("name") or board,
            title=j.get("text", ""),
            locations=locs,
            workplace=(j.get("workplaceType") or "").lower() or None,
            country=j.get("country"),
            department=" / ".join(filter(None, [cat.get("department"), cat.get("team")])),
            employment_type=cat.get("commitment") or "",
            description=desc,
            posted_at=parse_date(j.get("createdAt")),
            url=j.get("hostedUrl") or j.get("applyUrl"),
            salary=salary, salary_min=smin, salary_max=smax,
        ))
    return out


# ---------------------------------------------------------------- Ashby
def fetch_ashby(src, http, ctx):
    board = src["board"]
    data = http.get_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
    )
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations") or []]
        wp = (j.get("workplaceType") or "").lower() or None
        if j.get("isRemote") and not wp:
            wp = "remote"
        comp = j.get("compensation") or {}
        comp_text = comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary") or ""
        salary, smin, smax = find_salary(comp_text)
        country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
        out.append(posting(
            id=f"ashby:{board}:{j.get('id')}",
            company=src.get("name") or board,
            title=j.get("title", ""),
            locations=[l for l in locs if l],
            workplace=wp,
            country=country,
            department=" / ".join(filter(None, [j.get("department"), j.get("team")])),
            employment_type=j.get("employmentType") or "",
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            posted_at=parse_date(j.get("publishedAt")),
            url=j.get("jobUrl") or j.get("applyUrl"),
            salary=salary, salary_min=smin, salary_max=smax,
        ))
    return out


# ---------------------------------------------------------------- USAJobs
class SkipSource(Exception):
    """Raised when a source can't run for a known, harmless reason."""


def fetch_usajobs(src, http, ctx):
    key = os.environ.get("USAJOBS_API_KEY")
    email = os.environ.get("USAJOBS_EMAIL")
    if not key or not email:
        raise SkipSource("USAJOBS_API_KEY / USAJOBS_EMAIL not set")
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}
    paths = ";".join(src.get("hiring_paths") or ["public"])

    searches = [{"LocationName": loc} for loc in ctx["usajobs_locations"]]
    if ctx["include_remote_us"]:
        searches.append({"RemoteIndicator": "True"})

    seen, out = set(), []
    for params in searches:
        page = 1
        while True:
            q = dict(params, ResultsPerPage=500, DatePosted=30, HiringPath=paths, Page=page)
            url = "https://data.usajobs.gov/api/search?" + urllib.parse.urlencode(q)
            res = http.get_json(url, headers).get("SearchResult", {})
            for item in res.get("SearchResultItems", []):
                d = item.get("MatchedObjectDescriptor", {})
                pid = item.get("MatchedObjectId") or d.get("PositionID")
                if pid in seen:
                    continue
                seen.add(pid)
                out.append(_usajobs_posting(pid, d, src))
            pages = int((res.get("UserArea") or {}).get("NumberOfPages") or 1)
            if page >= pages:
                break
            page += 1
    return out


def _usajobs_posting(pid, d, src):
    details = (d.get("UserArea") or {}).get("Details") or {}
    pay = (d.get("PositionRemuneration") or [{}])[0]
    salary = smin = smax = None
    if pay.get("MinimumRange"):
        smin, smax = float(pay["MinimumRange"]), float(pay.get("MaximumRange") or pay["MinimumRange"])
        salary = format_salary(smin, smax, "hour" if pay.get("RateIntervalCode") == "PH" else "year")
    remote = str(details.get("RemoteIndicator")).lower() == "true"
    duties = details.get("MajorDuties") or []
    desc = "\n".join(filter(None, [
        details.get("JobSummary"),
        "\n".join(duties) if isinstance(duties, list) else str(duties),
        d.get("QualificationSummary"),
    ]))
    grades = [g.get("Code") for g in d.get("JobGrade") or []]
    try:
        low_grade = int(details.get("LowGrade"))
    except (TypeError, ValueError):
        low_grade = None
    return posting(
        id=f"usajobs:{pid}",
        company=d.get("OrganizationName") or d.get("DepartmentName") or "US Federal Government",
        title=d.get("PositionTitle", ""),
        locations=[l.get("LocationName") for l in d.get("PositionLocation") or [] if l.get("LocationName")],
        workplace="remote" if remote else None,
        country="US",
        department=d.get("DepartmentName") or "",
        employment_type=", ".join(s.get("Name", "") for s in d.get("PositionSchedule") or []),
        description=desc,
        posted_at=parse_date(d.get("PublicationStartDate")),
        closes_at=parse_date(d.get("ApplicationCloseDate")),
        url=d.get("PositionURI") or (d.get("ApplyURI") or [None])[0],
        salary=salary, salary_min=smin, salary_max=smax,
        extra={
            "pay_plan": grades[0] if grades else None,
            "low_grade": low_grade,
            "hiring_paths": details.get("HiringPath") or [],
            "max_entry_gs_grade": src.get("max_entry_gs_grade", 7),
        },
    )


# ---------------------------------------------------------------- RSS / Atom
def fetch_rss(src, http, ctx):
    root = ET.fromstring(http.get(src["url"]))
    atom = "{http://www.w3.org/2005/Atom}"
    items = root.findall(".//item") or root.findall(f".//{atom}entry")
    out = []
    for it in items:
        def t(tag):
            el = it.find(tag)
            if el is None:
                el = it.find(atom + tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        link = t("link")
        if not link:
            el = it.find(atom + "link")
            link = el.get("href") if el is not None else None
        desc = html_to_text(t("description") or t("summary") or t("content"))
        loc = t("location") or src.get("default_location", "")
        out.append(posting(
            id=f"rss:{src.get('name')}:{t('guid') or t('id') or link}",
            company=src.get("company") or src.get("name"),
            title=t("title"),
            locations=[loc] if loc else [],
            description=desc,
            posted_at=parse_date(t("pubDate") or t("published") or t("updated")),
            url=link,
        ))
    return out


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "usajobs": fetch_usajobs,
    "rss": fetch_rss,
}
