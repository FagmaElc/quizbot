import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ✅ Список вопросов (сокращён для примера)
QUESTIONS = [
    ("Столица Франции?", ["Париж", "Лондон", "Берлин", "Мадрид"], 0),
    ("Какой элемент обозначается символом 'O'?", ["Кислород", "Золото", "Углерод", "Азот"], 0),
    ("Кто написал 'Война и мир'?", ["Пушкин", "Толстой", "Достоевский", "Чехов"], 1),
("Столица Германии?", ["Берлин", "Мюнхен", "Франкфурт", "Гамбург"], 0),
    ("Какой элемент обозначается символом 'O'?", ["Кислород", "Золото", "Углерод", "Азот"], 0),
    ("Кто написал 'Война и мир'?", ["Пушкин", "Толстой", "Достоевский", "Чехов"], 1),
    ("Сколько планет в Солнечной системе?", ["7", "8", "9", "10"], 1),
    ("Самая длинная река в мире?", ["Амазонка", "Нил", "Янцзы", "Миссисипи"], 0),
    ("Какой город называют Большим Яблоком?", ["Лос-Анджелес", "Чикаго", "Нью-Йорк", "Сан-Франциско"], 2),
    ("В каком году распался СССР?", ["1991", "1989", "1993", "1990"], 0),
    ("Сколько хромосом у человека?", ["46", "44", "48", "42"], 0),
    ("Кто нарисовал 'Мону Лизу'?", ["Ван Гог", "Пикассо", "Да Винчи", "Рембрандт"], 2),
    ("Какой металл самый лёгкий?", ["Алюминий", "Железо", "Литий", "Медь"], 2),
    ("Какой язык программирования используется для сайтов?", ["Python", "HTML", "C++", "Java"], 1),
    ("Сколько часов в сутках?", ["24", "12", "36", "48"], 0),
    ("Сколько ног у паука?", ["6", "8", "10", "12"], 1),
    ("Столица Японии?", ["Осака", "Токио", "Киото", "Нагоя"], 1),
    ("Какой океан самый большой?", ["Атлантический", "Индийский", "Тихий", "Северный Ледовитый"], 2),
    ("Как называется красная планета?", ["Юпитер", "Марс", "Меркурий", "Сатурн"], 1),
    ("Кто написал 'Гарри Поттера'?", ["Дж. К. Роулинг", "Стивен Кинг", "Толкин", "Хемингуэй"], 0),
    ("Сколько дней в високосном году?", ["365", "364", "366", "367"], 2),
    ("Какая страна самая большая по площади?", ["Канада", "Россия", "США", "Китай"], 1),
    ("Что из этого — млекопитающее?", ["Курица", "Акула", "Кит", "Черепаха"], 2),
    ("Какой газ нужен для дыхания?", ["Азот", "Гелий", "Кислород", "Углекислый газ"], 2),
    ("Самая высокая гора мира?", ["Килиманджаро", "Эльбрус", "Монблан", "Эверест"], 3),
    ("Где проводятся Олимпийские игры 2024 года?", ["Париж", "Токио", "Берлин", "Рим"], 0),
    ("Что делает сердце?", ["Пищеварение", "Качает кровь", "Фильтрует", "Дышит"], 1),
    ("Кто открыл Америку?", ["Магеллан", "Колумб", "Кук", "Вашингтон"], 1),
    ("Сколько материков на Земле?", ["5", "6", "7", "8"], 2),
    ("Где находится Эйфелева башня?", ["Берлин", "Рим", "Лондон", "Париж"], 3),
    ("Какой цвет получается при смешивании синего и жёлтого?", ["Зелёный", "Фиолетовый", "Оранжевый", "Красный"], 0),
    ("Кто был первым человеком в космосе?", ["Армстронг", "Гагарин", "Титов", "Королёв"], 1),
    ("Сколько ушей у человека?", ["1", "2", "3", "4"], 1),
    # ... добавь остальные до 30!
]

assert len(QUESTIONS) >= 30, "⚠️ Нужно минимум 30 вопросов!"

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
        return QUESTIONS[self.q_order[self.current_q]]

games = {}

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("❌ Команда доступна только в группах.")
        return

    if chat.id in games and games[chat.id].active:
        await update.message.reply_text("❗ Игра уже идёт!")
        return

    games[chat.id] = QuizGame(chat.id)
    kb = [[InlineKeyboardButton("🎮 Присоединиться", callback_data="join")]]
    await update.message.reply_text(
        "🎯 Игра начинается! Нажмите кнопку ниже, чтобы присоединиться. У вас есть 30 секунд!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await asyncio.sleep(30)
    game = games.get(chat.id)
    if not game or len(game.players) < 1:
        await context.bot.send_message(chat.id, "⏹ Никто не присоединился. Игра отменена.")
        games.pop(chat.id, None)
        return

    game.active = True
    await context.bot.send_message(chat.id, f"🚀 Викторина начинается! Всего 30 вопросов.")
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
        except:
            continue

    await q.message.edit_text(
        "👥 Участники:\n" + "\n".join(names),
        reply_markup=q.message.reply_markup
    )

async def send_next_question(context, game: QuizGame):
    if game.current_q + 1 >= 30:
        return await finish_quiz(context, game)

    text, opts, correct = game.next_question()
    kb = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(opts)]
    msg = await context.bot.send_message(
        game.chat_id,
        f"❓ Вопрос {game.current_q + 1}:\n\n{text}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    # Авто-пропуск по таймауту
    context.application.create_task(wait_answer_timeout(context, game, msg.message_id))

async def wait_answer_timeout(context, game: QuizGame, message_id):
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

async def finish_quiz(context, game: QuizGame):
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

def main():
    TOKEN = "7630074850:AAFUMyj-EYzvWjBoHdymTB8Fdemk7KbIcAY"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CallbackQueryHandler(join_cb, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(answer_cb, pattern="^answer:"))

    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
