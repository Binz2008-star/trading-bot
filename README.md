# Trading Bot - Personal Flask App

Personal-use trading bot **web app** based on the Roben Trading AI Bot project.

This repository is not a frontend/backend multi-folder app. The dashboard UI is embedded inside:

```text
roben_enhanced_trading_system.py
```

The app starts a local Flask server and opens through the browser.

## App structure

```text
roben_enhanced_trading_system.py   # Main Flask app + API routes + embedded dashboard UI
config.json                        # Trading and risk settings
requirements.txt                   # Python dependencies
.env.example                       # Local environment template
INSTALLATION_FIX_GUIDE.md          # Install notes
API_KEYS_INTEGRATION_GUIDE.pdf     # API key guide
```

## Safety defaults

- No `.env` file is committed.
- Keep real API keys only in your local `.env`.
- Use testnet/demo mode first.
- Keep auto trading off until tested.
- Start with very small order sizes only.

## Setup on Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python roben_enhanced_trading_system.py
```

Then open:

```text
http://127.0.0.1:8082
```

If the app says it is running on `0.0.0.0`, still open it locally with:

```text
http://localhost:8082
```

## Main API routes

```text
/                    Dashboard UI
/api/health          Health check
/api/config          Current config
/api/balance         Account balance
/api/price/<symbol>  Symbol price
/api/trade           Manual trade endpoint
/api/auto-mode       Toggle auto mode
/api/sniper-mode     Toggle sniper mode
/api/stats           Dashboard stats
```

## TA-Lib note

If `TA-Lib` fails to install on Windows, temporarily remove `TA-Lib` from `requirements.txt`, install the rest, and run again. The app has fallback behavior when TA-Lib is unavailable.

## Important

This is for personal testing and learning only. It is not financial advice. Use at your own risk.
