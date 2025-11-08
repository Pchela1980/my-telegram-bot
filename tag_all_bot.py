# =================================================================
# ==     ФИНАЛЬНАЯ ВЕРСИЯ (с редактированием и счетчиком)     ==
# =================================================================

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# ↓↓↓ Бот будет брать токен из секретного хранилища Render ↓↓↓
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# "База данных" участников чата
chat_members = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Привет! Я бот для упоминания всех участников. \n'
        'Администратор может использовать команду /checkin, чтобы начать перекличку, \n'
        'а затем /all, чтобы упомянуть всех отметившихся.'
    )

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("✅ Я здесь!", callback_data="user_check_in")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Начинаем перекличку! Нажмите на кнопку ниже, чтобы я вас запомнил:", reply_markup=reply_markup)

# --- ОБНОВЛЕННАЯ ФУНКЦИЯ ДЛЯ ОБРАБОТКИ НАЖАТИЯ КНОПКИ ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat_id

    await query.answer()

    if chat_id not in chat_members:
        chat_members[chat_id] = {}

    if user.id not in chat_members[chat_id]:
        chat_members[chat_id][user.id] = user.first_name
        logger.info(f"+++ Пользователь {user.first_name} отметил себя в чате {chat_id}")
        await query.answer(text=f"Спасибо, {user.first_name}, я вас запомнил!", show_alert=False)

        # --- БЛОК РЕДАКТИРОВАНИЯ СООБЩЕНИЯ ---
        
        current_members = chat_members.get(chat_id, {})
        names_list = [name for name in current_members.values()]
        
        # --- НОВОЕ ИЗМЕНЕНИЕ: ПОЛУЧАЕМ КОЛИЧЕСТВО ---
        members_count = len(names_list)
        
        text_of_names = ", ".join(names_list)

        # --- НОВОЕ ИЗМЕНЕНИЕ: ДОБАВЛЯЕМ СЧЕТЧИК В ТЕКСТ ---
        new_text = f"Перекличка! Уже отметились ({members_count}):\n\n{text_of_names}"

        keyboard = [[InlineKeyboardButton("✅ Я здесь!", callback_data="user_check_in")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.message.edit_text(text=new_text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Не удалось отредактировать сообщение: {e}")

    else:
        await query.answer(text="Я вас уже знаю :)", show_alert=False)


async def remember_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    chat_id = update.message.chat_id
    if chat_id not in chat_members:
        chat_members[chat_id] = {}
    if user.id not in chat_members[chat_id]:
        logger.info(f"+++ Запомнил нового пользователя: {user.first_name} (из обычного сообщения)")
        chat_members[chat_id][user.id] = user.first_name

async def tag_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    chat_id = update.message.chat_id
    try:
        chat_admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in chat_admins]
        if user.id not in admin_ids:
            await update.message.reply_text("Эту команду могут использовать только администраторы.")
            return
    except Exception:
        await update.message.reply_text("Не могу проверить права, убедитесь, что я админ.")
        return

    if not chat_members.get(chat_id):
        await update.message.reply_text("Пока никто не отметился. Используйте /checkin, чтобы начать перекличку.")
        return

    user_list = chat_members.get(chat_id, {})
    mentions = [f"[{name.replace(']', '').replace('[', '')}](tg://user?id={uid})" for uid, name in user_list.items()]
    text = " ".join(mentions)
    await update.message.reply_text("Общий сбор!")
    await context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)

def main() -> None:
    if not BOT_TOKEN:
        logger.error("!!! КРИТИЧЕСКАЯ ОШИБКА: Токен бота не найден в переменных окружения!")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("all", tag_all))
    application.add_handler(CommandHandler("checkin", checkin_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, remember_user))

    logger.info("Бот запущен. Ожидаю сообщений...")
    application.run_polling()

if __name__ == "__main__":
    main()