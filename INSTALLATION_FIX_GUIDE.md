# 🔧 دليل الإصلاح السريع - Roben Trading AI Bot

## ❌ **المشكلة:**
ملف التثبيت `install_windows.bat` يظهر نصوص مشوهة بسبب مشكلة الترميز.

## ✅ **الحل:**

### **الطريقة الأولى: استخدام الملف المُصلح**
1. حمل الملف الجديد: `install_windows_fixed.bat`
2. ضعه في نفس مجلد المشروع
3. اضغط عليه مرتين لتشغيله

### **الطريقة الثانية: التثبيت اليدوي**
```cmd
# افتح Command Prompt كمدير
# انتقل لمجلد المشروع
cd C:\path\to\your\project

# تثبيت المكتبات
pip install python-dotenv flask flask-cors requests pandas numpy

# تشغيل النظام
python roben_enhanced_trading_system.py
```

### **الطريقة الثالثة: استخدام PowerShell**
```powershell
# افتح PowerShell كمدير
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# تثبيت المكتبات
pip install python-dotenv flask flask-cors requests pandas numpy

# تشغيل النظام
python roben_enhanced_trading_system.py
```

## 🚀 **بعد التثبيت:**
1. عدل ملف `.env` وأضف مفاتيح Binance API
2. شغل النظام: `python roben_enhanced_trading_system.py`
3. افتح المتصفح: `http://localhost:8082`

## 📞 **الدعم:**
- التليجرام: @RobenTradingSupport
- البريد: support@robentrading.ai

## ⚠️ **تذكر:**
ابدأ بمبالغ صغيرة للاختبار (10-50$)

