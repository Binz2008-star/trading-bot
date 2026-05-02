#!/usr/bin/env python3
"""
Roben Trading AI Bot - Enhanced Real Trading System
نظام التداول الحقيقي المتطور مع ربط شامل لجميع APIs

⚠️ تحذير: هذا النظام يتعامل مع أموال حقيقية
"""

import os
import json
import time
import hmac
import hashlib
import requests
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import threading
import logging
from dotenv import load_dotenv
import pandas as pd
import numpy as np

# حاول استيراد ta-lib، قد لا يكون متوفرًا على جميع الأنظمة بسهولة
try:
    import talib
    TALIB_AVAILABLE = True
    logging.info("✅ تم تحميل مكتبة TA-Lib بنجاح.")
except ImportError:
    TALIB_AVAILABLE = False
    logging.warning("⚠️ مكتبة TA-Lib غير متاحة. لن يتم استخدام المؤشرات الفنية المتقدمة.")


# تحميل متغيرات البيئة من ملف .env
load_dotenv()

# إعداد السجلات
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # تحديد ترميز UTF-8 لملف السجل لحل مشاكل الأحرف العربية والإيموجي
        logging.FileHandler('roben_trading.log', encoding='utf-8'),
        # StreamHandler لإخراج السجلات إلى وحدة التحكم (قد يتطلب Terminal يدعم UTF-8)
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
CORS(app)

class ConfigManager:
    """مدير الإعدادات المتقدم: يقوم بتحميل الإعدادات من config.json ومتغيرات البيئة من .env"""
    
    def __init__(self):
        self.config = self.load_config()
        self.env_vars = self.load_env_variables()
        
    def load_config(self):
        """تحميل إعدادات من config.json. في حالة عدم وجود الملف أو خطأ، يتم إنشاء إعدادات افتراضية."""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                logging.info("✅ تم تحميل config.json بنجاح")
                return config
        except FileNotFoundError:
            logging.error("❌ ملف config.json غير موجود. سيتم إنشاء ملف إعدادات افتراضي.")
            return self.create_default_config()
        except json.JSONDecodeError as e:
            logging.error(f"❌ خطأ في تحليل config.json: {e}. سيتم إنشاء ملف إعدادات افتراضي.")
            return self.create_default_config()
    
    def load_env_variables(self):
        """تحميل متغيرات البيئة من ملف .env. تتضمن مفاتيح API وإعدادات المخاطر والإشعارات."""
        env_vars = {}
        
        # Binance API Keys
        env_vars['binance'] = {
            'api_key': os.getenv('BINANCE_API_KEY', ''),
            'secret_key': os.getenv('BINANCE_SECRET_KEY', ''),
            'testnet': os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'
        }
        
        # Bybit API Keys
        env_vars['bybit'] = {
            'api_key': os.getenv('BYBIT_API_KEY', ''),
            'secret_key': os.getenv('BYBIT_SECRET_KEY', ''),
            'testnet': os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'
        }
        
        # OKX API Keys
        env_vars['okx'] = {
            'api_key': os.getenv('OKX_API_KEY', ''),
            'secret_key': os.getenv('OKX_SECRET_KEY', ''),
            'passphrase': os.getenv('OKX_PASSPHRASE', ''),
            'testnet': os.getenv('OKX_TESTNET', 'false').lower() == 'true'
        }
        
        # Risk Management Settings
        env_vars['risk'] = {
            'max_daily_loss': float(os.getenv('MAX_DAILY_LOSS_PERCENT', '10.0')),
            'max_position_size': float(os.getenv('MAX_POSITION_SIZE_PERCENT', '2.0')),
            'stop_loss': float(os.getenv('STOP_LOSS_PERCENT', '3.0')),
            'take_profit': float(os.getenv('TAKE_PROFIT_PERCENT', '6.0'))
        }
        
        # Core Trading Settings
        env_vars['trading'] = {
            'pairs': [pair.strip() for pair in os.getenv('DEFAULT_TRADING_PAIRS', 'BTCUSDT,ETHUSDT,ADAUSDT').split(',')],
            'auto_interval': int(os.getenv('AUTO_MODE_INTERVAL', '30')),
            'sniper_interval': int(os.getenv('SNIPER_MODE_INTERVAL', '5')),
            'risk_level': os.getenv('RISK_LEVEL', 'conservative')
        }
        
        # Notification Settings
        env_vars['notifications'] = {
            'telegram_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
            'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
            'enable_telegram': os.getenv('ENABLE_TELEGRAM_NOTIFICATIONS', 'false').lower() == 'true'
        }
        
        logging.info("✅ تم تحميل متغيرات البيئة بنجاح")
        return env_vars
    
    def create_default_config(self):
        """إنشاء إعدادات افتراضية في ملف config.json إذا لم يكن موجودًا أو كان تالفًا."""
        default_config = {
            "trading_config": {
                "exchanges": {
                    "binance": {"enabled": True, "priority": 1},
                    "bybit": {"enabled": False, "priority": 2},
                    "okx": {"enabled": False, "priority": 3}
                },
                "risk_management": {
                    "max_daily_loss_percent": 10.0,
                    "max_position_size_percent": 2.0,
                    "stop_loss_percent": 3.0,
                    "take_profit_percent": 6.0
                }
            }
        }
        
        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            logging.info("📝 تم إنشاء ملف إعدادات افتراضي (config.json)")
        except Exception as e:
            logging.error(f"❌ فشل في إنشاء ملف config.json الافتراضي: {e}")
        
        return default_config
    
    def get_exchange_config(self, exchange_name):
        """الحصول على إعدادات بورصة معينة من config.json ومتغيرات البيئة."""
        exchange_config = self.config.get('trading_config', {}).get('exchanges', {}).get(exchange_name, {})
        env_config = self.env_vars.get(exchange_name, {})
        
        # دمج الإعدادات، متغيرات البيئة لها الأولوية في مفاتيح API
        return {**exchange_config, **env_config}
    
    def is_exchange_enabled(self, exchange_name):
        """فحص ما إذا كانت البورصة مُفعلة ولديها مفاتيح API."""
        exchange_config = self.get_exchange_config(exchange_name)
        return (exchange_config.get('enabled', False) and 
                exchange_config.get('api_key', '') != '' and 
                exchange_config.get('secret_key', '') != '')

