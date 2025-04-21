import os
import json
import requests
import openai
import re
import difflib
import random
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
USED_TOPICS_FILE = "ux_used_curriculum_topics.txt"
CURRICULUM_FILE = "ux_curriculum.json"

# ==== Curriculum laden ====
with open(CURRICULUM_FILE, "r", encoding="utf-8") as f:
    CURRICULUM = json.load(f)

def load_used_topics():
    if not os.path.exists(USED_TOPICS_FILE):
        return []
    with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def save_used_topic(topic_path):
    with open(USED_TOPICS_FILE, "a", encoding="utf-8") as f:
        f.write(topic_path + "\n")

def get_all_topic_paths():
    paths = []
    for category, levels in CURRICULUM.items():
        for level, topics in levels.items():
            for topic in topics:
                paths.append(f"{category} > {level} > {topic}")
    return paths

def get_next_curriculum_topic():
    used = set(load_used_topics())
    all_topics = get_all_topic_paths()
    unused = [t for t in all_topics if t not in used]
    if not unused:
        return None
    selected = random.choice(unused)
    save_used_topic(selected)
    return selected.split(" > ")[-1]

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

def save_topic(topic):
    with open(TOPIC_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(topic + "\n")

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
    prompt = (
        f"Du bist ein erfahrener deutschsprachiger UX-Mentor.\n"
        f"Heutiges Thema: {topic}\n"
        "Erkläre das Thema praxisnah in einem Mini-Lektion Format:\n"
        "1. Titel\n"
        "2. Erklärung mit Beispiel (5–10 Sätze)\n"
        "3. Optional: Verständliches Praxisbespiel\n"
        "5. Optional: Cheat Sheet mit den wichtigsten Infos\n"
        "4. Optional: hilfreicher Link\n\n"
        "Sprache: Locker, aber professionell. Kein 'Heute geht es um …'."
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
    topic = get_next_curriculum_topic()

    if not topic:
        return "✅ Alle Curriculum-Themen wurden bereits verwendet."

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
