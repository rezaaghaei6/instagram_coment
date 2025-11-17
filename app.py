import os
import json
import time
import random
from flask import Flask, request, jsonify
from flask_cors import CORS
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired

# ========================================================================
# 🔥 پچ رسمی برای حذف کامل validate پydantic در instagrapi (رفع خطای Media)
# ========================================================================
from instagrapi import mixins
from pydantic import BaseModel

class NoValidateMedia(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow"
    }

mixins.media.Media = NoValidateMedia
# ========================================================================

# ------------------- تنظیمات -------------------
IG_USERNAME = "fgfgfgfg5623"
IG_PASSWORD = "reza_1388"

IG_USE_PROXY = True
IG_PROXY = "socks5://127.0.0.1:10808"

SESSION_FILE = "instagram_session.json"

app = Flask(__name__)
CORS(app)

client = None
playwright_cookies = []
challenge_data = {} 


# ------------------- رفتار انسانی -------------------
def human_sleep(total_seconds=40, chunks=5, jitter=2):
    remaining = total_seconds
    for i in range(chunks):
        portion = total_seconds / chunks
        t = max(1, portion + random.uniform(-jitter, jitter))
        remaining -= t
        print(f"[sleep] {t:.1f} ثانیه...")
        time.sleep(t)


# ------------------- تبدیل کوکی برای Playwright -------------------
def inject_client(cl: Client):
    global playwright_cookies

    cookies = cl.get_settings().get("cookies", {})
    pw = []

    for name, obj in cookies.items():
        pw.append({
            "name": name,
            "value": obj.get("value"),
            "domain": ".instagram.com",
            "path": "/",
            "httpOnly": True,
            "secure": True
        })

    playwright_cookies = pw
    print(f"[inject_client] {len(pw)} کوکی منتقل شد")


# ------------------- ارسال کد چالش به ایمیل -------------------
def send_email_security_code(cl: Client, cp_path: str):
    print("[Challenge] درخواست ارسال کد به ایمیل...")
    try:
        cl.challenge_send_method(cp_path, choice="email")
        print("[Challenge] کد به ایمیل ارسال شد ✔")
        return True
    except Exception as e:
        print(f"[Challenge] ارسال ایمیل نشد: {e}")
        return False


# ------------------- لاگین -------------------
def try_login(attempts=3):
    global client, challenge_data

    for attempt in range(1, attempts + 1):
        print(f"[Login] تلاش {attempt}/{attempts}")

        cl = Client()
        cl.delay_range = [5, 10]

        if IG_USE_PROXY:
            cl.set_proxy(IG_PROXY)
            print(f"[Proxy] فعال: {IG_PROXY}")
        else:
            cl.set_proxy(None)

        if os.path.exists(SESSION_FILE) and attempt == 1:
            try:
                cl.load_settings(SESSION_FILE)
                cl.relogin()
                client = cl
                inject_client(cl)
                print("[Login] موفق با session موجود ✔")
                return cl
            except Exception as e:
                print("[Warning] session خراب بود:", e)

        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
            print("[Session] پاک شد → device جدید ساخته می‌شود")

        human_sleep(random.uniform(20, 60))

        try:
            cl.login(IG_USERNAME, IG_PASSWORD)

            cl.dump_settings(SESSION_FILE)
            client = cl
            inject_client(cl)

            print("[Success] لاگین کامل ✔")
            return cl

        except ChallengeRequired:
            print("[Challenge] ChallengeRequired دریافت شد")

            cp_path = cl.last_json.get("challenge", {}).get("api_path")
            if not cp_path:
                print("[Challenge] api_path پیدا نشد!")
                return None

            challenge_data["cp_path"] = cp_path
            challenge_data["cl"] = cl

            send_email_security_code(cl, cp_path)

            print("[Challenge] منتظر ارسال کد هستیم...")
            return "CHALLENGE"

        except TwoFactorRequired:
            print("[2FA] فعال است → پشتیبانی نمی‌شود")
            return None

        except Exception as e:
            print(f"[Error] لاگین نشد: {e}")
            time.sleep(random.uniform(5, 15))

    return None


# ------------------- شروع لاگین اولیه -------------------
print("[Rocket] شروع لاگین اولیه …")
try_login()


# ------------------- API ها -------------------
@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "logged_in": bool(client),
        "session_exists": os.path.exists(SESSION_FILE)
    })


@app.route("/send-code-again", methods=["POST"])
def resend_code():
    if "cl" not in challenge_data:
        return jsonify({"success": False, "error": "No active challenge"}), 400

    cl = challenge_data["cl"]
    cp_path = challenge_data["cp_path"]

    ok = send_email_security_code(cl, cp_path)
    return jsonify({"success": ok})


