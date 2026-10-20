"""Daily run: fetch -> filter -> dedupe -> track new/expired -> log -> build site.

Usage:
    python -m jobagent.run                  # normal daily run
    python -m jobagent.run --only stripe    # just one source (by board or name)
    python -m jobagent.run --fixtures tests/fixtures   # offline test data
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .http import Fetcher
from .regions import LocationMatcher
from .rules import Categorizer, EntryLevelRules
from .site import build_site
from .sources import FETCHERS, SkipSource
from .summarize import summarize
from .text import norm_key

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(name, config_dir):
    with open(Path(config_dir) / name) as f:
        return yaml.safe_load(f)


def source_label(src):
    return src.get("name") or src.get("board") or src["type"]


class FixtureHttp:
    """Serves saved JSON/XML files instead of the network, for testing.
    File names: greenhouse_<board>.json, lever_<board>.json, ashby_<board>.json,
    usajobs.json, rss_<name>.xml"""

    def __init__(self, folder):
        self.folder = Path(folder)

    def _file(self, url):
        if "greenhouse.io" in url:
            return f"greenhouse_{url.split('/boards/')[1].split('/')[0]}.json"
        if "lever.co" in url:
            return f"lever_{url.split('/postings/')[1].split('?')[0]}.json"
        if "ashbyhq.com" in url:
            return f"ashby_{url.split('/job-board/')[1].split('?')[0]}.json"
        if "usajobs.gov" in url:
            return "usajobs.json"
        return "rss_" + norm_key(url).replace(" ", "_")[-40:] + ".xml"

    def get(self, url, headers=None):
        path = self.folder / self._file(url)
        if not path.exists():
            raise FileNotFoundError(f"no fixture {path.name}")
        return path.read_bytes()

    def get_json(self, url, headers=None):
        data = json.loads(self.get(url, headers))
        if "usajobs.gov" in url and "Page=1" not in url:
            return {"SearchResult": {}}  # fixture only has one page
        return data


def dedupe_key(item):
    return "|".join([norm_key(item["company"]), norm_key(item["title"]), norm_key(item["area"])])


def merge_duplicates(a, b):
    """Same company + title + location: keep one listing. Prefer the copy that
    shows a salary, then the one that states experience; keep the earliest date."""
    def score(x):
        return (bool(x["salary"]), not x["flags"])
    keep = a if score(a) >= score(b) else b
    dates = [x["posted"] for x in (a, b) if x["posted"]]
    keep["posted"] = min(dates) if dates else None
    return keep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config"))
    ap.add_argument("--sources", default=None, help="use a different sources file")
    ap.add_argument("--data", default=str(ROOT / "data"), help="where run state is kept")
    ap.add_argument("--logs", default=str(ROOT / "logs"))
    ap.add_argument("--out", default=None, help="website output folder (default from settings)")
    ap.add_argument("--only", default=None, help="run only the source with this board/name")
    ap.add_argument("--fixtures", default=None, help="read saved files instead of fetching")
    ap.add_argument("--now", default=None, help=argparse.SUPPRESS)  # for tests
    args = ap.parse_args(argv)

    settings = load_yaml("settings.yaml", args.config)
    sources_cfg = (yaml.safe_load(open(args.sources)) if args.sources
                   else load_yaml("sources.yaml", args.config))
    regions_cfg = load_yaml("regions.yaml", args.config)
    rules_cfg = load_yaml("rules.yaml", args.config)

    tz = ZoneInfo(settings.get("timezone", "America/Los_Angeles"))
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.astimezone(tz).date().isoformat()
    max_age = timedelta(days=settings.get("max_age_days", 30))

    http = FixtureHttp(args.fixtures) if args.fixtures else Fetcher(
        contact=settings.get("contact", "not-set"),
        respect_robots=settings.get("respect_robots", True),
    )
    matcher = LocationMatcher(regions_cfg)
    entry = EntryLevelRules(rules_cfg)
    cats = Categorizer(rules_cfg)

    usajobs_locations = []
    for key in regions_cfg.get("active_regions", []):
        usajobs_locations += regions_cfg["regions"][key].get("usajobs_locations") or []
    ctx = dict(usajobs_locations=usajobs_locations,
               include_remote_us=regions_cfg.get("include_remote_us", True))

    data_dir = Path(args.data)
    data_dir.mkdir(parents=True, exist_ok=True)
    state_path = data_dir / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"listings": {}, "source_counts": {}}
    first_run = not state["listings"]

    # ---- 1. Fetch + 2. filter, per source
    current, report, failed_sources = {}, [], set()
    sources = [s for s in sources_cfg.get("sources", []) if s.get("enabled", True)]
    if args.only:
        sources = [s for s in sources if args.only.lower() in (str(s.get("board", "")).lower(), source_label(s).lower())]

    for src in sources:
        label = source_label(src)
        row = dict(source=label, type=src["type"], status="ok", fetched=0,
                   in_area=0, entry_level=0, error="")
        try:
            raw = FETCHERS[src["type"]](src, http, ctx)
        except SkipSource as e:
            row.update(status="skipped", error=str(e))
            report.append(row)
            continue
        except Exception as e:  # noqa: BLE001 - any failure is logged, run continues
            row.update(status="error", error=f"{type(e).__name__}: {e}"[:300])
            failed_sources.add(label)
            report.append(row)
            continue

        row["fetched"] = len(raw)
        for p in raw:
            p["source"], p["source_type"] = label, src["type"]
            p["sector"] = src.get("sector")
            loc = matcher.classify(p)
            if not loc:
                continue
            row["in_area"] += 1
            p.update(loc)
            keep, reason, flags = entry.evaluate(p)
            if not keep:
                continue
            if p.get("closes_at") and p["closes_at"] < now:
                continue
            posted = p.get("posted_at")
            if posted and now - posted > max_age:
                continue
            row["entry_level"] += 1
            item = dict(
                title=p["title"].strip(),
                company=p["company"],
                location=p["location_display"],
                area=p["area"],
                region=p["region"],
                work_mode=p["work_mode"],
                remote=p["remote"],
                salary=p.get("salary"),
                posted=posted.date().isoformat() if posted else None,
                closes=p["closes_at"].date().isoformat() if p.get("closes_at") else None,
                summary=summarize(p),
                url=p["url"],
                category=cats.categorize(p),
                flags=flags,
                match_reason=reason,
                source=label,
                id=p["id"],
            )
            key = dedupe_key(item)
            current[key] = merge_duplicates(current[key], item) if key in current else item
        report.append(row)

    # ---- 3/4. Merge with yesterday: new / carried over / expired
    listings = {}
    old = state["listings"]
    for key, item in current.items():
        item["first_seen"] = old.get(key, {}).get("first_seen", today)
        item["last_seen"] = today
        listings[key] = item
    carried = 0
    for key, item in old.items():
        if key in listings or item["source"] not in failed_sources:
            continue  # gone from a working source = closed
        last = datetime.fromisoformat(item["last_seen"]).date()
        if (now.astimezone(tz).date() - last).days <= settings.get("keep_on_source_error_days", 3):
            listings[key] = item
            carried += 1
    cutoff = (now.astimezone(tz) - max_age).date().isoformat()
    removed_age = 0
    for key in list(listings):
        it = listings[key]
        if (it.get("posted") or it["first_seen"]) < cutoff or (it.get("closes") and it["closes"] < today):
            del listings[key]
            removed_age += 1
    for it in listings.values():
        it["is_new"] = it["first_seen"] == today
    closed = len([k for k in old if k not in listings])

    # ---- 5. Logging
    prev_counts = state.get("source_counts", {})
    warnings = []
    for row in report:
        before = prev_counts.get(row["source"])
        if row["status"] == "error":
            warnings.append(f"{row['source']}: ERROR {row['error']}")
        elif row["status"] == "ok" and row["fetched"] == 0:
            warnings.append(f"{row['source']}: returned 0 postings (board slug may have changed)")
        elif row["status"] == "ok" and before and row["fetched"] < before * 0.3:
            warnings.append(f"{row['source']}: dropped from {before} to {row['fetched']} postings")
    log_dir = Path(args.logs)
    log_dir.mkdir(parents=True, exist_ok=True)
    csv_path = log_dir / "source_counts.csv"
    new_file = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["run_date", "source", "type", "status", "fetched", "in_area", "entry_level", "error"])
        for r in report:
            w.writerow([today, r["source"], r["type"], r["status"], r["fetched"], r["in_area"], r["entry_level"], r["error"]])

    lines = [f"Run {now.astimezone(tz):%Y-%m-%d %H:%M %Z}", ""]
    lines.append(f"{'SOURCE':28} {'STATUS':8} {'FETCHED':>8} {'IN AREA':>8} {'ENTRY':>6}")
    for r in report:
        lines.append(f"{r['source'][:28]:28} {r['status']:8} {r['fetched']:>8} {r['in_area']:>8} {r['entry_level']:>6}"
                     + (f"   {r['error'][:80]}" if r["error"] else ""))
    total_new = sum(1 for it in listings.values() if it["is_new"])
    lines += ["", f"Listings on site: {len(listings)}  (new today: {total_new}, "
              f"removed as closed/expired: {closed}, carried over from failed sources: {carried})"]
    if first_run:
        lines.append("First run: every listing is marked new.")
    if warnings:
        lines += ["", "CHECK THESE SOURCES:"] + [f"  - {w}" for w in warnings]
    summary_text = "\n".join(lines)
    (log_dir / "last_run.txt").write_text(summary_text + "\n")
    print(summary_text)

    # ---- Save state + build website
    state = {
        "last_run": now.isoformat(),
        "listings": listings,
        "source_counts": {r["source"]: r["fetched"] for r in report if r["status"] == "ok"} | {
            k: v for k, v in prev_counts.items() if k in failed_sources
        },
    }
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True))

    out_dir = Path(args.out or ROOT / settings.get("output_dir", "site"))
    build_site(out_dir, sorted(listings.values(), key=lambda x: (x.get("posted") or x["first_seen"]), reverse=True),
               settings, sources_cfg, regions_cfg, now.astimezone(tz))
    print(f"\nWebsite written to {out_dir}/index.html")
    return 0 if not any(r["status"] == "error" for r in report) or listings else 1


if __name__ == "__main__":
    sys.exit(main())
