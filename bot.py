import random
import os
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Flask-приложение
app = Flask(__name__)

# Задачи (оставим без изменений)
tasks = [
    # ... твой список задач здесь ...
]

# Состояние пользователей
user_current_tasks = {}

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

application = Application.builder().token(BOT_TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я бот по фармакологии. Напиши /quiz чтобы начать викторину.")

# Команда /quiz
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = random.choice(tasks)
    user_id = update.effective_user.id
    user_current_tasks[user_id] = task
    await update.message.reply_text(f"🧠 Ситуационная задача:\n{task['question']}")

# Обработка ответа
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answer = update.message.text.strip().lower()

    if user_id in user_current_tasks:
        correct_answer = user_current_tasks[user_id]["answer"].lower()
        if user_answer == correct_answer:
            await update.message.reply_text("✅ Верно! Напиши /quiz для следующей задачи.")
        else:
            await update.message.reply_text(f"❌ Неверно. Правильный ответ: {correct_answer}\nНапиши /quiz для следующей задачи.")
        del user_current_tasks[user_id]
    else:
        await update.message.reply_text("Напиши /quiz чтобы начать новую задачу.")

# Регистрируем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("quiz", quiz))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook endpoint для Telegram
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.from_dict(data)
    # Для запуска async функции из sync обработчика используем run_sync
    application.create_task(application.process_update(update))
    return Response("ok", status=200)

# Endpoint для проверки (UptimeRobot)
@app.route("/", methods=["GET"])
def index():
    return "✅ Бот работает"

# Установка webhook при старте Flask-приложения
@app.before_first_request
def set_webhook():
    application.bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")

if __name__ == "__main__":
    # Запуск Flask-приложения
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
