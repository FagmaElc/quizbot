import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from questions import QUESTIONS
games = {}

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
        except Exception:
            continue

    await q.message.edit_text(
        "👥 Участники:\n" + "\n".join(names),
        reply_markup=q.message.reply_markup
    )

async def send_next_question(context: ContextTypes.DEFAULT_TYPE, game: QuizGame):
    if game.current_q + 1 >= 30:
        return await finish_quiz(context, game)

    text, opts, correct = game.next_question()
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
