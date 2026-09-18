import os
import sqlite3

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

DB = "qazaq_home.db"


def init_db():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            language TEXT
        )
    """)
    con.commit()
    con.close()


def get_language(user_id):
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT language FROM users WHERE telegram_id = ?",
        (user_id,)
    ).fetchone()
    con.close()
    return row[0] if row else None


def set_language(user_id, language):
    con = sqlite3.connect(DB)
    con.execute("""
        INSERT INTO users (telegram_id, language)
        VALUES (?, ?)
        ON CONFLICT(telegram_id)
        DO UPDATE SET language = excluded.language
    """, (user_id, language))
    con.commit()
    con.close()


def main_menu(language):
    if language == "ru":
        buttons = [
            ["🏠 ПОИСК КВАРТИРЫ", "👥 ИЩУ СОСЕДА"],
            ["🧑‍💼 ПРОДАЮ / СДАЮ", "❤️ СОХРАНЕННЫЕ"],
            ["👤 МОЙ ПРОФИЛЬ", "✨ РЕЙТИНГ"],
            ["⚙️ НАСТРОЙКИ"],
        ]
    else:
        buttons = [
            ["🏠 ПӘТЕР ІЗДЕУ", "👥 БІРГЕ ПӘТЕР ІЗДЕУ"],
            ["🧑‍💼 САТУШЫ / ЖАЛҒА БЕРУШІ", "❤️ САҚТАЛҒАНДАР"],
            ["👤 МЕНІҢ ПРОФИЛІМ", "✨ РЕЙТИНГ"],
            ["⚙️ БАПТАУЛАР"],
        ]

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    language = get_language(user_id)

    if language:
        text = (
            "🏠 QAZAQ HOME\n\n"
            "Пәтер табуға немесе жалға/сатуға арналған сервис."
            if language == "kz"
            else
            "🏠 QAZAQ HOME\n\n"
            "Сервис для поиска, аренды и продажи жилья."
        )

        await update.message.reply_text(
            text,
            reply_markup=main_menu(language)
        )
        return

    keyboard = [
        [InlineKeyboardButton("🇰🇿 ҚАЗАҚША", callback_data="lang_kz")],
        [InlineKeyboardButton("🇷🇺 РУССКИЙ", callback_data="lang_ru")],
    ]

    await update.message.reply_text(
        "ТІЛДІ ТАҢДАҢЫЗ\nВЫБЕРИТЕ ЯЗЫК",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    language = "kz" if query.data == "lang_kz" else "ru"

    set_language(user_id, language)

    if language == "kz":
        text = "✅ Қазақ тілі таңдалды!"
    else:
        text = "✅ Русский язык выбран!"

    await query.edit_message_text(text)

    await query.message.reply_text(
        "🏠 QAZAQ HOME",
        reply_markup=main_menu(language)
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    language = get_language(user_id) or "kz"
    button = update.message.text

    if button in ["⚙️ БАПТАУЛАР", "⚙️ НАСТРОЙКИ"]:
        keyboard = [
            [
                InlineKeyboardButton(
                    "🇰🇿 Қазақша",
                    callback_data="lang_kz"
                )
            ],
            [
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="lang_ru"
                )
            ],
        ]

        text = (
            "⚙️ Тілді таңдаңыз:"
            if language == "kz"
            else
            "⚙️ Выберите язык:"
        )

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    text = (
        "🚧 Бұл бөлім әзірлену үстінде.\n\n"
        "Жақында толық жұмыс істейді!"
        if language == "kz"
        else
        "🚧 Этот раздел пока в разработке.\n\n"
        "Скоро он будет полностью работать!"
    )

    await update.message.reply_text(text)


def main():
    init_db()

    token = os.environ["TELEGRAM_BOT_TOKEN"]

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(
            language_callback,
            pattern="^lang_(kz|ru)$"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            menu_handler
        )
    )

    app.run_polling()


if __name__ == "__main__":
    main()
