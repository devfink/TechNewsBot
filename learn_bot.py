import os
import requests
import openai
import re
import difflib
from flask import Flask
from datetime import date
from dotenv import load_dotenv

# ==== .env laden ====
load_dotenv()

# ==== Flask App ====
app = Flask(__name__)

# ==== Funktion zum Entfernen von Emojis ====
def remove_emojis(text):
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # Emoticons
        u"\U0001F300-\U0001F5FF"  # Symbole & Piktogramme
        u"\U0001F680-\U0001F6FF"  # Transport & Karten
        u"\U0001F1E0-\U0001F1FF"  # Flaggen
        u"\U00002700-\U000027BF"  # Verschiedene Symbole
        u"\U0001F900-\U0001F9FF"  # Zusätzliche Symbole
        u"\U0001FA70-\U0001FAFF"  # Weitere Symbole
        u"\U00002600-\U000026FF"  # Wetter usw.
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

# ==== Konfiguration ====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("UX_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("UX_TELEGRAM_CHAT_ID")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ==== Verlauf speichern ====
HISTORY_FILE = "ux_sent_titles.txt"

def is_too_similar_to_recent_topics(new_text, threshold=0.8):
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        recent = f.read().splitlines()
    for old in recent[-10:]:
        similarity = difflib.SequenceMatcher(None, new_text, old.strip()).ratio()
        if similarity > threshold:
            return True
    return False

def save_current_topic(text):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(text.strip() + "\n")

# ==== Telegram senden ====
def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    clean_text = remove_emojis(text)

    payload = {
        "chat_id": CHAT_ID,
        "text": clean_text,
        "disable_web_page_preview": True
    }

    response = requests.post(url, data=payload)
    print("📤 Telegram senden…")
    print("Statuscode:", response.status_code)
    print("Antwort:", response.text)

# ==== GPT-Generierung ====
def generate_lesson():
    prompt = (
        "Du bist ein erfahrener deutschsprachiger UX-Mentor. "
        "Sende eine tägliche Mini-Lektion für UX-Teams (Designer:innen, Researchers, Produktleute), die sich weiterentwickeln wollen.\n\n"
        "Wechsle die Themen regelmäßig zwischen UX-Design, UX-Research, Usability, Microcopy, Accessibility, Prototyping oder UX-Strategie. "
        "Greife nicht mehrmals pro Woche das gleiche Thema auf.\n\n"
        "Format:\n"
        "1. Ein klarer Titel (ohne Anführungszeichen)\n"
        "2. Eine verständliche Erklärung in 3–6 Sätzen mit Praxisbeispiel\n"
        "3. Optional: Ein Tipp oder Reflexionsfrage\n"
        "4. Optional: Ein hilfreicher Link (Blog, Tool, Artikel)\n\n"
        "Sprache: Locker, aber professionell. Keine Einleitungen wie 'heute geht es um…'. Zielgruppe: UX-Praktiker:innen mit 1–5 Jahren Erfahrung. "
        "Vermeide bitte Themen, die sich stark mit den letzten Antworten überschneiden oder sehr ähnlich sind. "
        "Biete stattdessen neue, interessante Perspektiven oder Konzepte aus dem Bereich UX und UX Research."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# ==== Endpunkte ====

@app.route("/")
def home():
    return "UX-Bot ist online."

@app.route("/run")
def run_lesson():
    text = generate_lesson()
    
    title = text.splitlines()[0].strip()

    if was_already_sent(title):
        print("🔁 Bereits gesendet:", title)
        return "🚫 Thema bereits gesendet, wird übersprungen."

    send_to_telegram(text)
    save_title(title)
    return "✅ UX-Lektion wurde gesendet."
