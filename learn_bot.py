import os
import requests
import openai
from flask import Flask
from datetime import date
from dotenv import load_dotenv

# ==== .env laden ====
load_dotenv()

# ==== Flask App ====
app = Flask(__name__)

# ==== Konfiguration ====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("UX_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("UX_TELEGRAM_CHAT_ID")

# ==== OpenAI Client ====
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ==== Verlauf speichern ====
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

# ==== Telegram senden ====
def send_to_telegram(text):
    message = f"\ud83d\udcd8 UX-Lernimpuls – {date.today().strftime('%d.%m.%Y')}\n\n{text}"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, data=payload)
    print("\ud83d\udce4 Telegram gesendet:", response.status_code)

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
        "Sprache: Locker, aber professionell. Keine Einleitungen wie 'heute geht es um…'. Zielgruppe: UX-Praktiker:innen mit 1–5 Jahren Erfahrung."
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
        print("\ud83d\udd04 Bereits gesendet:", title)
        return "Thema bereits gesendet. Kein Duplikat."

    send_to_telegram(text)
    save_title(title)
    return "UX-Lektion gesendet."

# ==== Server starten ====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
