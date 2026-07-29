# High-Speed X (Twitter) to JustAnotherPanel (JAP) Automation Bot

An ultra-fast, zero-cost, 24/7 automated bridge that monitors any target X (Twitter) channel without official Twitter Developer API keys, parses incoming post content for target URLs, and immediately places SMM panel orders on **JustAnotherPanel (JAP)**.

---

## ⚡ Key Highlights & Architecture

- **No Twitter Developer API Required**: Bypasses official Twitter API restrictions by utilizing high-resilience, auto-rotating public Nitter RSS mirrors.
- **Sub-Second Execution Speed**: Powered by Python's `httpx` async I/O engine to capture first-come, first-served orders instantly.
- **Intelligent Link Parser**: Automatically extracts target URLs (Instagram, TikTok, YouTube, X, etc.) from post descriptions and handles URL shortener redirects (e.g., `t.co`).
- **Dynamic Service ID Routing**: Automatically maps target domains (e.g. `instagram.com` vs `tiktok.com`) to specific JAP Service IDs on the fly.
- **Zero Duplicate Orders**: SQLite database tracking guarantees each post GUID is processed exactly once.

---

## 📁 File Overview

- [`main.py`](file:///c:/Users/salat/OneDrive/Desktop/python/main.py): The 24/7 core monitoring and auto-order daemon.
- [`config.py`](file:///c:/Users/salat/OneDrive/Desktop/python/config.py): Configuration parser loading variables from `.env`.
- [`jap_client.py`](file:///c:/Users/salat/OneDrive/Desktop/python/jap_client.py): Async HTTP client for JustAnotherPanel PerfectPanel API.
- [`x_tracker.py`](file:///c:/Users/salat/OneDrive/Desktop/python/x_tracker.py): Resilient X feed tracker with automatic Nitter mirror failover.
- [`link_parser.py`](file:///c:/Users/salat/OneDrive/Desktop/python/link_parser.py): Regex URL extractor & link redirect resolver.
- [`state_manager.py`](file:///c:/Users/salat/OneDrive/Desktop/python/state_manager.py): SQLite database manager for tracking processed posts.
- [`test_jap.py`](file:///c:/Users/salat/OneDrive/Desktop/python/test_jap.py): CLI utility for testing JAP API keys, balance, and test orders.
- [`.env.example`](file:///c:/Users/salat/OneDrive/Desktop/python/.env.example): Environment variable template.
- [`requirements.txt`](file:///c:/Users/salat/OneDrive/Desktop/python/requirements.txt): Python dependency requirements.

---

## 🚀 Quick Setup Guide

### 1. Install Dependencies

```bash
cd c:\Users\salat\OneDrive\Desktop\python
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```ini
# JustAnotherPanel Credentials
JAP_API_KEY=your_actual_jap_api_key_here
JAP_API_URL=https://justanotherpanel.com/api/v2

# X Target Channel
TARGET_X_USERNAME=target_username_here
POLL_INTERVAL_SECONDS=3.0

# Order Settings
DEFAULT_SERVICE_ID=1234
DEFAULT_QUANTITY=1000

# Domain-to-Service Mapping (Optional)
SERVICE_MAPPING_JSON={"instagram.com": 1234, "tiktok.com": 2345, "youtube.com": 3456, "x.com": 4567}
```

---

## 🧪 Testing your Setup

Test your JAP API Key and check account balance:

```bash
python test_jap.py --balance
```

Test placing a sample order:

```bash
python test_jap.py --order --service 1234 --link "https://instagram.com/p/sample" --quantity 100
```

---

## 🟢 Running the 24/7 Monitoring Daemon

Start the main daemon:

```bash
python main.py
```

### 24/7 Cloud Deployment (AWS / DigitalOcean / VPS)

To keep the script running 24/7 in the background on Linux servers:

```bash
nohup python3 main.py > bot.log 2>&1 &
```

Or using `pm2`:

```bash
pm2 start main.py --name "jap-x-bot" --interpreter python3
```

---

## 🛡️ Fallback & Resilience Strategy

1. **Instance Auto-Rotation**: If a public Nitter mirror slows down or goes offline, `XTracker` automatically switches to the next configured mirror instance in real-time.
2. **Duplicate Protection**: If the script restarts, `state_manager.py` checks SQLite memory to prevent duplicate orders for already processed posts.
