import feedparser
import requests
import openai
from datetime import date, datetime, timedelta
import re
import hashlib
import json
import os
from flask import Flask

app = Flask(__name__)

# ==== KONFIGURATION ====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SENT_ARTICLES_FILE = "sent_articles.json"
EXCLUDE_KEYWORDS = ["Test", "Review", "Fahrbericht", "Elektroauto", "SUV", "Hyundai", "Tesla", "BMW", "Lucid", "Reichweite"]

client = openai.OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = [
    "https://www.theverge.com/rss/index.xml",
    "https://www.techcrunch.com/feed/",
    "https://www.smashingmagazine.com/feed/",
    "https://uxdesign.cc/feed",
    "https://www.heise.de/rss/heise-atom.xml",
    "https://openai.com/blog/rss.xml",
    "https://www.technologyreview.com/feed/", 
    "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/technology/rss.xml",
    "https://www.bbc.com/news/technology/rss.xml",
    "https://www.engadget.com/rss.xml",
    "https://www.forbes.com/ai/feed/"
]

# ==== Hilfsfunktionen ====
def escape_markdown_v2(text):
    escape_chars = r"_*[]()~`>#+=|{}.!-"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

def generate_article_hash(article):
    return hashlib.sha256((article['title'] + article['link']).encode()).hexdigest()

def load_sent_articles_full():
    if os.path.exists(SENT_ARTICLES_FILE):
        with open(SENT_ARTICLES_FILE, "r") as f:
            return json.load(f)
    return []

def save_sent_articles_full(hashes_and_sources):
    all_sends = load_sent_articles_full()
    today = date.today().isoformat()
    for h, source in hashes_and_sources:
        all_sends.append({"hash": h, "source": source, "date": today})
    with open(SENT_ARTICLES_FILE, "w") as f:
        json.dump(all_sends, f)

def get_dynamic_source_penalty(source_title):
    days_back = 7
    since_date = datetime.now() - timedelta(days=days_back)
    all_sends = load_sent_articles_full()
    recent = [a for a in all_sends if a["source"] == source_title and datetime.fromisoformat(a["date"]) > since_date]
    return len(recent)

def is_irrelevant(article):
    text = f"{article['title']} {article['summary']}`".lower()
    return any(keyword.lower() in text for keyword in EXCLUDE_KEYWORDS)

# ==== Artikel holen & filtern ====
def fetch_and_filter_articles():
    articles = []
    sent_hashes = {a["hash"] for a in load_sent_articles_full()}
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        source = feed.feed.title if hasattr(feed.feed, "title") else "Unbekannt"
        for entry in feed.entries[:3]:
            summary = entry.summary if hasattr(entry, "summary") else ""
            article = {
                "title": entry.title,
                "link": entry.link,
                "summary": summary[:600],
                "source": source
            }
            if is_irrelevant(article):
                continue
            article_hash = generate_article_hash(article)
            if article_hash in sent_hashes:
                continue
            article["hash"] = article_hash
            article["penalty"] = get_dynamic_source_penalty(source)
            articles.append(article)
    return sorted(articles, key=lambda a: a["penalty"])

# ==== GPT-Zusammenfassung ====
def summarize_top_article(source, articles):
    all_text = ""
    for i, a in enumerate(articles, 1):
        all_text += (
            f"{i}. Titel: {a['title']}\n"
            f"Inhalt: {a['summary']}\n"
            f"Link: {a['link']}\n\n"
        )
    prompt = (
        f"Du bist ein deutschsprachiger Tech-News-Kurator. Hier sind mehrere neue Artikel aus der Quelle '{source}'. "
        f"Wähle den relevantesten Artikel für Tech-, UX- oder KI-Teams.\n\n"
        f"Formatiere deine Antwort im einfachen Klartext (kein Markdown!), exakt in diesem Format:\n\n"
        f"Kategorie: KI oder UX oder Tech\n"
        f"Titel: <Titel des Artikels>\n"
        f"Zusammenfassung: 1–3 Sätze über den Inhalt und warum er relevant ist\n"
        f"Quelle: <Quellenname> – <Link>\n\n"
        f"Nur ein Artikel. Kein Intro, keine Aufzählung, kein *fett*, keine Klammern, keine Anführungszeichen.\n\n"
        f"Hier die Artikel:\n\n{all_text}"
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()

# ==== Telegram senden ====
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    final_message = f"\U0001F4EC Tech & UX Digest – {date.today().strftime('%d.%m.%Y')}\n\n{message}"
    payload = {
        "chat_id": CHAT_ID,
        "text": final_message,
        "disable_web_page_preview": True
    }
    response = requests.post(url, data=payload)
    print("\U0001F4E4 Telegram senden…")
    print("Statuscode:", response.status_code)
    print("Antwort:", response.text)

# ==== Digest ====
def run_digest():
    print("\U0001F4E1 run_digest gestartet...")
    all_articles = fetch_and_filter_articles()
    digest_sections = []
    used_hashes = set()
    for source in set(a["source"] for a in all_articles):
        articles_from_source = [a for a in all_articles if a["source"] == source][:3]
        if not articles_from_source:
            continue
        result = summarize_top_article(source, articles_from_source)
        print("\U0001F9E0 GPT-Ergebnis:", result)
        if result:
            digest_sections.append(result)
            used_hashes.update([(a["hash"], source) for a in articles_from_source])
        if len(digest_sections) >= 6:
            break
    if digest_sections:
        save_sent_articles_full(used_hashes)
        final_message = "\n\n".join(digest_sections)
        send_to_telegram(final_message.strip())
    return "\u2705 Digest wurde gesendet."

# ==== Routen ====
@app.route("/")
def home():
    return "\U0001F44B Bot is alive."

@app.route("/run")
def trigger_from_web():
    print("\U0001F680 /run wurde aufgerufen!")
    return run_digest()

if __name__ == "__main__":
    from time import sleep
    sleep(1)
    app.run(host="0.0.0.0", port=81)
