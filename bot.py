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

# --- Flask приложение ---
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "Баба Маня живёт 🔮"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# --- Вопросы викторины ---
QUESTIONS = [
    ("Какой язык разметки используют в вебе?", ["HTML", "Python", "C++", "CSS"], 0),
    ("Сколько будет 2 + 2 * 2?", ["4", "6", "8", "2"], 1),
    ("Столица Японии?", ["Киото", "Осака", "Токио", "Хиросима"], 2),
]

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

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id in games and games[chat.id].active:
        await update.message.reply_text("Игра уже идёт!")
        return

    games[chat.id] = QuizGame(chat.id)

    kb = [[InlineKeyboardButton("👤 Присоединиться", callback_data="join")]]
    await update.message.reply_text(
        "🎮 Викторина начинается! Нажмите кнопку, чтобы присоединиться. У вас есть 30 секунд!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await asyncio.sleep(30)
    game = games.get(chat.id)
    if not game or len(game.players) < 1:
        await context.bot.send_message(chat.id, "⏹️ Никто не присоединился. Игра отменена.")
        games.pop(chat.id, None)
        return

    game.active = True
    await context.bot.send_message(chat.id, f"🚀 Викторина начинается! Всего {len(QUESTIONS)} вопросов.")
    await send_next_question(context, game)

async def join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    cid = q.message.chat.id

    game = games.get(cid)
    if not game or game.active:
        return await q.answer("🚫 Игра уже идёт или не запущена!")

    if user.id in game.players:
        return await q.answer("✅ Вы уже в игре!")

    game.add_player(user.id)
    await q.answer("🎉 Вы присоединились!")

    names = []
    for pid in game.players:
        try:
            member = await context.bot.get_chat_member(cid, pid)
            uname = f"@{member.user.username}" if member.user.username else member.user.full_name
            names.append(uname)
        except Exception:
            continue

    await q.message.edit_text(
        "👥 Участники:\n" + "\n".join(names),
        reply_markup=q.message.reply_markup
    )

async def send_next_question(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    if game.current_q + 1 >= len(QUESTIONS):
        return await finish_quiz(context, game)

    text, options, correct_index = game.next_question()
    kb = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(options)]
    msg = await context.bot.send_message(
        game.chat_id,
        f"❓ Вопрос {game.current_q + 1}:\n\n{text}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    context.application.create_task(wait_answer_timeout(context, game, msg.message_id))

async def wait_answer_timeout(context: ContextTypes.DEFAULT_TYPE, game: QuizGame, message_id: int):
    await asyncio.sleep(15)
    if not game.answered:
        await context.bot.send_message(game.chat_id, "⏰ Время вышло! Никто не ответил.")
        await send_next_question(context, game)

async def answer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    cid = q.message.chat.id
    data = q.data

    game = games.get(cid)
    if not game or not game.active or game.answered or user.id not in game.players:
        return await q.answer()

    idx = int(data.split(":")[1])
    _, _, correct = QUESTIONS[game.q_order[game.current_q]]
    game.answered = True

    if idx == correct:
        game.scores[user.id] += 1
        await q.answer("✅ Правильно!", show_alert=True)
        await context.bot.send_message(cid, f"🎯 {user.full_name} получает 1 очко!")
    else:
        await q.answer("❌ Неверно!", show_alert=True)
        await context.bot.send_message(cid, f"🙈 {user.full_name} ошибся.")

    await send_next_question(context, game)

async def finish_quiz(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    winners = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    best_score = winners[0][1]
    top_players = [uid for uid, score in winners if score == best_score]

    result_text = "🏁 Игра завершена!\n\n🏆 Победители:\n"
    for uid in top_players:
        member = await context.bot.get_chat_member(game.chat_id, uid)
        uname = f"@{member.user.username}" if member.user.username else member.user.full_name
        result_text += f"- {uname}: {best_score} очков\n"

    await context.bot.send_message(game.chat_id, result_text)
    games.pop(game.chat_id, None)

# --- Запуск бота ---

async def run_bot():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("❌ Ошибка: Переменная окружения BOT_TOKEN не задана!")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CallbackQueryHandler(join_cb, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(answer_cb, pattern="^answer:"))

    print("🤖 Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(run_bot())
    
