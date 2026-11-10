"""
GX SMM MANAGEMENT BOT — safer rebuilt version

This bot provides:
- Separate user and admin menus
- No pre-filled channel/project URL
- Per-user project settings
- Manual top-up proof submission and admin approval
- Balance ledger and request history
- Admin controls for pausing requests and editing support/join links
- Promotion/content-service requests queued for admin review

It intentionally does NOT buy or automate artificial views, reactions, followers,
or other fake engagement. Configure only legitimate services you are authorized
to provide.

Install:
    pip install "python-telegram-bot>=21,<23"
"""

import logging
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Optional

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- কনফিগারেশন ---
BOT_TOKEN = "9201048894:AAFmPupyT_zzzhICH4X2pylIwnrF4YCcMQ4"
ADMIN_ID = 8419760844
REQUIRED_CHAT_ID = "-1003908562163"  # Force Join Group ID
REQUIRED_CHAT_LINK = "https://t.me/GX_SMM_PREMIUM_PANEL"
SUPPORT_LINK = "https://t.me/NIROB_GX"
PAYMENT_INSTRUCTIONS = "📌 Binance UID: 1122595327\n\nপেমেন্ট করে স্ক্রিনশট বা রেফারেন্স এখানে পাঠান।"
DB_PATH = "gx_bot.db"

API_URL = "https://1xpanel.com/api/v2"
API_KEY = "e19e34d1e991b739cc18a9917e6d9144"
DEFAULT_BINANCE_UID = "1122595327"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("gx-bot")

USER_MENU = [
    [KeyboardButton("⚙️ My Project"), KeyboardButton("👤 Profile")],
    [KeyboardButton("📝 New Request"), KeyboardButton("📦 My Requests")],
    [KeyboardButton("💳 Add Balance"), KeyboardButton("🧾 Transactions")],
    [KeyboardButton("🛠 Settings"), KeyboardButton("🎧 Support")],
]
ADMIN_MENU = [
    [KeyboardButton("📊 Admin Dashboard"), KeyboardButton("👥 Users")],
    [KeyboardButton("💰 Pending Top-ups"), KeyboardButton("📋 Pending Requests")],
    [KeyboardButton("⏯ Pause/Resume Requests"), KeyboardButton("⚙️ Admin Settings")],
]

def db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with closing(db()) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
            total_spent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projects (
            user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
            target_link TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS topups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            proof_file_id TEXT,
            note TEXT NOT NULL DEFAULT '',
            amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL,
            reviewed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            project_link TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            admin_note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            amount INTEGER NOT NULL,
            kind TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        defaults = {
            "requests_enabled": "ON",
            "support_link": SUPPORT_LINK,
            "required_chat_id": REQUIRED_CHAT_ID,
            "required_chat_link": REQUIRED_CHAT_LINK,
        }
        for key, value in defaults.items():
            con.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                (key, value),
            )
        con.commit()

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def setting(key: str, fallback: str = "") -> str:
    with closing(db()) as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else fallback

def set_setting(key: str, value: str):
    with closing(db()) as con:
        con.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        con.commit()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID and ADMIN_ID != 0

def menu_for(user_id: int):
    return ReplyKeyboardMarkup(
        ADMIN_MENU if is_admin(user_id) else USER_MENU,
        resize_keyboard=True,
        is_persistent=True,
    )

def ensure_user(tg_user):
    with closing(db()) as con:
        con.execute(
            """INSERT INTO users(user_id,username,first_name,created_at)
               VALUES(?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username=excluded.username, first_name=excluded.first_name""",
            (tg_user.id, tg_user.username or "", tg_user.first_name or "", now()),
        )
        con.execute(
            "INSERT OR IGNORE INTO projects(user_id,target_link,updated_at) VALUES(?,?,?)",
            (tg_user.id, "", now()),
        )
        con.commit()

def valid_telegram_link(value: str) -> bool:
    value = value.strip()
    return bool(
        re.fullmatch(r"(https?://)?t\.me/[A-Za-z0-9_+/=-]+/?", value)
        or re.fullmatch(r"@[A-Za-z0-9_]{5,}", value)
    )

