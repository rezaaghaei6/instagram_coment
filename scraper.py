# scraper.py
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

LOG_PREFIX = "[SCRAPER-LOG]"

def log(msg):
    print(f"{LOG_PREFIX} {msg}")

def human_sleep(min_s=1.0, max_s=3.0):
    t = random.uniform(min_s, max_s)
    log(f"[sleep] {t:.2f}s...")
    time.sleep(t)

def sanitize_cookies(cookies):
    """
    تبدیل کوکی‌ها به فرمت Selenium
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

def get_all_comments(post_url: str, max_comments: int = 0, cookies=None, user_agent=None, headless=True, proxy: str = None):
    """
    جمع‌آوری کامنت‌ها با Selenium
    cookies + user_agent → از session واقعی instagrapi
    """
    if cookies is None:
        cookies = []

    result = {"success": False, "post_url": post_url, "comments": [], "count": 0}

    try:
        log("شروع فرایند اسکرپینگ با Selenium...")

        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--log-level=3")

        if user_agent:
            chrome_options.add_argument(f"user-agent={user_agent}")

        if proxy:
            chrome_options.add_argument(f"--proxy-server={proxy}")
            log(f"[Proxy] استفاده می‌شود: {proxy}")

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(60)

        # باز کردن صفحه اصلی اینستاگرام برای set کردن کوکی‌ها
        driver.get("https://www.instagram.com/")
        human_sleep(2, 4)

        # اضافه کردن کوکی‌ها
        if cookies:
            log(f"در حال اضافه کردن {len(cookies)} کوکی معتبر...")
            for c in sanitize_cookies(cookies):
                try:
                    driver.add_cookie(c)
                except Exception as e:
                    log(f"خطا در اضافه کردن کوکی: {e}")

        # باز کردن صفحه پست
        driver.get(post_url)
        human_sleep(3, 5)

        # پیدا کردن کانتینر کامنت
        try:
            container = driver.find_element(By.CSS_SELECTOR, "ul.XQXOT")  # کانتینر کامنت در پست‌ها
        except NoSuchElementException:
            log("❌ کانتینر کامنت پیدا نشد")
            result["error"] = "comments_container_not_found"
            driver.quit()
            return result

        seen = set()
        collected = 0
        scroll_attempts = 0

        while max_comments == 0 or collected < max_comments:
            comment_items = container.find_elements(By.CSS_SELECTOR, "li")
            log(f"{len(comment_items)} کامنت خام یافت شد.")

            for item in comment_items:
                try:
                    username_el = item.find_element(By.CSS_SELECTOR, "h3 a")
                    username = username_el.text.strip()
                    comment_el = item.find_element(By.CSS_SELECTOR, "span")
                    text = comment_el.text.strip()

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

            # اسکرول به پایین کانتینر
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
            human_sleep(1.5, 3.0)

            # بررسی پایان اسکرول
            new_height = driver.execute_script("return arguments[0].scrollHeight", container)
            if new_height == 0 or scroll_attempts >= 5:
                log("اسکرول به انتها رسید")
                break
            scroll_attempts += 1

        result["success"] = True
        result["count"] = collected
        driver.quit()

    except TimeoutException as e:
        log(f"❌ Timeout در باز کردن پست: {e}")
        result["error"] = str(e)
    except WebDriverException as e:
        log(f"❌ خطای WebDriver: {e}")
        result["error"] = str(e)
    except Exception as e:
        log(f"❌ خطای بحرانی: {e}")
        result["error"] = str(e)

    return result
