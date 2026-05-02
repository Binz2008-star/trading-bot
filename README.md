# Trading Bot - Personal Safe Setup

Personal-use trading bot dashboard based on the Roben Trading AI Bot project.

## Safety defaults

- No `.env` file is committed.
- All exchanges are disabled in `config.json` by default.
- Auto trading and sniper mode are disabled by default.
- The Flask app binds to `127.0.0.1` by default.
- Random trading signals are disabled.
- Fake exchange balances/prices are disabled.

## Setup

```bash
python -m venv .venv
.venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
pip install --upgrade pip
copy .env.example .env
python roben_enhanced_trading_system.py
```

Open:

```text
http://127.0.0.1:8082
```

## Before using real funds

1. Use exchange testnet/demo mode first.
2. Add your API keys only in local `.env`.
3. Enable only one exchange at a time in `config.json`.
4. Keep auto trading off until the strategy is tested.
5. Start with very small order sizes.

## Important

This is not financial advice. Use at your own risk.
