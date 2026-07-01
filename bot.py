import os
import asyncio
import logging

import google.generativeai as genai
from telegram import Update
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, ContextTypes, MessageHandler, filters


def load_env(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not TELEGRAM_TOKEN:
    raise RuntimeError("Missing TELEGRAM_TOKEN in .env or environment")

if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env or environment")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def send_reply(update: Update, text: str):
    if not update.message:
        return

    text = text[:3900]
    last_error = None

    for attempt in range(1, 4):
        try:
            await update.message.reply_text(
                text,
                connect_timeout=30,
                read_timeout=30,
                write_timeout=30,
                pool_timeout=30,
            )
            return
        except RetryAfter as exc:
            wait_seconds = int(exc.retry_after) + 1
            logger.warning("Telegram rate limit. Retrying in %s seconds.", wait_seconds)
            await asyncio.sleep(wait_seconds)
        except (TimedOut, NetworkError) as exc:
            last_error = exc
            wait_seconds = attempt * 3
            logger.warning(
                "Telegram send failed on attempt %s/3: %s. Retrying in %s seconds.",
                attempt,
                exc,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)

    logger.error("Could not send Telegram reply after retries: %s", last_error)


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()
    if not user_message:
        return

    prompt = f"""
You are a Career Guidance Expert.

Only answer career-related questions. If the user asks about anything else,
politely redirect them back to career guidance.

User Question:
{user_message}
"""

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        answer = (response.text or "").strip()
    except Exception:
        logger.exception("Gemini request failed")
        answer = "Sorry, I could not reach Gemini right now. Please try again in a moment."

    if not answer:
        answer = "I could not generate a useful answer. Please ask your career question again."

    await send_reply(update, answer)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled bot error", exc_info=context.error)


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    app.add_error_handler(error_handler)

    print("Bot running. Press Ctrl+C to stop.", flush=True)
    app.run_polling(
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
