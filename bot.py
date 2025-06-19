import asyncio
import random
import os

from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Пример: https://your-app-name.onrender.com/webhook

# Вопросы
QUESTIONS = [
    ("Какой язык программирования используется для веб-верстки?", ["Python", "HTML", "C++", "Java"], 1),
    ("Сколько будет 2 + 2 * 2?", ["4", "6", "8", "10"], 1),
    ("Столица Японии?", ["Киото", "Осака", "Токио", "Хиросима"], 2),
]

# Игра
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

# Flask app
app = Flask(__name__)
telegram_app: Application = ApplicationBuilder().token(TOKEN).build()

@app.route("/")
def index():
    return "🤖 Quiz Bot is running!"

@app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return "OK", 200

# === Бот-обработчики ===

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    games[chat.id] = QuizGame(chat.id)

    kb = [[InlineKeyboardButton("🎮 Присоединиться", callback_data="join")]]
    await update.message.reply_text(
        "🎯 Игра начинается! Нажмите кнопку ниже, чтобы присоединиться. У вас есть 30 секунд!",
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
        return await q.answer("✅ Вы уже присоединились!")

    game.add_player(user.id)
    await q.answer("🎉 Участие подтверждено!")

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

    text, opts, _ = game.next_question()
    kb = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(opts)]
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

# === Запуск ===

if __name__ == "__main__":
    telegram_app.add_handler(CommandHandler("quiz", start_quiz))
    telegram_app.add_handler(CallbackQueryHandler(join_cb, pattern="^join$"))
    telegram_app.add_handler(CallbackQueryHandler(answer_cb, pattern="^answer:"))

    # Запуск Telegram приложения
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        webhook_url=WEBHOOK_URL + "/webhook"
    )
