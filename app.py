import os
import json
import time
import random
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

# -------- تنظیمات --------
IG_USERNAME = "reza_429593"
IG_PASSWORD = "reza_1388"
PROXY = "socks5://127.0.0.1:10808"  # پروکسی SOCKS5 محلی روی 10808
SESSION_FILE = "instagram_cookies.json"

app = Flask(__name__)
CORS(app)

driver = None
cookies = None

def human_sleep(total=60.0, chunks=6, jitter=2.0):
    for _ in range(chunks):
        t = total / chunks + random.uniform(-jitter, jitter)
        t = max(t, 0.3)
        print(f"[sleep] {t:.1f}s...")
        time.sleep(t)

def setup_driver():
    global driver
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # پاک کردن cache
    options.add_argument('--disable-cache')  # cache رو کامل خاموش کن
    options.add_argument('--disk-cache-size=1')  # cache size رو 1 بایت کن
    options.add_argument('--disable-web-security')  # امنیت وب رو موقت خاموش کن
    options.add_argument('--disable-features=VizDisplayCompositor')  # برای لود سریع‌تر
    
    if PROXY:
        options.add_argument(f'--proxy-server={PROXY}')
        print(f"[Proxy] SOCKS5 فعال: {PROXY}")
    else:
        print("[Proxy] بدون پروکسی")
    
    options.headless = False  # False تا ببینی چی می‌شه
    
    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def clear_cache_and_cookies():
    """پاک کردن cache و کوکی‌ها (فقط بعد از لود صفحه)"""
    try:
        driver.delete_all_cookies()
        driver.execute_script("if (window.localStorage) { window.localStorage.clear(); }")
        driver.execute_script("if (window.sessionStorage) { window.sessionStorage.clear(); }")
        print("[Debug] cache و کوکی‌ها پاک شد")
    except Exception as e:
        print(f"[Debug] cache پاک نشد (OK): {e}")

def handle_cookies_popup():
    """هندل popup cookies policy IG — Decline optional cookies رو کلیک کن (با JS برای overlay)"""
    try:
        # منتظر popup
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'cookies from Instagram')]")))
        print("[Debug] cookies popup پیدا شد")
        
        # Decline optional cookies (اولویت اول، با JS click)
        try:
            decline_btn = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Decline optional cookies')]")))
            driver.execute_script("arguments[0].click();", decline_btn)
            print("[Debug] 'Decline optional cookies' با JS کلیک شد")
        except TimeoutException:
            # Allow all cookies (جایگزین)
            try:
                allow_btn = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Allow all cookies')]")))
                driver.execute_script("arguments[0].click();", allow_btn)
                print("[Debug] 'Allow all cookies' با JS کلیک شد")
            except TimeoutException:
                print("[Debug] popup پیدا نشد — ادامه...")
        
        # sleep بیشتر بعد از popup (برای animation)
        human_sleep(8, 4, 2)
        driver.save_screenshot("after_cookies.png")
        print("[Debug] popup بسته شد — screenshot: after_cookies.png")
    except TimeoutException:
        print("[Debug] هیچ cookies popup پیدا نشد — OK")
        pass

def test_proxy():
    """تست ساده پروکسی — برو به اینستاگرام و چک کن لود می‌شه"""
    try:
        driver.get("https://www.instagram.com")
        time.sleep(5)
        title = driver.title
        print(f"[Proxy Test] صفحه لود شد: {title[:50]}...")
        if "Instagram" in title:
            clear_cache_and_cookies()  # cache رو بعد از لود پاک کن
            driver.save_screenshot("proxy_test_ok.png")
            return True
        else:
            raise Exception("صفحه درست لود نشد")
    except Exception as e:
        print(f"[Proxy Test Failed] {e}")
        driver.save_screenshot("proxy_test_error.png")
        return False