async def joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = setting("required_chat_id")
    if not chat_id or is_admin(update.effective_user.id):
        return True
    try:
        member = await context.bot.get_chat_member(
            chat_id=int(chat_id), user_id=update.effective_user.id
        )
        return member.status in ("member", "administrator", "creator")
    except Exception:
        log.exception("Membership check failed")
        return False

async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await joined(update, context):
        return True
    link = setting("required_chat_link")
    rows = []
    if link:
        rows.append([InlineKeyboardButton("📢 Join group", url=link)])
    rows.append([InlineKeyboardButton("✅ Check again", callback_data="check_join")])
    await update.effective_message.reply_text(
        "বট ব্যবহার করতে আগে নির্ধারিত গ্রুপে যোগ দিন।",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    context.user_data.clear()
    if not await gate(update, context):
        return
    await update.effective_message.reply_text(
        "🟢 GX Service Desk\n\nআপনার প্রজেক্টের লিংক নিজে সেট করুন। "
        "কোনো ডিফল্ট চ্যানেল/গ্রুপ লিংক রাখা নেই।",
        reply_markup=menu_for(update.effective_user.id),
    )

async def show_profile(message, user_id: int):
    with closing(db()) as con:
        u = con.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        p = con.execute("SELECT target_link FROM projects WHERE user_id=?", (user_id,)).fetchone()
        count = con.execute("SELECT COUNT(*) n FROM requests WHERE user_id=?", (user_id,)).fetchone()["n"]
    await message.reply_text(
        f"👤 Profile\nID: {user_id}\nBalance: {u['balance']} credits\n"
        f"Total spent: {u['total_spent']} credits\nRequests: {count}\n"
        f"Project: {p['target_link'] or 'Not configured'}"
    )

async def show_project(message, user_id: int):
    with closing(db()) as con:
        p = con.execute("SELECT target_link FROM projects WHERE user_id=?", (user_id,)).fetchone()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Set / change project link", callback_data="project_edit")]
    ])
    await message.reply_text(
        f"⚙️ My Project\nCurrent link: {p['target_link'] or 'Not set'}",
        reply_markup=kb,
    )

async def show_settings(message, user_id: int):
    with closing(db()) as con:
        p = con.execute("SELECT target_link FROM projects WHERE user_id=?", (user_id,)).fetchone()
    await message.reply_text(
        "🛠 User Settings\n"
        f"Project link: {p['target_link'] or 'Not set'}\n"
        "Use My Project to change the link. Request notifications are sent here."
    )

async def submit_request(message, user_id: int, context):
    with closing(db()) as con:
        p = con.execute("SELECT target_link FROM projects WHERE user_id=?", (user_id,)).fetchone()
    if not p or not p["target_link"]:
        await message.reply_text("আগে ⚙️ My Project থেকে আপনার নিজের লিংক সেট করুন।")
        return
    if setting("requests_enabled", "ON") != "ON":
        await message.reply_text("দুঃখিত, নতুন request আপাতত বন্ধ আছে।")
        return
    context.user_data["awaiting_request_description"] = True
    await message.reply_text(
        "আপনার বৈধ প্রচার/কনটেন্ট/ডিজাইন কাজের বিবরণ লিখুন। "
        "কৃত্রিম views, reactions বা followers কেনার অনুরোধ গ্রহণ করা হয় না।"
    )

