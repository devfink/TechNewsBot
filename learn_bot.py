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
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002700-\U000027BF"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA70-\U0001FAFF"
        u"\U00002600-\U000026FF"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

# ==== Konfiguration ====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("UX_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("UX_TELEGRAM_CHAT_ID")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ==== Verlauf ====
HISTORY_FILE = "ux_sent_titles.txt"

def was_already_sent(title: str) -> bool:
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = f.read().splitlines()
    return title.strip() in history

def save_title(title: str):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(title.strip() + "\n")

def is_too_similar_to_recent_topics(new_title, threshold=0.8):
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        recent = f.read().splitlines()
    for old in recent[-10:]:
        similarity = difflib.SequenceMatcher(None, new_title.lower(), old.lower()).ratio()
        if similarity > threshold:
            return True
    return False

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
    recent_titles = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            recent_titles = f.read().splitlines()[-5:]

    recent_prompt_addition = (
        "Vermeide bitte diese zuletzt behandelten Themen: "
        + ", ".join(recent_titles)
        + ".\n\n"
    )
    prompt = (
        recent_prompt_addition +
        "Du bist ein erfahrener deutschsprachiger UX-Mentor. "
        "Erstelle **genau eine** tägliche Mini-Lektion für UX-Teams (Designer:innen, Researchers, Produktleute), die sich weiterentwickeln wollen.\n\n"
        "Die Themen sollen sich regelmäßig abwechseln: UX-Design, UX-Research, Usability, Microcopy, Accessibility, Prototyping oder UX-Strategie. "
        "Wiederhole kein Thema mehrmals pro Woche.\n\n"
        "Format:\n"
        "1. Ein klarer Titel (ohne Anführungszeichen)\n"
        "2. Eine verständliche Erklärung in 3–6 Sätzen mit Praxisbeispiel\n"
        "3. Optional: Ein Tipp oder eine Reflexionsfrage\n"
        "4. Optional: Ein hilfreicher Link (Blog, Tool, Artikel)\n\n"
        "Sprache: Locker, aber professionell. Keine Einleitungen wie 'heute geht es um…'. "
        "Zielgruppe: UX-Praktiker:innen mit 1–5 Jahren Erfahrung.\n\n"
        "Gib nur **eine einzelne Lektion** zurück, keine Liste und keine Aufzählung."
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

    if was_already_sent(title) or is_too_similar_to_recent_topics(title):
        print("🔁 Thema zu ähnlich oder bereits gesendet:", title)
        return "🚫 Thema wurde übersprungen."

    send_to_telegram(text)
    save_title(title)
    return "✅ UX-Lektion wurde gesendet."

# ==== Server starten ====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
