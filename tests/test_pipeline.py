"""Offline tests. Run from the job-agent folder:  python -m unittest discover tests"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from jobagent import run
from jobagent.rules import EntryLevelRules, years_required
from jobagent.regions import LocationMatcher
import yaml

HERE = Path(__file__).parent
CONFIG = HERE.parent / "config"


def cfg(name):
    return yaml.safe_load(open(CONFIG / name))


class Rules(unittest.TestCase):
    def setUp(self):
        self.rules = EntryLevelRules(cfg("rules.yaml"))

    def keep(self, title, desc="", **kw):
        return self.rules.evaluate(dict(title=title, description=desc, **kw))[0]

    def test_years(self):
        self.assertEqual(years_required("3+ years of experience in sales"), 3)
        self.assertEqual(years_required("0-2 years of relevant experience"), 0)
        self.assertEqual(years_required("two (2) years of experience"), 2)
        self.assertIsNone(years_required("Founded 10 years ago, we build things"))

    def test_titles(self):
        self.assertTrue(self.keep("Marketing Coordinator"))
        self.assertTrue(self.keep("Associate Product Manager"))
        self.assertFalse(self.keep("Senior Marketing Manager"))
        self.assertFalse(self.keep("Engineering Manager"))
        self.assertFalse(self.keep("Data Analyst", "Requires 4+ years of experience"))

    def test_exclusions(self):
        self.assertFalse(self.keep("Brand Ambassador"))
        self.assertFalse(self.keep("Sales Associate", "This is a commission-only role."))
        self.assertFalse(self.keep("Marketing Intern", "Unpaid internship"))
        self.assertTrue(self.keep("Marketing Intern", "Paid", salary="$25/hr"))

    def test_vague_flag(self):
        keep, _, flags = self.rules.evaluate(dict(title="Office Assistant", description="Help run our office."))
        self.assertTrue(keep)
        self.assertEqual(flags, ["Experience not stated"])
        # Neutral title, no experience info: dropped under the default policy.
        self.assertFalse(self.keep("Software Engineer, Search Infrastructure", "Build search."))


class Locations(unittest.TestCase):
    def setUp(self):
        self.m = LocationMatcher(cfg("regions.yaml"))

    def area(self, loc, **kw):
        r = self.m.classify(dict(locations=[loc], title="x", **kw))
        return r and r["area"]

    def test_bay_area(self):
        self.assertEqual(self.area("San Francisco, CA"), "San Francisco")
        self.assertEqual(self.area("Oakland, California"), "East Bay")
        self.assertEqual(self.area("Napa, CA"), "North Bay")
        self.assertEqual(self.area("Dublin, CA"), "East Bay")
        self.assertIsNone(self.area("Dublin, Ireland"))
        self.assertIsNone(self.area("Newark, NJ"))
        self.assertIsNone(self.area("New York, NY"))

    def test_remote(self):
        self.assertEqual(self.area("Remote - US"), "Remote (US)")
        self.assertEqual(self.area("Remote"), "Remote (US)")
        self.assertIsNone(self.area("Remote - Canada"))
        self.assertIsNone(self.area("London", workplace="remote"))


class Pipeline(unittest.TestCase):
    def test_two_day_run(self):
        os.environ.setdefault("USAJOBS_API_KEY", "test")
        os.environ.setdefault("USAJOBS_EMAIL", "test@example.com")
        with tempfile.TemporaryDirectory() as t:
            args = ["--sources", str(HERE / "sources_test.yaml"), "--fixtures", str(HERE / "fixtures"),
                    "--data", f"{t}/data", "--logs", f"{t}/logs", "--out", f"{t}/site"]
            run.main(args + ["--now", "2026-10-07T17:00:00+00:00"])
            jobs = json.load(open(f"{t}/site/jobs.json"))["jobs"]
            titles = sorted(j["title"] for j in jobs)
            self.assertIn("Marketing Coordinator", titles)
            self.assertEqual(titles.count("Marketing Coordinator"), 1)  # deduped
            self.assertNotIn("Senior Software Engineer", titles)
            self.assertNotIn("Brand Ambassador", titles)
            self.assertNotIn("Junior Analyst", titles)  # older than 30 days
            self.assertNotIn("Supervisory Program Analyst", titles)
            mc = next(j for j in jobs if j["title"] == "Marketing Coordinator")
            self.assertEqual(mc["salary"], "$65K–$80K/yr")
            self.assertEqual(mc["category"], "Marketing")
            self.assertTrue(all(j["is_new"] for j in jobs))
            self.assertTrue((Path(t) / "site" / "index.html").exists())
            log = (Path(t) / "logs" / "last_run.txt").read_text()
            self.assertIn("Broken Board Co", log)
            self.assertIn("CHECK THESE SOURCES", log)

            # Next day: nothing changed, so nothing is new.
            run.main(args + ["--now", "2026-10-08T17:00:00+00:00"])
            jobs2 = json.load(open(f"{t}/site/jobs.json"))["jobs"]
            self.assertEqual(len(jobs2), len(jobs))
            self.assertFalse(any(j["is_new"] for j in jobs2))


if __name__ == "__main__":
    unittest.main()
