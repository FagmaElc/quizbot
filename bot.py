import os
import random
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# --- Flask для web ---
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "Фармакология Бот живёт!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# --- Данные ---
chat_members = {}
chat_ids = set()
auto_posting_enabled = {}

pharma_tasks = [
    "Пациенту назначен препарат А. Какие возможные побочные эффекты?",
    "Какой механизм действия у препарата Б?",
    "Что противопоказано при приёме препарата В?",
    "Опишите фармакокинетику препарата Г."
]

user_added_tasks = []

# --- Основные хэндлеры ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот с ситуационными задачами по фармакологии.\n"
        "Напиши /task, чтобы получить задачу."
    )

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in chat_members:
        chat_members[chat_id] = {}

    chat_members[chat_id][user.id] = {
        "id": user.id,
        "username": f"@{user.username}" if user.username else user.full_name,
        "first_name": user.first_name,
    }
    chat_ids.add(chat_id)

async def send_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    members = list(chat_members.get(chat_id, {}).values())

    if not members:
        await update.message.reply_text("Я пока никого не вижу в чате. Напиши что-нибудь, чтобы я тебя запомнил.")
        return

    # Выбираем случайного пользователя и задачу
    user = random.choice(members)
    tasks_pool = pharma_tasks + user_added_tasks
    task = random.choice(tasks_pool)

    message = f"🩺 Задача для {user['username']}:\n\n{task}"
    await update.message.reply_text(message)

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Пример: /addtask Опишите механизм действия препарата X")
        return
    task = " ".join(context.args)
    user_added_tasks.append(task)
    await update.message.reply_text("✅ Ваша задача добавлена!")

async def auto_post(app):
    await asyncio.sleep(10)
    while True:
        for chat_id in chat_ids:
            if not auto_posting_enabled.get(chat_id, True):
                continue
            members = list(chat_members.get(chat_id, {}).values())
            if members:
                user = random.choice(members)
                task = random.choice(pharma_tasks + user_added_tasks)
                try:
                    await app.bot.send_message(chat_id=chat_id, text=f"⏰ Автозадача для {user['username']}:\n\n{task}")
                except Exception as e:
                    print(f"Ошибка отправки автозадачи в чат {chat_id}: {e}")
        await asyncio.sleep(3600)  # каждый час

async def disable_autopost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    auto_posting_enabled[chat_id] = False
    await update.message.reply_text("🔕 Автозадачи отключены в этом чате.")

async def enable_autopost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    auto_posting_enabled[chat_id] = True
    await update.message.reply_text("🔔 Автозадачи включены в этом чате.")

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Команда /test сработала!")

def main():
    Thread(target=run_flask).start()

    TOKEN = os.environ["BOT_TOKEN"]
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("task", send_task))
    app.add_handler(CommandHandler("addtask", add_task))
    app.add_handler(CommandHandler("disable_autopost", disable_autopost))
    app.add_handler(CommandHandler("enable_autopost", enable_autopost))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_user))

    async def after_startup(app):
        asyncio.create_task(auto_post(app))

    print("🧪 Фармакология Бот запущен!")
    app.run_polling(post_init=after_startup)

if __name__ == "__main__":
    main()
