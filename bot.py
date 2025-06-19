import os
import random
import asyncio
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://yourapp.onrender.com/<TOKEN>

app = Flask(__name__)
bot = Bot(token=TOKEN)
application = ApplicationBuilder().token(TOKEN).build()

# Вопросы
QUESTIONS = [
    ("Столица Франции?", ["Париж", "Лондон", "Берлин", "Мадрид"], 0),
    ("Сколько ушей у человека?", ["1", "2", "3", "4"], 1),
    # ... остальные вопросы ...
]

class QuizGame:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = set()
        self.scores = {}
        self.current_q = -1
        self.q_order = random.sample(range(len(QUESTIONS)), 30)
        self.active = False
        self.answered = False

    def add_player(self, user_id):
        self.players.add(user_id)
        self.scores.setdefault(user_id, 0)

    def next_question(self):
        self.current_q += 1
        self.answered = False
        if self.current_q >= 30:
            return None
        return QUESTIONS[self.q_order[self.current_q]]

games = {}  # chat_id -> QuizGame

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Игра доступна только в группах.")
        return

    if chat.id in games and games[chat.id].active:
        await update.message.reply_text("Игра уже идёт.")
        return

    game = QuizGame(chat.id)
    games[chat.id] = game

    kb = [[InlineKeyboardButton("Присоединиться", callback_data="join")]]
    await update.message.reply_text(
        "Набираем участников! Нажмите кнопку, чтобы присоединиться. Игра начнётся через 30 секунд.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await asyncio.sleep(30)
    if not game.players:
        await context.bot.send_message(chat.id, "Нет участников — викторина отменена.")
        games.pop(chat.id, None)
        return

    game.active = True
    await context.bot.send_message(chat.id, "Игра начинается!")
    await send_next_question(context, game)

async def join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    chat_id = q.message.chat.id

    game = games.get(chat_id)
    if not game:
        return

    if game.active:
        await q.answer("Игра уже идёт", show_alert=True)
        return

    if user.id in game.players:
        await q.answer("Вы уже присоединились", show_alert=True)
        return

    game.add_player(user.id)
    await context.bot.send_message(chat_id, f"{user.full_name} присоединился к игре!")

async def send_next_question(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    q = game.next_question()
    if not q:
        await finish_quiz(context, game)
        return

    text, options, correct = q
    kb = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(options)]

    await context.bot.send_message(
        game.chat_id,
        f"Вопрос {game.current_q + 1}: {text}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await asyncio.sleep(15)
    if not game.answered:
        await context.bot.send_message(game.chat_id, "⏱ Время вышло!")
        await send_next_question(context, game)

async def answer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    chat_id = q.message.chat.id

    game = games.get(chat_id)
    if not game or not game.active:
        return

    if user.id not in game.players or game.answered:
        return

    game.answered = True
    selected = int(q.data.split(":")[1])
    _, _, correct = QUESTIONS[game.q_order[game.current_q]]

    if selected == correct:
        game.scores[user.id] += 1
        await context.bot.send_message(chat_id, f"{user.full_name} ✅ Правильно!")
    else:
        await context.bot.send_message(chat_id, f"{user.full_name} ❌ Неправильно.")

    await send_next_question(context, game)

async def finish_quiz(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    winners = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    text = "🏁 Игра окончена!\n"
    for uid, score in winners:
        try:
            user = await context.bot.get_chat_member(game.chat_id, uid)
            name = user.user.full_name
        except:
            name = "Неизвестный игрок"
        text += f"{name}: {score} очков\n"

    await context.bot.send_message(game.chat_id, text)
    games.pop(game.chat_id, None)

# Добавляем обработчики
application.add_handler(CommandHandler("quiz", start_quiz))
application.add_handler(CallbackQueryHandler(join_cb, pattern=r"^join$"))
application.add_handler(CallbackQueryHandler(answer_cb, pattern=r"^answer:\d+$"))

# Webhook endpoint
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "OK"

@app.route("/")
def home():
    return "Бот работает!"

if __name__ == "__main__":
    print("Запуск бота...")
    if WEBHOOK_URL:
        import asyncio
        asyncio.run(bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}"))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