async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)
    msg = update.effective_message
    text = (msg.text or "").strip()

    # Admin-only conversation states
    if is_admin(user.id):
        if context.user_data.get("admin_waiting") == "credit":
            context.user_data.pop("admin_waiting", None)
            parts = text.split()
            if len(parts) != 2 or not all(x.isdigit() for x in parts):
                await msg.reply_text("ফরম্যাট: USER_ID AMOUNT")
                return
            uid, amount = map(int, parts)
            if amount <= 0:
                await msg.reply_text("Amount অবশ্যই 0-এর বেশি হতে হবে।")
                return
            with closing(db()) as con:
                exists = con.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone()
                if not exists:
                    await msg.reply_text("এই ইউজার বট চালু করেননি।")
                    return
                con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
                con.execute(
                    "INSERT INTO ledger(user_id,amount,kind,note,created_at) VALUES(?,?,?,?,?)",
                    (uid, amount, "CREDIT", "Admin top-up", now()),
                )
                con.commit()
            await msg.reply_text(f"✅ {amount} credits যোগ হয়েছে।")
            try:
                await context.bot.send_message(uid, f"আপনার ব্যালেন্সে {amount} credits যোগ হয়েছে।")
            except Exception:
                pass
            return

        if context.user_data.get("admin_waiting") == "support":
            set_setting("support_link", text)
            context.user_data.pop("admin_waiting", None)
            await msg.reply_text("Support link আপডেট হয়েছে।")
            return
        if context.user_data.get("admin_waiting") == "join_link":
            set_setting("required_chat_link", text)
            context.user_data.pop("admin_waiting", None)
            await msg.reply_text("Join link আপডেট হয়েছে।")
            return
        if context.user_data.get("admin_waiting") == "join_id":
            set_setting("required_chat_id", text)
            context.user_data.pop("admin_waiting", None)
            await msg.reply_text("Required chat ID আপডেট হয়েছে।")
            return

    # User flow states
    if context.user_data.get("awaiting_project_link"):
        context.user_data.pop("awaiting_project_link", None)
        if not valid_telegram_link(text):
            await msg.reply_text("সঠিক Telegram link বা @username দিন।")
            return
        with closing(db()) as con:
            con.execute(
                "UPDATE projects SET target_link=?,updated_at=? WHERE user_id=?",
                (text, now(), user.id),
            )
            con.commit()
        await msg.reply_text(f"✅ Project link saved:\n{text}", reply_markup=menu_for(user.id))
        return

    if context.user_data.get("awaiting_request_description"):
        context.user_data.pop("awaiting_request_description", None)
        if len(text) < 8:
            await msg.reply_text("আরও বিস্তারিত লিখুন (কমপক্ষে ৮ অক্ষর)।")
            return
        with closing(db()) as con:
            p = con.execute("SELECT target_link FROM projects WHERE user_id=?", (user.id,)).fetchone()
            cur = con.execute(
                """INSERT INTO requests(user_id,project_link,description,status,created_at,updated_at)
                   VALUES(?,?,?,'PENDING',?,?)""",
                (user.id, p["target_link"], text, now(), now()),
            )
            rid = cur.lastrowid
            con.commit()
        await msg.reply_text(f"✅ Request #{rid} admin review-এর জন্য পাঠানো হয়েছে।")
        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"📝 New request #{rid}\nUser: {user.id}\nProject: {p['target_link']}\n"
                    f"Details: {text}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ Mark reviewed", callback_data=f"review_req:{rid}")
                    ]]),
                )
            except Exception:
                log.exception("Could not notify admin")
        return

    if context.user_data.get("awaiting_topup_note"):
        context.user_data.pop("awaiting_topup_note", None)
        with closing(db()) as con:
            con.execute(
                "INSERT INTO topups(user_id,note,created_at) VALUES(?,?,?)",
                (user.id, text, now()),
            )
            topup_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            con.commit()
        await msg.reply_text(f"Top-up request #{topup_id} জমা হয়েছে। প্রমাণ যাচাইয়ের পর admin সিদ্ধান্ত নেবেন।")
        if ADMIN_ID:
            await context.bot.send_message(
                ADMIN_ID, f"💳 Top-up request #{topup_id}\nUser: {user.id}\nNote: {text}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Approve / credit", callback_data=f"topup_credit:{topup_id}")
                ]]),
            )
        return

    # Admin menu
    if is_admin(user.id):
        if text == "📊 Admin Dashboard":
            with closing(db()) as con:
                users = con.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
                pending = con.execute("SELECT COUNT(*) n FROM requests WHERE status='PENDING'").fetchone()["n"]
                topups = con.execute("SELECT COUNT(*) n FROM topups WHERE status='PENDING'").fetchone()["n"]
            await msg.reply_text(
                f"👑 Admin Dashboard\nUsers: {users}\nPending requests: {pending}\nPending top-ups: {topups}\n"
                f"New requests: {setting('requests_enabled','ON')}"
            )
        elif text == "👥 Users":
            with closing(db()) as con:
                rows = con.execute("SELECT user_id,username,balance FROM users ORDER BY created_at DESC LIMIT 20").fetchall()
            lines = [f"{r['user_id']} @{r['username']} — {r['balance']} credits" for r in rows]
            await msg.reply_text("Recent users:\n" + ("\n".join(lines) if lines else "No users"))
        elif text == "💰 Pending Top-ups":
            with closing(db()) as con:
                rows = con.execute("SELECT id,user_id,note FROM topups WHERE status='PENDING' ORDER BY id DESC LIMIT 15").fetchall()
            await msg.reply_text("\n".join([f"#{r['id']} user {r['user_id']}: {r['note']}" for r in rows]) or "No pending top-ups")
        elif text == "📋 Pending Requests":
            with closing(db()) as con:
                rows = con.execute("SELECT id,user_id,project_link,description FROM requests WHERE status='PENDING' ORDER BY id DESC LIMIT 10").fetchall()
            if not rows:
                await msg.reply_text("No pending requests.")
            else:
                for r in rows:
                    await msg.reply_text(
                        f"Request #{r['id']}\nUser: {r['user_id']}\nProject: {r['project_link']}\n{r['description']}",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("Mark reviewed", callback_data=f"review_req:{r['id']}")
                        ]]),
                    )
        elif text == "⏯ Pause/Resume Requests":
            new = "OFF" if setting("requests_enabled", "ON") == "ON" else "ON"
            set_setting("requests_enabled", new)
            await msg.reply_text(f"New requests: {new}")
        elif text == "⚙️ Admin Settings":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Set support link", callback_data="admin_support")],
                [InlineKeyboardButton("Set required chat ID", callback_data="admin_join_id")],
                [InlineKeyboardButton("Set required chat link", callback_data="admin_join_link")],
                [InlineKeyboardButton("Add user credits", callback_data="admin_credit")],
            ])
            await msg.reply_text("Admin Settings", reply_markup=kb)
        else:
            await msg.reply_text("Admin menu থেকে একটি অপশন বেছে নিন।", reply_markup=menu_for(user.id))
        return

    # User menu
    if text == "👤 Profile":
        await show_profile(msg, user.id)
    elif text == "⚙️ My Project":
        await show_project(msg, user.id)
    elif text == "📝 New Request":
        await submit_request(msg, user.id, context)
    elif text == "📦 My Requests":
        with closing(db()) as con:
            rows = con.execute(
                "SELECT id,description,status,created_at FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 10",
                (user.id,),
            ).fetchall()
        await msg.reply_text(
            "\n\n".join([f"#{r['id']} — {r['status']}\n{r['description']}" for r in rows])
            or "এখনো কোনো request নেই।"
        )
    elif text == "💳 Add Balance":
        context.user_data["awaiting_topup_note"] = True
        await msg.reply_text(PAYMENT_INSTRUCTIONS + "\n\nপেমেন্ট রেফারেন্স/বিবরণ লিখুন।")
    elif text == "🧾 Transactions":
        with closing(db()) as con:
            rows = con.execute(
                "SELECT amount,kind,note,created_at FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 10",
                (user.id,),
            ).fetchall()
        await msg.reply_text(
            "\n".join([f"{r['kind']} {r['amount']} — {r['note']}" for r in rows])
            or "কোনো transaction নেই।"
        )
    elif text == "🛠 Settings":
        await show_settings(msg, user.id)
    elif text == "🎧 Support":
        link = setting("support_link")
        await msg.reply_text(f"Support: {link}" if link else "Support link এখনো সেট করা হয়নি।")
    else:
        await msg.reply_text("মেনু থেকে একটি অপশন বেছে নিন।", reply_markup=menu_for(user.id))

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)
    msg = update.effective_message
    if not msg.photo:
        await msg.reply_text("Top-up প্রমাণ হিসেবে একটি ছবি পাঠান।")
        return
    file_id = msg.photo[-1].file_id
    with closing(db()) as con:
        cur = con.execute(
            "INSERT INTO topups(user_id,proof_file_id,note,created_at) VALUES(?,?,?,?)",
            (user.id, file_id, msg.caption or "", now()),
        )
        tid = cur.lastrowid
        con.commit()
    await msg.reply_text(f"Top-up proof #{tid} admin-এর কাছে পাঠানো হয়েছে।")
    if ADMIN_ID:
        await context.bot.send_photo(
            ADMIN_ID, file_id,
            caption=f"Top-up proof #{tid}\nUser: {user.id}\n{msg.caption or ''}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Approve / credit", callback_data=f"topup_credit:{tid}")
            ]]),
        )

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data or ""

    if data == "check_join":
        if await joined(update, context):
            await q.message.edit_text("✅ Membership verified. Send /start")
        else:
            await q.answer("আগে গ্রুপে যোগ দিন।", show_alert=True)
        return

    if data == "project_edit":
        if is_admin(uid):
            await q.answer("Admin account-এ user project menu নেই।", show_alert=True)
            return
        context.user_data["awaiting_project_link"] = True
        await q.message.reply_text("আপনার Telegram channel/group link বা @username পাঠান:")
        return

    if not is_admin(uid):
        await q.answer("এই অপশন শুধু অ্যাডমিনের জন্য।", show_alert=True)
        return

    if data == "admin_credit":
        context.user_data["admin_waiting"] = "credit"
        await q.message.reply_text("ফরম্যাটে পাঠান: USER_ID AMOUNT")
    elif data == "admin_support":
        context.user_data["admin_waiting"] = "support"
        await q.message.reply_text("নতুন support link পাঠান:")
    elif data == "admin_join_id":
        context.user_data["admin_waiting"] = "join_id"
        await q.message.reply_text("Required chat numeric ID পাঠান; বন্ধ করতে ফাঁকা নয়, 0 দিন:")
    elif data == "admin_join_link":
        context.user_data["admin_waiting"] = "join_link"
        await q.message.reply_text("Join group link পাঠান:")
    elif data.startswith("review_req:"):
        rid = int(data.split(":", 1)[1])
        with closing(db()) as con:
            con.execute(
                "UPDATE requests SET status='REVIEWED',updated_at=? WHERE id=?",
                (now(), rid),
            )
            row = con.execute("SELECT user_id FROM requests WHERE id=?", (rid,)).fetchone()
            con.commit()
        await q.message.edit_reply_markup(reply_markup=None)
        if row:
            try:
                await context.bot.send_message(row["user_id"], f"আপনার request #{rid} admin review করেছেন।")
            except Exception:
                pass
    elif data.startswith("topup_credit:"):
        tid = int(data.split(":", 1)[1])
        context.user_data["admin_topup_id"] = tid
        context.user_data["admin_waiting"] = "topup_amount"
        await q.message.reply_text(f"Top-up #{tid} এর জন্য amount লিখুন:")
    else:
        await q.answer("Unknown action", show_alert=True)