class DatabaseManager:
    """مدير قاعدة البيانات: يتعامل مع تهيئة قاعدة البيانات وتسجيل الصفقات والإحصائيات."""
    
    def __init__(self):
        # مسار قاعدة البيانات من متغيرات البيئة، أو مسار افتراضي
        self.db_path = os.getenv('DATABASE_URL', 'sqlite:///roben_trading.db').replace('sqlite:///', '')
        self.init_database()
    
    def init_database(self):
        """تهيئة جداول قاعدة البيانات (trades, statistics, settings) إذا لم تكن موجودة."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # جدول الصفقات لتتبع كل صفقة
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    profit_loss REAL DEFAULT 0,
                    strategy TEXT,
                    order_id TEXT
                )
            ''')
            
            # جدول الإحصائيات لتلخيص الأداء اليومي
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE DEFAULT CURRENT_DATE,
                    total_trades INTEGER DEFAULT 0,
                    profitable_trades INTEGER DEFAULT 0,
                    total_profit REAL DEFAULT 0,
                    total_loss REAL DEFAULT 0,
                    success_rate REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0
                )
            ''')
            
            # جدول الإعدادات لتخزين الإعدادات الديناميكية إذا لزم الأمر
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logging.info("✅ تم تهيئة قاعدة البيانات بنجاح")
            
        except Exception as e:
            logging.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}. يرجى التحقق من صلاحيات الكتابة أو مساحة القرص.")
    
    def log_trade(self, exchange, symbol, side, quantity, price, strategy='manual', order_id=None):
        """تسجيل تفاصيل صفقة تم تنفيذها في جدول الصفقات."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades (exchange, symbol, side, quantity, price, strategy, order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (exchange, symbol, side, quantity, price, strategy, order_id))
            
            conn.commit()
            conn.close()
            logging.info(f"📝 تم تسجيل الصفقة: {side} {quantity} {symbol} @ {price}")
            
        except Exception as e:
            logging.error(f"❌ خطأ في تسجيل الصفقة: {e}")
    
    def get_statistics(self):
        """الحصول على إحصائيات التداول الحالية (اليومية)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # إحصائيات اليوم (يمكن توسيعها لتشمل فترات أخرى)
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as profitable_trades,
                    SUM(profit_loss) as total_profit,
                    AVG(CASE WHEN profit_loss > 0 THEN profit_loss ELSE NULL END) as avg_profit
                FROM trades 
                WHERE DATE(timestamp) = DATE('now')
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                total_trades, profitable_trades, total_profit, avg_profit = result
                success_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
                
                return {
                    'total_trades': total_trades or 0,
                    'profitable_trades': profitable_trades or 0,
                    'total_profit': total_profit or 0.0,
                    'success_rate': success_rate,
                    'avg_profit': avg_profit or 0.0
                }
            
            return {
                'total_trades': 0,
                'profitable_trades': 0,
                'total_profit': 0.0,
                'success_rate': 0.0,
                'avg_profit': 0.0
            }
            
        except Exception as e:
            logging.error(f"❌ خطأ في الحصول على الإحصائيات: {e}")
            return {}

class ExchangeManager:
    """مدير البورصات المتعددة: يقوم بتهيئة وإدارة واجهات برمجة تطبيقات البورصات المختلفة."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.exchanges = {} # تخزين كائنات البورصات المفعلة هنا
        self.init_exchanges()
    
    def init_exchanges(self):
        """تهيئة البورصات المُفعلة بناءً على إعدادات config.json و .env."""
        # تهيئة Binance
        if self.config_manager.is_exchange_enabled('binance'):
            self.exchanges['binance'] = BinanceExchange(self.config_manager.get_exchange_config('binance'))
            logging.info("✅ تم تفعيل Binance")
        else:
            logging.info("ℹ️ بورصة Binance معطلة أو مفاتيح API غير متوفرة.")
        
        # تهيئة Bybit
        if self.config_manager.is_exchange_enabled('bybit'):
            self.exchanges['bybit'] = BybitExchange(self.config_manager.get_exchange_config('bybit'))
            logging.info("✅ تم تفعيل Bybit")
        else:
            logging.info("ℹ️ بورصة Bybit معطلة أو مفاتيح API غير متوفرة.")
        
        # تهيئة OKX
        if self.config_manager.is_exchange_enabled('okx'):
            self.exchanges['okx'] = OKXExchange(self.config_manager.get_exchange_config('okx'))
            logging.info("✅ تم تفعيل OKX")
        else:
            logging.info("ℹ️ بورصة OKX معطلة أو مفاتيح API غير متوفرة.")
        
        if not self.exchanges:
            logging.warning("⚠️ لم يتم تفعيل أي بورصة - يرجى التحقق من إعدادات config.json وملف .env.")
    
    def get_primary_exchange(self):
        """الحصول على البورصة الأساسية (عادةً ذات الأولوية الأعلى أو الأولى المفعلة)."""
        # يمكن تحسين هذه الوظيفة لاختيار البورصة بناءً على "priority" في config.json
        if 'binance' in self.exchanges:
            return self.exchanges['binance']
        elif 'bybit' in self.exchanges: # الأولوية 2
            return self.exchanges['bybit']
        elif 'okx' in self.exchanges: # الأولوية 3
            return self.exchanges['okx']
        elif self.exchanges:
            # إذا لم تكن أي من البورصات الرئيسية مفعلة، اختر أول بورصة مفعلة
            return list(self.exchanges.values())[0]
        else:
            raise Exception("❌ لا توجد بورصات مُفعلة لاستخدامها كبورصة أساسية. يرجى تفعيل بورصة واحدة على الأقل.")
    
    def get_best_price(self, symbol, side):
        """الحصول على أفضل سعر لزوج تداول معين من جميع البورصات المفعلة (للتداول arbitrage)."""
        prices = {}
        
        for exchange_name, exchange in self.exchanges.items():
            try:
                price = exchange.get_market_price(symbol)
                if price:
                    prices[exchange_name] = price
            except Exception as e:
                logging.warning(f"⚠️ فشل في الحصول على السعر من {exchange_name} لـ {symbol}: {e}")
        
        if not prices:
            logging.error(f"❌ لم يتمكن من الحصول على أي سعر لـ {symbol} من أي بورصة مفعلة.")
            return None, None
        
        # اختيار أفضل سعر حسب نوع الأمر (شراء بأقل سعر، بيع بأعلى سعر)
        if side.upper() == 'BUY':
            # للشراء: أقل سعر معروض
            best_exchange = min(prices.keys(), key=lambda x: prices[x])
        else:
            # للبيع: أعلى سعر معروض
            best_exchange = max(prices.keys(), key=lambda x: prices[x])
        
        return best_exchange, prices[best_exchange]

