import os
import sqlite3

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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

    con.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            purpose TEXT,
            property_type TEXT,
            city TEXT,
            district TEXT,
            address TEXT,
            rooms TEXT,
            area TEXT,
            floor TEXT,
            total_floors TEXT,
            price TEXT,
            furniture TEXT,
            renovation TEXT,
            parking TEXT,
            pets TEXT,
            available_date TEXT,
            whatsapp TEXT,
            extra_info TEXT
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
        await update.message.reply_text(
            "🏠 QAZAQ HOME",
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

    language = "kz" if query.data == "lang_kz" else "ru"

    set_language(query.from_user.id, language)

    await query.edit_message_text(
        "✅ Қазақ тілі таңдалды!"
        if language == "kz"
        else
        "✅ Русский язык выбран!"
    )

    await query.message.reply_text(
        "🏠 QAZAQ HOME",
        reply_markup=main_menu(language)
    )


async def seller_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = get_language(update.effective_user.id) or "kz"

    if language == "kz":
        buttons = [
            ["🏢 Пәтер жалға беремін"],
            ["🏠 Үй жалға беремін"],
            ["🏢 Пәтер сатамын"],
            ["🏠 Үй сатамын"],
            ["⬅️ Артқа"],
        ]
        text = "🧑‍💼 Қандай қызметті таңдайсыз?"
    else:
        buttons = [
            ["🏢 Сдам квартиру"],
            ["🏠 Сдам дом"],
            ["🏢 Продам квартиру"],
            ["🏠 Продам дом"],
            ["⬅️ Назад"],
        ]
        text = "🧑‍💼 Что вы хотите сделать?"

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(
            buttons,
            resize_keyboard=True
        )
    )


async def start_listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "Пәтер жалға" in text or "Сдам квартиру" in text:
        purpose = "rent"
        property_type = "apartment"

    elif "Үй жалға" in text or "Сдам дом" in text:
        purpose = "rent"
        property_type = "house"

    elif "Пәтер сатамын" in text or "Продам квартиру" in text:
        purpose = "sale"
        property_type = "apartment"

    elif "Үй сатамын" in text or "Продам дом" in text:
        purpose = "sale"
        property_type = "house"

    else:
        return

    context.user_data["listing"] = {
        "purpose": purpose,
        "property_type": property_type
    }

    context.user_data["step"] = "city"

    language = get_language(update.effective_user.id) or "kz"

    await update.message.reply_text(
        "📍 Қай қалада орналасқан?"
        if language == "kz"
        else
        "📍 В каком городе находится?"
    )


async def listing_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    listing = context.user_data.get("listing")

    if not listing:
        return

    user_id = update.effective_user.id
    language = get_language(user_id) or "kz"
    text = update.message.text
    step = context.user_data.get("step")

    questions = {
        "city": ("district", "city",
                  "📍 Қай аудан?", "📍 Какой район?"),

        "district": ("address", "district",
                     "🏠 Мекенжайын жазыңыз.",
                     "🏠 Напишите адрес."),

        "address": ("rooms", "address",
                    "🚪 Неше бөлме?",
                    "🚪 Сколько комнат?"),

        "rooms": ("area", "rooms",
                  "📐 Ауданы қанша м²?",
                  "📐 Какая площадь в м²?"),

        "area": ("floor", "area",
                 "🏢 Қай қабат?",
                 "🏢 Какой этаж?"),

        "floor": ("total_floors", "floor",
                  "🏢 Барлығы неше қабат?",
                  "🏢 Сколько всего этажей?"),

        "total_floors": ("price", "total_floors",
                         "💰 Бағасы қанша?\nМысалы: 250 000 тг",
                         "💰 Какая цена?\nНапример: 250 000 тг"),

        "price": ("furniture", "price",
                  "🛋 Жиһаз бар ма?",
                  "🛋 Есть ли мебель?"),

        "furniture": ("renovation", "furniture",
                      "🔨 Жөндеу жағдайы қандай?",
                      "🔨 Какое состояние ремонта?"),

        "renovation": ("parking", "renovation",
                       "🚗 Паркинг бар ма?",
                       "🚗 Есть ли парковка?"),

        "parking": ("pets", "parking",
                    "🐕 Үй жануарларына рұқсат бар ма?",
                    "🐕 Разрешены ли животные?"),

        "pets": ("available_date", "pets",
                 "📅 Қай күннен бастап қолжетімді?",
                 "📅 С какой даты доступно?"),

        "available_date": ("whatsapp", "available_date",
                           "📱 WhatsApp нөміріңізді жазыңыз.",
                           "📱 Напишите номер WhatsApp."),

        "whatsapp": ("extra_info", "whatsapp",
                     "📝 Қосымша ақпарат жазыңыз.\nЕгер жоқ болса: -",
                     "📝 Дополнительная информация.\nЕсли нет: -"),
    }

    if step in questions:
        next_step, field, kz_question, ru_question = questions[step]

        listing[field] = text
        context.user_data["step"] = next_step

        await update.message.reply_text(
            kz_question if language == "kz" else ru_question
        )
        return

    if step == "extra_info":
        listing["extra_info"] = text

        await show_preview(update, context)


