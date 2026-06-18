import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, date, timedelta
import logging
import re
import time
import sys
import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from config import BOT_TOKEN
from db_handler import Database
from analyzer import Analyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

try:
    bot = telebot.TeleBot(BOT_TOKEN)
    session = requests.Session()
    session.mount('https://', SSLAdapter())
    bot.session = session
    logger.info("Бот создан")
except Exception as e:
    logger.error(f"Ошибка создания бота: {e}")
    sys.exit(1)

try:
    bot.remove_webhook()
    logger.info("Вебхук удалён")
except Exception as e:
    logger.warning(f"Ошибка удаления вебхука: {e}")

try:
    bot_info = bot.get_me()
    logger.info(f"Бот @{bot_info.username} запущен и готов к работе!")
    logger.info(f"ID бота: {bot_info.id}")
except Exception as e:
    logger.error(f"Ошибка подключения к боту: {e}")
    sys.exit(1)

try:
    db = Database()
    db.create_tables()
    logger.info("База данных подключена")
except Exception as e:
    logger.error(f"Ошибка подключения к БД: {e}")
    sys.exit(1)

user_data = {}

def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("➕ Записать день"), KeyboardButton("📊 Статистика"))
    markup.add(KeyboardButton("📜 История"), KeyboardButton("⚙️ Настройки"))
    markup.add(KeyboardButton("🗑 Очистить данные"), KeyboardButton("❓ Помощь"))
    return markup

def mood_keyboard():
    markup = InlineKeyboardMarkup(row_width=5)
    buttons = [
        InlineKeyboardButton("1 😞", callback_data="mood_1"),
        InlineKeyboardButton("2 😐", callback_data="mood_2"),
        InlineKeyboardButton("3 🙂", callback_data="mood_3"),
        InlineKeyboardButton("4 😊", callback_data="mood_4"),
        InlineKeyboardButton("5 🤩", callback_data="mood_5")
    ]
    markup.add(*buttons)
    return markup

def hours_keyboard(prefix, options):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for opt in options:
        markup.add(KeyboardButton(f"{opt} ч"))
    markup.add(KeyboardButton("Другое..."))
    return markup

def confirm_clear_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Да, удалить всё", callback_data="clear_confirm"))
    markup.add(InlineKeyboardButton("❌ Отмена", callback_data="clear_cancel"))
    return markup

def stats_menu_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📅 За неделю", callback_data="stats_week"),
        InlineKeyboardButton("🗓 За месяц", callback_data="stats_month"),
        InlineKeyboardButton("🔍 Мои инсайты", callback_data="stats_insights"),
        InlineKeyboardButton("📉 График", callback_data="stats_graph")
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    try:
        bot.send_message(
            user_id,
            "🌟 Привет! Я бот для отслеживания настроения и продуктивности.\n\n"
            "Я помогу тебе заметить скрытые связи между сном, работой и настроением.\n"
            "Используй кнопки меню для записи данных и получения аналитики.\n\n"
            "Команды:\n"
            "/add — записать сегодняшний день\n"
            "/stats — статистика и инсайты\n"
            "/history — последние записи\n"
            "/help — подробная справка\n"
            "/clear — очистить все мои данные",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    user_id = message.chat.id
    try:
        bot.send_message(
            user_id,
            "📖 **Справка по боту**\n\n"
            "➕ **Записать день** — бот задаст 4 вопроса: настроение, часы работы/учебы, часы сна и комментарий.\n"
            "📊 **Статистика** — показывает сводку за неделю/месяц, инсайты и график.\n"
            "📜 **История** — последние 10 ваших записей.\n"
            "⚙️ **Настройки** — пока в разработке.\n"
            "🗑 **Очистить данные** — безвозвратно удалит все ваши записи (с подтверждением).\n\n"
            "Данные хранятся в защищённой базе. Бот не передаёт информацию третьим лицам.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в help: {e}")

@bot.message_handler(commands=['add'])
def add_entry(message):
    user_id = message.chat.id
    today = date.today()
    
    try:
        existing = db.get_record_for_date(user_id, today)
        if existing:
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("Да, обновить", callback_data="overwrite_yes"),
                InlineKeyboardButton("Нет, отмена", callback_data="overwrite_no")
            )
            bot.send_message(user_id, "За сегодня уже есть запись. Хотите обновить её?", reply_markup=markup)
            return
        
        start_data_entry(user_id, today)
    except Exception as e:
        logger.error(f"Ошибка в add_entry: {e}")
        bot.send_message(user_id, "❌ Произошла ошибка. Попробуйте позже.")

def start_data_entry(user_id, record_date):
    user_data[user_id] = {'record_date': record_date, 'step': 'mood'}
    bot.send_message(user_id, "Оцени своё настроение сегодня от 1 до 5:", reply_markup=mood_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('overwrite_'))
