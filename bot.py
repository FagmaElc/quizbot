import os
import random
import asyncio
from threading import Thread

from flask import Flask, request, abort
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler

TOKEN = os.getenv("TOKEN")  # токен из переменной окружения
if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")

bot = Bot(token=TOKEN)
app = Flask(__name__)

# Вопросы
QUESTIONS = [
    ("Столица Франции?", ["Париж", "Лондон", "Берлин", "Мадрид"], 0),
    # ... (твой список вопросов) ...
    ("Сколько ушей у человека?", ["1", "2", "3", "4"], 1),
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
        self.message_id = None

    def add_player(self, user_id):
        self.players.add(user_id)
        self.scores.setdefault(user_id, 0)

    def next_question(self):
        self.current_q += 1
        self.answered = False
        if self.current_q >= 30:
            return None
        return QUESTIONS[self.q_order[self.current_q]]

games = {}

dispatcher = Dispatcher(bot, None, workers=0, use_context=True)  # workers=0 — чтобы sync

# === Хендлеры ===

def start_quiz(update, context):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        update.message.reply_text("Игра доступна только в группах.")
        return

    if chat.id in games and games[chat.id].active:
        update.message.reply_text("Игра уже идёт в этом чате.")
        return

    game = QuizGame(chat.id)
    games[chat.id] = game

    kb = [[InlineKeyboardButton("Присоединиться", callback_data="join")]]
    update.message.reply_text(
        "Набираем участников! Нажмите кнопку, чтобы присоединиться. Игра начнётся через 30 секунд.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    # Запускаем таймер для старта игры в отдельном потоке (asyncio в Flask без loop не работает)
    def wait_and_start():
        asyncio.run(wait_and_start_async(context, game))

    Thread(target=wait_and_start).start()

async def wait_and_start_async(context, game):
    await asyncio.sleep(30)
    chat_id = game.chat_id

    if not game.players:
        await bot.send_message(chat_id, "Нет участников — викторина отменена.")
        games.pop(chat_id, None)
        return

    game.active = True
    await bot.send_message(chat_id, f"Игра началась! Вопросов: 30. Удачи!")
    await send_next_question(bot, game)

async def send_next_question(bot, game):
    qdata = game.next_question()
    if qdata is None:
        await finish_quiz(bot, game)
        return

    text, options, correct = qdata
    kb = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(options)]
    msg = await bot.send_message(game.chat_id, f"Вопрос {game.current_q + 1}: {text}",
                                 reply_markup=InlineKeyboardMarkup(kb))
    game.message_id = msg.message_id

    # Запускаем таймер ответа
    async def timeout():
        await asyncio.sleep(15)
        if not game.answered:
            await bot.send_message(game.chat_id, "Время ответа истекло!")
            await send_next_question(bot, game)

    asyncio.create_task(timeout())

def join_cb(update, context):
    q = update.callback_query
    q.answer()

    user = q.from_user
    cid = q.message.chat.id

    game = games.get(cid)
    if not game:
        q.message.reply_text("Игра не найдена.")
        return

    if game.active:
        q.answer("Набор участников завершён — игра уже идёт!", show_alert=True)
        return

    if user.id in game.players:
        q.answer("Вы уже в игре!", show_alert=True)
        return

    game.add_player(user.id)

    # Составляем список участников
    names = []
    for pid in game.players:
        try:
            member = bot.get_chat_member(cid, pid)
            names.append(member.user.full_name or member.user.username or "Unknown")
        except:
            names.append("Unknown")

    text = "🎯 Участники:\n" + "\n".join(names)
    bot.send_message(cid, text)

def answer_cb(update, context):
    q = update.callback_query
    q.answer()

    uid = q.from_user.id
    cid = q.message.chat.id

    game = games.get(cid)
    if not game or not game.active:
        q.answer("Игра не активна.", show_alert=True)
        return

    if uid not in game.players:
        q.answer("Вы не участвуете в игре.", show_alert=True)
        return

    if game.answered:
        q.answer("Вопрос уже отвечен.", show_alert=True)
        return

    idx = int(q.data.split(":")[1])
    _, _, correct = QUESTIONS[game.q_order[game.current_q]]

    game.answered = True
    if idx == correct:
        game.scores[uid] += 1
        q.answer("✅ Правильно!", show_alert=True)
        bot.send_message(cid, f"{q.from_user.full_name} отвечает правильно и получает 1 очко!")
    else:
        q.answer("❌ Неверно!", show_alert=True)
        bot.send_message(cid, f"{q.from_user.full_name} ответил неправильно.")

    # Запускаем следующий вопрос в отдельном потоке с asyncio
    def next_q():
        asyncio.run(send_next_question(bot, game))
    Thread(target=next_q).start()

async def finish_quiz(bot, game):
    if not game.scores:
        await bot.send_message(game.chat_id, "Игра окончена. Нет участников.")
        games.pop(game.chat_id, None)
        return

    winners = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    best_score = winners[0][1]
    winners_list = [uid for uid, sc in winners if sc == best_score]

    text = "🏆 Игра завершена! Победители:\n"
    for uid in winners_list:
        try:
            member = await bot.get_chat_member(game.chat_id, uid)
            name = member.user.full_name or member.user.username or "Unknown"
        except Exception:
            name = "Unknown"
        text += f"- {name} — {game.scores[uid]} очков\n"

    await bot.send_message(game.chat_id, text)
    games.pop(game.chat_id, None)

# Регистрируем хендлеры
dispatcher.add_handler(CommandHandler("quiz", start_quiz))
dispatcher.add_handler(CallbackQueryHandler(join_cb, pattern="^join$"))
dispatcher.add_handler(CallbackQueryHandler(answer_cb, pattern="^answer:\d$"))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return "OK"
    else:
        abort(405)

@app.route("/")
def index():
    return "Бот работает"

if __name__ == "__main__":
    # Перед запуском на Render укажи WEBHOOK_URL в переменных окружения, например:
    # https://yourdomain.com/<TOKEN>
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        print("WEBHOOK_URL не установлен, запускаем без webhook")
        app.run(port=5000)
    else:
        bot.delete_webhook()
        bot.set_webhook(WEBHOOK_URL)
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
