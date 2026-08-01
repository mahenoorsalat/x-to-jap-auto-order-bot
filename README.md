# X-to-JAP High-Speed Auto-Order Bot

High-speed Python automation bot that monitors X (Twitter) channels without Twitter Developer API and automatically places orders on JustAnotherPanel (JAP) SMM panel.

---

## 🚀 What It Does

- **Multi-Engine Monitoring**: Monitors X target accounts using Nitter RSS mirrors (with cache-busting), VxTwitter API fallback, and optional direct Twikit GraphQL mode.
- **Universal URL Sanitization**: Automatically normalizes all detected tweet links into clean `https://x.com/<username>/status/<id>` links, removing mirror domain leaks and `#m` anchors.
- **Auto-Rotation & Resilience**: Seamlessly rotates across 11+ backup Nitter mirrors with cache-busting headers (`Cache-Control: no-cache`).
- **Instant Order Execution**: Detects new posts instantly, extracts target/tweet links, and fires orders to JustAnotherPanel API.
- **SQLite Memory**: Prevents duplicate orders across restarts.
- **Dynamic Platform Routing**: Supports mapping Instagram, TikTok, YouTube, and X links to separate JAP Service IDs.

---

## 🛠️ Quick Setup

**1. Install dependencies:**

```bash
pip install -r requirements.txt
```

**2. Create your `.env` file:**

```bash
copy .env.example .env
```

**3. Configure `.env` details:**

```env
JAP_API_KEY=your_jap_api_key_here
TARGET_X_USERNAME=target_username_without_at
DEFAULT_SERVICE_ID=2098
DEFAULT_QUANTITY=200
POLL_INTERVAL_SECONDS=5.0
USE_TWEET_URL=true
```

*(Optional: Set `X_AUTH_TOKEN` or `X_USERNAME`/`X_PASSWORD` in `.env` for 100% 0-delay real-time Twikit GraphQL mode).*

---

## ▶️ Running the Bot

**Run Full Test Suite:**
```bash
python run_tests.py
```

**Test JAP Balance & API:**
```bash
python test_jap.py --balance
```

**Instant Order Trigger (Test on Latest Tweet):**
```bash
python trigger_latest.py
```

**Start 24/7 Live Daemon:**
```bash
python main.py
```

---

## 🖥️ Running 24/7 on a VPS / Cloud

**Linux VPS:**
```bash
nohup python3 main.py > bot.log 2>&1 &
```

**PM2 Daemon:**
```bash
pm2 start main.py --name jap-bot --interpreter python3
```

---

## 📋 Architecture & Multi-Engine Strategy

1. **Engine 1 (Twikit GraphQL - Priority)**: If `X_AUTH_TOKEN` or credentials are set in `.env`, runs directly against X API with 0-delay.
2. **Engine 2 (Nitter RSS with Cache-Busting)**: Polled with cache-busting headers (`Cache-Control: no-cache`, timestamp parameters) and automatic rotation across 11+ public mirrors.
3. **Engine 3 (VxTwitter API)**: Reliable API fallback when RSS mirrors undergo temporary rate-limiting.
