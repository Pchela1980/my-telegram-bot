# =================================================================
# ==     ФИНАЛЬНАЯ ВЕРСИЯ (с отправкой текста сообщения)     ==
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
        'а затем /all [текст], чтобы отправить всем уведомление с вашим сообщением.'
    )

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("✅ Я здесь!", callback_data="user_check_in")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Начинаем перекличку! Нажмите на кнопку ниже, чтобы я вас запомнил:", reply_markup=reply_markup)

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

        current_members = chat_members.get(chat_id, {})
        names_list = [name for name in current_members.values()]
        members_count = len(names_list)
        text_of_names = ", ".join(names_list)
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

# --- ПОЛНОСТЬЮ ПЕРЕДЕЛАННАЯ ФУНКЦИЯ tag_all ---
async def tag_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /all. Отправляет текст админа с невидимыми упоминаниями."""
    logger.info(f"Получена команда /all от {update.effective_user.first_name}")
    
    user = update.message.from_user
    chat_id = update.message.chat_id

    try:
        chat_admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in chat_admins]
        if user.id not in admin_ids:
            await update.message.delete()
            return
    except Exception:
        return

    # Получаем текст, который админ написал ПОСЛЕ команды /all
    # context.args - это список слов после команды
    admin_message = " ".join(context.args)
    if not admin_message:
        await update.message.reply_text("Пожалуйста, напишите сообщение после команды /all. Например: `/all Срочный сбор!`")
        return

    if not chat_members.get(chat_id):
        await update.message.reply_text("Пока никто не отметился. Используйте /checkin, чтобы начать перекличку.")
        return

    # Собираем НЕВИДИМЫЕ упоминания
    user_list = chat_members.get(chat_id, {})
    # \u200b - это специальный символ "пробел нулевой ширины"
    invisible_mentions = [f"[\u200b](tg://user?id={uid})" for uid in user_list.keys()]
    mentions_text = "".join(invisible_mentions)

    # Соединяем текст админа и невидимые упоминания
    final_message = f"{admin_message}\n{mentions_text}"

    # Отправляем итоговое сообщение
    await context.bot.send_message(chat_id, final_message, parse_mode=ParseMode.MARKDOWN_V2)
    
    # Удаляем исходное сообщение с командой /all
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить команду /all: {e}")


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