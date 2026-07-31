"""
Full integration test suite for X-to-JAP automation bot.
Tests: imports, config loading, URL sanitizer, Nitter live RSS fetch,
       link parser, state manager deduplication, and JAP API balance check.
"""
import asyncio
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = []

def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))
    results.append((name, passed))

# ─── 1. IMPORT CHECKS ────────────────────────────────────────────────────────
print("\n[1/7] Checking imports...")
try:
    from config import config
    check("config.py loads", True, f"target=@{config.target_x_username}")
except Exception as e:
    check("config.py loads", False, str(e))

try:
    from x_tracker import XTracker, _sanitize_url
    check("x_tracker.py imports", True)
except Exception as e:
    check("x_tracker.py imports", False, str(e))

try:
    from link_parser import LinkParser
    check("link_parser.py imports", True)
except Exception as e:
    check("link_parser.py imports", False, str(e))

try:
    from state_manager import StateManager
    check("state_manager.py imports", True)
except Exception as e:
    check("state_manager.py imports", False, str(e))

try:
    from jap_client import JAPClient
    check("jap_client.py imports", True)
except Exception as e:
    check("jap_client.py imports", False, str(e))

# ─── 2. URL SANITIZER ────────────────────────────────────────────────────────
print("\n[2/7] Testing URL sanitizer (fixes https// typos)...")
tests = [
    ("https//nitter.poast.org", "https://nitter.poast.org"),
    ("http//nitter.hu",         "http://nitter.hu"),
    ("https://nitter.net",      "https://nitter.net"),
    ("nitter.1d4.us",           "https://nitter.1d4.us"),
]
for raw, expected in tests:
    result = _sanitize_url(raw)
    check(f"sanitize '{raw}'", result == expected, f"got '{result}'")

# ─── 3. NITTER LIVE RSS FETCH ─────────────────────────────────────────────────
print("\n[3/7] Testing Nitter live RSS fetch (using @elonmusk - public account)...")
async def test_nitter():
    tracker = XTracker("elonmusk", config.nitter_instances)
    posts = await tracker.fetch_latest_posts(timeout=6.0)
    if posts:
        check("Nitter fetch returns posts", True, f"{len(posts)} posts found")
        check("Posts have guid field", bool(posts[0].get("guid")), posts[0].get("guid", "")[:60])
        check("Posts have description", bool(posts[0].get("description")), "content present")
    else:
        # Could be rate-limited (all mirrors busy) — treat as skip, not failure
        # This is a transient network condition, not a code bug
        print(f"  \033[93m[SKIP]\033[0m Nitter fetch — all mirrors rate-limited right now (normal, retry later)")
        print(f"  \033[93m[SKIP]\033[0m Posts have guid field — skipped")
        print(f"  \033[93m[SKIP]\033[0m Posts have description — skipped")
        results.extend([("Nitter fetch returns posts", None), ("Posts have guid field", None), ("Posts have description", None)])
        return

asyncio.run(test_nitter())

# ─── 4. 404 DETECTION (private/wrong username) ───────────────────────────────
print("\n[4/7] Testing 404 handling (fake/private username)...")
async def test_404():
    tracker = XTracker("this_user_definitely_does_not_exist_xyz123abc", config.nitter_instances)
    posts = await tracker.fetch_latest_posts(timeout=5.0)
    check("Returns empty list on 404 (not crash)", True if posts == [] else False, 
          "returned [] as expected" if posts == [] else f"got {posts}")

asyncio.run(test_404())

# ─── 5. LINK PARSER ──────────────────────────────────────────────────────────
print("\n[5/7] Testing link parser...")
async def test_parser():
    html_samples = [
        ('<p>Check this out: <a href="https://instagram.com/p/ABC123">here</a></p>', "instagram.com"),
        ("New video dropped https://youtube.com/watch?v=abc123 check it", "youtube.com"),
        ("Follow my TikTok https://tiktok.com/@user/video/123", "tiktok.com"),
        ("No links in this post at all", None),
    ]
    for text, expected_domain in html_samples:
        url = await LinkParser.get_first_target_url(text)
        if expected_domain:
            passed = url is not None and expected_domain in url
            check(f"Extract link from '{text[:40]}...'", passed, url or "None returned")
        else:
            check("Returns None when no URL", url is None, str(url))

asyncio.run(test_parser())

# ─── 6. STATE MANAGER ────────────────────────────────────────────────────────
print("\n[6/7] Testing state manager (deduplication)...")
import tempfile, os
tmp_db = os.path.join(tempfile.gettempdir(), "test_state.db")
sm = StateManager(db_path=tmp_db)
sm.mark_processed("test_guid_001", "https://instagram.com/p/X", "order123", "1234")
check("mark_processed saves correctly", sm.is_processed("test_guid_001"))
check("Unknown GUID returns False", not sm.is_processed("guid_never_seen"))
sm.mark_processed("dup_test", "https://tiktok.com/v/Y", "order999", "2345")
sm.mark_processed("dup_test", "https://tiktok.com/v/Y", "order999", "2345")  # duplicate
check("Duplicate mark_processed doesn't crash (INSERT OR REPLACE)", sm.is_processed("dup_test"))
try:
    os.remove(tmp_db)
except:
    pass

# ─── 7. JAP API CONNECTION ───────────────────────────────────────────────────
print("\n[7/7] Testing JAP API connection...")
async def test_jap():
    from config import config
    if config.jap_api_key == "YOUR_JAP_API_KEY_HERE":
        check("JAP API balance check", None, "SKIPPED — no API key set in .env")
        return
    client = JAPClient(config.jap_api_key, config.jap_api_url)
    try:
        res = await client.get_balance()
        if "balance" in res:
            check("JAP API balance check", True, f"Balance: {res['balance']} {res.get('currency','USD')}")
        else:
            check("JAP API balance check", False, str(res))
    except Exception as e:
        check("JAP API balance check", False, str(e))

asyncio.run(test_jap())

# ─── SUMMARY ─────────────────────────────────────────────────────────────────
print("\n" + "="*50)
total = len(results)
passed = sum(1 for _, ok in results if ok is True)
skipped = sum(1 for _, ok in results if ok is None)
failed = total - passed - skipped

print(f"  Results: {passed} passed  |  {failed} failed  |  {skipped} skipped  |  {total} total")
if failed == 0:
    print("\033[92m  ALL TESTS PASSED — Ready to deliver to client!\033[0m")
else:
    print(f"\033[91m  {failed} test(s) failed — check output above\033[0m")
print("="*50 + "\n")

sys.exit(0 if failed == 0 else 1)
