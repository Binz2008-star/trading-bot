#!/usr/bin/env python3
"""Professional personal trading bot app.

Features:
- Flask dashboard + JSON API
- Binance Spot/Testnet support
- Dry-run mode by default
- Deterministic EMA/RSI strategy, no random signals
- Risk controls before every trade
- Token protection for unsafe endpoints
- SQLite audit log
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()


# -----------------------------
# Logging
# -----------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("pro_trading_bot")
logger.setLevel(LOG_LEVEL)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
file_handler = RotatingFileHandler("trading_bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
file_handler.setFormatter(formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


# -----------------------------
# Settings
# -----------------------------
@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8082"))
    app_token: str = os.getenv("APP_TOKEN", "change-me-local-token")
    exchange: str = os.getenv("EXCHANGE", "binance").lower()
    binance_api_key: str = os.getenv("BINANCE_API_KEY", "")
    binance_api_secret: str = os.getenv("BINANCE_API_SECRET", os.getenv("BINANCE_SECRET_KEY", ""))
    binance_testnet: bool = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    live_trading_enabled: bool = os.getenv("ENABLE_LIVE_TRADING", "false").lower() == "true"
    default_symbols: Tuple[str, ...] = tuple(s.strip().upper() for s in os.getenv("DEFAULT_SYMBOLS", "BTCUSDT,ETHUSDT").split(",") if s.strip())
    quote_asset: str = os.getenv("QUOTE_ASSET", "USDT").upper()
    max_trade_usdt: Decimal = Decimal(os.getenv("MAX_TRADE_USDT", "25"))
    max_daily_trades: int = int(os.getenv("MAX_DAILY_TRADES", "5"))
    max_daily_loss_usdt: Decimal = Decimal(os.getenv("MAX_DAILY_LOSS_USDT", "25"))
    auto_interval_seconds: int = int(os.getenv("AUTO_INTERVAL_SECONDS", "60"))
    db_path: str = os.getenv("DB_PATH", "trading_bot.sqlite3")


settings = Settings()


# -----------------------------
# Database / audit log
# -----------------------------
class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    price TEXT NOT NULL,
                    status TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    order_id TEXT,
                    dry_run INTEGER NOT NULL,
                    reason TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )

    def log_event(self, level: str, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events (created_at, level, message) VALUES (?, ?, ?)",
                (utc_now(), level, message),
            )

    def log_trade(self, trade: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO trades
                (created_at, exchange, symbol, side, quantity, price, status, strategy, order_id, dry_run, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    trade.get("exchange", "unknown"),
                    trade["symbol"],
                    trade["side"],
                    str(trade["quantity"]),
                    str(trade.get("price", "0")),
                    trade.get("status", "unknown"),
                    trade.get("strategy", "manual"),
                    str(trade.get("order_id", "")),
                    1 if trade.get("dry_run", True) else 0,
                    trade.get("reason", ""),
                ),
            )

    def todays_trade_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM trades WHERE date(created_at) = date('now')"
            ).fetchone()
            return int(row["n"] or 0)

    def recent_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]


# -----------------------------
# Exchange clients
# -----------------------------
class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool) -> None:
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-MBX-APIKEY": api_key})

    def _public(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        response = self.session.get(f"{self.base_url}{path}", params=params or {}, timeout=15)
        response.raise_for_status()
        return response.json()

    def _signed(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("Binance API keys are missing")
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        query = urlencode(payload, doseq=True)
        signature = hmac.new(self.api_secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
        payload["signature"] = signature
        response = self.session.request(method, f"{self.base_url}{path}", params=payload, timeout=15)
        response.raise_for_status()
        return response.json()

    def price(self, symbol: str) -> Decimal:
        data = self._public("/api/v3/ticker/price", {"symbol": symbol})
        return Decimal(str(data["price"]))

    def candles(self, symbol: str, interval: str = "15m", limit: int = 120) -> List[Dict[str, Decimal]]:
        data = self._public("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        candles: List[Dict[str, Decimal]] = []
        for k in data:
            candles.append({
                "open": Decimal(str(k[1])),
                "high": Decimal(str(k[2])),
                "low": Decimal(str(k[3])),
                "close": Decimal(str(k[4])),
                "volume": Decimal(str(k[5])),
            })
        return candles

    def account(self) -> Dict[str, Any]:
        return self._signed("GET", "/api/v3/account")

    def balances(self) -> Dict[str, Dict[str, str]]:
        account = self.account()
        result: Dict[str, Dict[str, str]] = {}
        for item in account.get("balances", []):
            free = Decimal(item["free"])
            locked = Decimal(item["locked"])
            if free or locked:
                result[item["asset"]] = {"free": str(free), "locked": str(locked), "total": str(free + locked)}
        return result

    def market_order(self, symbol: str, side: str, quantity: Decimal) -> Dict[str, Any]:
        return self._signed("POST", "/api/v3/order", {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": format_quantity(quantity),
        })


# -----------------------------
# Strategy / risk
# -----------------------------
def ema(values: List[Decimal], period: int) -> Decimal:
    if len(values) < period:
        return values[-1]
    multiplier = Decimal("2") / Decimal(period + 1)
    current = sum(values[:period]) / Decimal(period)
    for price in values[period:]:
        current = (price - current) * multiplier + current
    return current


def rsi(values: List[Decimal], period: int = 14) -> Decimal:
    if len(values) <= period:
        return Decimal("50")
    gains: List[Decimal] = []
    losses: List[Decimal] = []
    for prev, curr in zip(values[-period - 1:-1], values[-period:]):
        delta = curr - prev
        gains.append(max(delta, Decimal("0")))
        losses.append(abs(min(delta, Decimal("0"))))
    avg_gain = sum(gains) / Decimal(period)
    avg_loss = sum(losses) / Decimal(period)
    if avg_loss == 0:
        return Decimal("100")
    rs = avg_gain / avg_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))


class Strategy:
    """Conservative trend-following strategy.

    BUY only when short EMA > long EMA and RSI is not overbought.
    SELL when trend weakens or RSI is overbought.
    HOLD otherwise.
    """

    def analyze(self, candles: List[Dict[str, Decimal]]) -> Dict[str, Any]:
        closes = [c["close"] for c in candles]
        if len(closes) < 60:
            return {"signal": "HOLD", "confidence": 0, "reason": "not enough candles"}
        fast = ema(closes, 12)
        slow = ema(closes, 26)
        trend = ema(closes, 50)
        current_rsi = rsi(closes, 14)
        last_price = closes[-1]

        if fast > slow and last_price > trend and Decimal("45") <= current_rsi <= Decimal("68"):
            confidence = min(95, int(55 + (fast - slow) / last_price * Decimal("10000")))
            return {"signal": "BUY", "confidence": confidence, "reason": f"EMA trend up, RSI={current_rsi:.2f}"}
        if fast < slow or current_rsi >= Decimal("72"):
            confidence = 65 if fast < slow else 55
            return {"signal": "SELL", "confidence": confidence, "reason": f"trend weak or RSI high, RSI={current_rsi:.2f}"}
        return {"signal": "HOLD", "confidence": 40, "reason": f"neutral, RSI={current_rsi:.2f}"}


class RiskManager:
    def __init__(self, db: Database, cfg: Settings) -> None:
        self.db = db
        self.cfg = cfg

    def validate(self, symbol: str, side: str, quote_amount: Decimal, confidence: int, auto: bool) -> Tuple[bool, str]:
        if side.upper() not in {"BUY", "SELL"}:
            return False, "side must be BUY or SELL"
        if quote_amount <= 0:
            return False, "quote amount must be positive"
        if quote_amount > self.cfg.max_trade_usdt:
            return False, f"quote amount exceeds MAX_TRADE_USDT={self.cfg.max_trade_usdt}"
        if self.db.todays_trade_count() >= self.cfg.max_daily_trades:
            return False, f"daily trade limit reached: {self.cfg.max_daily_trades}"
        if auto and confidence < 60:
            return False, "auto trade confidence below 60"
        if not symbol.endswith(self.cfg.quote_asset):
            return False, f"only {self.cfg.quote_asset} quote pairs are allowed"
        return True, "approved"


# -----------------------------
# Engine
# -----------------------------
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_quantity(value: Decimal) -> str:
    # Generic precision safe for common spot symbols. For production, use exchangeInfo filters per symbol.
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_DOWN).normalize())


class TradingEngine:
    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        self.db = Database(cfg.db_path)
        self.exchange = BinanceClient(cfg.binance_api_key, cfg.binance_api_secret, cfg.binance_testnet)
        self.strategy = Strategy()
        self.risk = RiskManager(self.db, cfg)
        self.auto_enabled = False
        self._auto_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @property
    def dry_run(self) -> bool:
        return not self.cfg.live_trading_enabled

    def status(self) -> Dict[str, Any]:
        return {
            "app": "pro_trading_app",
            "exchange": self.cfg.exchange,
            "binance_testnet": self.cfg.binance_testnet,
            "live_trading_enabled": self.cfg.live_trading_enabled,
            "dry_run": self.dry_run,
            "auto_enabled": self.auto_enabled,
            "symbols": list(self.cfg.default_symbols),
            "max_trade_usdt": str(self.cfg.max_trade_usdt),
            "max_daily_trades": self.cfg.max_daily_trades,
            "todays_trade_count": self.db.todays_trade_count(),
        }

    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        candles = self.exchange.candles(symbol)
        price = candles[-1]["close"]
        decision = self.strategy.analyze(candles)
        return {"symbol": symbol, "price": str(price), **decision}

    def execute_trade(self, symbol: str, side: str, quote_amount: Decimal, strategy: str = "manual", confidence: int = 100, auto: bool = False) -> Dict[str, Any]:
        symbol = symbol.upper().strip()
        side = side.upper().strip()
        ok, reason = self.risk.validate(symbol, side, quote_amount, confidence, auto)
        if not ok:
            return {"success": False, "status": "rejected", "reason": reason}

        price = self.exchange.price(symbol)
        quantity = quote_amount / price
        trade = {
            "exchange": "binance-testnet" if self.cfg.binance_testnet else "binance",
            "symbol": symbol,
            "side": side,
            "quantity": format_quantity(quantity),
            "price": str(price),
            "status": "DRY_RUN" if self.dry_run else "SUBMITTED",
            "strategy": strategy,
            "dry_run": self.dry_run,
            "reason": reason,
        }

        if self.dry_run:
            self.db.log_trade(trade)
            logger.info("Dry-run trade: %s", trade)
            return {"success": True, **trade}

        order = self.exchange.market_order(symbol, side, quantity)
        trade["order_id"] = str(order.get("orderId", ""))
        trade["status"] = order.get("status", "SUBMITTED")
        self.db.log_trade(trade)
        logger.info("Live/testnet order submitted: %s", trade)
        return {"success": True, "order": order, **trade}

    def auto_loop(self) -> None:
        logger.info("Auto loop started")
        while not self._stop.is_set():
            if self.auto_enabled:
                for symbol in self.cfg.default_symbols:
                    try:
                        analysis = self.analyze_symbol(symbol)
                        if analysis["signal"] in {"BUY", "SELL"}:
                            self.execute_trade(
                                symbol=symbol,
                                side=analysis["signal"],
                                quote_amount=min(self.cfg.max_trade_usdt, Decimal("10")),
                                strategy="ema_rsi_auto",
                                confidence=int(analysis["confidence"]),
                                auto=True,
                            )
                    except Exception as exc:
                        logger.exception("Auto trading error for %s: %s", symbol, exc)
                        self.db.log_event("ERROR", f"auto trading error for {symbol}: {exc}")
            self._stop.wait(self.cfg.auto_interval_seconds)

    def set_auto(self, enabled: bool) -> Dict[str, Any]:
        self.auto_enabled = enabled
        if enabled and (self._auto_thread is None or not self._auto_thread.is_alive()):
            self._stop.clear()
            self._auto_thread = threading.Thread(target=self.auto_loop, daemon=True)
            self._auto_thread.start()
        return {"auto_enabled": self.auto_enabled}


engine = TradingEngine(settings)
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "http://127.0.0.1:8082").split(",")}})


def require_token() -> Optional[Any]:
    token = request.headers.get("X-App-Token") or request.args.get("token")
    if token != settings.app_token:
        return jsonify({"success": False, "error": "missing or invalid X-App-Token"}), 401
    return None


@app.get("/")
def dashboard() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pro Trading Bot</title>
  <style>
    body{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}
    .card{background:#111827;border:1px solid #334155;border-radius:14px;padding:18px;margin:12px 0;max-width:960px}
    button,input{padding:10px;border-radius:8px;border:1px solid #475569;margin:4px}
    button{cursor:pointer;background:#2563eb;color:white}
    pre{white-space:pre-wrap;background:#020617;padding:12px;border-radius:10px}
  </style>
</head>
<body>
  <h1>Pro Trading Bot</h1>
  <div class="card">
    <h3>Status</h3>
    <button onclick="loadStatus()">Refresh</button>
    <pre id="status"></pre>
  </div>
  <div class="card">
    <h3>Analyze</h3>
    <input id="symbol" value="BTCUSDT">
    <button onclick="analyze()">Analyze</button>
    <pre id="analysis"></pre>
  </div>
  <div class="card">
    <h3>Manual Dry-Run / Testnet Trade</h3>
    <input id="token" placeholder="APP_TOKEN">
    <input id="tradeSymbol" value="BTCUSDT">
    <input id="side" value="BUY">
    <input id="amount" value="10">
    <button onclick="trade()">Submit</button>
    <pre id="trade"></pre>
  </div>
<script>
async function j(url, opts={}){ const r=await fetch(url, opts); return await r.json(); }
async function loadStatus(){ status.textContent=JSON.stringify(await j('/api/status'), null, 2); }
async function analyze(){ analysis.textContent=JSON.stringify(await j('/api/analyze/'+symbol.value), null, 2); }
async function trade(){
  trade.textContent=JSON.stringify(await j('/api/trade', {method:'POST', headers:{'Content-Type':'application/json','X-App-Token':token.value}, body:JSON.stringify({symbol:tradeSymbol.value, side:side.value, quote_amount:amount.value})}), null, 2);
}
loadStatus();
</script>
</body>
</html>
"""