async def show_preview(update, context):
    listing = context.user_data["listing"]

    property_type = (
        "Пәтер"
        if listing["property_type"] == "apartment"
        else "Үй"
    )

    purpose = (
        "Жалға беру"
        if listing["purpose"] == "rent"
        else "Сату"
    )

    preview = f"""
🏠 ХАБАРЛАНДЫРУ

🏷 Түрі: {property_type}
📌 Мақсаты: {purpose}

📍 Қала: {listing.get("city", "-")}
📍 Аудан: {listing.get("district", "-")}
🏠 Мекенжай: {listing.get("address", "-")}

🚪 Бөлме: {listing.get("rooms", "-")}
📐 Аудан: {listing.get("area", "-")} м²
🏢 Қабат: {listing.get("floor", "-")} / {listing.get("total_floors", "-")}

💰 Баға: {listing.get("price", "-")}
🛋 Жиһаз: {listing.get("furniture", "-")}
🔨 Жөндеу: {listing.get("renovation", "-")}
🚗 Паркинг: {listing.get("parking", "-")}
🐕 Жануар: {listing.get("pets", "-")}
📅 Қолжетімді: {listing.get("available_date", "-")}

📱 WhatsApp: {listing.get("whatsapp", "-")}
📝 Қосымша: {listing.get("extra_info", "-")}
"""

    keyboard = [
        [InlineKeyboardButton(
            "✅ ЖАРИЯЛАУ",
            callback_data="publish"
        )],
        [InlineKeyboardButton(
            "❌ БОЛДЫРМАУ",
            callback_data="cancel"
        )],
    ]

    await update.message.reply_text(
        preview,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def listing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        context.user_data.clear()

        await query.edit_message_text(
            "❌ Хабарландыру тоқтатылды."
        )
        return

    if query.data == "publish":
        listing = context.user_data.get("listing")

        if not listing:
            return

        con = sqlite3.connect(DB)

        con.execute("""
            INSERT INTO listings (
                telegram_id,
                purpose,
                property_type,
                city,
                district,
                address,
                rooms,
                area,
                floor,
                total_floors,
                price,
                furniture,
                renovation,
                parking,
                pets,
                available_date,
                whatsapp,
                extra_info
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            query.from_user.id,
            listing.get("purpose"),
            listing.get("property_type"),
            listing.get("city"),
            listing.get("district"),
            listing.get("address"),
            listing.get("rooms"),
            listing.get("area"),
            listing.get("floor"),
            listing.get("total_floors"),
            listing.get("price"),
            listing.get("furniture"),
            listing.get("renovation"),
            listing.get("parking"),
            listing.get("pets"),
            listing.get("available_date"),
            listing.get("whatsapp"),
            listing.get("extra_info"),
        ))

        con.commit()
        con.close()

        context.user_data.clear()

        await query.edit_message_text(
            "✅ Хабарландыру сәтті жарияланды!"
        )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    language = get_language(user_id) or "kz"
    button = update.message.text

    if button in [
        "🧑‍💼 САТУШЫ / ЖАЛҒА БЕРУШІ",
        "🧑‍💼 ПРОДАЮ / СДАЮ"
    ]:
        await seller_menu(update, context)
        return

    if button in [
        "🏢 Пәтер жалға беремін",
        "🏠 Үй жалға беремін",
        "🏢 Пәтер сатамын",
        "🏠 Үй сатамын",
        "🏢 Сдам квартиру",
        "🏠 Сдам дом",
        "🏢 Продам квартиру",
        "🏠 Продам дом"
    ]:
        await start_listing(update, context)
        return

    if button in ["⬅️ Артқа", "⬅️ Назад"]:
        await update.message.reply_text(
            "🏠 QAZAQ HOME",
            reply_markup=main_menu(language)
        )
        return

    if context.user_data.get("listing"):
        await listing_handler(update, context)
        return

    if button in ["⚙️ БАПТАУЛАР", "⚙️ НАСТРОЙКИ"]:
        keyboard = [
            [InlineKeyboardButton(
                "🇰🇿 Қазақша",
                callback_data="lang_kz"
            )],
            [InlineKeyboardButton(
                "🇷🇺 Русский",
                callback_data="lang_ru"
            )],
        ]

        await update.message.reply_text(
            "⚙️ Тілді таңдаңыз:"
            if language == "kz"
            else
            "⚙️ Выберите язык:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await update.message.reply_text(
        "🚧 Бұл бөлім әзірлену үстінде."
        if language == "kz"
        else
        "🚧 Этот раздел пока в разработке."
    )


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
        CallbackQueryHandler(
            listing_callback,
            pattern="^(publish|cancel)$"
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
