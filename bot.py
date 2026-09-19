import os
import sqlite3
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =========================
# SETTINGS
# =========================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
DB_FILE = "qazaq_home.db"

BACK = "⬅️ АРТҚА"
HOME = "🏠 БАС МӘЗІР"
CANCEL = "❌ БОЛДЫРМАУ"

# =========================
# STATES
# =========================

(
    LANG,

    SELL_TYPE,
    SELL_CITY,
    SELL_ROOMS,
    SELL_ADDRESS,
    SELL_PRICE,
    SELL_ALLOWED,
    SELL_FORBIDDEN,
    SELL_PHOTOS,
    SELL_VIDEO,
    SELL_PHONE,
    SELL_EXTRA,
    SELL_PREVIEW,

    SEARCH_KIND,
    SEARCH_CITY,

    ROOM_MENU,
    ROOM_CITY,
    ROOM_AGE,
    ROOM_BUDGET,
    ROOM_EXTRA,
    ROOM_PREVIEW,

    SETTINGS,
) = range(22)


# =========================
# DATABASE
# =========================

def get_db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        lang TEXT DEFAULT '',
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT DEFAULT '',
        property_type TEXT,
        deal_type TEXT,
        city TEXT,
        rooms TEXT,
        address TEXT,
        price TEXT,
        allowed TEXT,
        forbidden TEXT,
        photos TEXT DEFAULT '',
        video TEXT DEFAULT '',
        phone TEXT,
        extra TEXT DEFAULT '',
        created_at TEXT,
        expires_at TEXT,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS roommates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        city TEXT,
        age TEXT,
        budget TEXT,
        extra TEXT DEFAULT '',
        created_at TEXT,
        expires_at TEXT,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS saved (
        user_id INTEGER,
        item_type TEXT,
        item_id INTEGER,
        UNIQUE(user_id, item_type, item_id)
    );

    CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER,
        seller_id INTEGER,
        item_type TEXT,
        item_id INTEGER,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interaction_id INTEGER,
        from_user INTEGER,
        to_user INTEGER,
        rating_type TEXT,
        stars INTEGER,
        comment TEXT DEFAULT '',
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER,
        item_type TEXT,
        item_id INTEGER,
        reason TEXT,
        created_at TEXT
    );
    """)

    con.commit()
    con.close()


def current_time():
    return datetime.utcnow().isoformat(timespec="seconds")


def expiration_time():
    return (
        datetime.utcnow() + timedelta(days=14)
    ).isoformat(timespec="seconds")


# =========================
# USER
# =========================

def save_user(user):
    con = get_db()

    con.execute("""
        INSERT INTO users(id, username, lang, created_at)
        VALUES (?, ?, '', ?)
        ON CONFLICT(id)
        DO UPDATE SET username=excluded.username
    """, (
        user.id,
        user.username or "",
        current_time()
    ))

    con.commit()
    con.close()


def get_language(user_id):
    con = get_db()

    row = con.execute(
        "SELECT lang FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    con.close()

    if row:
        return row["lang"]

    return ""


def set_language(user_id, lang):
    con = get_db()

    con.execute(
        "UPDATE users SET lang=? WHERE id=?",
        (lang, user_id)
    )

    con.commit()
    con.close()


# =========================
# KEYBOARDS
# =========================

def keyboard(rows):
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True
    )


def main_menu():
    return keyboard([
        ["🏠 ПӘТЕР ІЗДЕУ", "👥 БІРГЕ ПӘТЕР ІЗДЕУ"],
        ["🧑‍💼 САТУШЫ / ЖАЛҒА БЕРУШІ"],
        ["❤️ САҚТАЛҒАНДАР", "👤 МЕНІҢ ПРОФИЛІМ"],
        ["✨ РЕЙТИНГ", "⚙️ БАПТАУЛАР"],
    ])


def back_home():
    return keyboard([
        [BACK, HOME]
    ])


def home_only():
    return keyboard([
        [HOME]
    ])


def language_keyboard():
    return keyboard([
        ["🇰🇿 ҚАЗАҚША", "🇷🇺 РУССКИЙ"]
    ])


# =========================
# START / HOME
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)

    lang = get_language(update.effective_user.id)

    if not lang:
        await update.message.reply_text(
            "ТІЛДІ ТАҢДАҢЫЗ\n\nВЫБЕРИТЕ ЯЗЫК",
            reply_markup=language_keyboard()
        )
        return

    await update.message.reply_text(
        "🏠 Басты мәзір",
        reply_markup=main_menu()
    )


async def go_home(update, context):
    context.user_data.clear()

    if update.message:
        await update.message.reply_text(
            "🏠 Басты мәзір",
            reply_markup=main_menu()
        )

    return ConversationHandler.END


# =========================
# LANGUAGE
# =========================

async def language(update, context):
    text = update.message.text

    if text == "🇰🇿 ҚАЗАҚША":
        set_language(update.effective_user.id, "kk")

        await update.message.reply_text(
            "🇰🇿 Қазақ тілі таңдалды.",
            reply_markup=main_menu()
        )

        return ConversationHandler.END

    if text == "🇷🇺 РУССКИЙ":
        set_language(update.effective_user.id, "ru")

        await update.message.reply_text(
            "🇷🇺 Русский язык выбран.",
            reply_markup=main_menu()
        )

        return ConversationHandler.END

    return LANG


# =========================
# SELLER
# =========================

SELL_TYPES = {
    "🏢 Пәтер жалға беремін": ("apartment", "rent"),
    "🏠 Үй жалға беремін": ("house", "rent"),
    "🏢 Пәтер сатамын": ("apartment", "sale"),
    "🏠 Үй сатамын": ("house", "sale"),
}


async def seller_start(update, context):
    context.user_data["seller"] = {
        "photos": []
    }

    await update.message.reply_text(
        "🧑‍💼 Жарнама түрін таңдаңыз:",
        reply_markup=keyboard([
            ["🏢 Пәтер жалға беремін"],
            ["🏠 Үй жалға беремін"],
            ["🏢 Пәтер сатамын"],
            ["🏠 Үй сатамын"],
            [HOME]
        ])
    )

    return SELL_TYPE


async def seller_type(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text not in SELL_TYPES:
        return SELL_TYPE

    property_type, deal_type = SELL_TYPES[text]

    context.user_data["seller"]["property_type"] = property_type
    context.user_data["seller"]["deal_type"] = deal_type

    await update.message.reply_text(
        "🏙 Қаланы жазыңыз:",
        reply_markup=back_home()
    )

    return SELL_CITY


async def seller_city(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        return await seller_start(update, context)

    context.user_data["seller"]["city"] = text.strip()

    await update.message.reply_text(
        "🚪 Бөлме санын жазыңыз:",
        reply_markup=back_home()
    )

    return SELL_ROOMS


async def seller_rooms(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🏙 Қаланы жазыңыз:",
            reply_markup=back_home()
        )
        return SELL_CITY

    context.user_data["seller"]["rooms"] = text.strip()

    await update.message.reply_text(
        "📍 Мекенжайын жазыңыз:",
        reply_markup=back_home()
    )

    return SELL_ADDRESS


async def seller_address(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🚪 Бөлме санын жазыңыз:",
            reply_markup=back_home()
        )
        return SELL_ROOMS

    context.user_data["seller"]["address"] = text.strip()

    await update.message.reply_text(
        "💰 Бағасын жазыңыз:",
        reply_markup=back_home()
    )

    return SELL_PRICE


async def seller_price(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "📍 Мекенжайын жазыңыз:",
            reply_markup=back_home()
        )
        return SELL_ADDRESS

    context.user_data["seller"]["price"] = text.strip()

    await update.message.reply_text(
        "✅ Рұқсат етіледі:",
        reply_markup=back_home()
    )

    return SELL_ALLOWED


async def seller_allowed(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "💰 Бағасын жазыңыз:",
            reply_markup=back_home()
        )
        return SELL_PRICE

    context.user_data["seller"]["allowed"] = text.strip()

    await update.message.reply_text(
        "🚫 Рұқсат етілмейді:",
        reply_markup=back_home()
    )

    return SELL_FORBIDDEN


async def seller_forbidden(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "✅ Рұқсат етіледі:",
            reply_markup=back_home()
        )
        return SELL_ALLOWED

    context.user_data["seller"]["forbidden"] = text.strip()

    await update.message.reply_text(
        "📸 Фото жіберіңіз.\n\n"
        "Бірнеше фото жіберуге болады.\n"
        "Аяқтаған соң «ДАЙЫН» басыңыз.",
        reply_markup=keyboard([
            ["ДАЙЫН"],
            [BACK, HOME]
        ])
    )

    return SELL_PHOTOS


async def seller_photos(update, context):
    text = update.message.text if update.message else ""

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🚫 Рұқсат етілмейді:",
            reply_markup=back_home()
        )
        return SELL_FORBIDDEN

    if update.message.photo:
        file_id = update.message.photo[-1].file_id

        context.user_data["seller"]["photos"].append(file_id)

        await update.message.reply_text(
            "📸 Фото қабылданды. Тағы фото жіберіңіз немесе «ДАЙЫН» басыңыз.",
            reply_markup=keyboard([
                ["ДАЙЫН"],
                [BACK, HOME]
            ])
        )

        return SELL_PHOTOS

    if text == "ДАЙЫН":
        await update.message.reply_text(
            "🎥 Видео жіберіңіз немесе «ВИДЕО ЖОҚ» басыңыз.",
            reply_markup=keyboard([
                ["ВИДЕО ЖОҚ"],
                [BACK, HOME]
            ])
        )

        return SELL_VIDEO

    return SELL_PHOTOS


async def seller_video(update, context):
    text = update.message.text if update.message else ""

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "📸 Фото жіберіңіз немесе «ДАЙЫН» басыңыз.",
            reply_markup=keyboard([
                ["ДАЙЫН"],
                [BACK, HOME]
            ])
        )
        return SELL_PHOTOS

    if update.message.video:
        context.user_data["seller"]["video"] = (
            update.message.video.file_id
        )
    elif text == "ВИДЕО ЖОҚ":
        context.user_data["seller"]["video"] = ""
    else:
        return SELL_VIDEO

    await update.message.reply_text(
        "📞 Байланыс нөмірін жазыңыз:",
        reply_markup=back_home()
    )

    return SELL_PHONE


async def seller_phone(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🎥 Видео жіберіңіз немесе «ВИДЕО ЖОҚ» басыңыз.",
            reply_markup=keyboard([
                ["ВИДЕО ЖОҚ"],
                [BACK, HOME]
            ])
        )
        return SELL_VIDEO

    context.user_data["seller"]["phone"] = text.strip()

    await update.message.reply_text(
        "📝 Қосымша ақпарат жазыңыз:",
        reply_markup=back_home()
    )

    return SELL_EXTRA


async def seller_extra(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "📞 Байланыс нөмірін жазыңыз:",
            reply_markup=back_home()
        )
        return SELL_PHONE

    context.user_data["seller"]["extra"] = text.strip()

    await show_seller_preview(update, context)

    return SELL_PREVIEW


async def show_seller_preview(update, context):
    s = context.user_data["seller"]

    property_name = (
        "Пәтер"
        if s["property_type"] == "apartment"
        else "Үй"
    )

    deal_name = (
        "Жалға беру"
        if s["deal_type"] == "rent"
        else "Сату"
    )

    text = (
        "👀 ЖАРНАМАНЫ ҚАРАУ\n\n"
        f"🏠 Түрі: {property_name}\n"
        f"📌 Әрекет: {deal_name}\n"
        f"🏙 Қала: {s.get('city', '')}\n"
        f"🚪 Бөлме: {s.get('rooms', '')}\n"
        f"📍 Мекенжай: {s.get('address', '')}\n"
        f"💰 Баға: {s.get('price', '')}\n"
        f"✅ Рұқсат: {s.get('allowed', '')}\n"
        f"🚫 Тыйым: {s.get('forbidden', '')}\n"
        f"📸 Фото: {len(s.get('photos', []))}\n"
        f"🎥 Видео: {'Бар' if s.get('video') else 'Жоқ'}\n"
        f"📝 {s.get('extra', '')}"
    )

    await update.message.reply_text(
        text,
        reply_markup=keyboard([
            ["✏️ ӨЗГЕРТУ"],
            ["✅ ЖАРИЯЛАУ"],
            [CANCEL, HOME]
        ])
    )


async def seller_preview(update, context):
    text = update.message.text

    if text == HOME or text == CANCEL:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "📝 Қосымша ақпарат жазыңыз:",
            reply_markup=back_home()
        )
        return SELL_EXTRA

    if text == "✏️ ӨЗГЕРТУ":
        return await seller_start(update, context)

    if text == "✅ ЖАРИЯЛАУ":
        s = context.user_data["seller"]
        user = update.effective_user

        con = get_db()

        con.execute("""
            INSERT INTO listings (
                user_id,
                username,
                property_type,
                deal_type,
                city,
                rooms,
                address,
                price,
                allowed,
                forbidden,
                photos,
                video,
                phone,
                extra,
                created_at,
                expires_at,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            user.id,
            user.username or "",
            s["property_type"],
            s["deal_type"],
            s["city"],
            s["rooms"],
            s["address"],
            s["price"],
            s["allowed"],
            s["forbidden"],
            ",".join(s["photos"]),
            s.get("video", ""),
            s["phone"],
            s["extra"],
            current_time(),
            expiration_time()
        ))

        con.commit()
        con.close()

        context.user_data.clear()

        await update.message.reply_text(
            "✅ Жарнама сәтті жарияланды!\n\n"
            "⏳ Жарнама 14 күн белсенді болады.",
            reply_markup=main_menu()
        )

        return ConversationHandler.END

    return SELL_PREVIEW