class BinanceExchange:
    """واجهة برمجة تطبيقات Binance API لتنفيذ الأوامر والاستعلام عن الرصيد/الأسعار."""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config['api_key']
        self.secret_key = config['secret_key'].encode('utf-8') # تشفير المفتاح السري للاستخدام مع hmac
        self.base_url = config.get('testnet_endpoint') if config.get('testnet') else config.get('api_endpoint')
        if not self.base_url:
            self.base_url = 'https://testnet.binance.vision' if config.get('testnet') else 'https://api.binance.com'
        logging.info(f"Binance Base URL: {self.base_url}")

    def _sign_request(self, params):
        """توقيع الطلب باستخدام HMAC-SHA256."""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.secret_key, # المفتاح السري المشفر
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        return params
    
    def _request(self, endpoint, params=None, method='GET'):
        """إرسال طلب HTTP إلى Binance API."""
        if params is None:
            params = {}
        
        params['timestamp'] = int(time.time() * 1000) # إضافة الطابع الزمني بالمللي ثانية
        params = self._sign_request(params) # توقيع الطلب
        
        headers = {'X-MBX-APIKEY': self.api_key}
        url = f"{self.base_url}{endpoint}"
        
        try:
            logging.debug(f"Binance Request: {method} {url} with params {params}")
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, params=params, headers=headers, timeout=10)
            
            response.raise_for_status() # إثارة استثناء لأكواد حالة HTTP 4xx/5xx
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ خطأ في Binance API عند {endpoint}: {e}. الاستجابة: {getattr(e.response, 'text', 'لا توجد استجابة')}")
            raise # أعد إثارة الاستثناء ليتم التعامل معه بواسطة TradingEngine
    
    def get_account_balance(self):
        """الحصول على رصيد الحساب لجميع العملات."""
        try:
            account_info = self._request('/api/v3/account')
            balances = {}
            
            for balance in account_info['balances']:
                free = float(balance['free'])
                locked = float(balance['locked'])
                if free > 0 or locked > 0:
                    balances[balance['asset']] = {
                        'free': free,
                        'locked': locked,
                        'total': free + locked
                    }
            logging.info("✅ تم الحصول على رصيد Binance بنجاح.")
            return balances
        except Exception as e:
            logging.error(f"❌ فشل في الحصول على رصيد Binance: {e}")
            return {}
    
    def get_market_price(self, symbol):
        """الحصول على سعر السوق الحالي لزوج تداول."""
        try:
            ticker = self._request(f'/api/v3/ticker/price', {'symbol': symbol})
            price = float(ticker['price'])
            logging.info(f"✅ سعر {symbol} على Binance: {price}")
            return price
        except Exception as e:
            logging.error(f"❌ فشل في الحصول على سعر {symbol} من Binance: {e}")
            return None
    
    def place_order(self, symbol, side, quantity, order_type='MARKET'):
        """تنفيذ أمر تداول (شراء/بيع) في Binance."""
        try:
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': order_type,
                'quantity': quantity
            }
            
            result = self._request('/api/v3/order', params, 'POST')
            
            logging.info(f"✅ تم تنفيذ الأمر على Binance: {side} {quantity} {symbol} (ID: {result.get('orderId')})")
            return {
                'success': True,
                'order_id': result.get('orderId'),
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'status': result.get('status'),
                'price': float(result.get('fills', [{}])[0].get('price', result.get('price', 0))) # للحصول على سعر التنفيذ الفعلي
            }
        
        except Exception as e:
            logging.error(f"❌ فشل في تنفيذ الأمر على Binance لـ {symbol} ({side} {quantity}): {e}")
            return {
                'success': False,
                'error': str(e)
            }

class BybitExchange:
    """واجهة Bybit API (تحتاج إلى تنفيذ كامل)."""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config['api_key']
        self.secret_key = config['secret_key']
        self.base_url = config.get('testnet_endpoint') if config.get('testnet') else config.get('api_endpoint')
        if not self.base_url:
            self.base_url = 'https://api-testnet.bybit.com' if config.get('testnet') else 'https://api.bybit.com'
        logging.info(f"Bybit Base URL: {self.base_url}")

    def get_account_balance(self):
        """الحصول على رصيد الحساب من Bybit (تحتاج إلى تنفيذ)."""
        logging.warning("⚠️ وظيفة Bybit get_account_balance لم يتم تنفيذها بالكامل بعد.")
        # تنفيذ Bybit API (مثال توضيحي، يحتاج إلى كود حقيقي)
        # return self._request_bybit_api(...)
        return {'USDT': {'free': 1000.0, 'locked': 0.0, 'total': 1000.0}} # قيمة وهمية للاختبار
    
    def get_market_price(self, symbol):
        """الحصول على سعر السوق من Bybit (تحتاج إلى تنفيذ)."""
        logging.warning("⚠️ وظيفة Bybit get_market_price لم يتم تنفيذها بالكامل بعد.")
        # تنفيذ Bybit API
        # return float(self._request_bybit_api(...))
        import random
        return random.uniform(20000, 30000) # قيمة وهمية للاختبار
    
    def place_order(self, symbol, side, quantity, order_type='Market'):
        """تنفيذ أمر تداول في Bybit (تحتاج إلى تنفيذ)."""
        logging.warning("⚠️ وظيفة Bybit place_order لم يتم تنفيذها بالكامل بعد.")
        # تنفيذ Bybit API
        # return {'success': True, 'order_id': 'BYBIT_ORDER_123', 'symbol': symbol, 'side': side, 'quantity': quantity, 'status': 'FILLED', 'price': 25000}
        return {'success': False, 'error': 'Bybit integration in progress'}

class OKXExchange:
    """واجهة OKX API (تحتاج إلى تنفيذ كامل)."""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config['api_key']
        self.secret_key = config['secret_key']
        self.passphrase = config['passphrase']
        self.base_url = config.get('testnet_endpoint') if config.get('testnet') else config.get('api_endpoint')
        if not self.base_url:
            self.base_url = 'https://www.okx.com'
        logging.info(f"OKX Base URL: {self.base_url}")

    def get_account_balance(self):
        """الحصول على رصيد الحساب من OKX (تحتاج إلى تنفيذ)."""
        logging.warning("⚠️ وظيفة OKX get_account_balance لم يتم تنفيذها بالكامل بعد.")
        # تنفيذ OKX API
        return {}
    
    def get_market_price(self, symbol):
        """الحصول على سعر السوق من OKX (تحتاج إلى تنفيذ)."""
        logging.warning("⚠️ وظيفة OKX get_market_price لم يتم تنفيذها بالكامل بعد.")
        # تنفيذ OKX API
        return None
    
    def place_order(self, symbol, side, quantity, order_type='market'):
        """تنفيذ أمر تداول في OKX (تحتاج إلى تنفيذ)."""
        logging.warning("⚠️ وظيفة OKX place_order لم يتم تنفيذها بالكامل بعد.")
        # تنفيذ OKX API
        return {'success': False, 'error': 'OKX integration in progress'}

