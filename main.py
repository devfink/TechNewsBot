import feedparser
import requests
import openai
from datetime import date
import re
from flask import Flask

app = Flask(__name__)

# ==== KONFIGURATION ====
import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = "7986975854:AAH_LYH50yMaRd3lJySUb-vKnoBWrKbLTLU"
CHAT_ID = "2016595606"

# ==== OpenAI Client ====
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
    "https://www.forbes.com/ai/feed/ ",

]

# ==== MarkdownV2 escapen ====
def escape_markdown_v2(text):
    escape_chars = r"_*[]()~`>#+=|{}.!-"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

# ==== Artikel holen ====
def fetch_articles_by_feed():
    feed_articles = {}
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        if feed.entries:
            articles = []
            for entry in feed.entries[:3]:
                summary = entry.summary if hasattr(entry, "summary") else ""
                summary = summary[:600]
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": summary,
                    "source": feed.feed.title
                })
            feed_articles[feed.feed.title] = articles
    return feed_articles

# ==== GPT-Zusammenfassung ====
def summarize_top_article(feed_title, articles):
    all_text = ""
    for i, a in enumerate(articles, 1):
        all_text += (
            f"{i}. Titel: {a['title']}\n"
            f"Inhalt: {a['summary']}\n"
            f"Link: {a['link']}\n\n"
        )

    prompt = (
        f"Du bist ein deutschsprachiger Tech-News-Kurator. "
        f"Hier sind mehrere neue Artikel aus der Quelle '{feed_title}'. "
        f"Wähle den relevantesten Artikel für Tech-, UX- oder KI-Teams.\n\n"
        f"Formatiere deine Antwort im einfachen Klartext (kein Markdown!), exakt in diesem Format:\n\n"
        f"Kategorie: KI oder UX oder Tech\n"
        f"Titel: <Titel des Artikels>\n"
        f"Zusammenfassung: 1–3 Sätze über den Inhalt und warum er relevant ist\n"
        f"Quelle: <Quellenname> – <Link>\n\n"
        f"Nur ein Artikel. Kein Intro, keine Aufzählung, keine Formatierungen, kein *fett*, keine Klammern, keine Anführungszeichen.\n\n"
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

    final_message = f"📬 Tech & UX Digest – {date.today().strftime('%d.%m.%Y')}\n\n{message}"


    payload = {
        "chat_id": CHAT_ID,
        "text": final_message,
        "disable_web_page_preview": True
        # kein parse_mode!
    }

    response = requests.post(url, data=payload)
    print("📤 Telegram senden…")
    print("Statuscode:", response.status_code)
    print("Antwort:", response.text)

    if response.status_code != 200:
        print("⚠️ Telegram-Fehler – versuche Klartext...")
        fallback_payload = {
            "chat_id": CHAT_ID,
            "text": f"Tech & UX Digest – {date.today().strftime('%d.%m.%Y')}\n\n{message}"
        }
        fallback_response = requests.post(url, data=fallback_payload)
        print("Fallback Statuscode:", fallback_response.status_code)

# === Digest ausführen ===
def run_digest():
    print("📡 run_digest gestartet...")
    all_articles = fetch_articles_by_feed()
    digest_sections = []
    for source, articles in all_articles.items():
        result = summarize_top_article(source, articles)
        print("🧠 GPT-Ergebnis:", result)
        if result:
            digest_sections.append(result)

    # Nur die ersten 6 Artikel verwenden
    selected = digest_sections[:8]
    final_message = "\n\n".join(selected)
    send_to_telegram(final_message.strip())

    return "✅ Digest wurde gesendet."

# ==== Routen ====
@app.route("/")
def home():
    return "👋 Bot is alive."

@app.route("/run")
def trigger_from_web():
    print("🚀 /run wurde aufgerufen!")
    return run_digest()

# ==== Server starten ====
if __name__ == "__main__":
    from time import sleep
    sleep(1)
    app.run(host="0.0.0.0", port=81)
