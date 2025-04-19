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

# ==== Emojis entfernen ====
def remove_emojis(text):
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
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
TEXT_HISTORY_FILE = "ux_sent_texts.txt"
TOPIC_HISTORY_FILE = "ux_topic_history.txt"

# ==== Themen & Unterthemen ====
UX_TOPICS = [
    "UX-Design",
    "UX-Research",
    "Usability",
    "Microcopy",
    "Accessibility",
    "Prototyping",
    "UX-Strategie",
    "Design Systeme",
    "Interaction Design",
    "Information Architecture",
    "Service Design",
    "UX-Metriken"
]

TOPIC_PROMPT_MAPPING = {
    "UX-Design": "Wähle ein konkretes Designprinzip wie visuelle Hierarchie, Farbeinsatz oder Layout.",
    "UX-Research": "Fokussiere auf ein Research-Format wie Interviews, Diary Studies oder Usability-Tests.",
    "Usability": "Gehe auf gängige Usability-Heuristiken oder typische Stolperfallen ein.",
    "Microcopy": "Zeige, wie man hilfreiche Mikrotexte schreibt, z. B. für Fehlermeldungen oder CTAs.",
    "Accessibility": "Erkläre einen konkreten Aspekt wie Tastaturbedienbarkeit oder Farbkontraste.",
    "Prototyping": "Fokussiere auf Tools, Methoden oder Testarten für Prototypen.",
    "UX-Strategie": "Behandle strategische Themen wie UX-Roadmaps oder Stakeholder-Kommunikation.",
    "Design Systeme": "Fokussiere auf Komponenten, Konsistenz und Wartbarkeit in Designsystemen.",
    "Interaction Design": "Beschreibe z. B. States, Transitions oder Feedback bei Interaktionen.",
    "Information Architecture": "Erkläre Strukturen, Navigation oder Card Sorting.",
    "Service Design": "Gib Einblicke in Journey Maps, Touchpoints oder Backstage-Prozesse.",
    "UX-Metriken": "Zeige Metriken wie Task Success Rate, NPS oder Time on Task auf."
}

# ==== Helper ====
def get_next_topic():
    if not os.path.exists(TOPIC_HISTORY_FILE):
        return UX_TOPICS[0]
    with open(TOPIC_HISTORY_FILE, "r", encoding="utf-8") as f:
        history = f.read().splitlines()
    for topic in UX_TOPICS:
        if topic not in history[-4:]:
            return topic
    return UX_TOPICS[0]

def save_topic(topic):
    with open(TOPIC_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(topic + "\n")

def was_already_sent(title):
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = f.read().splitlines()
    return title.strip() in history

def is_too_similar_to_recent_topics(title, threshold=0.8):
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        recent = f.read().splitlines()
    for old in recent[-10:]:
        if difflib.SequenceMatcher(None, title.lower(), old.lower()).ratio() > threshold:
            return True
    return False

def is_text_too_similar(new_text, threshold=0.75):
    if not os.path.exists(TEXT_HISTORY_FILE):
        return False
    with open(TEXT_HISTORY_FILE, "r", encoding="utf-8") as f:
        texts = f.read().split("\n---\n")
    for old in texts[-10:]:
        if difflib.SequenceMatcher(None, new_text, old).ratio() > threshold:
            return True
    return False

def save_title(title):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(title.strip() + "\n")

def save_full_text(text):
    with open(TEXT_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(text.strip() + "\n---\n")

# ==== Telegram senden ====
def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": remove_emojis(text),
        "disable_web_page_preview": True
    }
    response = requests.post(url, data=payload)
    print("Statuscode:", response.status_code)

# ==== GPT-Generierung ====
def generate_lesson(topic):
    recent_titles = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            recent_titles = f.read().splitlines()[-5:]

    topic_instruction = TOPIC_PROMPT_MAPPING.get(topic, "")
    recent_prompt = "Vermeide diese zuletzt behandelten Titel: " + ", ".join(recent_titles) + ".\n"

    prompt = (
        f"{recent_prompt}\n"
        f"Du bist ein erfahrener deutschsprachiger UX-Mentor.\n"
        f"Heutiges Thema: **{topic}**. {topic_instruction}\n\n"
        "Erstelle eine tägliche Mini-Lektion für UX-Praktiker:innen mit 1–5 Jahren Erfahrung im folgenden Format:\n\n"
        "**[Titel]**\n\n"
        "**Kontext:**\n"
        "2–3 Sätze über die Bedeutung oder typischen Herausforderungen des Themas.\n\n"
        "**Praxisbeispiel:**\n"
        "Konkretes Beispiel, wie das Thema in einem Projekt oder Tool zur Anwendung kommt.\n\n"
        "**Tipp oder Reflexionsfrage:**\n"
        "Eine Anregung, wie das Thema im eigenen Team überprüft oder ausprobiert werden kann.\n\n"
        "**Weiterlesen:**\n"
        "Ein optionaler Link zu einem Tool, Blogartikel oder weiterem Material (wenn sinnvoll).\n\n"
        "Sprache: Locker, aber professionell. Kein 'Heute geht es um …'. Halte die Gesamtantwort unter 3500 Zeichen."
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
    max_attempts = 4
    attempts = 0
    topic = get_next_topic()

    while attempts < max_attempts:
        text = generate_lesson(topic)
        title = text.splitlines()[0].strip()

        if not is_too_similar_to_recent_topics(title) and not is_text_too_similar(text):
            send_to_telegram(text)
            save_title(title)
            save_full_text(text)
            save_topic(topic)
            return f"✅ UX-Lektion wurde gesendet ({title})"

        print(f"⚠️ Ähnlichkeitsprüfung nicht bestanden ({title})")
        attempts += 1

    return "🚫 Kein geeignetes Thema gefunden."

# ==== Server starten ====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
