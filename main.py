import os
import re
import time
import hashlib
import sqlite3
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from langdetect import detect
from deep_translator import GoogleTranslator
from telegram import Bot

# ======================
# CONFIGURATION
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@theuncivilizedarchive" 

MAX_POSTS_PER_RUN = 5
SLEEP_BETWEEN_POSTS_SEC = 2

# 1) Fonti RSS
FEEDS = [
    "https://theanarchistlibrary.org/listing.rss",
    "https://offgridsurvival.com/feed/",
    "https://news.mongabay.com/list/rewilding/feed/",
    "https://crimethinc.com/feed"
]

# 2) Fonti SCRAPING (Siti senza RSS)
# container: il selettore dell'elemento che contiene il link
# link_selector: il selettore specifico per l'<a> (opzionale)
SCRAPE_SOURCES = [
    {
        "name": "Survivor Library",
        "url": "http://www.survivorlibrary.com/library-download.html",
        "container": "li", 
        "filter": ".pdf" # Prende solo link che finiscono in .pdf
    },
    {
        "name": "Primitivism Writings",
        "url": "http://www.primitivism.com/writings.htm",
        "container": "p",
        "filter": "" 
    },
    {
        "name": "Machorka Books",
        "url": "https://machorka.espivblogs.net/category/books-pamphlets/",
        "container": "article h2",
        "filter": ""
    }
]

UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

TOPIC_KEYWORDS = {
    "anprim": ["anprim", "anti-civ", "primitivism", "rewilding", "wildness", "hunter-gatherer", "nature"],
    "survival": ["survival", "prepping", "off-grid", "bushcraft", "foraging", "emergency", "wilderness", "guide", "manual"],
    "urbex": ["urbex", "urban exploration", "abandoned", "infiltrating", "ruins", "decay", "underground"],
    "resources": ["pdf", "ebook", "manual", "book", "archive", "pamphlet", "download"]
}

# ======================
# DATABASE SETUP
# ======================
bot = Bot(BOT_TOKEN)
conn = sqlite3.connect("archive.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS sent (id TEXT PRIMARY KEY)")
conn.commit()

def already_sent(post_id: str) -> bool:
    cur.execute("SELECT 1 FROM sent WHERE id=?", (post_id,))
    return cur.fetchone() is not None

def save_post(post_id: str) -> None:
    cur.execute("INSERT INTO sent VALUES (?)", (post_id,))
    conn.commit()

# ======================
# TRANSLATION & TOPIC
# ======================
def translate_to_english(text: str):
    if not text or len(text) < 5: return text
    try:
        # Se il testo è troppo lungo, lo accorciamo per la traduzione
        to_translate = text[:3000]
        if detect(to_translate) == 'en': return text
        return GoogleTranslator(source='auto', target='en').translate(to_translate)
    except:
        return text

def detect_topic(title: str, text: str) -> str:
    hay = f"{title} {text}".lower()
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(kw in hay for kw in kws): return topic
    return "knowledge"

# ======================
# CORE SCRAPER
# ======================
def process_item(title, summary, link):
    post_id = hashlib.sha256(link.encode()).hexdigest()
    if already_sent(post_id):
        return False

    topic = detect_topic(title, summary)
    en_title = translate_to_english(title)
    en_text = translate_to_english(summary)
    
    emoji = {"anprim": "🌿", "survival": "🔥", "urbex": "🏚", "resources": "📚"}.get(topic, "📌")
    
    message = (
        f"{emoji} **{en_title.upper()}**\n\n"
        f"{en_text[:800]}...\n\n"
        f"🔗 **Link:** {link}\n\n"
        f"#{topic} #international #archive"
    )

    try:
        bot.send_message(chat_id=CHANNEL, text=message, parse_mode='Markdown')
        save_post(post_id)
        return True
    except Exception as e:
        print(f"Send error: {e}")
        return False

def main():
    posted = 0
    
    # --- PARTE 1: RSS FEEDS ---
    for url in FEEDS:
        if posted >= MAX_POSTS_PER_RUN: break
        feed = feedparser.parse(url)
        for e in feed.entries:
            if posted >= MAX_POSTS_PER_RUN: break
            link = getattr(e, "link", "")
            title = getattr(e, "title", "No Title")
            summary = BeautifulSoup(getattr(e, "summary", ""), "html.parser").get_text()
            if process_item(title, summary, link):
                posted += 1
                time.sleep(SLEEP_BETWEEN_POSTS_SEC)

    # --- PARTE 2: WEB SCRAPING ---
    for source in SCRAPE_SOURCES:
        if posted >= MAX_POSTS_PER_RUN: break
        try:
            res = requests.get(source["url"], headers=UA_HEADERS, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.select(source["container"])
            
            for item in items:
                if posted >= MAX_POSTS_PER_RUN: break
                a_tag = item.find("a") if item.name != "a" else item
                if not a_tag or not a_tag.get("href"): continue
                
                link = urljoin(source["url"], a_tag["href"])
                # Filtro per estensione (es. .pdf)
                if source["filter"] and not link.lower().endswith(source["filter"]):
                    continue
                
                title = a_tag.get_text(strip=True) or "Resource"
                if process_item(title, "", link):
                    posted += 1
                    time.sleep(SLEEP_BETWEEN_POSTS_SEC)
        except Exception as e:
            print(f"Scrape error on {source['url']}: {e}")

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()