@app.get("/api/status")
def api_status() -> Any:
    return jsonify(engine.status())


@app.get("/api/analyze/<symbol>")
def api_analyze(symbol: str) -> Any:
    try:
        return jsonify(engine.analyze_symbol(symbol.upper()))
    except Exception as exc:
        logger.exception("Analyze failed")
        return jsonify({"success": False, "error": str(exc)}), 400


@app.get("/api/balance")
def api_balance() -> Any:
    auth_error = require_token()
    if auth_error:
        return auth_error
    try:
        return jsonify(engine.exchange.balances())
    except Exception as exc:
        logger.exception("Balance failed")
        return jsonify({"success": False, "error": str(exc)}), 400


@app.post("/api/trade")
def api_trade() -> Any:
    auth_error = require_token()
    if auth_error:
        return auth_error
    data = request.get_json(force=True)
    try:
        result = engine.execute_trade(
            symbol=str(data.get("symbol", "BTCUSDT")),
            side=str(data.get("side", "BUY")),
            quote_amount=Decimal(str(data.get("quote_amount", "10"))),
            strategy="manual_api",
        )
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as exc:
        logger.exception("Trade failed")
        return jsonify({"success": False, "error": str(exc)}), 400


@app.post("/api/auto")
def api_auto() -> Any:
    auth_error = require_token()
    if auth_error:
        return auth_error
    data = request.get_json(force=True)
    enabled = bool(data.get("enabled", False))
    return jsonify(engine.set_auto(enabled))


@app.get("/api/trades")
def api_trades() -> Any:
    return jsonify(engine.db.recent_trades())


if __name__ == "__main__":
    logger.info("Starting Pro Trading Bot on http://%s:%s", settings.host, settings.port)
    app.run(host=settings.host, port=settings.port, debug=False)
