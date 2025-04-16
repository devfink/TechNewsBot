import openai
import requests
import os
from datetime import date

# === UX-Bot Umgebungsvariablen ===
OPENAI_API_KEY = os.getenv("UX_OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("UX_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("UX_TELEGRAM_CHAT_ID")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def send_to_telegram(text):
    message = f"📘 UX-Lernimpuls – {date.today().strftime('%d.%m.%Y')}\n\n{text}"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, data=payload)
    print("📤 Telegram gesendet:", response.status_code)

def generate_lesson():
    prompt = (
        "Du bist ein UX-Mentor. "
        "Schicke täglich eine Lektion zu UX-Design oder UX-Research. "
        "Erkläre es in einfachen Worten, gib ein Beispiel und einen weiterführenden Tipp oder Link."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    text = generate_lesson()
    send_to_telegram(text)
