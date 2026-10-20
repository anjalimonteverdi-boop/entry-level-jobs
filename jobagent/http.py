"""Polite HTTP helpers: identifying User-Agent, retries, robots.txt, per-host delay."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

DEFAULT_UA = "EntryLevelJobsBot/1.0 (daily job digest; contact: {contact})"
MIN_DELAY_SECONDS = 1.0


class Fetcher:
    def __init__(self, contact="not-set", respect_robots=True, timeout=30):
        self.user_agent = DEFAULT_UA.format(contact=contact)
        self.respect_robots = respect_robots
        self.timeout = timeout
        self._robots = {}
        self._last_hit = {}

    def _host(self, url):
        return urllib.parse.urlsplit(url).netloc

    def _robots_for(self, url):
        parts = urllib.parse.urlsplit(url)
        host = parts.netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{parts.scheme}://{host}/robots.txt"
            try:
                body = self._raw_get(robots_url, {})
                rp.parse(body.decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError:
                # No robots.txt (404) or an API that answers 401/403 for
                # unknown paths: no crawling policy is published, so allow.
                rp = None
            except Exception:
                rp = None
            self._robots[host] = rp
        return self._robots[host]

    def allowed(self, url):
        if not self.respect_robots:
            return True
        rp = self._robots_for(url)
        return rp is None or rp.can_fetch(self.user_agent, url)

    def _wait_turn(self, url):
        host = self._host(url)
        rp = self._robots.get(host)
        delay = MIN_DELAY_SECONDS
        if rp is not None:
            delay = max(delay, rp.crawl_delay(self.user_agent) or 0)
        last = self._last_hit.get(host)
        if last is not None:
            remaining = delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_hit[host] = time.monotonic()

    def _raw_get(self, url, headers):
        hdrs = {"User-Agent": self.user_agent, "Accept": "application/json, */*"}
        hdrs.update(headers)
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read()

    def get(self, url, headers=None, retries=2):
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        last_err = None
        for attempt in range(retries + 1):
            self._wait_turn(url)
            try:
                return self._raw_get(url, headers or {})
            except urllib.error.HTTPError as e:
                # 4xx other than rate limiting won't fix itself.
                if e.code < 500 and e.code != 429:
                    raise
                last_err = e
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
            time.sleep(2 * (attempt + 1))
        raise last_err

    def get_json(self, url, headers=None):
        return json.loads(self.get(url, headers))
