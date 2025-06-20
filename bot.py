import os
import random
import asyncio
import threading
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Flask-приложение для UptimeRobot ping
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Бот работает!"

# Вопросы
questions = [
    ("Сколько будет 2 + 2?", ["3", "4", "5", "6"], 1),
    ("Столица Франции?", ["Берлин", "Лондон", "Париж", "Рим"], 2),
    ("Какой язык мы используем?", ["Java", "C++", "Python", "Ruby"], 2),
    # Добавь свои 27+ вопросов по аналогии
]

games = {}  # chat_id -> игра

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши /join чтобы присоединиться к игре.")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = games.setdefault(chat_id, {
        "players": {},
        "questions": random.sample(questions, len(questions)),
        "current_q_index": 0,
        "started": False,
        "answers": {},
    })

    if game["started"]:
        await update.message.reply_text("Игра уже началась.")
        return

    if user.id not in game["players"]:
        game["players"][user.id] = {"score": 0}
        await update.message.reply_text(f"{user.first_name} присоединился к игре!")
    else:
        await update.message.reply_text("Вы уже в игре.")

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)

    if not game or not game["players"]:
        return await update.message.reply_text("Нет игроков. Введите /join")

    if game["started"]:
        return await update.message.reply_text("Игра уже началась.")

    game["started"] = True
    game["current_q_index"] = 0
    await send_question_all(context, chat_id)

async def send_question_all(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games[chat_id]
    q_index = game["current_q_index"]
    if q_index >= len(game["questions"]):
        return await show_results(context, chat_id)

    q_text, options, correct_idx = game["questions"][q_index]
    game["answers"] = {}

    for user_id in game["players"]:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(opt, callback_data=f"{user_id}:{i}")]
            for i, opt in enumerate(options)
        ])
        try:
            await context.bot.send_message(user_id, f"Вопрос {q_index + 1}: {q_text}", reply_markup=keyboard)
        except:
            pass  # Игрок не принимает личные сообщения

    asyncio.create_task(question_timeout(context, chat_id, q_index))

async def question_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int, q_index: int):
    await asyncio.sleep(30)
    game = games.get(chat_id)
    if not game or game["current_q_index"] != q_index:
        return

    for user_id in game["players"]:
        if user_id not in game["answers"]:
            await context.bot.send_message(user_id, "⏰ Время вышло. Ответ не засчитан.")

    game["current_q_index"] += 1
    await send_question_all(context, chat_id)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid_str, selected_str = query.data.split(":")
    user_id = int(uid_str)
    selected = int(selected_str)

    if query.from_user.id != user_id:
        return await query.answer("Это не ваш вопрос!", show_alert=True)

    chat_id = next((cid for cid, g in games.items() if user_id in g["players"]), None)
    if not chat_id:
        return await query.edit_message_text("Ошибка: игра не найдена.")

    game = games[chat_id]

    if user_id in game["answers"]:
        return await query.answer("Вы уже ответили.", show_alert=True)

    q_index = game["current_q_index"]
    _, options, correct_idx = game["questions"][q_index]

    if selected == correct_idx:
        game["players"][user_id]["score"] += 1
        await query.edit_message_text(query.message.text + "\n✅ Верно!")
    else:
        await query.edit_message_text(query.message.text + "\n❌ Неверно!")

    game["answers"][user_id] = True

    if len(game["answers"]) == len(game["players"]):
        game["current_q_index"] += 1
        await send_question_all(context, chat_id)

async def show_results(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games[chat_id]
    results = sorted(game["players"].items(), key=lambda x: x[1]["score"], reverse=True)
    text = "🏁 Игра окончена! Результаты:\n\n"
    for idx, (uid, data) in enumerate(results, start=1):
        user = await context.bot.get_chat(uid)
        text += f"{idx}. {user.first_name}: {data['score']} баллов\n"
    winner = await context.bot.get_chat(results[0][0])
    text += f"\n🏆 Победитель: {winner.first_name}"
    await context.bot.send_message(chat_id, text)
    del games[chat_id]

# Основной Telegram бот
async def telegram_main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CallbackQueryHandler(button))

    print("🤖 Бот запущен.")
    await app.run_polling()

# Запуск Flask и Telegram-бота
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=port)).start()
    asyncio.run(telegram_main())
