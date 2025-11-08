# =================================================================
# ==     ВЕРСИЯ С УЛУЧШЕННОЙ ДИАГНОСТИКОЙ КОМАНДЫ /all     ==
# =================================================================

import logging
import os
import json
import re # Импортируем модуль для экранирования символов
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest # Импортируем класс ошибки для отлова
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_DIR = "/data" 
DATA_FILE = os.path.join(DATA_DIR, "bot_data.json")
os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

chat_members = {}

def load_data():
    global chat_members
    try:
        with open(DATA_FILE, "r") as f:
            chat_members = json.load(f)
            chat_members = {int(k): v for k, v in chat_members.items()}
            logger.info("Данные успешно загружены из файла.")
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("Файл данных не найден или поврежден. Начинаем с пустым списком.")
        chat_members = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(chat_members, f, indent=4)
        logger.info("Данные успешно сохранены в файл.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Привет! Я бот для упоминания всех участников. \n'
        'Администратор может использовать команду /checkin, чтобы начать перекличку, \n'
        'а затем /all [заголовок: текст], чтобы отправить всем уведомление.'
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
    if str(user.id) not in chat_members[chat_id]:
        chat_members[chat_id][str(user.id)] = user.first_name
        logger.info(f"+++ Пользователь {user.first_name} отметил себя в чате {chat_id}")
        await query.answer(text=f"Спасибо, {user.first_name}, я вас запомнил!", show_alert=False)
        save_data()
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
    if str(user.id) not in chat_members[chat_id]:
        chat_members[chat_id][str(user.id)] = user.first_name
        logger.info(f"+++ Запомнил нового пользователя: {user.first_name} (из обычного сообщения)")
        save_data()

# --- ФУНКЦИЯ tag_all С УЛУЧШЕННОЙ ДИАГНОСТИКОЙ И ИСПРАВЛЕНИЕМ ---
async def tag_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"[DIAGNOSTICS] Получена команда /all от {update.effective_user.first_name}")
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

    admin_message_text = " ".join(context.args)
    logger.info(f"[DIAGNOSTICS] Текст от админа: {admin_message_text}")
    if not admin_message_text:
        await update.message.reply_text("Пожалуйста, напишите сообщение после команды /all.")
        return
    if not chat_members.get(chat_id):
        await update.message.reply_text("Пока никто не отметился.")
        return

    # --- ИСПРАВЛЕНИЕ: Функция для экранирования спецсимволов для MarkdownV2 ---
    def escape_markdown(text: str) -> str:
        # Экранируем все зарезервированные символы
        escape_chars = r'_*[]()~`>#+-.=|{}!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

    if ":" in admin_message_text:
        parts = admin_message_text.split(":", 1)
        title = escape_markdown(parts[0].strip())
        body = escape_markdown(parts[1].strip())
        formatted_message = f"*{title}*\n\n{body}"
    else:
        formatted_message = escape_markdown(admin_message_text)
    
    logger.info(f"[DIAGNOSTICS] Отформатированный текст: {formatted_message}")

    user_list = chat_members.get(chat_id, {})
    logger.info(f"[DIAGNOSTICS] Список пользователей для тега: {user_list}")
    
    # Создаем невидимые упоминания, экранируя имена на всякий случай
    invisible_mentions = [f"[\u200b](tg://user?id={uid})" for uid in user_list.keys()]
    mentions_text = "".join(invisible_mentions)
    
    final_message = f"{formatted_message}\n{mentions_text}"
    logger.info(f"[DIAGNOSTICS] Финальное сообщение для отправки (без упоминаний): {formatted_message}")

    try:
        await context.bot.send_message(chat_id, final_message, parse_mode=ParseMode.MARKDOWN_V2)
        logger.info("[DIAGNOSTICS] Сообщение с тегами успешно отправлено.")
    except BadRequest as e:
        # --- ЛОВИМ ОШИБКУ ---
        logger.error(f"[DIAGNOSTICS] !!! TELEGRAM ВЕРНУЛ ОШИБКУ: {e.message}")
        # Отправляем сообщение без форматирования, чтобы оно точно дошло
        await context.bot.send_message(chat_id, f"{admin_message_text}\n{mentions_text}", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить команду /all: {e}")

def main() -> None:
    if not BOT_TOKEN:
        logger.error("!!! КРИТИЧЕСКАЯ ОШИБКА: Токен бота не найден!")
        return
    load_data()
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