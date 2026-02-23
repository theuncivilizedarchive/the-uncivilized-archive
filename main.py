import os, re, time, hashlib, sqlite3, requests, feedparser
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from langdetect import detect
from deep_translator import GoogleTranslator
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@TheUncivilizedArchive" 

# CONFIG TEST
MAX_POSTS_PER_RUN = 10 
SLEEP_BETWEEN_POSTS_SEC = 2

FEEDS = ["https://www.prepperwebsite.com/feed/", "https://survivalblog.com/feed/", "https://news.mongabay.com/feed/", "https://theanarchistlibrary.org/listing.rss"]
SCRAPE_SOURCES = [{"name": "Urbex Hub", "url": "https://urbexhub.com/", "container": "h2.entry-title", "filter": ""}]

bot = Bot(BOT_TOKEN)

def translate_to_english(text):
    if not text or len(text) < 5: return text
    try:
        if detect(text[:1000]) == 'en': return text
        return GoogleTranslator(source='auto', target='en').translate(text[:2000])
    except: return text

def process_item(title, summary, link):
    en_title = translate_to_english(title)
    en_text = translate_to_english(summary)
    message = f"🧪 **TEST POST**\n\n📌 **{en_title.upper()}**\n\n{en_text[:500]}...\n\n🔗 {link}"
    try:
        bot.send_message(chat_id=CHANNEL, text=message, parse_mode='Markdown')
        print(f"Test Sent: {title}")
        return True
    except Exception as e:
        print(f"Error: {e}"); return False

def main():
    posted = 0
    for url in FEEDS:
        if posted >= MAX_POSTS_PER_RUN: break
        feed = feedparser.parse(url)
        for e in feed.entries:
            if posted >= MAX_POSTS_PER_RUN: break
            if process_item(e.title, e.summary if 'summary' in e else "", e.link):
                posted += 1; time.sleep(SLEEP_BETWEEN_POSTS_SEC)

if __name__ == "__main__":
    main()
