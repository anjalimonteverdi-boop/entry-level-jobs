# Entry-Level Job Agent

Runs once a day, collects entry-level job postings for recent college grads
from public job-board APIs, and builds a simple static website you can publish.

Starts with the **SF Bay Area + remote US**. Adding regions is a config change
(see "Adding a region").

## What one run does

1. **Fetch** postings from every source in `config/sources.yaml`.
2. **Location filter**: keeps Bay Area postings (SF, East Bay, Peninsula,
   South Bay / San Jose, North Bay incl. Napa/Sonoma) and remote roles open
   in the US. Rules are in `config/regions.yaml`.
3. **Entry-level filter** (`config/rules.yaml`):
   - keeps titles like entry level, associate, coordinator, assistant, junior,
     new grad, early career, rotational; roles asking for 0–2 years; roles
     that only ask for a bachelor's degree; federal jobs at GS-7 or below
   - drops senior / lead / manager / director titles, roles asking for 3+
     years, unpaid internships, commission-only roles, MLM / "brand ambassador"
   - **flags** (doesn't drop) postings that don't say how much experience is
     needed: they show an "Experience not stated" tag
4. **Dedupe**: same company + title + location shows once.
5. **New / closed / old**: a listing is "New today" the first day it appears.
   Listings that disappear from their source are treated as closed and
   removed. Anything posted more than 30 days ago is removed. If a source
   fails, its listings from the last 3 days are kept so one bad day doesn't
   wipe them.
6. **Log** per-source counts to `logs/source_counts.csv` and a readable summary
   to `logs/last_run.txt`, including a "CHECK THESE SOURCES" list for
   sources that errored, returned 0, or dropped sharply.
7. **Build the website** into `site/`.

Each listing shows title, company, location (or Remote), salary if listed,
date posted, a 1–2 sentence summary, a category tag, and an Apply link.

## Setup (one time)

You need Python 3.10 or newer.

```bash
cd job-agent
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then open `config/settings.yaml` and set `contact:` to your email. It's sent
with each request so job sites know who runs the bot.

### Optional: federal jobs (USAJobs)

USAJobs needs a free API key. Without it, the USAJobs source is skipped and
everything else still runs.

1. Request a key at https://developer.usajobs.gov/apirequest/ (free, emailed to you).
2. Create a file named `.env` in the `job-agent` folder:
   ```
   USAJOBS_API_KEY=your-key-here
   USAJOBS_EMAIL=the-email-you-registered-with
   ```
   (For a one-off manual run you can instead `export` those two variables.)

## Run it

```bash
source .venv/bin/activate
set -a; . ./.env; set +a     # only if you made a .env file
python -m jobagent.run
```

Then open `site/index.html` in a browser. It works straight from disk.

Useful options:

- `python -m jobagent.run --only stripe` runs just one source (handy for testing a new one)
- `python -m unittest discover tests` runs the offline tests

## Scheduling the daily run

Pick whichever matches where you'll run it.

**On a Mac or Linux computer (cron).** The computer has to be on at the scheduled time.

```bash
crontab -e
```

Add this line (runs at 6:30am every day; change the path to where the folder lives):

```
30 6 * * * /full/path/to/job-agent/scheduling/run_daily.sh
```

Output goes to `logs/cron.log`. On macOS, the first time you may need to
allow cron "Full Disk Access" in System Settings > Privacy & Security.

**On Windows (Task Scheduler).** Create a Basic Task that runs daily with:
Program `C:\path\to\job-agent\.venv\Scripts\python.exe`, arguments
`-m jobagent.run`, "Start in" `C:\path\to\job-agent`.

**In the cloud with GitHub Actions (chosen).** `.github/workflows/daily.yml`
runs the agent every morning, saves run history to `data/` and `logs/`, and
publishes `site/` to GitHub Pages. See "Hosting the website".

## Hosting the website (GitHub Pages)

1. Create a new **public** repository on GitHub (Pages is free for public repos)
   and push this folder to it.
2. In the repo: Settings > Pages > Build and deployment > Source: **GitHub Actions**.
3. Optional: Settings > Secrets and variables > Actions, add `USAJOBS_API_KEY`
   and `USAJOBS_EMAIL`.
4. Actions tab > "Daily job update" > **Run workflow** for the first run.
   After that it runs daily at 7am Pacific.

The site will be at `https://<your-username>.github.io/<repo-name>/`.
Per-source counts for each run are in `logs/last_run.txt` in the repo, and
in the Actions run log.

## Adding or removing sources

Edit `config/sources.yaml`. Each line is one company board:

```yaml
- {type: greenhouse, board: acme, name: Acme}
```

To find a company's board: open one of their job postings. If the link looks like
`boards.greenhouse.io/acme/...`, `job-boards.greenhouse.io/acme/...`,
`jobs.lever.co/acme/...` or `jobs.ashbyhq.com/acme/...`, the type is
greenhouse / lever / ashby and the board is `acme`. Add `sector: nonprofit`
or `sector: government` to tag everything from that source that way.

Pause a source with `enabled: false`. Run `python -m jobagent.run --only acme`
to check it works. After each daily run, look at `logs/last_run.txt`: a
source that shows `error` or `0` fetched probably changed its board name.

RSS feeds are supported too (`type: rss`), for government or university
boards that publish one. See the commented example in `sources.yaml`.

Sites that forbid automated collection (LinkedIn, Indeed, Handshake...) are
never fetched; they're listed under `search_links` and shown on the website
as "More places to search".

## Adding a region

In `config/regions.yaml`, add a region with its areas and city names (there's
a commented Los Angeles example), then add its key to `active_regions`:

```yaml
active_regions: [sf_bay_area, los_angeles]
```

Also add companies that hire there to `sources.yaml`. The USAJobs source
automatically searches each active region's `usajobs_locations`.

## Tuning the filters

Everything is in `config/rules.yaml`: the include/exclude title words,
the maximum years of experience (2), whether to keep paid internships
(`internships: paid_only`), whether to keep "experience not stated" roles
(`include_vague: true`), and the words that decide each category tag.

## Respecting site rules

- Only official public job-board APIs and feeds are used (Greenhouse, Lever
  and Ashby job-board APIs, USAJobs API). These exist so job listings can be
  shown on other sites.
- Every request checks the site's robots.txt and follows its crawl delay, with
  at least 1 second between requests to the same site.
- Requests identify the bot and your contact email.

## Summaries and categories

Both are rule-based and free. The summary is the first sentence or two of the
"about the role" part of the posting. If you later want better summaries, an
LLM (e.g. Claude via the Anthropic API) could rewrite them for a small per-run
cost; that isn't built in.

## Files

```
config/        sources, regions, filter rules, settings  <- the parts you edit
jobagent/      the code
site_template/ website HTML/CSS/JS (copied into site/ on each run)
site/          generated website (publish this folder)
data/state.json  what was seen on earlier runs (for "new" and expiry)
logs/          per-source counts and run summaries
scheduling/    cron script for running on your own computer
.github/       daily GitHub Actions schedule + Pages deploy
tests/         offline tests with sample data
```
