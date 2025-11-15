# scraper.py
import time
import random
from playwright.sync_api import sync_playwright

LOG_PREFIX = "[SCRAPER-LOG]"

def log(msg):
    print(f"{LOG_PREFIX} {msg}")

def human_sleep(min_s=1.0, max_s=3.0):
    t = random.uniform(min_s, max_s)
    log(f"[sleep] {t:.2f}s...")
    time.sleep(t)

def get_all_comments(post_url: str, max_comments: int = 0, cookies=None, headless=True):
    """
    جمع‌آوری کامنت‌ها با Playwright و اسکرول روی کانتینر
    """
    if cookies is None:
        cookies = []

    result = {"success": False, "post_url": post_url, "comments": [], "count": 0}

    try:
        log("شروع فرایند اسکرپینگ...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()

            # اضافه کردن کوکی‌ها
            if cookies:
                log("در حال اضافه کردن کوکی‌ها...")
                context.add_cookies(cookies)

            page = context.new_page()
            log("باز کردن صفحه پست اینستاگرام...")
            page.goto(post_url)
            page.wait_for_timeout(5000)

            # پیدا کردن کانتینر کامنت
            container = None
            for attempt in range(5):
                log(f"تلاش {attempt+1} برای پیدا کردن کانتینر کامنت...")
                container = page.query_selector("ul.XQXOT, div[role='dialog'] ul")
                if container:
                    log("کانتینر کامنت پیدا شد.")
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
                comment_items = container.query_selector_all("li div.C4VMK span, li span")
                log(f"{len(comment_items)} کامنت خام یافت شد.")

                for c in comment_items:
                    text = c.inner_text().strip()
                    if not text or text in seen:
                        continue
                    try:
                        parent = c.query_selector("..")
                        username = parent.query_selector("h3 a").inner_text().strip()
                    except Exception:
                        username = "unknown"

                    seen.add(text)
                    collected += 1
                    result["comments"].append({"username": username, "text": text})
                    log(f"[{collected}] {username}: {text[:40]}...")

                    if max_comments > 0 and collected >= max_comments:
                        result["success"] = True
                        result["count"] = collected
                        browser.close()
                        return result

                # اسکرول کانتینر
                scroll_height_before = page.evaluate("(el) => el.scrollHeight", container)
                page.evaluate("(el) => el.scrollBy(0, 500)", container)
                human_sleep(1.5, 3.0)
                scroll_height_after = page.evaluate("(el) => el.scrollHeight", container)

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
