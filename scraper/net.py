"""A polite HTTP client: one request at a time, a pause between requests,
retries on temporary errors, and it obeys each site's robots.txt."""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; CompareCyprusBot/1.0; "
    "+https://github.com/compare-cyprus) price comparison, once a day"
)


class Blocked(Exception):
    """The site's robots.txt does not allow this URL."""


class Http:
    def __init__(self, delay: float = 1.0, timeout: float = 30, retries: int = 3, obey_robots: bool = True):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en,tr;q=0.8,el;q=0.6"})
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.obey_robots = obey_robots
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last = 0.0
        self.count = 0

    def _allowed(self, url: str) -> bool:
        if not self.obey_robots:
            return True
        p = urlsplit(url)
        root = f"{p.scheme}://{p.netloc}"
        if root not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.s.get(root + "/robots.txt", timeout=self.timeout)
                if r.status_code >= 400:
                    rp = None  # no robots.txt -> everything allowed
                else:
                    rp.parse(r.text.splitlines())
            except requests.RequestException:
                rp = None
            self._robots[root] = rp
        rp = self._robots[root]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, **kw) -> requests.Response:
        if not self._allowed(url):
            raise Blocked(f"robots.txt disallows {url}")
        last_err = None
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                self._last = time.monotonic()
                self.count += 1
                r = self.s.get(url, timeout=self.timeout, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                last_err = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status and status < 500 and status != 429:
                    break  # 403/404 won't fix themselves
                log.warning("  %s failed (%s), attempt %d/%d", url, e, attempt, self.retries)
                time.sleep(2 ** attempt)
        raise last_err

    def json(self, url: str, **kw):
        return self.get(url, headers={"Accept": "application/json"}, **kw).json()

    def text(self, url: str, **kw) -> str:
        r = self.get(url, **kw)
        r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else r.apparent_encoding
        return r.text
