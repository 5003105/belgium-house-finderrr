import requests
import json
import os
import hashlib
from datetime import datetime

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SEEN_FILE = "seen_listings.json"

# مشخصات خونه مورد نظر
SEARCH_CONFIG = {
    "location": "Lier, Belgium",
    "radius_km": 10,
    "min_price": 300000,
    "max_price": 400000,
    "min_bedrooms": 3,
    "features": ["garden", "tuin"],
}

# سایت‌های جستجو
SEARCH_QUERIES = [
    'site:immoweb.be huis te koop Lier tuin 3 slaapkamers 300000 400000',
    'site:immovlan.be woning kopen Lier tuin 3 slaapkamers',
    'site:logic-immo.be maison vendre Lier jardin 3 chambres 300000 400000',
    'site:era.be huis te koop Lier omgeving tuin slaapkamers',
    'site:century21.be woning Lier tuin 3 slaapkamers te koop',
    'huis te koop Lier omgeving 10km tuin 3 slaapkamers 300000 400000 euro',
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


def search_google(query):
    """جستجو با Google Custom Search API (رایگان تا ۱۰۰ درخواست در روز)"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX")

    if not api_key or not cx:
        print("⚠️ Google API key یا CX تنظیم نشده")
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": 10,
        "gl": "be",
        "hl": "nl",
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return results
    except Exception as e:
        print(f"❌ خطا در جستجوی Google: {e}")
        return []


def is_relevant(result):
    """بررسی اینکه نتیجه مرتبطه یا نه"""
    text = (result["title"] + " " + result["snippet"]).lower()

    # باید از سایت‌های ملک باشه
    real_estate_sites = ["immoweb", "immovlan", "logic-immo", "era.be", 
                         "century21", "remax", "axan", "zimmo"]
    url = result["link"].lower()
    if not any(site in url for site in real_estate_sites):
        return False

    # باید کلمات مرتبط داشته باشه
    keywords = ["koop", "vendre", "vente", "lier", "slaapkamer", "chambre", 
                "tuin", "jardin", "woning", "huis", "maison"]
    if not any(kw in text for kw in keywords):
        return False

    return True


def format_message(new_listings, total_found):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if not new_listings:
        return (
            f"🏠 <b>جستجوی روزانه خونه - Lier</b>\n"
            f"📅 {now}\n\n"
            f"✅ جستجو انجام شد — {total_found} نتیجه پیدا شد\n"
            f"🔄 خبر جدیدی نیست (همه قبلاً دیده شدن)"
        )

    msg = (
        f"🏠 <b>خونه‌های جدید پیدا شد! - Lier</b>\n"
        f"📅 {now}\n"
        f"🆕 {len(new_listings)} آگهی جدید از {total_found} نتیجه\n\n"
        f"📋 <b>مشخصات جستجو:</b>\n"
        f"📍 Lier + ۱۰ کیلومتر اطراف\n"
        f"💶 ۳۰۰,۰۰۰ - ۴۰۰,۰۰۰ یورو\n"
        f"🛏 ۳+ اتاق خواب | 🌿 حیاط\n\n"
        f"━━━━━━━━━━━━━━━\n"
    )

    for i, listing in enumerate(new_listings[:10], 1):
        msg += (
            f"\n{i}. <b>{listing['title'][:60]}</b>\n"
            f"📝 {listing['snippet'][:100]}...\n"
            f"🔗 {listing['link']}\n"
            f"━━━━━━━━━━━━━━━\n"
        )

    if len(new_listings) > 10:
        msg += f"\n... و {len(new_listings) - 10} آگهی دیگه"

    return msg


def main():
    print(f"🔍 شروع جستجو - {datetime.now()}")
    seen = load_seen()
    all_results = []

    for query in SEARCH_QUERIES:
        print(f"  جستجو: {query[:50]}...")
        results = search_google(query)
        for r in results:
            if is_relevant(r):
                all_results.append(r)

    # حذف تکراری‌ها
    unique = {r["link"]: r for r in all_results}.values()
    total_found = len(list(unique))

    # فیلتر جدیدها
    new_listings = []
    new_hashes = []
    for r in unique:
        h = make_hash(r["link"])
        if h not in seen:
            new_listings.append(r)
            new_hashes.append(h)

    print(f"✅ {total_found} نتیجه یافت شد، {len(new_listings)} جدید")

    # ارسال پیام
    message = format_message(new_listings, total_found)
    send_telegram(message)

    # ذخیره دیده‌شده‌ها
    seen.extend(new_hashes)
    save_seen(seen[-500:])  # نگه‌داشتن آخرین ۵۰۰ تا


if __name__ == "__main__":
    main()
