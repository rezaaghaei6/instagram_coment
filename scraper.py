# scraper.py
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

LOG_PREFIX = "[SCRAPER-LOG]"

def log(msg):
    print(f"{LOG_PREFIX} {msg}")

def human_sleep(min_s=1.0, max_s=3.0):
    t = random.uniform(min_s, max_s)
    log(f"[sleep] {t:.2f}s...")
    time.sleep(t)

def sanitize_cookies(cookies):
    """
    تبدیل کوکی‌ها به فرمت صحیح Playwright
    """
    valid_cookies = []
    for c in cookies:
        if "name" not in c or "value" not in c:
            continue
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain") or ".instagram.com",
            "path": c.get("path") or "/",
            "httpOnly": c.get("httpOnly", True),
            "secure": c.get("secure", True),
        }
        valid_cookies.append(cookie)
    return valid_cookies

def get_all_comments(post_url: str, max_comments: int = 0, cookies=None, headless=True, proxy: str = None):
    """
    جمع‌آوری کامنت‌ها با Playwright و اسکرول روی کانتینر
    """
    if cookies is None:
        cookies = []

    result = {"success": False, "post_url": post_url, "comments": [], "count": 0}

    try:
        log("شروع فرایند اسکرپینگ...")
        with sync_playwright() as p:
            browser_args = {}
            if proxy:
                browser_args["proxy"] = {"server": proxy}
                log(f"[Proxy] استفاده می‌شود: {proxy}")

            browser = p.chromium.launch(headless=headless, **browser_args)
            context = browser.new_context()

            # اضافه کردن کوکی‌ها
            if cookies:
                log(f"در حال اضافه کردن {len(cookies)} کوکی معتبر...")
                context.add_cookies(sanitize_cookies(cookies))

            page = context.new_page()
            log("باز کردن صفحه پست اینستاگرام...")
            try:
                page.goto(post_url, timeout=60000)
                page.wait_for_timeout(5000)
            except PlaywrightTimeoutError as e:
                log(f"❌ خطای بحرانی در باز کردن پست: {e}")
                result["error"] = str(e)
                browser.close()
                return result

            # پیدا کردن کانتینر کامنت با تلاش چندباره
            container = None
            is_dialog = False
            for attempt in range(10):
                log(f"تلاش {attempt+1} برای پیدا کردن کانتینر کامنت...")
                container = page.query_selector("div[role='dialog'] ul")
                if container:
                    is_dialog = True
                    log("کانتینر کامنت در دیالوگ پیدا شد.")
                    break
                container = page.query_selector("main ul")
                if container:
                    log("کانتینر کامنت در صفحه اصلی پیدا شد.")
                    break
                human_sleep(2, 4)

            if not container:
                log("❌ کانتینر کامنت پیدا نشد، پایان اسکرپینگ")
                result["error"] = "comments_container_not_found"
                browser.close()
                return result

            # اسکرول روی کانتینر و جمع‌آوری کامنت‌ها
            seen = set()
            collected = 0
            scroll_attempts = 0

            while max_comments == 0 or collected < max_comments:
                comment_items = container.query_selector_all("ul > li")
                log(f"{len(comment_items)} کامنت خام یافت شد.")

                for item in comment_items:
                    try:
                        # استخراج نام کاربری
                        username_el = item.query_selector("h3 a, h2 a")
                        username = username_el.inner_text().strip() if username_el else "unknown"

                        # استخراج متن کامنت
                        comment_el = item.query_selector("span")
                        text = comment_el.inner_text().strip() if comment_el else ""

                        if not text or f"{username}:{text}" in seen:
                            continue

                        seen.add(f"{username}:{text}")
                        collected += 1
                        result["comments"].append({"username": username, "text": text})
                        log(f"[{collected}] {username}: {text[:40]}...")

                        if max_comments > 0 and collected >= max_comments:
                            break
                    except Exception as e:
                        log(f"خطا در پردازش کامنت: {e}")

                if max_comments > 0 and collected >= max_comments:
                    break

                # اسکرول کانتینر
                scroll_target = "document.documentElement"
                if is_dialog:
                    scroll_target = "document.querySelector(\"div[role='dialog'] ul\")"

                scroll_height_before = page.evaluate(f"{scroll_target}.scrollHeight")
                page.evaluate(f"{scroll_target}.scrollBy(0, 500)")
                human_sleep(1.5, 3.0)
                scroll_height_after = page.evaluate(f"{scroll_target}.scrollHeight")

                if scroll_height_after == scroll_height_before:
                    scroll_attempts += 1
                    if scroll_attempts >= 3:
                        log("اسکرول به انتها رسید، پایان جمع‌آوری کامنت‌ها")
                        break
                else:
                    scroll_attempts = 0

            result["success"] = True
            result["count"] = collected
            browser.close()

    except Exception as e:
        log(f"❌ خطای بحرانی: {e}")
        result["error"] = str(e)

    return result