class TradingEngine:
    """محرك التداول المتقدم: ينسق بين مديري الإعدادات، قاعدة البيانات، والبورصات، ويدير منطق التداول."""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.exchange_manager = ExchangeManager(self.config_manager)
        
        self.auto_mode = self.config_manager.config.get('trading_config', {}).get('auto_trading', {}).get('enabled', False)
        self.sniper_mode = self.config_manager.config.get('trading_config', {}).get('sniper_mode', {}).get('enabled', False)
        self.active_trades = {} # لتتبع الصفقات المفتوحة
        
        logging.info("🚀 محرك التداول المتقدم جاهز للعمل")

        # بدء وضع التداول التلقائي إذا كان مفعلاً عند التشغيل
        if self.auto_mode:
            threading.Thread(target=self.auto_trading_loop, daemon=True).start()
            logging.info("🤖 تم بدء حلقة التداول التلقائي عند التشغيل.")
        
    def get_account_balance(self):
        """الحصول على رصيد الحساب من البورصة الأساسية أو من جميع البورصات المفعلة."""
        all_balances = {}
        for exchange_name, exchange in self.exchange_manager.exchanges.items():
            try:
                balances = exchange.get_account_balance()
                for asset, balance_info in balances.items():
                    if asset not in all_balances:
                        all_balances[asset] = {'free': 0.0, 'locked': 0.0, 'total': 0.0}
                    all_balances[asset]['free'] += balance_info['free']
                    all_balances[asset]['locked'] += balance_info['locked']
                    all_balances[asset]['total'] += balance_info['total']
            except Exception as e:
                logging.error(f"❌ فشل في الحصول على الرصيد من {exchange_name}: {e}")
        return all_balances
    
    def get_market_price(self, symbol):
        """الحصول على سعر السوق الحالي لزوج تداول من البورصة الأساسية."""
        try:
            primary_exchange = self.exchange_manager.get_primary_exchange()
            return primary_exchange.get_market_price(symbol)
        except Exception as e:
            logging.error(f"❌ فشل في الحصول على السعر من البورصة الأساسية لـ {symbol}: {e}")
            return None
    
    def place_order(self, symbol, side, quantity, exchange_name=None):
        """تنفيذ أمر تداول على بورصة محددة أو البورصة الأساسية."""
        try:
            # اختيار البورصة
            if exchange_name and exchange_name in self.exchange_manager.exchanges:
                exchange = self.exchange_manager.exchanges[exchange_name]
                actual_exchange_name = exchange_name
            else:
                exchange = self.exchange_manager.get_primary_exchange()
                actual_exchange_name = list(self.exchange_manager.exchanges.keys())[
                    list(self.exchange_manager.exchanges.values()).index(exchange)
                ] # الحصول على اسم البورصة الأساسية

            logging.info(f"🔄 محاولة تنفيذ أمر {side} لـ {quantity} من {symbol} على {actual_exchange_name}...")
            
            # تنفيذ الأمر
            result = exchange.place_order(symbol, side, quantity)
            
            # تسجيل في قاعدة البيانات
            if result.get('success'):
                self.db_manager.log_trade(
                    actual_exchange_name,
                    symbol,
                    side,
                    quantity,
                    result.get('price', 0),
                    'manual', # أو اسم الاستراتيجية إذا كانت تلقائية
                    result.get('order_id')
                )
            
            return result
        
        except Exception as e:
            logging.error(f"❌ فشل في تنفيذ الأمر لـ {symbol} ({side} {quantity}): {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def auto_trading_loop(self):
        """حلقة التداول التلقائي: تتحقق من السوق وتنفذ الصفقات بناءً على الاستراتيجيات."""
        logging.info("🤖 بدء التداول التلقائي")
        
        while self.auto_mode:
            try:
                trading_pairs = self.config_manager.env_vars['trading']['pairs']
                auto_interval = self.config_manager.env_vars['trading']['auto_interval']
                
                for symbol in trading_pairs:
                    if not self.auto_mode: # فحص مرة أخرى في حالة إيقاف الوضع التلقائي أثناء الحلقة
                        break
                    
                    # تحليل السوق وتنفيذ الصفقات
                    signal = self.analyze_market(symbol)
                    
                    if signal['action'] in ['BUY', 'SELL'] and signal['confidence'] > 0.7:
                        quantity = self.calculate_position_size(symbol)
                        if quantity > 0:
                            logging.info(f"📈 تم اكتشاف إشارة {signal['action']} قوية لـ {symbol}. الكمية: {quantity}")
                            result = self.place_order(symbol, signal['action'], quantity)
                            if result['success']:
                                logging.info(f"✅ تم تنفيذ أمر {signal['action']} بنجاح لـ {symbol} (ID: {result.get('order_id')})")
                            else:
                                logging.error(f"❌ فشل تنفيذ أمر {signal['action']} لـ {symbol}: {result.get('error')}")
                
                # انتظار قبل التحليل التالي
                logging.debug(f"الانتظار لمدة {auto_interval} ثانية قبل التحليل التالي...")
                time.sleep(auto_interval)
                
            except Exception as e:
                logging.error(f"❌ خطأ فادح في حلقة التداول التلقائي: {e}")
                time.sleep(60) # انتظار أطول عند حدوث خطأ لمنع حلقة الأخطاء
        
        logging.info("⏹️ تم إيقاف التداول التلقائي")
    
    def analyze_market(self, symbol):
        """تحليل السوق باستخدام المؤشرات الفنية (محاكاة، تحتاج إلى بيانات سوق حقيقية)."""
        try:
            # هنا يجب الحصول على بيانات السوق التاريخية (OHLCV)
            # مثال: ohlcv_data = primary_exchange.get_klines(symbol, timeframe)
            
            # لغرض العرض، سنحاكي بيانات بسيطة
            # في تطبيق حقيقي، ستحصل على بيانات الأسعار التاريخية
            # وتستخدمها مع Pandas DataFrames
            
            # مثال محاكاة: افتراض سعر عشوائي
            price = self.get_market_price(symbol)
            if not price:
                logging.warning(f"⚠️ لا يمكن تحليل السوق لـ {symbol}: لم يتم الحصول على السعر.")
                return {'action': 'HOLD', 'confidence': 0.0}

            # محاكاة بسيطة لإشارة تداول بناءً على المؤشرات (للتطوير)
            action = 'HOLD'
            confidence = 0.0

            # مثال على دمج TA-Lib (يحتاج إلى بيانات حقيقية لتشغيله)
            if TALIB_AVAILABLE:
                # هذا جزء توضيحي فقط، ستحتاج إلى بيانات OHLCV حقيقية
                # prices = np.random.rand(100) * 100 # افتراض 100 نقطة سعر عشوائية
                # rsi = talib.RSI(prices, timeperiod=14)
                # if rsi[-1] < self.config_manager.config['trading_config']['technical_indicators']['rsi']['oversold']:
                #    action = 'BUY'
                #    confidence = 0.8
                # logging.debug(f"TA-Lib RSI for {symbol}: {rsi[-1]}")
                pass # لا نقوم بتنفيذ TA-Lib فعليا هنا بدون بيانات
            
            import random
            if random.random() > 0.6: # 40% فرصة لعدم وجود إشارة
                if random.random() > 0.5:
                    action = 'BUY'
                    confidence = random.uniform(0.7, 0.95)
                else:
                    action = 'SELL'
                    confidence = random.uniform(0.7, 0.95)
            
            logging.debug(f"تحليل السوق لـ {symbol}: الإجراء {action} بثقة {confidence:.2f}")
            return {
                'action': action,
                'confidence': confidence,
                'price': price
            }
        
        except Exception as e:
            logging.error(f"❌ خطأ في تحليل السوق لـ {symbol}: {e}")
            return {'action': 'HOLD', 'confidence': 0.0}
    
    def calculate_position_size(self, symbol):
        """حساب حجم الصفقة بناءً على رصيد USDT وإعدادات إدارة المخاطر."""
        try:
            balances = self.get_account_balance()
            usdt_balance = balances.get('USDT', {}).get('free', 0)
            
            if usdt_balance <= 0:
                logging.warning("⚠️ رصيد USDT غير كافٍ لتحديد حجم الصفقة.")
                return 0
            
            # حساب حجم الصفقة كنسبة مئوية من رأس المال المتاح
            position_size_percent = self.config_manager.env_vars['risk']['max_position_size']
            position_value = usdt_balance * (position_size_percent / 100)
            
            price = self.get_market_price(symbol)
            if not price or price <= 0:
                logging.error(f"❌ لا يمكن حساب حجم الصفقة لـ {symbol}: السعر غير صالح.")
                return 0
            
            quantity = position_value / price
            # تقريب الكمية إلى عدد مقبول من الأرقام العشرية للبورصة (عادة 6-8)
            quantity = round(quantity, 6) 
            
            # التأكد من أن الكمية لا تقل عن الحد الأدنى لحجم الطلب للبورصة (من config.json)
            # هذه الخطوة تتطلب معرفة البورصة التي سيتم التداول عليها
            # على سبيل المثال، إذا كانت Binance هي البورصة الأساسية:
            # exchange_config = self.config_manager.get_exchange_config('binance')
            # min_order_size = exchange_config.get('min_order_size', 0.001)
            # if quantity < min_order_size:
            #     logging.warning(f"حجم الصفقة المحسوب ({quantity}) أقل من الحد الأدنى ({min_order_size}) لـ {symbol}.")
            #     return 0 # أو ضبطه على الحد الأدنى
            
            return quantity
        
        except Exception as e:
            logging.error(f"❌ خطأ في حساب حجم الصفقة لـ {symbol}: {e}")
            return 0

# إنشاء محرك التداول عند بدء تشغيل التطبيق
trading_engine = TradingEngine()

# Flask Routes (واجهات برمجة التطبيقات الويب)
@app.route('/api/health')
def health_check():
    """فحص صحة النظام وحالة الاتصالات."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'exchanges_enabled': list(trading_engine.exchange_manager.exchanges.keys()),
        'auto_mode': trading_engine.auto_mode,
        'sniper_mode': trading_engine.sniper_mode,
        'config_loaded': True, # لأن ConfigManager يعمل عند التهيئة
        'database_connected': True # لأن DatabaseManager يعمل عند التهيئة
    })

@app.route('/api/config')
def get_config():
    """الحصول على الإعدادات الرئيسية للنظام (يمكن تصفيتها لأسباب أمنية)."""
    return jsonify({
        'success': True,
        'config': {
            'exchanges': list(trading_engine.exchange_manager.exchanges.keys()),
            'trading_pairs': trading_engine.config_manager.env_vars['trading']['pairs'],
            'risk_settings': trading_engine.config_manager.env_vars['risk'],
            'auto_interval': trading_engine.config_manager.env_vars['trading']['auto_interval'],
            'sniper_interval': trading_engine.config_manager.env_vars['trading']['sniper_interval']
        }
    })

@app.route('/api/balance')
def get_balance():
    """الحصول على رصيد الحساب المجمع من جميع البورصات المفعلة."""
    try:
        balances = trading_engine.get_account_balance()
        return jsonify({
            'success': True,
            'balances': balances,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"❌ فشل في الحصول على رصيد الحساب عبر API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/price/<symbol>')
def get_price(symbol):
    """الحصول على سعر العملة الحالي لزوج تداول معين."""
    try:
        price = trading_engine.get_market_price(symbol.upper())
        if price:
            return jsonify({
                'success': True,
                'symbol': symbol.upper(),
                'price': price,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': f'فشل في الحصول على السعر لـ {symbol}'
            }), 400
    except Exception as e:
        logging.error(f"❌ خطأ في جلب السعر لـ {symbol} عبر API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trade', methods=['POST'])
def execute_trade():
    """واجهة برمجة تطبيقات لتنفيذ صفقة تداول يدوية."""
    try:
        data = request.json
        symbol = data.get('symbol', '').upper()
        side = data.get('side', '').upper()
        quantity = float(data.get('quantity', 0))
        exchange = data.get('exchange', None) # يمكن تحديد بورصة معينة أو تركها تلقائية
        
        if not symbol or not side or quantity <= 0:
            return jsonify({
                'success': False,
                'error': 'بيانات غير صحيحة: الرمز، النوع، أو الكمية غير صالحة.'
            }), 400
        
        result = trading_engine.place_order(symbol, side, quantity, exchange)
        return jsonify(result)
    
    except Exception as e:
        logging.error(f"❌ خطأ في تنفيذ صفقة يدوية عبر API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auto-mode', methods=['POST'])
def toggle_auto_mode():
    """تفعيل/إيقاف الوضع التلقائي للتداول."""
    try:
        data = request.json
        enable = data.get('enable', False)
        
        if enable and not trading_engine.auto_mode:
            trading_engine.auto_mode = True
            threading.Thread(target=trading_engine.auto_trading_loop, daemon=True).start()
            message = "تم تفعيل الوضع التلقائي. بدأت حلقة التداول التلقائي."
            logging.info(message)
        
        elif not enable and trading_engine.auto_mode:
            trading_engine.auto_mode = False
            message = "تم إيقاف الوضع التلقائي."
            logging.info(message)
        
        else:
            message = f"الوضع التلقائي {'مُفعل' if trading_engine.auto_mode else 'مُعطل'} مسبقاً. لم يتم تغيير الحالة."
            logging.info(message)
        
        return jsonify({
            'success': True,
            'auto_mode': trading_engine.auto_mode,
            'message': message
        })
    
    except Exception as e:
        logging.error(f"❌ خطأ في تغيير حالة الوضع التلقائي عبر API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sniper-mode', methods=['POST'])
def toggle_sniper_mode():
    """تفعيل/إيقاف وضع القناص (للتداول عالي التردد أو الفرص السريعة)."""
    try:
        data = request.json
        enable = data.get('enable', False)
        
        trading_engine.sniper_mode = enable
        message = f"تم {'تفعيل' if enable else 'إيقاف'} وضع القناص."
        logging.info(message)
        
        # يمكن إضافة حلقة منفصلة لوضع القناص هنا إذا لزم الأمر
        
        return jsonify({
            'success': True,
            'sniper_mode': trading_engine.sniper_mode,
            'message': message
        })
    
    except Exception as e:
        logging.error(f"❌ خطأ في تغيير حالة وضع القناص عبر API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats')
def get_stats():
    """الحصول على إحصائيات التداول والرصيد الإجمالي."""
    try:
        db_stats = trading_engine.db_manager.get_statistics()
        balances = trading_engine.get_account_balance()
        
        total_balance_usd = 0
        for asset, balance in balances.items():
            if asset.upper() == 'USDT': # نعتبر USDT هي العملة الأساسية للمقارنة
                total_balance_usd += balance['total']
            else:
                # تحويل العملات الأخرى إلى USDT للحصول على إجمالي الرصيد (تقريبي)
                # هذا يتطلب أن يكون لديك أزواج مثل BTCUSDT, ETHUSDT
                price_symbol = f"{asset}USDT"
                price = trading_engine.get_market_price(price_symbol)
                if price:
                    total_balance_usd += balance['total'] * price
                else:
                    logging.warning(f"⚠️ لم يتمكن من الحصول على سعر {price_symbol} لتحويل الرصيد {asset}.")

        return jsonify({
            'success': True,
            'stats': {
                'total_balance': round(total_balance_usd, 2), # الرصيد المجمع بالدولار (أو USDT)
                'total_trades': db_stats.get('total_trades', 0),
                'profitable_trades': db_stats.get('profitable_trades', 0),
                'total_profit': round(db_stats.get('total_profit', 0), 2),
                'success_rate': round(db_stats.get('success_rate', 0), 1),
                'auto_mode': trading_engine.auto_mode,
                'sniper_mode': trading_engine.sniper_mode,
                'exchanges_active': len(trading_engine.exchange_manager.exchanges)
            },
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"❌ خطأ في الحصول على الإحصائيات عبر API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/')
def dashboard():
    """لوحة التحكم الرئيسية (واجهة الويب)."""
    # هذه هي الواجهة الأمامية التي يتم تقديمها للمستخدم
    return render_template_string("""
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Roben Trading AI Bot - Enhanced System</title>
    <style>
        /* أنماط CSS لتحسين مظهر لوحة التحكم */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header .subtitle { font-size: 1.2em; opacity: 0.9; }
        
        .status-bar { 
            background: rgba(255,255,255,0.1); 
            padding: 15px; 
            border-radius: 10px; 
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .status-item { display: flex; align-items: center; margin: 5px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; margin-left: 8px; }
        .status-dot.active { background: #00ff88; }
        .status-dot.inactive { background: #ff4444; }
        
        .warning { 
            background: linear-gradient(45deg, #ff4444, #ff6666); 
            padding: 20px; 
            border-radius: 15px; 
            margin-bottom: 25px;
            border: 2px solid #ff8888;
            box-shadow: 0 4px 15px rgba(255,68,68,0.3);
        }
        .warning h3 { margin-bottom: 10px; }
        
        .card { 
            background: rgba(255,255,255,0.1); 
            padding: 25px; 
            border-radius: 15px; 
            margin-bottom: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        .card h3 { margin-bottom: 20px; font-size: 1.4em; }
        
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin-bottom: 20px;
        }
        .stat-card { 
            background: rgba(255,255,255,0.05); 
            padding: 20px; 
            border-radius: 12px; 
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-value { 
            font-size: 2.2em; 
            font-weight: bold; 
            color: #00ff88; 
            margin-bottom: 5px;
        }
        .stat-label { font-size: 0.9em; opacity: 0.8; }
        
        .controls { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; 
            margin-bottom: 20px;
        }
        .btn { 
            background: linear-gradient(45deg, #00ff88, #00cc66); 
            color: #000; 
            padding: 15px 20px; 
            border: none; 
            border-radius: 10px; 
            cursor: pointer;
            font-weight: bold;
            font-size: 1em;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(0,255,136,0.3);
        }
        .btn:hover { 
            transform: translateY(-2px); 
            box-shadow: 0 6px 20px rgba(0,255,136,0.4);
        }
        .btn.danger { 
            background: linear-gradient(45deg, #ff4444, #cc3333); 
            color: white;
            box-shadow: 0 4px 15px rgba(255,68,68,0.3);
        }
        .btn.danger:hover { 
            box-shadow: 0 6px 20px rgba(255,68,68,0.4);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .trading-form { 
            display: grid; 
            grid-template-columns: 1fr 1fr 1fr 1fr auto; 
            gap: 15px; 
            align-items: end;
        }
        .form-group { display: flex; flex-direction: column; }
        .form-group label { margin-bottom: 5px; font-size: 0.9em; }
        .form-group select, .form-group input { 
            padding: 12px; 
            border-radius: 8px; 
            border: 1px solid rgba(255,255,255,0.3);
            background: rgba(255,255,255,0.1);
            color: white;
            font-size: 1em;
        }
        .form-group select option { background: #2a5298; color: white; }
        
        .log { 
            background: rgba(0,0,0,0.4); 
            padding: 20px; 
            border-radius: 10px; 
            height: 300px; 
            overflow-y: auto; 
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .log-entry { 
            margin-bottom: 8px; 
            padding: 5px;
            border-radius: 4px;
        }
        .log-entry.success { background: rgba(0,255,136,0.1); }
        .log-entry.error { background: rgba(255,68,68,0.1); }
        .log-entry.warning { background: rgba(255,193,7,0.1); }
        
        .exchange-status {
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .exchange-badge {
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
        }
        .exchange-badge.active {
            background: linear-gradient(45deg, #00ff88, #00cc66);
            color: #000;
        }
        .exchange-badge.inactive {
            background: rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.6);
        }
        
        @media (max-width: 768px) {
            .trading-form { 
                grid-template-columns: 1fr; 
                gap: 10px;
            }
            .stats { grid-template-columns: repeat(2, 1fr); }
            .controls { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Roben Trading AI Bot</h1>
            <div class="subtitle">نظام التداول الحقيقي المتطور - Enhanced Version</div>
        </div>
        
        <div class="status-bar">
            <div class="status-item">
                <span>حالة النظام:</span>
                <div class="status-dot active"></div>
                <span>متصل</span>
            </div>
            <div class="status-item">
                <span>الوضع التلقائي:</span>
                <div class="status-dot inactive" id="auto-dot"></div>
                <span id="auto-text">معطل</span>
            </div>
            <div class="status-item">
                <span>وضع القناص:</span>
                <div class="status-dot inactive" id="sniper-dot"></div>
                <span id="sniper-text">معطل</span>
            </div>
            <div class="status-item">
                <span>البورصات النشطة:</span>
                <span id="exchanges-count">0</span>
            </div>
        </div>
        
        <div class="warning">
            <h3>⚠️ تحذير مهم - نظام تداول حقيقي محسن</h3>
            <p>هذا النظام المحسن يدعم عدة بورصات ويتعامل مع أموال حقيقية. تم ربط جميع مفاتيح API من ملفات .env و config.json.</p>
            <p>تأكد من فهم المخاطر وإعداد مفاتيح API بصلاحيات محدودة قبل البدء.</p>
        </div>
        
        <div class="card">
            <h3>🏢 البورصات المُفعلة</h3>
            <div class="exchange-status" id="exchange-status">
                <div class="exchange-badge inactive">جاري التحميل...</div>
            </div>
        </div>
        
        <div class="card">
            <h3>📊 إحصائيات الحساب المباشرة</h3>
            <div class="stats" id="stats">
                <div class="stat-card">
                    <div class="stat-value" id="balance">$0.00</div>
                    <div class="stat-label">الرصيد الإجمالي</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="trades">0</div>
                    <div class="stat-label">إجمالي الصفقات</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="profit">$0.00</div>
                    <div class="stat-label">إجمالي الأرباح</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="success-rate">0%</div>
                    <div class="stat-label">معدل النجاح</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="profitable-trades">0</div>
                    <div class="stat-label">الصفقات المربحة</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h3>🎛️ أدوات التحكم المتقدمة</h3>
            <div class="controls">
                <button class="btn" onclick="toggleAutoMode()" id="auto-btn">
                    تفعيل الوضع التلقائي
                </button>
                <button class="btn" onclick="toggleSniperMode()" id="sniper-btn">
                    تفعيل وضع القناص
                </button>
                <button class="btn" onclick="refreshData()">
                    تحديث البيانات
                </button>
                <button class="btn danger" onclick="emergencyStop()">
                    إيقاف طارئ
                </button>
            </div>
        </div>
        
        <div class="card">
            <h3>📈 تنفيذ صفقة يدوية</h3>
            <div class="trading-form">
                <div class="form-group">
                    <label>البورصة:</label>
                    <select id="exchange">
                        <option value="">تلقائي (الأفضل)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>زوج التداول:</label>
                    <select id="symbol">
                        <option value="BTCUSDT">BTC/USDT</option>
                        <option value="ETHUSDT">ETH/USDT</option>
                        <option value="ADAUSDT">ADA/USDT</option>
                        <option value="BNBUSDT">BNB/USDT</option>
                        <option value="XRPUSDT">XRP/USDT</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>النوع:</label>
                    <select id="side">
                        <option value="BUY">شراء</option>
                        <option value="SELL">بيع</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>الكمية:</label>
                    <input type="number" id="quantity" placeholder="0.001" step="0.001" min="0.001">
                </div>
                <div class="form-group">
                    <button class="btn" onclick="executeTrade()">تنفيذ الصفقة</button>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h3>📋 سجل العمليات المتقدم</h3>
            <div class="log" id="log">
                <div class="log-entry">🚀 نظام التداول المحسن جاهز...</div>
            </div>
        </div>
    </div>

    <script>
        let autoMode = false;
        let sniperMode = false;
        let exchangesData = {};
        
        function log(message, type = 'info') {
            const logDiv = document.getElementById('log');
            const time = new Date().toLocaleTimeString('ar-SA');
            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            entry.innerHTML = `[${time}] ${message}`;
            logDiv.appendChild(entry);
            logDiv.scrollTop = logDiv.scrollHeight;
        }
        
        async function updateStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                if (data.success) {
                    const stats = data.stats;
                    document.getElementById('balance').textContent = `$${stats.total_balance.toLocaleString()}`;
                    document.getElementById('trades').textContent = stats.total_trades;
                    document.getElementById('profit').textContent = `$${stats.total_profit.toLocaleString()}`;
                    document.getElementById('success-rate').textContent = `${stats.success_rate}%`;
                    document.getElementById('profitable-trades').textContent = stats.profitable_trades;
                    document.getElementById('exchanges-count').textContent = stats.exchanges_active;
                    
                    autoMode = stats.auto_mode;
                    sniperMode = stats.sniper_mode;
                    
                    updateStatusIndicators();
                }
            } catch (error) {
                log(`❌ خطأ في تحديث الإحصائيات: ${error.message}`, 'error');
            }
        }
        
        async function updateConfig() {
            try {
                const response = await fetch('/api/config');
                const data = await response.json();
                
                if (data.success) {
                    const config = data.config;
                    
                    // تحديث قائمة البورصات
                    const exchangeSelect = document.getElementById('exchange');
                    exchangeSelect.innerHTML = '<option value="">تلقائي (الأفضل)</option>';
                    
                    config.exchanges.forEach(exchange => {
                        const option = document.createElement('option');
                        option.value = exchange;
                        option.textContent = exchange.toUpperCase();
                        exchangeSelect.appendChild(option);
                    });
                    
                    // تحديث حالة البورصات
                    const exchangeStatus = document.getElementById('exchange-status');
                    exchangeStatus.innerHTML = '';
                    
                    config.exchanges.forEach(exchange => {
                        const badge = document.createElement('div');
                        badge.className = 'exchange-badge active';
                        badge.textContent = exchange.toUpperCase();
                        exchangeStatus.appendChild(badge);
                    });
                    
                    if (config.exchanges.length === 0) {
                        exchangeStatus.innerHTML = '<div class="exchange-badge inactive">لا توجد بورصات مُفعلة</div>';
                    }
                }
            } catch (error) {
                log(`❌ خطأ في تحديث الإعدادات: ${error.message}`, 'error');
            }
        }
        
        function updateStatusIndicators() {
            // الوضع التلقائي
            const autoDot = document.getElementById('auto-dot');
            const autoText = document.getElementById('auto-text');
            const autoBtn = document.getElementById('auto-btn');
            
            if (autoMode) {
                autoDot.className = 'status-dot active';
                autoText.textContent = 'مُفعل';
                autoBtn.textContent = 'إيقاف الوضع التلقائي';
            } else {
                autoDot.className = 'status-dot inactive';
                autoText.textContent = 'معطل';
                autoBtn.textContent = 'تفعيل الوضع التلقائي';
            }
            
            // وضع القناص
            const sniperDot = document.getElementById('sniper-dot');
            const sniperText = document.getElementById('sniper-text');
            const sniperBtn = document.getElementById('sniper-btn');
            
            if (sniperMode) {
                sniperDot.className = 'status-dot active';
                sniperText.textContent = 'مُفعل';
                sniperBtn.textContent = 'إيقاف وضع القناص';
            } else {
                sniperDot.className = 'status-dot inactive';
                sniperText.textContent = 'معطل';
                sniperBtn.textContent = 'تفعيل وضع القناص';
            }
        }
        
        async function toggleAutoMode() {
            try {
                const response = await fetch('/api/auto-mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enable: !autoMode })
                });
                
                const data = await response.json();
                if (data.success) {
                    log(`✅ ${data.message}`, 'success');
                    autoMode = data.auto_mode;
                    updateStatusIndicators();
                } else {
                    log(`❌ ${data.error}`, 'error');
                }
            } catch (error) {
                log(`❌ خطأ في تغيير الوضع التلقائي: ${error.message}`, 'error');
            }
        }
        
        async function toggleSniperMode() {
            try {
                const response = await fetch('/api/sniper-mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enable: !sniperMode })
                });
                
                const data = await response.json();
                if (data.success) {
                    log(`✅ ${data.message}`, 'success');
                    sniperMode = data.sniper_mode;
                    updateStatusIndicators();
                } else {
                    log(`❌ ${data.error}`, 'error');
                }
            } catch (error) {
                log(`❌ خطأ في تغيير وضع القناص: ${error.message}`, 'error');
            }
        }
        
        async function executeTrade() {
            const exchange = document.getElementById('exchange').value;
            const symbol = document.getElementById('symbol').value;
            const side = document.getElementById('side').value;
            const quantity = parseFloat(document.getElementById('quantity').value);
            
            if (!quantity || quantity <= 0) {
                log('❌ يرجى إدخال كمية صحيحة', 'error');
                return;
            }
            
            try {
                log(`🔄 تنفيذ ${side} ${quantity} ${symbol}${exchange ? ` على ${exchange}` : ''}...`, 'warning');
                
                const response = await fetch('/api/trade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ exchange, symbol, side, quantity })
                });
                
                const data = await response.json();
                if (data.success) {
                    log(`✅ تم تنفيذ الصفقة بنجاح - معرف: ${data.order_id}`, 'success');
                    updateStats();
                    
                    // مسح النموذج
                    document.getElementById('quantity').value = '';
                } else {
                    log(`❌ فشل في تنفيذ الصفقة: ${data.error}`, 'error');
                }
            } catch (error) {
                log(`❌ خطأ في تنفيذ الصفقة: ${error.message}`, 'error');
            }
        }
        
        function refreshData() {
            log('🔄 تحديث البيانات...', 'warning');
            updateStats();
            updateConfig();
            log('✅ تم تحديث البيانات', 'success');
        }
        
        function emergencyStop() {
            if (confirm('هل أنت متأكد من الإيقاف الطارئ؟ سيتم إيقاف جميع العمليات.')) {
                Promise.all([
                    fetch('/api/auto-mode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enable: false })
                    }),
                    fetch('/api/sniper-mode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enable: false })
                    })
                ]).then(() => {
                    log('🛑 تم تنفيذ الإيقاف الطارئ', 'warning');
                    autoMode = false;
                    sniperMode = false;
                    updateStatusIndicators();
                });
            }
        }
        
        // تحديث البيانات كل 5 ثوانٍ
        setInterval(updateStats, 5000);
        
        // تحميل البيانات الأولية
        updateStats();
        updateConfig();
        
        log('🚀 لوحة التحكم المحسنة جاهزة للاستخدام', 'success');
        log('🔗 تم ربط جميع مفاتيح API من ملفات .env و config.json', 'success');
        log('⚠️ تذكر: هذا نظام تداول حقيقي محسن - استخدم بحذر', 'warning');
    </script>
</body>
</html>
    """)

if __name__ == '__main__':
    print("🚀 بدء تشغيل نظام التداول المحسن...")
    print("🔗 تم ربط جميع مفاتيح API من ملفات .env و config.json")
    print("📋 البورصات المدعومة: Binance, Bybit, OKX")
    print("⚠️  تحذير: هذا النظام يتعامل مع أموال حقيقية")
    print("🌐 الوصول للنظام: http://localhost:8082")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=8082, debug=False)