async def admin_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) or context.user_data.get("admin_waiting") != "topup_amount":
        return False
    raw = (update.effective_message.text or "").strip()
    context.user_data.pop("admin_waiting", None)
    tid = context.user_data.pop("admin_topup_id", None)
    if not raw.isdigit() or int(raw) <= 0 or not tid:
        await update.effective_message.reply_text("সঠিক positive amount দিন।")
        return True
    amount = int(raw)
    with closing(db()) as con:
        top = con.execute("SELECT user_id,status FROM topups WHERE id=?", (tid,)).fetchone()
        if not top or top["status"] != "PENDING":
            await update.effective_message.reply_text("Top-up পাওয়া যায়নি বা আগেই review হয়েছে।")
            return True
        con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, top["user_id"]))
        con.execute("UPDATE topups SET amount=?,status='APPROVED',reviewed_at=? WHERE id=?", (amount, now(), tid))
        con.execute(
            "INSERT INTO ledger(user_id,amount,kind,note,created_at) VALUES(?,?,?,?,?)",
            (top["user_id"], amount, "CREDIT", f"Top-up #{tid}", now()),
        )
        con.commit()
    await update.effective_message.reply_text(f"✅ Top-up #{tid} approved; {amount} credits added.")
    try:
        await context.bot.send_message(top["user_id"], f"আপনার Top-up #{tid} অনুমোদিত। {amount} credits যোগ হয়েছে।")
    except Exception:
        pass
    return True

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await admin_topup_amount(update, context):
        return
    await handle_user_text(update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled bot error", exc_info=context.error)

def main():
    init_db()
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_error_handler(error_handler)
    log.info("GX Service Desk bot is starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
