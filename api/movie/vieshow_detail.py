"""Vercel serverless: closed Vieshow theater-detail HTML fetch proxy.

Endpoint: GET /movie/vieshow_detail?cinema=<1..10>

The proxy exists because vps4 can receive 403 from Vieshow while the same
official theater-detail page is reachable from Vercel. Taclaw remains the
parser and LINE renderer; this endpoint only fetches official HTML.
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

VIESHOW_HOST = "www.vscinemas.com.tw"
HTTP_TIMEOUT = 8.0
ALLOWED_CINEMA_CODES = {str(i) for i in range(1, 11)}
IGNORED_FOREIGN_PARAMS = {"url", "host", "path", "redirect", "next"}


def _log(msg: str) -> None:
    print(f"[vieshow-detail-proxy] {msg}", file=sys.stderr, flush=True)


def build_vieshow_detail_url(cinema: str) -> str:
    return f"https://{VIESHOW_HOST}/theater/detail.aspx?{urlencode({'id': cinema})}"


def fetch_vieshow_detail_html(cinema: str) -> str:
    if cinema not in ALLOWED_CINEMA_CODES:
        raise ValueError("invalid_cinema")
    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        response = client.get(
            build_vieshow_detail_url(cinema),
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        response.raise_for_status()
        return response.text


class handler(BaseHTTPRequestHandler):
    """Vercel Python serverless entry. Class name MUST be `handler`."""

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        cinema = (qs.get("cinema") or [""])[0].strip()
        foreign = sorted(IGNORED_FOREIGN_PARAMS.intersection(qs))
        if foreign:
            _log(f"ignored_foreign_params={','.join(foreign)} cinema={cinema!r}")

        if cinema not in ALLOWED_CINEMA_CODES:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"invalid_cinema")
            return

        try:
            html = fetch_vieshow_detail_html(cinema)
        except (httpx.TimeoutException, httpx.HTTPStatusError,
                httpx.RequestError, ValueError) as exc:
            _log(f"upstream_error cinema={cinema!r} err={str(exc)[:200]}")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"vieshow_upstream_error")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=60, s-maxage=120")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
