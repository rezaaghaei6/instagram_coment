import os
import json
import time
import random
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired, ChallengeRequired
from scraper import get_all_comments

# -------- تنظیمات --------
IG_USERNAME = "reza.aghaie4295"
IG_PASSWORD = "Reza_1388"
IG_USE_PROXY = False
IG_PROXY = "socks5://127.0.0.1:10808"
SESSION_FILE = "instagram_session.json"

if not IG_USERNAME or not IG_PASSWORD:
    raise RuntimeError("IG_USERNAME و IG_PASSWORD الزامی است")

app = Flask(__name__)
CORS(app)

client: Client = None
selenium_cookies = None

# -------- تابع sleep انسانی --------
def human_sleep(total_seconds: float = 60.0, chunks: int = 6, jitter: float = 2.0):
    remaining = total_seconds
    for i in range(chunks):
        t = total_seconds / chunks + random.uniform(-jitter, jitter)
        if t < 0.3:
            t = 0.3
        print(f"[sleep] {t:.1f}s...")
        time.sleep(t)
        remaining -= t
        if remaining <= 0:
            break

# -------- تبدیل instagrapi settings به کوکی‌های وب --------
def build_web_cookies(settings):
    auth = settings.get("authorization_data", {})
    sessionid = auth.get("sessionid")
    ds_user_id = auth.get("ds_user_id")
    if not sessionid or not ds_user_id:
        return []
    return [
        {"name": "sessionid", "value": sessionid, "domain": ".instagram.com"},
        {"name": "ds_user_id", "value": ds_user_id, "domain": ".instagram.com"},
        {"name": "csrftoken", "value": "fixed-token", "domain": ".instagram.com"},
        {"name": "ig_did", "value": settings.get("device_settings", {}).get("device", "X123"), "domain": ".instagram.com"},
        {"name": "mid", "value": settings.get("mid", "Y123"), "domain": ".instagram.com"},
    ]

# -------- تابع لاگین --------
def try_login(attempts: int = 3) -> Client:
    global client, selenium_cookies
    for attempt in range(1, attempts + 1):
        print(f"[Login] تلاش {attempt}/{attempts}")
        cl = Client()
        cl.delay_range = [5, 15]

        if IG_USE_PROXY:
            try:
                cl.set_proxy(IG_PROXY)
                print(f"[Proxy] فعال: {IG_PROXY}")
            except:
                cl.set_proxy(None)

        # if os.path.exists(SESSION_FILE) and attempt == 1:
        #     try:
        #         with open(SESSION_FILE, "r") as f:
        #             settings = json.load(f)
        #         cl.set_settings(settings)
        #         cl.relogin()
        #         print("[Success] لاگین با سشن قبلی")
        #         client = cl
        #         selenium_cookies = build_web_cookies(cl.get_settings())
        #         return cl
        #     except Exception as e:
        #         print(f"[Session] نامعتبر: {e}")

        if os.path.exists(SESSION_FILE) and attempt > 1:
            try:
                os.remove(SESSION_FILE)
                print("[Session] حذف شد (سشن خراب)")
            except:
                pass

        human_sleep(random.uniform(5, 10), 3, 2.0)

        try:
            print("[Login] لاگین جدید...")
            cl.login(IG_USERNAME, IG_PASSWORD)
            with open(SESSION_FILE, "w") as f:
                json.dump(cl.get_settings(), f)
            client = cl
            selenium_cookies = build_web_cookies(cl.get_settings())
            print("[Success] لاگین موفق")
            return cl
        except TwoFactorRequired:
            print("[Error] 2FA نیاز است — توقف")
            return None
        except ChallengeRequired:
            print("[Error] چالش امنیتی — تلاش بعدی")
        except Exception as e:
            print(f"[Error] {e}")
            time.sleep(attempt * random.uniform(2, 5))
    return None

# -------- لاگین اولیه --------
print("[Start] شروع لاگین...")
try_login(attempts=3)
if not client or not selenium_cookies:
    print("[Error] لاگین نشد")
else:
    print("[Success] آماده استفاده")

# -------- API --------
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "logged_in": bool(client),
        "session_exists": os.path.exists(SESSION_FILE),
        "proxy": IG_PROXY if IG_USE_PROXY else None
    })

@app.route('/get-comments', methods=['POST'])
def get_comments_route():
    if not client or not selenium_cookies:
        return jsonify({"success": False, "error": "not logged in"}), 401

    data = request.json or {}
    post_url = data.get('post_url', '').strip()
    max_comments = int(data.get('max_comments', 0))

    if not post_url or not re.search(r'instagram\.com/(p|reel|tv)/[A-Za-z0-9_-]+', post_url):
        return jsonify({"success": False, "error": "invalid post_url"}), 400

    print(f"[API] جمع‌آوری کامنت‌ها: {post_url}")
    result = get_all_comments(post_url, max_comments=max_comments, cookies=selenium_cookies, headless=False)
    return jsonify(result)

if __name__ == '__main__':
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 5000))
    print(f"[Server] http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
