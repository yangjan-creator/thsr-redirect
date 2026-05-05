# thsr-redirect

Vercel serverless lazy redirect for THSR booking deeplinks.

LINE FLEX button click → this endpoint → fetch TDX MaaS deeplink → 302 to prefilled IRS booking page.

## Endpoint

```
GET https://<your-vercel-domain>/r/thsr?train_no=0833&date=20260530&from_zh=台北&to_zh=左營
  → 302 → https://maas.transportdata.tw/...?token=...
        → 302 → https://irs.thsrc.com.tw/IMINT/?queryData=... (prefilled)
```

Any TDX failure → 302 to `https://irs.thsrc.com.tw/IMINT/?locale=tw` (manual fill).

## Setup

1. Push this repo to GitHub.
2. Import to Vercel (https://vercel.com/new).
3. Set Environment Variables (Project Settings → Environment Variables):
   - `TDX_CLIENT_ID`   = TDX MaaS client_id
   - `TDX_CLIENT_SECRET` = TDX MaaS client_secret
4. Deploy. Vercel auto-detects Python serverless from `api/`.

## Update taclaw side

Set `THSR_REDIRECT_BASE` env on vps4 to Vercel domain:

```bash
THSR_REDIRECT_BASE=https://<project>.vercel.app/r/thsr
```

Without this var, taclaw uses `https://staging.zumii.ai/r/thsr` (self-hosted fallback).

## Why Vercel

- TDX MaaS rate limit = 5 calls/min/client_id. Lazy fetch on click 攤到用戶點按時刻, 自然分散.
- Vercel free tier 100K req/月 夠用 (高鐵幾百次/月).
- Auto HTTPS + global edge.
- Independent from taclaw deploy cycle.

## Local test

```bash
pip install -r requirements.txt
TDX_CLIENT_ID=... TDX_CLIENT_SECRET=... python3 -c "
from api.r.thsr import _fetch_deeplink_or_irs
print(_fetch_deeplink_or_irs(train_no='0833', date='20260530', from_zh='台北', to_zh='左營'))
"
# Expected: https://maas.transportdata.tw/...?token=... (or IRS fallback if TDX fails)
```

Origin: 2026-05-05 老爹 14:30 拍 — 從 taclaw vps4 搬到 Vercel.
