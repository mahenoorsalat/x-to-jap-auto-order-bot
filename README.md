# x-to-jap-auto-order-bot

So basically this script watches a Twitter/X account and the moment they post something, it grabs the link from the tweet and fires an order on JustAnotherPanel automatically. No manual work needed.

Built this because JAP is first-come-first-served so you need to be fast. This thing runs 24/7 and reacts in seconds.

---

## what it does

- watches any X account without needing a Twitter developer API key (uses public RSS feeds)
- pulls the link out of the tweet text automatically
- sends the order to JAP the second it detects a new post
- remembers what it already ordered so it never double-buys
- if one RSS mirror goes down it just switches to another one, no crashes

---

## files

- `main.py` — the main script, just run this
- `x_tracker.py` — the part that watches the X account
- `jap_client.py` — handles sending orders to JAP
- `link_parser.py` — pulls the link out of the tweet
- `state_manager.py` — tracks what's already been ordered
- `test_jap.py` — use this to test your API key before running
- `config.py` — loads your settings from the .env file
- `.env.example` — copy this to .env and fill in your details

---

## setup

**1. install the dependencies**

```bash
pip install -r requirements.txt
```

**2. create your .env file**

```bash
cp .env.example .env
```

on Windows:
```bash
copy .env.example .env
```

**3. open .env and fill in your stuff**

```
JAP_API_KEY=your_key_from_justanotherpanel
TARGET_X_USERNAME=the_username_you_want_to_track
DEFAULT_SERVICE_ID=put_your_service_id_here
DEFAULT_QUANTITY=1000
POLL_INTERVAL_SECONDS=3
```

to get your JAP API key: login → go to Account → API section → copy the key

if you post to different platforms and want different service IDs per platform, add this too:

```
SERVICE_MAPPING_JSON={"instagram.com": 1111, "tiktok.com": 2222, "youtube.com": 3333}
```

---

## running it

test your API key first:

```bash
python test_jap.py --balance
```

once that works, start the bot:

```bash
python main.py
```

---

## running it 24/7 on a server

if you're on a Linux VPS just do:

```bash
nohup python3 main.py > bot.log 2>&1 &
```

or with pm2:

```bash
pm2 start main.py --name jap-bot --interpreter python3
```

---

## notes

- the bot checks every 3 seconds by default, you can change that in .env
- it uses 6 different Nitter mirrors and auto-switches if one goes down
- processed tweet IDs are saved locally so even if you restart the bot it won't re-order old posts
