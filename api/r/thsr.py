"""Vercel serverless: lazy THSR booking deeplink redirect.

Endpoint: GET /api/r/thsr?train_no=<NNNN>&date=<YYYYMMDD>&from_zh=<>&to_zh=<>

Flow:
1. Receive query params from LINE FLEX button click
2. OAuth2 client_credentials → TDX access_token
3. GET /api/maas-thsr/booking/deeplink/web/hsr → deeplink
4. 302 redirect to maas.transportdata.tw/...?token=... → IRS prefilled
5. Any failure → 302 redirect to IRS_BOOKING_URL static (fail-loud per
   CLAUDE.md invariant: log warn but user still gets booking flow)

Why
- Lazy fetch on user click (NOT prefetch in carousel render):
  TDX MaaS rate limit = 5 calls/min/client_id.
  Prefetch 8+ classes burst → throttle. Lazy 攤到用戶點按時刻, 自然分散.
- Vercel serverless = 0 maintenance, auto-HTTPS, free tier 100K req/月.
- Independent deploy cycle from taclaw (taclaw deploy 不影響 redirect).

Env vars (set in Vercel Dashboard → Project Settings → Environment Variables):
- TDX_CLIENT_ID    : TDX MaaS client_id
- TDX_CLIENT_SECRET: TDX MaaS client_secret

Origin: 2026-05-05 老爹 14:30 拍 — 從 taclaw vps4 搬到 Vercel.
"""

from __future__ import annotations

import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import httpx

# IRS first page fallback (no prefill, user manually fills)
IRS_BOOKING_URL = "https://irs.thsrc.com.tw/IMINT/?locale=tw"

TDX_TOKEN_URL = (
    "https://tdx.transportdata.tw/auth/realms/TDXConnect/"
    "protocol/openid-connect/token"
)
TDX_DEEPLINK_URL = (
    "https://tdx.transportdata.tw/api/maas-thsr/booking/deeplink/web/hsr"
)
HTTP_TIMEOUT = 5.0

TDX_STATION_NAMES = {
    # TDX MaaS deeplink endpoint expects these public-facing Chinese station
    # names. Keep the full 12-station allowlist here so button parameters from
    # taclaw, speech aliases, or future clients normalize at this boundary.
    "南港": "南港",
    "臺北": "台北",
    "台北": "台北",
    "板橋": "板橋",
    "桃園": "桃園",
    "新竹": "新竹",
    "苗栗": "苗栗",
    "臺中": "台中",
    "台中": "台中",
    "彰化": "彰化",
    "雲林": "雲林",
    "嘉義": "嘉義",
    "臺南": "台南",
    "台南": "台南",
    "左營": "左營",
    "新左營": "左營",
}


def _log(msg: str) -> None:
    print(f"[thsr-redirect] {msg}", file=sys.stderr, flush=True)


def _normalize_tdx_station_name(name: str) -> str:
    normalized = name.strip()
    return TDX_STATION_NAMES.get(normalized, normalized)


def _fetch_deeplink_or_irs(
    *,
    train_no: str,
    date: str,
    from_zh: str,
    to_zh: str,
) -> str:
    """Sync fetch TDX deeplink, return URL string. Falls back to IRS on any error."""
    client_id = os.environ.get("TDX_CLIENT_ID", "").strip()
    client_secret = os.environ.get("TDX_CLIENT_SECRET", "").strip()
    if not (client_id and client_secret):
        _log("tdx_credentials_missing")
        return IRS_BOOKING_URL

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            # Step 1: OAuth2 token
            r1 = client.post(
                TDX_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r1.raise_for_status()
            token = r1.json().get("access_token")
            if not token:
                _log("tdx_token_missing")
                return IRS_BOOKING_URL

            # Step 2: deeplink fetch
            train_no_padded = train_no.zfill(4)
            start_station = _normalize_tdx_station_name(from_zh)
            end_station = _normalize_tdx_station_name(to_zh)
            r2 = client.get(
                TDX_DEEPLINK_URL,
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "ticket_type": "S",
                    "carriage_type": "Y",
                    "adult_ticket": 1,
                    "children_ticket": 0,
                    "disabled_ticket": 0,
                    "senior_ticket": 0,
                    "student_ticket": 0,
                    "start_station": start_station,
                    "end_station": end_station,
                    "departure_date": date,
                    "departure_number": train_no_padded,
                },
            )
            r2.raise_for_status()
            body = r2.json()
            if body.get("result") != "success":
                _log(f"tdx_non_success train={train_no_padded} body={str(body)[:200]}")
                return IRS_BOOKING_URL
            deeplink = (body.get("data") or {}).get("deeplink") or ""
            if not deeplink:
                _log(f"tdx_empty_deeplink train={train_no_padded}")
                return IRS_BOOKING_URL
            return deeplink
    except (httpx.TimeoutException, httpx.HTTPStatusError,
            httpx.RequestError, ValueError) as exc:
        _log(f"tdx_fetch_error train={train_no} err={str(exc)[:200]}")
        return IRS_BOOKING_URL


class handler(BaseHTTPRequestHandler):
    """Vercel Python serverless entry. Class name MUST be `handler`."""

    def do_GET(self) -> None:  # noqa: N802 — required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        train_no = (qs.get("train_no") or [""])[0].strip()
        date = (qs.get("date") or [""])[0].strip()
        from_zh = (qs.get("from_zh") or [""])[0].strip()
        to_zh = (qs.get("to_zh") or [""])[0].strip()

        if not (train_no and date and from_zh and to_zh):
            _log(f"invalid_params train_no={train_no!r} date={date!r}")
            target = IRS_BOOKING_URL
        else:
            target = _fetch_deeplink_or_irs(
                train_no=train_no, date=date, from_zh=from_zh, to_zh=to_zh,
            )

        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