# =========================
# SEARCH
# =========================

async def search_start(update, context):
    context.user_data["search"] = {
        "offset": 0
    }

    await update.message.reply_text(
        "🏠 Нені іздейсіз?",
        reply_markup=keyboard([
            ["🏢 ПӘТЕР ІЗДЕУ"],
            ["🏠 ҮЙ ІЗДЕУ"],
            [HOME]
        ])
    )

    return SEARCH_KIND


async def search_kind(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        return await go_home(update, context)

    if text == "🏢 ПӘТЕР ІЗДЕУ":
        context.user_data["search"]["property_type"] = "apartment"

    elif text == "🏠 ҮЙ ІЗДЕУ":
        context.user_data["search"]["property_type"] = "house"

    else:
        return SEARCH_KIND

    await update.message.reply_text(
        "🏙 Қай қаладан іздейсіз?",
        reply_markup=back_home()
    )

    return SEARCH_CITY


async def search_city(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🏠 Нені іздейсіз?",
            reply_markup=keyboard([
                ["🏢 ПӘТЕР ІЗДЕУ"],
                ["🏠 ҮЙ ІЗДЕУ"],
                [HOME]
            ])
        )
        return SEARCH_KIND

    context.user_data["search"]["city"] = text.strip()
    context.user_data["search"]["offset"] = 0

    await show_listing(update, context)

    return SEARCH_CITY


async def show_listing(update, context):
    search = context.user_data["search"]

    con = get_db()

    rows = con.execute("""
        SELECT *
        FROM listings
        WHERE active=1
        AND property_type=?
        AND city=?
        AND datetime(expires_at) > datetime('now')
        ORDER BY id DESC
    """, (
        search["property_type"],
        search["city"]
    )).fetchall()

    con.close()

    if not rows:
        await update.message.reply_text(
            "😔 Бұл қалада әзірге жарнама жоқ.",
            reply_markup=main_menu()
        )
        return

    index = search.get("offset", 0) % len(rows)

    row = rows[index]

    search["current_id"] = row["id"]

    property_name = (
        "Пәтер"
        if row["property_type"] == "apartment"
        else "Үй"
    )

    deal_name = (
        "Жалға беру"
        if row["deal_type"] == "rent"
        else "Сату"
    )

    text = (
        f"🏠 {property_name} — {deal_name}\n\n"
        f"🏙 Қала: {row['city']}\n"
        f"🚪 Бөлме: {row['rooms']}\n"
        f"📍 Мекенжай: {row['address']}\n"
        f"💰 Баға: {row['price']}\n"
        f"✅ Рұқсат: {row['allowed']}\n"
        f"🚫 Тыйым: {row['forbidden']}\n"
        f"📝 {row['extra']}"
    )

    await update.message.reply_text(
        text,
        reply_markup=keyboard([
            ["⏭ ӨТКІЗУ", "❤️ САҚТАУ"],
            ["✅ ТАҢДАУ", "🚨 ШАҒЫМДАНУ"],
            [BACK, HOME]
        ])
    )


async def search_action(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🏠 Нені іздейсіз?",
            reply_markup=keyboard([
                ["🏢 ПӘТЕР ІЗДЕУ"],
                ["🏠 ҮЙ ІЗДЕУ"],
                [HOME]
            ])
        )
        return SEARCH_KIND

    search = context.user_data.get("search", {})
    current_id = search.get("current_id")

    if not current_id:
        return SEARCH_CITY

    con = get_db()

    row = con.execute(
        "SELECT * FROM listings WHERE id=?",
        (current_id,)
    ).fetchone()

    if not row:
        con.close()
        return SEARCH_CITY

    if text == "⏭ ӨТКІЗУ":
        search["offset"] = search.get("offset", 0) + 1

        con.close()

        await show_listing(update, context)

        return SEARCH_CITY

    if text == "❤️ САҚТАУ":
        con.execute("""
            INSERT OR IGNORE INTO saved(user_id,item_type,item_id)
            VALUES (?, 'listing', ?)
        """, (
            update.effective_user.id,
            current_id
        ))

        con.commit()
        con.close()

        await update.message.reply_text(
            "❤️ Сақталды!",
            reply_markup=keyboard([
                ["⏭ ӨТКІЗУ", "❤️ САҚТАУ"],
                ["✅ ТАҢДАУ", "🚨 ШАҒЫМДАНУ"],
                [BACK, HOME]
            ])
        )

        return SEARCH_CITY

    if text == "🚨 ШАҒЫМДАНУ":
        context.user_data["report_listing"] = current_id

        con.close()

        await update.message.reply_text(
            "🚨 Шағым себебін таңдаңыз:",
            reply_markup=keyboard([
                ["Жалған жарнама"],
                ["Қате ақпарат"],
                ["Күдікті / қауіпті"],
                [BACK, HOME]
            ])
        )

        return SEARCH_CITY

    if text in [
        "Жалған жарнама",
        "Қате ақпарат",
        "Күдікті / қауіпті"
    ]:
        con.execute("""
            INSERT INTO reports(
                reporter_id,
                item_type,
                item_id,
                reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            update.effective_user.id,
            "listing",
            current_id,
            text,
            current_time()
        ))

        con.commit()
        con.close()

        await update.message.reply_text(
            "🚨 Шағым админге жіберілді.",
            reply_markup=main_menu()
        )

        return ConversationHandler.END

    if text == "✅ ТАҢДАУ":
        con.execute("""
            INSERT INTO interactions(
                buyer_id,
                seller_id,
                item_type,
                item_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            update.effective_user.id,
            row["user_id"],
            "listing",
            row["id"],
            current_time()
        ))

        con.commit()
        con.close()

        username = row["username"]

        telegram_text = (
            f"@{username}"
            if username
            else "Username көрсетілмеген"
        )

        await update.message.reply_text(
            "✅ БАЙЛАНЫС АШЫЛДЫ\n\n"
            f"📞 WhatsApp: {row['phone']}\n"
            f"👤 Telegram: {telegram_text}\n\n"
            "Енді сатушымен байланыса аласыз.",
            reply_markup=keyboard([
                ["⏭ ӨТКІЗУ"],
                [BACK, HOME]
            ])
        )

        return SEARCH_CITY

    con.close()

    return SEARCH_CITY


# =========================
# ROOMMATE
# =========================

async def roommate_start(update, context):
    await update.message.reply_text(
        "👥 БІРГЕ ПӘТЕР ІЗДЕУ",
        reply_markup=keyboard([
            ["🔎 ІЗДЕУ", "📝 АНКЕТА ҚАЛДЫРУ"],
            [HOME]
        ])
    )

    return ROOM_MENU


async def roommate_menu(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == "📝 АНКЕТА ҚАЛДЫРУ":
        context.user_data["room"] = {}

        await update.message.reply_text(
            "🏙 Қаланы жазыңыз:",
            reply_markup=back_home()
        )

        return ROOM_CITY

    if text == "🔎 ІЗДЕУ":
        context.user_data["room_search"] = {
            "offset": 0
        }

        await update.message.reply_text(
            "🏙 Қай қаладан іздейсіз?",
            reply_markup=back_home()
        )

        return ROOM_CITY

    return ROOM_MENU


async def roommate_city(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "👥 БІРГЕ ПӘТЕР ІЗДЕУ",
            reply_markup=keyboard([
                ["🔎 ІЗДЕУ", "📝 АНКЕТА ҚАЛДЫРУ"],
                [HOME]
            ])
        )
        return ROOM_MENU

    if "room" in context.user_data:
        context.user_data["room"]["city"] = text.strip()

        await update.message.reply_text(
            "🎂 Жасыңызды жазыңыз:",
            reply_markup=back_home()
        )

        return ROOM_AGE

    context.user_data["room_search"]["city"] = text.strip()

    await show_roommate(update, context)

    return ROOM_CITY


async def roommate_age(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🏙 Қаланы жазыңыз:",
            reply_markup=back_home()
        )
        return ROOM_CITY

    context.user_data["room"]["age"] = text.strip()

    await update.message.reply_text(
        "💰 Бюджетіңізді жазыңыз:",
        reply_markup=back_home()
    )

    return ROOM_BUDGET


async def roommate_budget(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🎂 Жасыңызды жазыңыз:",
            reply_markup=back_home()
        )
        return ROOM_AGE

    context.user_data["room"]["budget"] = text.strip()

    await update.message.reply_text(
        "📝 Қосымша ақпарат:",
        reply_markup=back_home()
    )

    return ROOM_EXTRA


async def roommate_extra(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "💰 Бюджетіңізді жазыңыз:",
            reply_markup=back_home()
        )
        return ROOM_BUDGET

    context.user_data["room"]["extra"] = text.strip()

    r = context.user_data["room"]

    await update.message.reply_text(
        "👀 АНКЕТАНЫ ҚАРАУ\n\n"
        f"🏙 Қала: {r['city']}\n"
        f"🎂 Жасы: {r['age']}\n"
        f"💰 Бюджет: {r['budget']}\n"
        f"📝 {r['extra']}",
        reply_markup=keyboard([
            ["✏️ ӨЗГЕРТУ"],
            ["✅ ЖАРИЯЛАУ"],
            [CANCEL, BACK, HOME]
        ])
    )

    return ROOM_PREVIEW


async def roommate_preview(update, context):
    text = update.message.text

    if text == HOME or text == CANCEL:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "📝 Қосымша ақпарат:",
            reply_markup=back_home()
        )
        return ROOM_EXTRA

    if text == "✏️ ӨЗГЕРТУ":
        context.user_data["room"] = {}

        await update.message.reply_text(
            "🏙 Қаланы жазыңыз:",
            reply_markup=back_home()
        )

        return ROOM_CITY

    if text == "✅ ЖАРИЯЛАУ":
        user = update.effective_user

        if not user.username:
            await update.message.reply_text(
                "⚠️ Анкетаны жариялау үшін Telegram username керек.\n\n"
                "Telegram → Settings → Username арқылы username қойыңыз.",
                reply_markup=main_menu()
            )

            return ConversationHandler.END

        r = context.user_data["room"]

        con = get_db()

        con.execute("""
            INSERT INTO roommates(
                user_id,
                username,
                city,
                age,
                budget,
                extra,
                created_at,
                expires_at,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            user.id,
            user.username,
            r["city"],
            r["age"],
            r["budget"],
            r["extra"],
            current_time(),
            expiration_time()
        ))

        con.commit()
        con.close()

        context.user_data.clear()

        await update.message.reply_text(
            "✅ Анкета жарияланды!\n\n"
            "⏳ Анкета 14 күн белсенді болады.",
            reply_markup=main_menu()
        )

        return ConversationHandler.END

    return ROOM_PREVIEW


async def show_roommate(update, context):
    search = context.user_data["room_search"]

    con = get_db()

    rows = con.execute("""
        SELECT *
        FROM roommates
        WHERE active=1
        AND city=?
        AND datetime(expires_at)>datetime('now')
        ORDER BY id DESC
    """, (
        search["city"],
    )).fetchall()

    con.close()

    if not rows:
        await update.message.reply_text(
            "😔 Бұл қалада әзірге анкета жоқ.",
            reply_markup=main_menu()
        )

        return

    index = search.get("offset", 0) % len(rows)

    row = rows[index]

    search["current_id"] = row["id"]

    await update.message.reply_text(
        "👥 БІРГЕ ПӘТЕР ІЗДЕУ\n\n"
        f"🏙 Қала: {row['city']}\n"
        f"🎂 Жасы: {row['age']}\n"
        f"💰 Бюджет: {row['budget']}\n"
        f"📝 {row['extra']}",
        reply_markup=keyboard([
            ["⏭ ӨТКІЗУ", "❤️ САҚТАУ"],
            ["✅ ТАҢДАУ"],
            [BACK, HOME]
        ])
    )


async def roommate_search_action(update, context):
    text = update.message.text

    if text == HOME:
        return await go_home(update, context)

    if text == BACK:
        await update.message.reply_text(
            "🏙 Қай қаладан іздейсіз?",
            reply_markup=back_home()
        )
        return ROOM_CITY

    search = context.user_data.get("room_search", {})
    current_id = search.get("current_id")

    if not current_id:
        return ROOM_CITY

    con = get_db()

    row = con.execute(
        "SELECT * FROM roommates WHERE id=?",
        (current_id,)
    ).fetchone()

    if not row:
        con.close()
        return ROOM_CITY

    if text == "⏭ ӨТКІЗУ":
        search["offset"] = search.get("offset", 0) + 1

        con.close()

        await show_roommate(update, context)

        return ROOM_CITY

    if text == "❤️ САҚТАУ":
        con.execute("""
            INSERT OR IGNORE INTO saved(
                user_id,
                item_type,
                item_id
            )
            VALUES (?, 'roommate', ?)
        """, (
            update.effective_user.id,
            current_id
        ))

        con.commit()
        con.close()

        await update.message.reply_text(
            "❤️ Сақталды!",
            reply_markup=keyboard([
                ["⏭ ӨТКІЗУ", "❤️ САҚТАУ"],
                ["✅ ТАҢДАУ"],
                [BACK, HOME]
            ])
        )

        return ROOM_CITY

    if text == "✅ ТАҢДАУ":
        con.execute("""
            INSERT INTO interactions(
                buyer_id,
                seller_id,
                item_type,
                item_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            update.effective_user.id,
            row["user_id"],
            "roommate",
            row["id"],
            current_time()
        ))

        con.commit()
        con.close()

        await update.message.reply_text(
            "✅ БАЙЛАНЫС АШЫЛДЫ\n\n"
            f"👤 Telegram: @{row['username']}",
            reply_markup=keyboard([
                ["⏭ ӨТКІЗУ"],
                [BACK, HOME]
            ])
        )

        return ROOM_CITY

    con.close()

    return ROOM_CITY


# =========================
# SAVED
# =========================

async def saved(update, context):
    con = get_db()

    rows = con.execute("""
        SELECT
            s.item_type,
            s.item_id,
            l.city AS listing_city,
            l.price,
            l.property_type,
            r.city AS room_city,
            r.age,
            r.budget
        FROM saved s
        LEFT JOIN listings l
            ON s.item_type='listing'
            AND s.item_id=l.id
        LEFT JOIN roommates r
            ON s.item_type='roommate'
            AND s.item_id=r.id
        WHERE s.user_id=?
        ORDER BY rowid DESC
    """, (
        update.effective_user.id,
    )).fetchall()

    con.close()

    if not rows:
        await update.message.reply_text(
            "❤️ Сақталғандар бос.",
            reply_markup=main_menu()
        )
        return

    text = "❤️ САҚТАЛҒАНДАР\n\n"

    for i, row in enumerate(rows, 1):

        if row["item_type"] == "listing":
            property_name = (
                "Пәтер"
                if row["property_type"] == "apartment"
                else "Үй"
            )

            text += (
                f"{i}. 🏠 {property_name}\n"
                f"   🏙 {row['listing_city']}\n"
                f"   💰 {row['price']}\n\n"
            )

        else:
            text += (
                f"{i}. 👥 Бірге пәтер\n"
                f"   🏙 {row['room_city']}\n"
                f"   🎂 {row['age']} жас\n"
                f"   💰 {row['budget']}\n\n"
            )

    await update.message.reply_text(
        text,
        reply_markup=main_menu()
    )


# =========================
# PROFILE
# =========================

async def profile(update, context):
    user_id = update.effective_user.id

    con = get_db()

    seller = con.execute("""
        SELECT
            AVG(stars) AS avg,
            COUNT(*) AS count
        FROM ratings
        WHERE to_user=?
        AND rating_type='seller'
    """, (
        user_id,
    )).fetchone()

    buyer = con.execute("""
        SELECT
            AVG(stars) AS avg,
            COUNT(*) AS count
        FROM ratings
        WHERE to_user=?
        AND rating_type='buyer'
    """, (
        user_id,
    )).fetchone()

    con.close()

    seller_avg = seller["avg"] or 0
    buyer_avg = buyer["avg"] or 0

    await update.message.reply_text(
        "👤 МЕНІҢ ПРОФИЛІМ\n\n"
        f"🏠 САТУШЫ РЕЙТИНГІМ\n"
        f"⭐ {seller_avg:.1f} / 5\n"
        f"Бағалау: {seller['count']}\n\n"
        f"🔎 САТЫП АЛУШЫ РЕЙТИНГІМ\n"
        f"⭐ {buyer_avg:.1f} / 5\n"
        f"Бағалау: {buyer['count']}",
        reply_markup=keyboard([
            ["📞 АДМИНМЕН ХАБАРЛАСУ"],
            [HOME]
        ])
    )


# =========================
# RATING
# =========================

async def rating_page(update, context):
    user_id = update.effective_user.id

    con = get_db()

    seller = con.execute("""
        SELECT AVG(stars) avg, COUNT(*) count
        FROM ratings
        WHERE to_user=?
        AND rating_type='seller'
    """, (user_id,)).fetchone()

    buyer = con.execute("""
        SELECT AVG(stars) avg, COUNT(*) count
        FROM ratings
        WHERE to_user=?
        AND rating_type='buyer'
    """, (user_id,)).fetchone()

    con.close()

    await update.message.reply_text(
        "✨ РЕЙТИНГ\n\n"
        f"🏠 Сатушы: ⭐ {seller['avg'] or 0:.1f}/5 "
        f"({seller['count']})\n\n"
        f"🔎 Сатып алушы: ⭐ {buyer['avg'] or 0:.1f}/5 "
        f"({buyer['count']})",
        reply_markup=main_menu()
    )


# =========================
# SETTINGS
# =========================

async def settings(update, context):
    await update.message.reply_text(
        "⚙️ БАПТАУЛАР",
        reply_markup=keyboard([
            ["🇰🇿 ҚАЗАҚША", "🇷🇺 РУССКИЙ"],
            [BACK, HOME]
        ])
    )


async def settings_action(update, context):
    text = update.message.text

    if text == HOME:
        await go_home(update, context)
        return

    if text == BACK:
        await update.message.reply_text(
            "🏠 Басты мәзір",
            reply_markup=main_menu()
        )
        return

    if text == "🇰🇿 ҚАЗАҚША":
        set_language(update.effective_user.id, "kk")

        await update.message.reply_text(
            "🇰🇿 Қазақша таңдалды.",
            reply_markup=main_menu()
        )

    elif text == "🇷🇺 РУССКИЙ":
        set_language(update.effective_user.id, "ru")

        await update.message.reply_text(
            "🇷🇺 Русский выбран.",
            reply_markup=main_menu()
        )


# =========================
# ADMIN
# =========================

async def admin(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ Қолжетім жоқ."
        )
        return

    await update.message.reply_text(
        "🛠 АДМИН ПАНЕЛІ",
        reply_markup=keyboard([
            ["👥 Қолданушылар", "🏠 Жарнамалар"],
            ["👥 Анкеталар", "🚨 Шағымдар"],
            ["📊 Статистика"],
            [HOME]
        ])
    )


async def admin_action(update, context):
    if update.effective_user.id != ADMIN_ID:
        return

    text = update.message.text

    con = get_db()

    if text == "👥 Қолданушылар":

        count = con.execute(
            "SELECT COUNT(*) count FROM users"
        ).fetchone()["count"]

        await update.message.reply_text(
            f"👥 Қолданушылар: {count}",
            reply_markup=main_menu()
        )

    elif text == "🏠 Жарнамалар":

        count = con.execute(
            "SELECT COUNT(*) count FROM listings WHERE active=1"
        ).fetchone()["count"]

        await update.message.reply_text(
            f"🏠 Белсенді жарнамалар: {count}",
            reply_markup=main_menu()
        )

    elif text == "👥 Анкеталар":

        count = con.execute(
            "SELECT COUNT(*) count FROM roommates WHERE active=1"
        ).fetchone()["count"]

        await update.message.reply_text(
            f"👥 Белсенді анкеталар: {count}",
            reply_markup=main_menu()
        )

    elif text == "🚨 Шағымдар":

        count = con.execute(
            "SELECT COUNT(*) count FROM reports"
        ).fetchone()["count"]

        await update.message.reply_text(
            f"🚨 Шағымдар: {count}",
            reply_markup=main_menu()
        )

    elif text == "📊 Статистика":

        users = con.execute(
            "SELECT COUNT(*) count FROM users"
        ).fetchone()["count"]

        listings = con.execute(
            "SELECT COUNT(*) count FROM listings"
        ).fetchone()["count"]

        roommates = con.execute(
            "SELECT COUNT(*) count FROM roommates"
        ).fetchone()["count"]

        await update.message.reply_text(
            "📊 СТАТИСТИКА\n\n"
            f"👥 Қолданушылар: {users}\n"
            f"🏠 Жарнамалар: {listings}\n"
            f"👥 Анкеталар: {roommates}",
            reply_markup=main_menu()
        )

    elif text == HOME:
        await go_home(update, context)

    con.close()


# =========================
# FALLBACK
# =========================

async def unknown(update, context):
    if update.message:
        await update.message.reply_text(
            "Мәзірден таңдаңыз:",
            reply_markup=main_menu()
        )


# =========================
# MAIN
# =========================

def main():

    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN variable is missing"
        )

    init_db()

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # LANGUAGE
    language_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    r"^(🇰🇿 ҚАЗАҚША|🇷🇺 РУССКИЙ)$"
                ),
                language
            )
        ],
        states={
            LANG: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    language
                )
            ]
        },
        fallbacks=[]
    )

    # SELLER
    seller_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    r"^🧑‍💼 САТУШЫ / ЖАЛҒА БЕРУШІ$"
                ),
                seller_start
            )
        ],
        states={

            SELL_TYPE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_type
                )
            ],

            SELL_CITY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_city
                )
            ],

            SELL_ROOMS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_rooms
                )
            ],

            SELL_ADDRESS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_address
                )
            ],

            SELL_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_price
                )
            ],

            SELL_ALLOWED: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_allowed
                )
            ],

            SELL_FORBIDDEN: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_forbidden
                )
            ],

            SELL_PHOTOS: [
                MessageHandler(
                    filters.PHOTO |
                    (filters.TEXT & ~filters.COMMAND),
                    seller_photos
                )
            ],

            SELL_VIDEO: [
                MessageHandler(
                    filters.VIDEO |
                    (filters.TEXT & ~filters.COMMAND),
                    seller_video
                )
            ],

            SELL_PHONE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_phone
                )
            ],

            SELL_EXTRA: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_extra
                )
            ],

            SELL_PREVIEW: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    seller_preview
                )
            ],
        },

        fallbacks=[
            CommandHandler("start", start)
        ]
    )

    # SEARCH
    search_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    r"^🏠 ПӘТЕР ІЗДЕУ$"
                ),
                search_start
            )
        ],

        states={

            SEARCH_KIND: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    search_kind
                )
            ],

            SEARCH_CITY: [
                MessageHandler(
                    filters.Regex(
                        r"^(⏭ ӨТКІЗУ|❤️ САҚТАУ|"
                        r"✅ ТАҢДАУ|🚨 ШАҒЫМДАНУ|"
                        r"Жалған жарнама|Қате ақпарат|"
                        r"Күдікті / қауіпті)$"
                    ),
                    search_action
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    search_city
                )
            ],
        },

        fallbacks=[
            CommandHandler("start", start)
        ]
    )

    # ROOMMATE
    roommate_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    r"^👥 БІРГЕ ПӘТЕР ІЗДЕУ$"
                ),
                roommate_start
            )
        ],

        states={

            ROOM_MENU: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    roommate_menu
                )
            ],

            ROOM_CITY: [
                MessageHandler(
                    filters.Regex(
                        r"^(⏭ ӨТКІЗУ|❤️ САҚТАУ|✅ ТАҢДАУ)$"
                    ),
                    roommate_search_action
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    roommate_city
                )
            ],

            ROOM_AGE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    roommate_age
                )
            ],

            ROOM_BUDGET: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    roommate_budget
                )
            ],

            ROOM_EXTRA: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    roommate_extra
                )
            ],

            ROOM_PREVIEW: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    roommate_preview
                )
            ],
        },

        fallbacks=[
            CommandHandler("start", start)
        ]
    )

    # BASIC COMMANDS
    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("admin", admin)
    )

    app.add_handler(language_conv)
    app.add_handler(seller_conv)
    app.add_handler(search_conv)
    app.add_handler(roommate_conv)

    # MAIN MENU
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^❤️ САҚТАЛҒАНДАР$"),
            saved
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^👤 МЕНІҢ ПРОФИЛІМ$"),
            profile
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^✨ РЕЙТИНГ$"),
            rating_page
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^⚙️ БАПТАУЛАР$"),
            settings
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(🇰🇿 ҚАЗАҚША|🇷🇺 РУССКИЙ)$"
            ),
            settings_action
        )
    )

    # ADMIN
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(👥 Қолданушылар|🏠 Жарнамалар|"
                r"👥 Анкеталар|🚨 Шағымдар|📊 Статистика)$"
            ),
            admin_action
        )
    )

    # UNKNOWN
    app.add_handler(
        MessageHandler(
            filters.ALL,
            unknown
        )
    )

    print("QAZAQ HOME BOT STARTED")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
