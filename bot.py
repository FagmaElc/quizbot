import os
import random
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.ext import defaults

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

app = Flask(__name__)

QUESTIONS = [
    ("Столица Франции?", ["Париж", "Лондон", "Берлин", "Мадрид"], 0),
    ("Кто написал 'Война и мир'?", ["Пушкин", "Толстой", "Гоголь", "Лермонтов"], 1),
    # Добавьте остальные вопросы
]

games = {}  # chat_id -> QuizGame

class QuizGame:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = set()
        self.scores = {}
        self.current_q = -1
        self.q_order = random.sample(range(len(QUESTIONS)), len(QUESTIONS))
        self.active = False
        self.answered = False

    def add_player(self, user_id):
        self.players.add(user_id)
        self.scores.setdefault(user_id, 0)

    def next_question(self):
        self.current_q += 1
        self.answered = False
        if self.current_q >= len(self.q_order):
            return None
        return QUESTIONS[self.q_order[self.current_q]]

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
        "Набираем участников! Нажмите кнопку. Старт через 30 секунд.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await asyncio.sleep(30)

    if not game.players:
        await context.bot.send_message(chat.id, "Нет участников. Игра отменена.")
        games.pop(chat.id)
        return

    game.active = True
    await context.bot.send_message(chat.id, f"Игра началась! Вопросов: {len(QUESTIONS)}")
    await send_next_question(context, game)

async def join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    cid = q.message.chat.id
    game = games.get(cid)
    if not game:
        return

    if game.active:
        return await q.answer("Игра уже началась.", show_alert=True)
    if user.id in game.players:
        return await q.answer("Вы уже присоединились.", show_alert=True)

    game.add_player(user.id)
    names = []
    for pid in game.players:
        try:
            member = await context.bot.get_chat_member(cid, pid)
            names.append(member.user.full_name or "Участник")
        except:
            names.append("Неизвестный")
    text = "Участники:\n" + "\n".join(names)
    await context.bot.send_message(cid, text)

async def send_next_question(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    qdata = game.next_question()
    if qdata is None:
        return await finish_quiz(context, game)

    text, options, correct = qdata
    kb = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(options)]
    await context.bot.send_message(game.chat_id, f"Вопрос {game.current_q + 1}: {text}", reply_markup=InlineKeyboardMarkup(kb))
    context.application.create_task(answer_timeout(context, game))

async def answer_timeout(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    await asyncio.sleep(15)
    if not game.answered:
        await context.bot.send_message(game.chat_id, "⏰ Время вышло!")
        await send_next_question(context, game)

async def answer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    cid = q.message.chat.id

    game = games.get(cid)
    if not game or not game.active or game.answered or uid not in game.players:
        return

    idx = int(q.data.split(":")[1])
    _, _, correct = QUESTIONS[game.q_order[game.current_q]]

    game.answered = True
    if idx == correct:
        game.scores[uid] += 1
        await q.answer("✅ Правильно!", show_alert=True)
        await context.bot.send_message(cid, f"{q.from_user.full_name} получает 1 очко!")
    else:
        await q.answer("❌ Неверно!", show_alert=True)
        await context.bot.send_message(cid, f"{q.from_user.full_name} ошибся.")

    await send_next_question(context, game)

async def finish_quiz(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    if not game.scores:
        await context.bot.send_message(game.chat_id, "Никто не ответил. Игра окончена.")
        games.pop(game.chat_id)
        return

    winners = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    best_score = winners[0][1]
    top_players = [uid for uid, score in winners if score == best_score]

    text = "🏁 Игра окончена! Победители:\n"
    for uid in top_players:
        member = await context.bot.get_chat_member(game.chat_id, uid)
        name = member.user.full_name or "Неизвестный"
        text += f"— {name}: {game.scores[uid]} очков\n"

    await context.bot.send_message(game.chat_id, text)
    games.pop(game.chat_id)

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("quiz", start_quiz))
application.add_handler(CallbackQueryHandler(join_cb, pattern="^join$"))
application.add_handler(CallbackQueryHandler(answer_cb, pattern=r"^answer:\d+$"))

@app.route("/webhook", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "Бот работает!"

if __name__ == "__main__":
    import asyncio
    import logging
    logging.basicConfig(level=logging.INFO)

    async def run():
        await application.initialize()
        await application.start()
        # Webhook устанавливаем один раз
        await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

    asyncio.run(run())