@app.route("/submit-code", methods=["POST"])
def submit_code():
    global client

    data = request.json or {}
    code = data.get("code", "").strip()

    if "cl" not in challenge_data:
        return jsonify({"success": False, "error": "No active challenge"}), 400

    cl = challenge_data["cl"]
    cp_path = challenge_data["cp_path"]

    try:
        print(f"[Challenge] ارسال کد: {code}")
        result = cl.challenge_send_security_code(code)

        if result:
            print("[Challenge] کد صحیح بود → لاگین کامل ✔")

            cl.dump_settings(SESSION_FILE)
            client = cl
            inject_client(cl)

            return jsonify({"success": True})

        else:
            return jsonify({"success": False, "error": "wrong code"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ========================================================================
# 🔥 مسیر جدید: گرفتن کامنت با Playwright بدون خطای Pydantic و با سشن واقعی
# ========================================================================
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def get_all_comments(post_url: str, max_comments: int = 0, cookies=None, user_agent=None, headless=False, proxy: str = None):
    if cookies is None:
        cookies = []

    result = {"success": False, "post_url": post_url, "comments": [], "count": 0}

    try:
        print("[SCRAPER] شروع فرایند اسکرپینگ...")
        with sync_playwright() as p:
            browser_args = {}
            if proxy:
                browser_args["proxy"] = {"server": proxy}
                print(f"[SCRAPER] استفاده از پروکسی: {proxy}")

            browser = p.chromium.launch(headless=headless, **browser_args)
            context_args = {}
            if user_agent:
                context_args["user_agent"] = user_agent
            context = browser.new_context(**context_args)

            if cookies:
                print(f"[SCRAPER] اضافه کردن {len(cookies)} کوکی...")
                context.add_cookies(cookies)

            page = context.new_page()
            try:
                page.goto(post_url, timeout=60000)
                page.wait_for_timeout(5000)
            except PlaywrightTimeoutError as e:
                print(f"[SCRAPER] خطا در باز کردن پست: {e}")
                result["error"] = str(e)
                browser.close()
                return result

            container = None
            is_dialog = False
            for attempt in range(10):
                container = page.query_selector("div[role='dialog'] ul")
                if container:
                    is_dialog = True
                    break
                container = page.query_selector("main ul")
                if container:
                    break
                time.sleep(random.uniform(1.5, 3.0))

            if not container:
                result["error"] = "comments_container_not_found"
                browser.close()
                return result

            seen = set()
            collected = 0
            scroll_attempts = 0

            while max_comments == 0 or collected < max_comments:
                comment_items = container.query_selector_all("ul > li")
                for item in comment_items:
                    try:
                        username_el = item.query_selector("h3 a, h2 a")
                        username = username_el.inner_text().strip() if username_el else "unknown"
                        comment_el = item.query_selector("span")
                        text = comment_el.inner_text().strip() if comment_el else ""

                        if not text or f"{username}:{text}" in seen:
                            continue

                        seen.add(f"{username}:{text}")
                        collected += 1
                        result["comments"].append({"username": username, "text": text})

                        if max_comments > 0 and collected >= max_comments:
                            break
                    except:
                        continue

                if max_comments > 0 and collected >= max_comments:
                    break

                scroll_target = "document.documentElement"
                if is_dialog:
                    scroll_target = "document.query_selector('div[role=\"dialog\"] ul')"

                scroll_height_before = page.evaluate(f"{scroll_target}.scrollHeight")
                page.evaluate(f"{scroll_target}.scrollBy(0, 500)")
                time.sleep(random.uniform(1.5, 3.0))
                scroll_height_after = page.evaluate(f"{scroll_target}.scrollHeight")

                if scroll_height_after == scroll_height_before:
                    scroll_attempts += 1
                    if scroll_attempts >= 3:
                        break
                else:
                    scroll_attempts = 0

            result["success"] = True
            result["count"] = collected
            browser.close()

    except Exception as e:
        result["error"] = str(e)

    return result

@app.route("/get-comments-playwright", methods=["POST"])
def get_comments_playwright():
    data = request.json or {}
    post_url = data.get("url", "").strip()
    max_comments = int(data.get("max_comments", 50))

    cookies = []
    user_agent = None
    if client:
        cookies = [
            {"name": k, "value": v.get("value"), "domain": ".instagram.com", "path": "/", "httpOnly": True, "secure": True}
            for k, v in client.get_settings().get("cookies", {}).items()
        ]
        user_agent = client.user_agent

    return get_all_comments(
        post_url,
        max_comments=max_comments,
        cookies=cookies,
        user_agent=user_agent,
        headless=False,
        proxy=IG_PROXY
    )


# ------------------- RUN -------------------
if __name__ == "__main__":
    print("[Server] http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
