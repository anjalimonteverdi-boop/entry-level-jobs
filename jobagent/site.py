"""Builds the static website: copies site_template/ and writes the data file."""

import json
import shutil
import urllib.parse
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "site_template"
CATEGORIES = ["Marketing", "Communications", "Design", "Sales", "Customer Support", "Operations",
              "Admin", "People/HR", "Finance", "Data/Analytics", "Tech", "Healthcare", "Science/Research",
              "Education", "Legal", "Merchandising", "Nonprofit", "Government", "Other"]


def build_site(out_dir, listings, settings, sources_cfg, regions_cfg, now_local):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in TEMPLATE.iterdir():
        if f.is_file():
            shutil.copy2(f, out_dir / f.name)

    areas = []
    for key in regions_cfg.get("active_regions", []):
        r = regions_cfg["regions"][key]
        areas += list((r.get("areas") or {}).keys())
        if r.get("region_default_area"):
            areas.append(r["region_default_area"])
    if regions_cfg.get("include_remote_us", True):
        areas.append("Remote (US)")

    search_name = " / ".join(
        regions_cfg["regions"][k].get("search_name", k) for k in regions_cfg.get("active_regions", [])
    )
    links = [
        {"name": l["name"], "url": l["url"].replace("{region}", urllib.parse.quote(search_name))}
        for l in sources_cfg.get("search_links") or []
    ]

    payload = {
        "title": settings.get("site_title", "Entry-Level Jobs"),
        "tagline": settings.get("site_tagline", ""),
        "updated": (f"{now_local:%b} {now_local.day}, {now_local:%Y} at "
                    f"{now_local.hour % 12 or 12}:{now_local:%M %p %Z}"),
        "updated_iso": now_local.isoformat(),
        "categories": CATEGORIES,
        "areas": areas,
        "search_links": links,
        "jobs": [{k: v for k, v in j.items() if k not in ("match_reason", "id", "last_seen")} for j in listings],
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (out_dir / "jobs.json").write_text(blob)
    # Also as a script so the page works when opened straight from disk.
    (out_dir / "data.js").write_text("window.JOBS_DATA=" + blob.replace("</", "<\\/") + ";\n")
