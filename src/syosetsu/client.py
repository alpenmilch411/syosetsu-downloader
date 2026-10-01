"""The only module that talks to the network: sequential, paced, retrying."""
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

USER_AGENT = "syosetsu/0.1 (+https://github.com/alpenmilch411/syosetsu-downloader; sequential, polite pacing)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(Exception):
    pass


class NotFound(FetchError):
    pass


class Client:
    def __init__(self, min_interval=1.5, max_tries=5, transport=None, sleep=time.sleep, clock=time.monotonic, log=None):
        self.min_interval = min_interval
        self.max_tries = max_tries
        self._sleep = sleep
        self._clock = clock
        self._log = log or (lambda msg: None)
        self._last: float | None = None
        self._http = httpx.Client(transport=transport, headers={"User-Agent": USER_AGENT},
                                  timeout=30, follow_redirects=True)

    def get_text(self, url: str, params: dict | None = None) -> str:
        err: Exception | None = None
        for attempt in range(1, self.max_tries + 1):
            self._pace()
            delay = self._backoff(attempt)
            try:
                r = self._http.get(url, params=params)
            except httpx.TransportError as e:
                err = e
            else:
                if r.status_code == 404:
                    raise NotFound(url)
                if r.status_code in RETRY_STATUS:
                    err = FetchError(f"HTTP {r.status_code}")
                    delay = _retry_after(r) or delay
                elif r.is_error:
                    raise FetchError(f"HTTP {r.status_code} for {url}")
                else:
                    return r.text
            if attempt < self.max_tries:
                self._log(f"retry {attempt}/{self.max_tries} after {err} ({url}), waiting {delay:.0f}s")
                self._sleep(delay)
        raise FetchError(f"giving up on {url} after {self.max_tries} tries: {err}")

    def _pace(self) -> None:
        if self._last is not None:
            wait = self.min_interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    @staticmethod
    def _backoff(attempt: int) -> float:
        return float(min(60, 2 ** attempt))


def _retry_after(r: httpx.Response) -> float | None:
    value = r.headers.get("Retry-After", "").strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:  # HTTP-date form
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
