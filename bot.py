import os
import random
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# === 🔐 Вставь сюда свой токен ===
BOT_TOKEN = "7630074850:AAFUMyj-EYzvWjBoHdymTB8Fdemk7KbIcAY"

# --- Flask сервер ---
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "Баба Маня живёт 🔮"

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000)

# --- Вопросы ---
QUESTIONS = [("2+2=?", ["3", "4", "5", "6"], 1)]  # ⚠️ Укорочено для примера

# --- Класс игры ---
class QuizGame:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = []
        self.scores = {}
        self.current_q = -1
        self.q_order = random.sample(range(len(QUESTIONS)), len(QUESTIONS))
        self.active = False
        self.answered = False

    def add_player(self, user_id):
        if user_id not in self.players:
            self.players.append(user_id)
            self.scores[user_id] = 0

    def next_question(self):
        self.current_q += 1
        self.answered = False
        q_index = self.q_order[self.current_q]
        return QUESTIONS[q_index]

games = {}

# --- Обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я бот-викторина. Напиши /quiz чтобы начать игру.")

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id in games and games[chat.id].active:
        await update.message.reply_text("Игра уже идёт!")
        return

    games[chat.id] = QuizGame(chat.id)
    kb = [[InlineKeyboardButton("👤 Присоединиться", callback_data="join")]]
    await update.message.reply_text("🎮 Нажмите кнопку, чтобы присоединиться (10 сек)", reply_markup=InlineKeyboardMarkup(kb))

    await asyncio.sleep(10)
    game = games.get(chat.id)
    if not game or not game.players:
        await context.bot.send_message(chat.id, "⛔ Никто не присоединился.")
        games.pop(chat.id, None)
        return

    game.active = True
    await context.bot.send_message(chat.id, "🚀 Начинаем игру!")
    await send_next_question(context, game)

async def join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    chat_id = q.message.chat.id

    game = games.get(chat_id)
    if not game or game.active:
        return await q.answer("❌ Уже началось или не создано.")

    game.add_player(user.id)
    await q.answer("🎉 Вы в игре!")

async def send_next_question(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    if game.current_q + 1 >= len(QUESTIONS):
        return await finish_quiz(context, game)

    text, options, correct_index = game.next_question()
    kb = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(options)]
    await context.bot.send_message(game.chat_id, f"❓ {text}", reply_markup=InlineKeyboardMarkup(kb))
    context.application.create_task(wait_answer_timeout(context, game))

async def wait_answer_timeout(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    await asyncio.sleep(15)
    if not game.answered:
        await context.bot.send_message(game.chat_id, "⌛ Время вышло!")
        await send_next_question(context, game)

async def answer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    cid = q.message.chat.id
    game = games.get(cid)
    if not game or not game.active or game.answered or user.id not in game.players:
        return

    idx = int(q.data.split(":")[1])
    _, _, correct = QUESTIONS[game.q_order[game.current_q]]
    game.answered = True

    if idx == correct:
        game.scores[user.id] += 1
        await context.bot.send_message(cid, f"✅ {user.first_name} — правильно!")
    else:
        await context.bot.send_message(cid, f"❌ {user.first_name} — ошибка.")

    await send_next_question(context, game)

async def finish_quiz(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    scores = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    result = "🏁 Игра завершена!\n\n"
    for uid, score in scores:
        user = await context.bot.get_chat_member(game.chat_id, uid)
        name = user.user.first_name
        result += f"{name}: {score} очков\n"

    await context.bot.send_message(game.chat_id, result)
    games.pop(game.chat_id)

# --- Запуск ---
async def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CallbackQueryHandler(join_cb, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(answer_cb, pattern="^answer:"))

    print("🤖 Бот запущен и ждёт команд.")
    await app.run_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(run_bot())
