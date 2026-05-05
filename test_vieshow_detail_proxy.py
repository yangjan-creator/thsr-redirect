import json

import httpx
import pytest

from api.movie import vieshow_detail


def test_build_vieshow_detail_url_is_closed_to_official_host():
    assert vieshow_detail.build_vieshow_detail_url("1") == (
        "https://www.vscinemas.com.tw/theater/detail.aspx?id=1"
    )


def test_fetch_vieshow_detail_rejects_invalid_cinema_before_http():
    with pytest.raises(ValueError, match="invalid_cinema"):
        vieshow_detail.fetch_vieshow_detail_html("999")


def test_fetch_vieshow_detail_uses_closed_url_and_ignores_foreign_params(monkeypatch):
    calls = []

    class FakeResponse:
        text = "<html>txtSessionId=SID1</html>"

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            calls.append(("init", kwargs))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers):
            calls.append(("get", url, headers))
            return FakeResponse()

    monkeypatch.setattr(vieshow_detail.httpx, "Client", FakeClient)

    assert vieshow_detail.fetch_vieshow_detail_html("1") == "<html>txtSessionId=SID1</html>"
    assert calls[1][1] == "https://www.vscinemas.com.tw/theater/detail.aspx?id=1"
    assert "Mozilla/5.0" in calls[1][2]["User-Agent"]


def test_fetch_vieshow_detail_surfaces_upstream_status(monkeypatch):
    class FakeResponse:
        text = ""

        def raise_for_status(self):
            request = httpx.Request("GET", "https://www.vscinemas.com.tw/theater/detail.aspx?id=1")
            response = httpx.Response(403, request=request)
            raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers):
            return FakeResponse()

    monkeypatch.setattr(vieshow_detail.httpx, "Client", FakeClient)

    with pytest.raises(httpx.HTTPStatusError):
        vieshow_detail.fetch_vieshow_detail_html("1")


def test_vercel_rewrites_preserve_thsr_and_add_vieshow():
    with open("vercel.json", encoding="utf-8") as fh:
        data = json.load(fh)

    rewrites = {(item["source"], item["destination"]) for item in data["rewrites"]}
    assert ("/r/thsr", "/api/r/thsr") in rewrites
    assert ("/movie/vieshow_detail", "/api/movie/vieshow_detail") in rewrites
