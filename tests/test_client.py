import httpx
import pytest

from syosetsu.client import Client, FetchError, NotFound


def make_client(handler, clock, **kw):
    return Client(transport=httpx.MockTransport(handler), sleep=clock.sleep, clock=clock.clock, **kw)


def test_paces_requests(fake_clock):
    c = make_client(lambda req: httpx.Response(200, text="ok"), fake_clock)
    assert c.get_text("https://x.test/a") == "ok"
    assert c.get_text("https://x.test/b") == "ok"
    assert fake_clock.sleeps == [1.5]          # first request immediate, second waits


def test_no_wait_when_enough_time_passed(fake_clock):
    c = make_client(lambda req: httpx.Response(200, text="ok"), fake_clock)
    c.get_text("https://x.test/a")
    fake_clock.now += 10
    c.get_text("https://x.test/b")
    assert fake_clock.sleeps == []


def test_retries_503_then_succeeds(fake_clock):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, text="ok")

    c = make_client(handler, fake_clock)
    assert c.get_text("https://x.test/a") == "ok"
    assert len(calls) == 3


def test_honours_retry_after(fake_clock):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "7"}) if len(calls) == 1 else httpx.Response(200, text="ok")

    c = make_client(handler, fake_clock)
    c.get_text("https://x.test/a")
    assert 7 in fake_clock.sleeps


def test_gives_up_after_max_tries(fake_clock):
    c = make_client(lambda req: httpx.Response(500), fake_clock, max_tries=3)
    with pytest.raises(FetchError, match="after 3 tries"):
        c.get_text("https://x.test/a")


def test_404_raises_not_found_without_retry(fake_clock):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(404)

    c = make_client(handler, fake_clock)
    with pytest.raises(NotFound):
        c.get_text("https://x.test/a")
    assert len(calls) == 1


def test_transport_error_is_retried(fake_clock):
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("slow")
        return httpx.Response(200, text="ok")

    c = make_client(handler, fake_clock)
    assert c.get_text("https://x.test/a") == "ok"


def test_sends_user_agent(fake_clock):
    seen = {}

    def handler(req):
        seen["ua"] = req.headers["user-agent"]
        return httpx.Response(200, text="ok")

    make_client(handler, fake_clock).get_text("https://x.test/a")
    assert seen["ua"].startswith("syosetsu/")


def test_honours_retry_after_http_date(fake_clock):
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime
    when = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=120), usegmt=True)
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503, headers={"Retry-After": when}) if len(calls) == 1 else httpx.Response(200, text="ok")

    make_client(handler, fake_clock).get_text("https://x.test/a")
    assert any(100 <= s <= 121 for s in fake_clock.sleeps), fake_clock.sleeps


def test_retries_are_logged(fake_clock):
    calls, logged = [], []

    def handler(req):
        calls.append(1)
        return httpx.Response(429) if len(calls) == 1 else httpx.Response(200, text="ok")

    make_client(handler, fake_clock, log=logged.append).get_text("https://x.test/a")
    assert len(logged) == 1 and "HTTP 429" in logged[0] and "retry 1/5" in logged[0]
