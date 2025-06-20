import asyncio
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

TOKEN = "7630074850:AAFUMyj-EYzvWjBoHdymTB8Fdemk7KbIcAY"  # вставь сюда свой токен

questions = [
    ("Сколько будет 2 + 2?", ["3", "4", "5", "6"], 1),
    ("Столица Франции?", ["Берлин", "Лондон", "Париж", "Рим"], 2),
    ("Какой язык мы используем?", ["Java", "C++", "Python", "Ruby"], 2),
    # ... остальные вопросы ...
]

games = {}  # chat_id -> игра

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in games:
        games[chat_id] = {
            "players": {},
            "questions": random.sample(questions, len(questions)),
            "current_q_index": 0,
            "started": False,
            "answers": {},
        }

    game = games[chat_id]

    if game["started"]:
        await update.message.reply_text("Игра уже идет, присоединиться нельзя.")
        return

    if user.id in game["players"]:
        await update.message.reply_text(f"{user.first_name}, вы уже в игре.")
    else:
        game["players"][user.id] = {"score": 0}
        await update.message.reply_text(f"{user.first_name} присоединился к игре!")

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in games or len(games[chat_id]["players"]) == 0:
        await update.message.reply_text("Нет игроков, которые присоединились. Попросите игроков ввести /join")
        return

    game = games[chat_id]
    if game["started"]:
        await update.message.reply_text("Игра уже идет.")
        return

    game["started"] = True
    game["current_q_index"] = 0

    await send_question_all(context, chat_id)

async def send_question_all(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games[chat_id]
    q_index = game["current_q_index"]

    if q_index >= len(game["questions"]):
        await show_results(context, chat_id)
        return

    question_text, options, correct_index = game["questions"][q_index]
    game["answers"] = {}

    for user_id in game["players"]:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(opt, callback_data=f"{user_id}:{i}")] for i, opt in enumerate(options)]
        )

        try:
            await context.bot.send_message(user_id, f"Вопрос {q_index+1}: {question_text}\nУ вас 30 секунд на ответ.", reply_markup=keyboard)
        except Exception as e:
            print(f"Не удалось отправить вопрос пользователю {user_id}: {e}")

    # Таймер 30 секунд на ответ
    asyncio.create_task(question_timeout(context, chat_id, q_index, 30))

async def question_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int, q_index: int, timeout_sec: int):
    await asyncio.sleep(timeout_sec)

    game = games.get(chat_id)
    if not game or game["current_q_index"] != q_index:
        return

    for user_id in game["players"]:
        if user_id not in game["answers"]:
            try:
                await context.bot.send_message(user_id, "Время на ответ вышло. Баллы не засчитаны.")
            except:
                pass

    game["current_q_index"] += 1
    await send_question_all(context, chat_id)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id_str, selected_str = data.split(":")
    user_id = int(user_id_str)
    selected = int(selected_str)

    if user_id != query.from_user.id:
        await query.answer("Это не ваш вопрос!", show_alert=True)
        return

    # Найдем игру пользователя
    chat_id = None
    for c_id, game in games.items():
        if user_id in game["players"]:
            chat_id = c_id
            break

    if chat_id is None:
        await query.edit_message_text("Игра не найдена.")
        return

    game = games[chat_id]
    if user_id in game["answers"]:
        await query.answer("Вы уже ответили на этот вопрос.", show_alert=True)
        return

    q_index = game["current_q_index"]
    _, options, correct_index = game["questions"][q_index]

    if selected == correct_index:
        game["players"][user_id]["score"] += 1
        await query.edit_message_text(query.message.text + "\n✅ Правильно!")
    else:
        await query.edit_message_text(query.message.text + f"\n❌ Неправильно.")

    game["answers"][user_id] = True

    # Если все ответили - сразу следующий вопрос
    if len(game["answers"]) == len(game["players"]):
        game["current_q_index"] += 1
        await send_question_all(context, chat_id)

async def show_results(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games[chat_id]
    text = "Игра окончена! Результаты:\n"
    players = game["players"]

    ranking = sorted(players.items(), key=lambda x: x[1]["score"], reverse=True)

    for i, (user_id, data) in enumerate(ranking, start=1):
        user_name = (await context.bot.get_chat(user_id)).first_name
        text += f"{i}. {user_name}: {data['score']} баллов\n"

    winner = ranking[0][0]
    winner_name = (await context.bot.get_chat(winner)).first_name

    text += f"\nПобедитель: {winner_name} 🎉"

    await context.bot.send_message(chat_id, text)
    del games[chat_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Введите /join чтобы присоединиться к викторине.")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CallbackQueryHandler(button))

    print("Бот запущен")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