def login_instagram():
    global driver, cookies
    if os.path.exists(SESSION_FILE):
        try:
            driver = setup_driver()
            driver.get("https://www.instagram.com")
            time.sleep(3)
            stored_cookies = json.load(open(SESSION_FILE))
            for cookie in stored_cookies:
                driver.add_cookie(cookie)
            driver.refresh()
            time.sleep(5)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "article")))
            print("[Success] لاگین با کوکی‌های قبلی موفق")
            cookies = stored_cookies
            return True
        except Exception as e:
            print(f"[Session] کوکی‌ها نامعتبر: {e} — لاگین جدید")
            driver.save_screenshot("session_error.png")
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
    
    driver = setup_driver()
    try:
        # تست پروکسی اول
        if not test_proxy():
            print("[Error] پروکسی کار نمی‌کنه — xray/v2ray رو چک کن و دوباره اجرا کن")
            return False
        
        driver.get("https://www.instagram.com/accounts/login/")
        clear_cache_and_cookies()  # cache رو بعد از لود پاک کن
        print("[Debug] صفحه لاگین لود شد — screenshot: login_page.png")
        driver.save_screenshot("login_page.png")
        
        # هندل cookies popup اول (مهم!)
        handle_cookies_popup()
        
        # username (loop با visibility)
        print("[Debug] جستجو برای username input...")
        username_input = None
        for i in range(8):  # 8 بار امتحان (۴۰ ثانیه)
            try:
                username_input = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.NAME, "username")))
                driver.execute_script("arguments[0].scrollIntoView(true);", username_input)  # اسکرول به فیلد
                break
            except TimeoutException:
                print(f"[Debug] username فیلد در تلاش {i+1} پیدا نشد — sleep...")
                human_sleep(5, 2, 1)
        
        if not username_input:
            raise Exception("username فیلد پیدا نشد")
        
        username_input.clear()
        username_input.send_keys(IG_USERNAME)
        print("[Debug] username وارد شد")
        human_sleep(2, 2, 0.5)
        
        # password
        print("[Debug] جستجو برای password input...")
        password_input = None
        for i in range(8):  # 8 بار امتحان
            try:
                password_input = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.NAME, "password")))
                driver.execute_script("arguments[0].scrollIntoView(true);", password_input)
                break
            except TimeoutException:
                print(f"[Debug] password فیلد در تلاش {i+1} پیدا نشد — sleep...")
                human_sleep(5, 2, 1)
        
        if not password_input:
            raise Exception("password فیلد پیدا نشد")
        
        password_input.clear()
        password_input.send_keys(IG_PASSWORD)
        print("[Debug] password وارد شد")
        human_sleep(2, 2, 0.5)
        
        # login button (با JS click)
        print("[Debug] جستجو برای login button...")
        login_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
        driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", login_button)
        print("[Debug] دکمه لاگین با JS کلیک شد")
        human_sleep(8, 4, 2)
        
        # هندل popup بعد از لاگین
        handle_cookies_popup()
        
        # چک موفقیت
        print("[Debug] چک لود صفحه اصلی...")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "article")))
        
        cookies = driver.get_cookies()
        with open(SESSION_FILE, "w") as f:
            json.dump(cookies, f)
        
        print("[Success] لاگین موفق — کوکی‌ها ذخیره شد")
        return True
        
    except Exception as e:
        print(f"[Error] لاگین ناموفق در مرحله: {e}")
        driver.save_screenshot("login_error.png")
        print("صفحه ارور رو چک کن (login_error.png)")
        if driver:
            driver.quit()
        return False

def get_all_comments(post_url, max_comments=100):
    if not driver:
        return {"success": False, "error": "not logged in"}
    
    driver.get(post_url)
    human_sleep(8, 4, 2)
    
    comments = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while len(comments) < max_comments:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        human_sleep(4, 3, 1)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        comment_elements = soup.find_all('div', class_=re.compile(r'^_a9zs|_acan'))
        
        for el in comment_elements:
            text = el.get_text(strip=True)
            if text and len(text) > 1 and text not in comments:
                comments.append(text)
                if len(comments) >= max_comments:
                    break
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print(f"[Info] همه کامنت‌ها لود شد ({len(comments)} تا)")
            break
        last_height = new_height
    
    return {"success": True, "comments": comments[:max_comments]}

# -------- لاگین اولیه --------
print("[Start] شروع لاگین با Selenium...")
if not login_instagram():
    print("[FATAL] لاگین نشد — screenshotها رو چک کن و اکانت/اینترنت رو تست کن")
    exit(1)
print("[Success] Selenium آماده — سرور شروع شد")

# -------- API --------
@app.route('/status', methods=['GET'])
def status():
    return jsonify({"logged_in": bool(cookies), "proxy": PROXY})

@app.route('/get-comments', methods=['POST'])
def get_comments_route():
    data = request.get_json() or {}
    post_url = data.get('post_url', '').strip()
    max_comments = int(data.get('max_comments', 100))
    
    if not post_url or not re.search(r'instagram\.com/(p|reel|tv)/[A-Za-z0-9_-]+', post_url):
        return jsonify({"success": False, "error": "invalid_url"}), 400
    
    print(f"[API] جمع‌آوری {max_comments} کامنت از {post_url}")
    result = get_all_comments(post_url, max_comments)
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"[Server] http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)