def handle_overwrite(call):
    user_id = call.message.chat.id
    try:
        if call.data == "overwrite_yes":
            bot.answer_callback_query(call.id, "Хорошо, давайте обновим запись.")
            start_data_entry(user_id, date.today())
        else:
            bot.answer_callback_query(call.id, "Запись не изменена.")
            bot.delete_message(user_id, call.message.message_id)
        bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
    except Exception as e:
        logger.error(f"Ошибка в handle_overwrite: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('mood_'))
def process_mood(call):
    user_id = call.message.chat.id
    try:
        mood = int(call.data.split('_')[1])
        
        if user_id not in user_data or user_data[user_id]['step'] != 'mood':
            bot.answer_callback_query(call.id, "Начните сначала командой /add")
            return
        
        user_data[user_id]['mood'] = mood
        user_data[user_id]['step'] = 'work'
        
        bot.edit_message_text(
            "Отлично! Теперь укажи, сколько часов ты потратил на полезную работу/учёбу? (можно дробное, например 3.5)",
            user_id, call.message.message_id
        )
        markup = hours_keyboard("work", [0.5, 1, 2, 4])
        bot.send_message(user_id, "Или выбери из вариантов:", reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в process_mood: {e}")

@bot.message_handler(func=lambda msg: msg.text and (msg.text.endswith('ч') or msg.text == "Другое...") and user_data.get(msg.chat.id, {}).get('step') == 'work')
def process_work_hours(message):
    user_id = message.chat.id
    if user_id not in user_data or user_data[user_id]['step'] != 'work':
        return
    
    text = message.text.strip()
    if text == "Другое...":
        bot.send_message(user_id, "Введи количество часов цифрой (например, 3 или 5.5):", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, receive_work_manual)
        return
    
    match = re.search(r'([\d\.]+)', text)
    if not match:
        bot.send_message(user_id, "Не понял. Введи число (например 4):", reply_markup=hours_keyboard("work", [0.5, 1, 2, 4]))
        return
    
    hours = float(match.group(1))
    if hours < 0 or hours > 24:
        bot.send_message(user_id, "Часы должны быть от 0 до 24. Попробуй снова.")
        return
    
    user_data[user_id]['work_hours'] = hours
    user_data[user_id]['step'] = 'sleep'
    ask_sleep(user_id)

def receive_work_manual(message):
    user_id = message.chat.id
    try:
        hours = float(message.text.strip())
        if hours < 0 or hours > 24:
            raise ValueError
        user_data[user_id]['work_hours'] = hours
        user_data[user_id]['step'] = 'sleep'
        ask_sleep(user_id)
    except:
        bot.send_message(user_id, "Пожалуйста, введи число от 0 до 24. Например: 4")
        bot.register_next_step_handler(message, receive_work_manual)

def ask_sleep(user_id):
    markup = hours_keyboard("sleep", [6, 7, 8, 9])
    bot.send_message(user_id, "Сколько часов ты спал?", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text and (msg.text.endswith('ч') or msg.text == "Другое...") and user_data.get(msg.chat.id, {}).get('step') == 'sleep')
def process_sleep(message):
    user_id = message.chat.id
    text = message.text.strip()
    
    if text == "Другое...":
        bot.send_message(user_id, "Введи количество часов сна цифрой:", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, receive_sleep_manual)
        return
    
    match = re.search(r'([\d\.]+)', text)
    if not match:
        bot.send_message(user_id, "Не понял. Введи число часов.", reply_markup=hours_keyboard("sleep", [6, 7, 8, 9]))
        return
    
    hours = float(match.group(1))
    if hours < 0 or hours > 24:
        bot.send_message(user_id, "Часы должны быть от 0 до 24.")
        return
    
    user_data[user_id]['sleep_hours'] = hours
    user_data[user_id]['step'] = 'comment'
    ask_comment(user_id)

def receive_sleep_manual(message):
    user_id = message.chat.id
    try:
        hours = float(message.text.strip())
        if hours < 0 or hours > 24:
            raise ValueError
        user_data[user_id]['sleep_hours'] = hours
        user_data[user_id]['step'] = 'comment'
        ask_comment(user_id)
    except:
        bot.send_message(user_id, "Введи число от 0 до 24.")
        bot.register_next_step_handler(message, receive_sleep_manual)

def ask_comment(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Пропустить"))
    bot.send_message(user_id, "Хочешь добавить комментарий? Напиши текст или нажми «Пропустить».", reply_markup=markup)

@bot.message_handler(func=lambda msg: user_data.get(msg.chat.id, {}).get('step') == 'comment')
def process_comment(message):
    user_id = message.chat.id
    comment = None if message.text == "Пропустить" else message.text
    
    data = user_data[user_id]
    try:
        db.insert_or_update_record(
            user_id, data['record_date'], data['mood'],
            data['work_hours'], data['sleep_hours'], comment
        )
        bot.send_message(user_id, "✅ Запись сохранена! Спасибо.", reply_markup=main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        bot.send_message(user_id, "❌ Произошла ошибка при сохранении. Попробуй позже.")
    finally:
        if user_id in user_data:
            del user_data[user_id]

@bot.message_handler(commands=['stats'])
def stats_command(message):
    try:
        bot.send_message(message.chat.id, "Что хочешь узнать?", reply_markup=stats_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в stats_command: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stats_'))
def process_stats_menu(call):
    user_id = call.message.chat.id
    action = call.data.split('_')[1]
    
    try:
        end_date = date.today()
        if action == 'week':
            start_date = end_date - timedelta(days=7)
            records = db.get_records_period(user_id, start_date, end_date)
            text = Analyzer.format_weekly_stats(records)
            bot.send_message(user_id, text, parse_mode="Markdown")
        elif action == 'month':
            start_date = end_date - timedelta(days=30)
            records = db.get_records_period(user_id, start_date, end_date)
            text = Analyzer.format_monthly_stats(records)
            bot.send_message(user_id, text, parse_mode="Markdown")
        elif action == 'insights':
            text = Analyzer.format_insights(db, user_id)
            bot.send_message(user_id, text, parse_mode="Markdown")
        elif action == 'graph':
            records = db.get_records_period(user_id, date.today() - timedelta(days=60), date.today())
            buf = Analyzer.generate_mood_plot(records, period_days=30)
            if buf:
                bot.send_photo(user_id, buf, caption="📈 График настроения, работы и сна за последние 30 дней")
            else:
                bot.send_message(user_id, "Недостаточно данных для построения графика. Добавьте больше записей.")
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в process_stats_menu: {e}")
        bot.send_message(user_id, "❌ Произошла ошибка при получении статистики.")

@bot.message_handler(commands=['history'])
def history_command(message):
    user_id = message.chat.id
    try:
        records = db.get_last_records(user_id, limit=10)
        if not records:
            bot.send_message(user_id, "История пуста. Добавьте первую запись с помощью /add")
            return
        
        text = "📜 **Последние 10 записей:**\n\n"
        for rec in records:
            date_str = rec['record_date'].strftime('%d.%m.%Y')
            text += f"📅 {date_str}: настроение {rec['mood']}, работа {rec['work_hours']}ч, сон {rec['sleep_hours']}ч"
            if rec['comment']:
                text += f", коммент: {rec['comment']}"
            text += "\n"
        bot.send_message(user_id, text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка в history_command: {e}")
        bot.send_message(user_id, "❌ Произошла ошибка при получении истории.")

@bot.message_handler(commands=['clear'])
def clear_command(message):
    try:
        bot.send_message(
            message.chat.id,
            "⚠️ Вы уверены, что хотите удалить ВСЕ свои данные? Это действие необратимо.",
            reply_markup=confirm_clear_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в clear_command: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('clear_'))
def handle_clear(call):
    user_id = call.message.chat.id
    try:
        if call.data == "clear_confirm":
            db.delete_all_user_data(user_id)
            bot.send_message(user_id, "🗑 Все ваши данные удалены.", reply_markup=main_keyboard())
        else:
            bot.send_message(user_id, "Очистка отменена.", reply_markup=main_keyboard())
        bot.delete_message(user_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в handle_clear: {e}")
        bot.send_message(user_id, "❌ Произошла ошибка при очистке данных.")

@bot.message_handler(commands=['settings'])
def settings_command(message):
    try:
        bot.send_message(
            message.chat.id,
            "⚙️ Настройки пока в разработке. Скоро здесь можно будет настроить время напоминаний и другие параметры.",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в settings_command: {e}")


@bot.message_handler(func=lambda msg: msg.text in ["➕ Записать день", "📊 Статистика", "📜 История", "⚙️ Настройки", "🗑 Очистить данные", "❓ Помощь"])
def handle_buttons(message):
    text = message.text
    if text == "➕ Записать день":
        add_entry(message)
    elif text == "📊 Статистика":
        stats_command(message)
    elif text == "📜 История":
        history_command(message)
    elif text == "⚙️ Настройки":
        settings_command(message)
    elif text == "🗑 Очистить данные":
        clear_command(message)
    elif text == "❓ Помощь":
        help_cmd(message)


if __name__ == "__main__":
    try:
        logger.info("Бот запущен, начинаем polling...")
        while True:
            try:
                bot.polling(none_stop=True, interval=1, timeout=60)
            except Exception as e:
                logger.error(f"Ошибка в polling: {e}")
                time.sleep(5)
                logger.info("Перезапуск polling...")
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        db.close()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        db.close()
        sys.exit(1)
        