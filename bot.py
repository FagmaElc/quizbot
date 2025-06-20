import os
import asyncio
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Установи BOT_TOKEN в настройках Render

questions = [ ... ]  # Твой список из 30 вопросов: (текст, [опции], индекс_правильного)

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
        return await update.message.reply_text("Игра уже идет.")
    if user.id in game["players"]:
        return await update.message.reply_text(f"{user.first_name}, вы уже в игре.")
    game["players"][user.id] = {"score": 0}
    await update.message.reply_text(f"{user.first_name} присоединился к игре!")

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game or not game["players"]:
        return await update.message.reply_text("Нет игроков. Напишите /join")
    if game["started"]:
        return await update.message.reply_text("Игра уже запущена.")
    game["started"] = True
    game["current_q_index"] = 0
    await send_question_all(context, chat_id)

async def send_question_all(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games[chat_id]
    idx = game["current_q_index"]
    if idx >= len(game["questions"]):
        return await show_results(context, chat_id)

    qtext, opts, correct_idx = game["questions"][idx]
    game["answers"] = {}

    kb_rows = [
        [InlineKeyboardButton(opt, callback_data=f"{uid}:{i}")]
        for i, opt in enumerate(opts)
        for uid in [None]  # trick to flatten
    ]
    for uid in game["players"]:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(opt, callback_data=f"{uid}:{i}") for i, opt in enumerate(opts)]
        ])
        await context.bot.send_message(uid, f"Вопрос {idx+1}: {qtext}\n30 секунд на ответ.", reply_markup=kb)

    asyncio.create_task(question_timeout(context, chat_id, idx))

async def question_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int, idx: int):
    await asyncio.sleep(30)
    game = games.get(chat_id)
    if not game or game["current_q_index"] != idx:
        return
    for uid in game["players"]:
        if uid not in game["answers"]:
            await context.bot.send_message(uid, "⏰ Время вышло, баллы не засчитаны.")
    game["current_q_index"] += 1
    await send_question_all(context, chat_id)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid_str, sel = q.data.split(":")
    uid = int(uid_str); sel = int(sel)
    if uid != q.from_user.id:
        return await q.answer("Это не ваш вопрос.", show_alert=True)

    chat_id = next(cid for cid, g in games.items() if uid in g["players"])
    game = games[chat_id]
    idx = game["current_q_index"]
    _, _, correct_idx = game["questions"][idx]
    if uid in game["answers"]:
        return await q.answer("Вы уже ответили.", show_alert=True)

    if sel == correct_idx:
        game["players"][uid]["score"] += 1
        await q.edit_message_text(q.message.text + "\n✅ Правильный!")
    else:
        await q.edit_message_text(q.message.text + "\n❌ Неправильно.")
    game["answers"][uid] = True

    if len(game["answers"]) == len(game["players"]):
        game["current_q_index"] += 1
        await send_question_all(context, chat_id)

async def show_results(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games[chat_id]
    items = sorted(game["players"].items(), key=lambda x: x[1]["score"], reverse=True)
    text = "Игра окончена! Результаты:\n" + "\n".join(
        f"{await context.bot.get_chat(uid).first_name}: {data['score']} баллов"
        for uid, data in items
    )
    text += f"\n\n🏆 Победитель: {await context.bot.get_chat(items[0][0]).first_name}"
    await context.bot.send_message(chat_id, text)
    del games[chat_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Введите /join в группе, затем /quiz, чтобы начать.")

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CallbackQueryHandler(button))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
