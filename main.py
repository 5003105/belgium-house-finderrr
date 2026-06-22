import requests
import json
import os
import hashlib
from datetime import datetime

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
SEEN_FILE = "seen_listings.json"

# کوئری‌های جستجو
SEARCH_QUERIES = [
    "huis te koop Lier omgeving tuin 3 slaapkamers 300000 400000",
    "woning kopen Lier 10km tuin 3 slaapkamers prijs 300000 400000",
    "maison vendre Lier jardin 3 chambres 300000 400000 euro",
    "immoweb huis Lier tuin 3 slaapkamers te koop",
    "immovlan woning Lier omgeving tuin slaapkamers",
]

REAL_ESTATE_SITES = [
    "immoweb", "immovlan", "logic-immo", "era.be",
    "century21", "remax", "axan", "zimmo", "hebbes",
    "vastgoed", "immo", "huis", "woning"
]


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return []


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f)


def make_hash(url):
    return hashlib.md5(url.encode()).hexdigest()


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("✅ پیام تلگرام ارسال شد")
    except Exception as e:
        print(f"❌ خطا در ارسال تلگرام: {e}")


def search_serpapi(query):
    url = "https://serpapi.com/search"
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google",
        "q": query,
        "gl": "be",
        "hl": "nl",
        "num": 10,
        "location": "Belgium",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        print(f"  ✅ {len(results)} نتیجه برای: {query[:40]}...")
        return results
    except Exception as e:
        print(f"  ❌ خطا: {e}")
        return []


def is_relevant(result):
    url = result["link"].lower()
    text = (result["title"] + " " + result["snippet"]).lower()
    combined = url + " " + text

    # باید از سایت‌های ملکی باشه
    if not any(site in combined for site in REAL_ESTATE_SITES):
        return False

    # باید مرتبط با خرید باشه
    buy_keywords = ["koop", "vendre", "vente", "verkoop", "te koop", "à vendre"]
    if not any(kw in combined for kw in buy_keywords):
        return False

    return True


def format_message(new_listings, total_found):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not new_listings:
        return (
            f"🏠 <b>جستجوی روزانه خونه - Lier</b>\n"
            f"📅 {now}\n\n"
            f"🔍 {total_found} نتیجه بررسی شد\n"
            f"✅ خبر جدیدی نیست — همه قبلاً دیده شدن"
        )

    msg = (
        f"🏠 <b>خونه‌های جدید پیدا شد!</b>\n"
        f"📅 {now}\n"
        f"🆕 {len(new_listings)} آگهی جدید\n\n"
        f"📋 <b>مشخصات جستجو:</b>\n"
        f"📍 Lier + ۱۰ کیلومتر\n"
        f"💶 ۳۰۰,۰۰۰ - ۴۰۰,۰۰۰ یورو\n"
        f"🛏 ۳+ اتاق | 🌿 حیاط\n\n"
        f"{'━'*20}\n"
    )

    for i, listing in enumerate(new_listings[:8], 1):
        title = listing['title'][:55]
        snippet = listing['snippet'][:90]
        msg += (
            f"\n{i}. <b>{title}</b>\n"
            f"📝 {snippet}...\n"
            f"🔗 {listing['link']}\n"
            f"{'━'*20}\n"
        )

    if len(new_listings) > 8:
        msg += f"\n➕ {len(new_listings) - 8} آگهی دیگه هم هست"

    return msg


def main():
    print(f"🔍 شروع جستجو - {datetime.now()}")

    if not SERPAPI_KEY:
        print("❌ SERPAPI_KEY تنظیم نشده!")
        send_telegram("❌ خطا: SERPAPI_KEY تنظیم نشده!")
        return

    seen = load_seen()
    all_results = []

    for query in SEARCH_QUERIES:
        results = search_serpapi(query)
        for r in results:
            if is_relevant(r):
                all_results.append(r)

    # حذف تکراری‌ها بر اساس لینک
    unique = list({r["link"]: r for r in all_results}.values())
    total_found = len(unique)
    print(f"📊 {total_found} نتیجه منحصربه‌فرد و مرتبط")

    # فیلتر جدیدها
    new_listings = []
    new_hashes = []
    for r in unique:
        h = make_hash(r["link"])
        if h not in seen:
            new_listings.append(r)
            new_hashes.append(h)

    print(f"🆕 {len(new_listings)} آگهی جدید")

    # ارسال پیام تلگرام
    message = format_message(new_listings, total_found)
    send_telegram(message)

    # ذخیره دیده‌شده‌ها
    seen.extend(new_hashes)
    save_seen(seen[-500:])
    print("✅ تمام شد!")


if __name__ == "__main__":
    main()
