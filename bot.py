import logging
import sqlite3
import requests
import os
import math
from urllib.parse import urlparse
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# --- কনফিগারেশন ---
TOKEN = os.getenv("9201048894:AAH4gNA1m_UphXVvKD6HmXcm5YMDbr2HOOo", "")
ADMIN_ID = 8419760844
REQUIRED_CHANNEL = "-1003908562163"  # Force Join Group ID
ORDER_CHANNEL_LINK = "https://t.me/GX_SMM_PREMIUM_PANEL"
API_URL = "https://1xpanel.com/api/v2"
API_KEY = os.getenv("e19e34d1e991b739cc18a9917e6d9144", "")
REACTION_SERVICE_ID = os.getenv("1936", "")
VIEW_SERVICE_ID = os.getenv("1936, "")
DEFAULT_BINANCE_UID = "1122595327"

# লগিং সেটআপ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ডাটাবেস সেটাপ ---
def init_db():
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            coins INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            active_projects INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referral_income INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_setups (
            user_id INTEGER PRIMARY KEY,
            channel_link TEXT DEFAULT 'Not set',
            views_count INTEGER DEFAULT 500,
            reacts_count INTEGER DEFAULT 500,
            react_service TEXT DEFAULT 'ON',
            view_service TEXT DEFAULT 'OFF',
            emojis TEXT DEFAULT '👍 ❤️ 🔥'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_id TEXT,
            link TEXT,
            quantity TEXT,
            status TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('binance_uid', ?)", (DEFAULT_BINANCE_UID,))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('global_orders', 'ON')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_premium', 'True')")
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""

def update_setting(key, value):
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# --- নিখুঁত লিংক ক্লিনার ---
def clean_telegram_link(raw_text):
    text = raw_text.strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text.startswith("@"):
        text = text[1:]
    return f"https://t.me/{text}"

# --- 1xPanel API ---
class OneXPanelAPI:
    def __init__(self, api_key):
        self.api_url = API_URL
        self.api_key = api_key

    def order(self, data):
        post = {'key': self.api_key, 'action': 'add'}
        post.update(data)
        try:
            response = requests.post(self.api_url, data=post, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"API Order Error: {e}")
            return {"error": "API Connection Failed"}

api_client = OneXPanelAPI(API_KEY)

# --- কিবোর্ড সেটআপ ---
def get_user_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⚙️ Setup"), KeyboardButton("👤 Profile")],
        [KeyboardButton("🛠️ Settings"), KeyboardButton("💳 Top-up")],
        [KeyboardButton("📦 Order List"), KeyboardButton("🎧 Support")],
        [KeyboardButton("💎 TON Income"), KeyboardButton("👥 Refer & Earn")]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👑 Admin Panel"), KeyboardButton("⚙️ Setup")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🛠️ Settings")],
        [KeyboardButton("💳 Top-up"), KeyboardButton("📦 Order List")],
        [KeyboardButton("🎧 Support"), KeyboardButton("💎 TON Income")],
        [KeyboardButton("👥 Refer & Earn")]
    ], resize_keyboard=True)

async def check_forced_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        logger.error(f"Force join check error: {e}")
    return False

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, coins) VALUES (?, 0)", (user_id,))
    cursor.execute("INSERT OR IGNORE INTO user_setups (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    if not await check_forced_join(update, context):
        inline_kb = [
            [InlineKeyboardButton("📢 Join Group/Channel", url=ORDER_CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Joined, Check Again", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ বট ব্যবহারের জন্য প্রথমে আমাদের অফিশিয়াল গ্রুপে জয়েন করতে হবে!\nদয়া করে জয়েন করে নিচের বাটনে ক্লিক করুন।",
            reply_markup=InlineKeyboardMarkup(inline_kb)
        )
        return

    await show_dashboard(update, context)

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    cursor.execute("SELECT channel_link, views_count, reacts_count FROM user_setups WHERE user_id = ?", (user_id,))
    setup_row = cursor.fetchone()
    conn.close()

    coins = row[0] if row else 0
    ch_link, views, reacts = setup_row if setup_row else ('Not set', 500, 500)

    is_prem = get_setting("is_premium") == "True"
    badge = "👑 [PREMIUM]" if is_prem else ""
    keyboard = get_admin_keyboard() if user_id == ADMIN_ID else get_user_keyboard()

    text = (
        f"Telegram Super Service {badge}\n"
        f"110 monthly users\n\n"
        f"🔗 Channel: {ch_link}\n"
        f"👀 Views: {views}\n"
        f"❤️ Reacts: {reacts}\n\n"
        f"🔥 **GX SMM PREMIUM PANEL** 🔥\n"
        f"💰 আপনার বর্তমান ব্যালেন্স: **{coins} coins**"
    )

    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        except:
            await update.callback_query.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

# --- সেটআপ মেনু খোলার ডেডিকেটেড ফাংশন ---
async def open_setup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_link, views_count, reacts_count FROM user_setups WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    ch, views, reacts = row if row else ('Not set', 500, 500)

    text = (
        f"⚙️ **Setup Menu**\n\n"
        f"🔗 Channel: {ch}\n"
        f"👀 Views: {views}\n"
        f"❤️ Reacts: {reacts}"
    )

    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔗 Channel: {ch}", callback_data="setup_set_channel")],
        [InlineKeyboardButton(f"👀 Views: {views}", callback_data="setup_set_views"),
         InlineKeyboardButton(f"❤️ Reacts: {reacts}", callback_data="setup_set_reacts")],
        [InlineKeyboardButton("✅ Save Setup", callback_data="setup_save")]
    ])

    await update.message.reply_text(text, reply_markup=inline_kb, parse_mode="Markdown")

# --- সেটিংস কার্ড দেখানোর ডেডিকেটেড ফাংশন ---
async def open_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_link, react_service, view_service, reacts_count, views_count, emojis FROM user_setups WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    ch, r_s, v_s, r_c, v_c, emo = row if row else ("Not set", "ON", "OFF", 500, 500, "👍 ❤️ 🔥")
    ch_name = ch.split('/')[-1] if '/' in ch else ch

    r_btn = f"👍 React: {r_s} {'✅' if r_s=='ON' else '❌'}"
    v_btn = f"👁 Views: {v_s} {'✅' if v_s=='ON' else '❌'}"

    card_text = (
        f"🛠️ **Project Settings: {ch_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 **Link:** {ch}\n"
        f"👍 **Reaction Service:** {r_s}\n"
        f"👁 **View Service:** {v_s}\n"
        f"🚀 **Reaction Count:** {r_c}\n"
        f"👁 **View Count:** {v_c}\n"
        f"😊 **Emoji:** POSITIVE {emo}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(r_btn, callback_data="toggle_react"), InlineKeyboardButton(v_btn, callback_data="toggle_view")],
        [InlineKeyboardButton("✏️ Edit Settings", callback_data="edit_settings_btn")]
    ])

    await update.message.reply_text(card_text, reply_markup=kb, parse_mode="Markdown")

# --- কলারব্যাক হ্যান্ডলার ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "check_join":
        if await check_forced_join(update, context):
            await query.message.delete()
            await show_dashboard(update, context)
        else:
            await query.answer("❌ আপনি এখনো গ্রুপে জয়েন করেননি!", show_alert=True)

    elif data == "setup_set_channel":
        context.user_data['setup_step'] = 'inline_wait_channel'
        await query.message.reply_text("🔗 আপনার চ্যানেলের বা গ্রুপের লিংক/ইউজারনেম দিন (যেমন: `@GX_BIG_COMMUNITY`):")

    elif data == "setup_set_views":
        context.user_data['setup_step'] = 'inline_wait_views'
        await query.message.reply_text("👀 কত ভিউ নিতে চান? (সংখ্যা লিখুন, যেমন: 500):")

    elif data == "setup_set_reacts":
        context.user_data['setup_step'] = 'inline_wait_reacts'
        await query.message.reply_text("❤️ কত রিঅ্যাকশন নিতে চান? (সংখ্যা লিখুন, যেমন: 500):")

    elif data == "setup_save":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT channel_link, views_count, reacts_count FROM user_setups WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        ch, v_cnt, r_cnt = row if row else ('Not set', 500, 500)
        
        v_cost = int((int(v_cnt) / 1000) * 2000)
        r_cost = int((int(r_cnt) / 1000) * 3000)

        saved_text = (
            f"✅ **Setup Saved!**\n\n"
            f"📡 {ch}\n"
            f"👀 Views: {v_cnt} ({v_cost} Coins/post)\n"
            f"❤️ Reacts: {r_cnt} ({r_cost} Coins/post)"
        )
        await query.message.edit_text(saved_text, parse_mode="Markdown")
        
        # ড্যাশবোর্ড আপডেট পাঠানো
        dummy_update = Update(update.update_id, message=query.message)
        await show_dashboard(dummy_update, context)

    elif data == "toggle_react":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT react_service FROM user_setups WHERE user_id = ?", (user_id,))
        curr = cursor.fetchone()[0]
        new_val = "OFF" if curr == "ON" else "ON"
        cursor.execute("UPDATE user_setups SET react_service = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        conn.close()
        await render_settings_msg_inline(query, user_id)

    elif data == "toggle_view":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT view_service FROM user_setups WHERE user_id = ?", (user_id,))
        curr = cursor.fetchone()[0]
        new_val = "OFF" if curr == "ON" else "ON"
        cursor.execute("UPDATE user_setups SET view_service = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        conn.close()
        await render_settings_msg_inline(query, user_id)

    elif data == "edit_settings_btn":
        await open_setup_menu_inline(query, user_id)

    elif data.startswith("approve_pay_"):
        target_uid = data.split("_")[2]
        context.user_data['target_user_for_coins'] = target_uid
        context.user_data['waiting_admin_coin_input'] = True
        await query.message.reply_text(f"👤 ইউজার আইডি: `{target_uid}`\n\n✍️ কত কয়েন দিতে চান তা লিখুন:", parse_mode="Markdown")

    elif data == "toggle_premium_mode":
        curr = get_setting("is_premium") == "True"
        new_v = "False" if curr else "True"
        update_setting("is_premium", new_v)
        await query.answer(f"Premium Mode set to {new_v}", show_alert=True)

async def render_settings_msg_inline(query, user_id):
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_link, react_service, view_service, reacts_count, views_count, emojis FROM user_setups WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    ch, r_s, v_s, r_c, v_c, emo = row if row else ("Not set", "ON", "OFF", 500, 500, "👍 ❤️ 🔥")
    ch_name = ch.split('/')[-1] if '/' in ch else ch

    r_btn = f"👍 React: {r_s} {'✅' if r_s=='ON' else '❌'}"
    v_btn = f"👁 Views: {v_s} {'✅' if v_s=='ON' else '❌'}"

    card_text = (
        f"🛠️ **Project Settings: {ch_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 **Link:** {ch}\n"
        f"👍 **Reaction Service:** {r_s}\n"
        f"👁 **View Service:** {v_s}\n"
        f"🚀 **Reaction Count:** {r_c}\n"
        f"👁 **View Count:** {v_c}\n"
        f"😊 **Emoji:** POSITIVE {emo}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(r_btn, callback_data="toggle_react"), InlineKeyboardButton(v_btn, callback_data="toggle_view")],
        [InlineKeyboardButton("✏️ Edit Settings", callback_data="edit_settings_btn")]
    ])

    try:
        await query.message.edit_text(card_text, reply_markup=kb, parse_mode="Markdown")
    except:
        await query.message.reply_text(card_text, reply_markup=kb, parse_mode="Markdown")

async def open_setup_menu_inline(query, user_id):
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_link, views_count, reacts_count FROM user_setups WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    ch, views, reacts = row if row else ('Not set', 500, 500)

    text = (
        f"⚙️ **Setup Menu**\n\n"
        f"🔗 Channel: {ch}\n"
        f"👀 Views: {views}\n"
        f"❤️ Reacts: {reacts}"
    )

    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔗 Channel: {ch}", callback_data="setup_set_channel")],
        [InlineKeyboardButton(f"👀 Views: {views}", callback_data="setup_set_views"),
         InlineKeyboardButton(f"❤️ Reacts: {reacts}", callback_data="setup_set_reacts")],
        [InlineKeyboardButton("✅ Save Setup", callback_data="setup_save")]
    ])

    try:
        await query.message.edit_text(text, reply_markup=inline_kb, parse_mode="Markdown")
    except:
        await query.message.reply_text(text, reply_markup=inline_kb, parse_mode="Markdown")


def _configured_channel_matches(saved_link, chat):
    """Match a public @username or a private t.me/c/<id> link to this channel."""
    raw = (saved_link or "").strip()
    if not raw or raw == "Not set":
        return False
    if raw.startswith("@"):
        username = raw[1:].lower()
    else:
        parsed = urlparse(raw if "://" in raw else "https://" + raw.lstrip("/"))
        path = parsed.path.strip("/")
        username = path.split("/")[0].lower() if path else ""
        if username == "c" and len(path.split("/")) > 1:
            private_id = path.split("/")[1]
            return str(chat.id) == "-100" + private_id
    return bool(chat.username and username and chat.username.lower() == username)


def _calc_cost(quantity, rate_per_1000):
    return int(math.ceil((int(quantity) * int(rate_per_1000)) / 1000.0))


def _reserve_coins(user_id, amount):
    """Atomically deduct only if the user's balance is sufficient."""
    conn = sqlite3.connect("smm_bot.db", timeout=20)
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            "UPDATE users SET coins = coins - ?, total_spent = total_spent + ? "
            "WHERE user_id = ? AND coins >= ?",
            (amount, amount, user_id, amount),
        )
        ok = cur.rowcount == 1
        conn.commit()
        return ok
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _refund_coins(user_id, amount):
    conn = sqlite3.connect("smm_bot.db", timeout=20)
    try:
        conn.execute(
            "UPDATE users SET coins = coins + ?, total_spent = MAX(0, total_spent - ?) WHERE user_id = ?",
            (amount, amount, user_id),
        )
        conn.commit()
    finally:
        conn.close()


async def process_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create enabled reaction/view orders for the user who configured this channel."""
    post = update.effective_message
    chat = post.chat
    conn = sqlite3.connect("smm_bot.db", timeout=20)
    try:
        rows = conn.execute(
            "SELECT user_id, channel_link, reacts_count, views_count, react_service, view_service "
            "FROM user_setups"
        ).fetchall()
    finally:
        conn.close()

    owners = [r for r in rows if _configured_channel_matches(r[1], chat)]
    if not owners:
        logger.info("No setup matched channel chat_id=%s username=%s", chat.id, chat.username)
        return
    if len(owners) > 1:
        logger.error("Multiple users configured the same channel: chat_id=%s", chat.id)
        return

    user_id, _, reacts_count, views_count, react_enabled, view_enabled = owners[0]
    post_link = (
        f"https://t.me/{chat.username}/{post.message_id}"
        if chat.username
        else f"https://t.me/c/{str(chat.id).replace('-100', '', 1)}/{post.message_id}"
    )

    jobs = []
    if react_enabled == "ON" and int(reacts_count) > 0:
        if not REACTION_SERVICE_ID:
            logger.error("REACTION_SERVICE_ID is not configured")
            await context.bot.send_message(user_id, "⚠️ Reaction service ID সেট করা নেই। Admin-কে জানান।")
            return
        jobs.append(("reaction", int(REACTION_SERVICE_ID), int(reacts_count), 3000))
    if view_enabled == "ON" and int(views_count) > 0:
        if not VIEW_SERVICE_ID:
            logger.error("VIEW_SERVICE_ID is not configured")
            await context.bot.send_message(user_id, "⚠️ View service ID সেট করা নেই। Admin-কে জানান।")
            return
        jobs.append(("view", int(VIEW_SERVICE_ID), int(views_count), 2000))

    if not jobs:
        return

    for kind, service_id, quantity, rate in jobs:
        cost = _calc_cost(quantity, rate)
        if not _reserve_coins(user_id, cost):
            conn = sqlite3.connect("smm_bot.db", timeout=20)
            try:
                row = conn.execute("SELECT coins FROM users WHERE user_id=?", (user_id,)).fetchone()
            finally:
                conn.close()
            balance = row[0] if row else 0
            await context.bot.send_message(
                user_id,
                f"⚠️ {kind.title()} অর্ডার হয়নি: পর্যাপ্ত কয়েন নেই।\\nব্যালেন্স: {balance}\\nপ্রয়োজন: {cost}"
            )
            continue

        api_res = api_client.order({
            "service": service_id,
            "link": post_link,
            "quantity": quantity,
        })
        if not isinstance(api_res, dict) or not api_res.get("order"):
            _refund_coins(user_id, cost)
            logger.error("Panel rejected %s order: %r", kind, api_res)
            await context.bot.send_message(
                user_id,
                f"❌ {kind.title()} অর্ডার API গ্রহণ করেনি। {cost} কয়েন ফেরত দেওয়া হয়েছে।"
            )
            continue

        order_id = str(api_res["order"])
        conn = sqlite3.connect("smm_bot.db", timeout=20)
        try:
            conn.execute(
                "INSERT INTO orders (user_id, order_id, link, quantity, status) VALUES (?, ?, ?, ?, ?)",
                (user_id, order_id, post_link, str(quantity), "PENDING"),
            )
            conn.commit()
        finally:
            conn.close()

        await context.bot.send_message(
            user_id,
            f"🚀 {kind.title()} অর্ডার পেন্ডিং!\\n"
            f"Order ID: #{order_id}\\nQuantity: {quantity}\\n"
            f"খরচ: {cost} Coins\\nলিংক: {post_link}"
        )
        try:
            await context.bot.send_message(
                chat_id=REQUIRED_CHANNEL,
                text=f"ORDER UPDATE\\n#{order_id}\\n{kind.title()}|{quantity}\\nPENDING"
            )
        except Exception:
            logger.exception("Could not post order update")


# --- মূল মেসেজ ও পোস্ট হ্যান্ডলার ---
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user_id = update.effective_user.id if update.effective_user else None
    text = message.text if message and message.text else ""
    photo = message.photo if message else None

    # ১. চ্যানেল পোস্ট হলে সংশ্লিষ্ট সেটআপ মালিকের অর্ডার প্রসেস
    if message and message.chat and message.chat.type in ["supergroup", "channel"]:
        if get_setting("global_orders") == "OFF":
            return
        await process_channel_post(update, context)
        return

    if not user_id:
        return

    # ২. ইনলাইন সেটআপ ইনপুট হ্যান্ডলিং
    setup_step = context.user_data.get('setup_step')
    if setup_step == 'inline_wait_channel':
        clean_ch = clean_telegram_link(text)
        context.user_data.pop('setup_step', None)
        
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_setups SET channel_link = ? WHERE user_id = ?", (clean_ch, user_id))
        conn.commit()
        conn.close()
        
        await message.reply_text("✅ চ্যানেল লিংক সফলভাবে আপডেট হয়েছে!")
        await open_setup_menu(update, context)
        return

    elif setup_step == 'inline_wait_views':
        if not text.isdigit() or not (1 <= int(text) <= 1000000):
            await message.reply_text("❌ ১ থেকে ১০০০০০০-এর মধ্যে সঠিক সংখ্যা লিখুন।")
            return
        context.user_data.pop('setup_step', None)
        
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_setups SET views_count = ? WHERE user_id = ?", (int(text), user_id))
        conn.commit()
        conn.close()
        
        await message.reply_text("✅ ভিউ সংখ্যা সফলভাবে আপডেট হয়েছে!")
        await open_setup_menu(update, context)
        return

    elif setup_step == 'inline_wait_reacts':
        if not text.isdigit() or not (1 <= int(text) <= 1000000):
            await message.reply_text("❌ ১ থেকে ১০০০০০০-এর মধ্যে সঠিক সংখ্যা লিখুন।")
            return
        context.user_data.pop('setup_step', None)
        
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_setups SET reacts_count = ? WHERE user_id = ?", (int(text), user_id))
        conn.commit()
        conn.close()
        
        await message.reply_text("✅ রিঅ্যাকশন সংখ্যা সফলভাবে আপডেট হয়েছে!")
        await open_setup_menu(update, context)
        return

    # ৩. এডমিন কয়েন অনুমোদন
    if user_id == ADMIN_ID and context.user_data.get('waiting_admin_coin_input'):
        target_uid = context.user_data.pop('target_user_for_coins', None)
        context.user_data['waiting_admin_coin_input'] = False

        if target_uid and text and text.isdigit():
            add_coins = int(text)
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (add_coins, target_uid))
            cursor.execute("SELECT coins FROM users WHERE user_id = ?", (target_uid,))
            new_bal = cursor.fetchone()[0]
            conn.commit()
            conn.close()

            await message.reply_text(f"✅ সফলভাবে ইউজার `{target_uid}` এর অ্যাকাউন্টে `{add_coins}` কয়েন জমা হয়েছে! বর্তমান ব্যালেন্স: {new_bal}", parse_mode="Markdown")
            try:
                await context.bot.send_message(chat_id=target_uid, text=f"🎉 পেমেন্ট কনফার্ম হয়েছে! অ্যাকাউন্টে **{add_coins} Coins** যোগ করা হয়েছে।\n💰 বর্তমান ব্যালেন্স: **{new_bal} Coins**", parse_mode="Markdown")
            except:
                pass
            return

    # ৪. TON Income ম্যানুয়াল অর্ডার প্রসেস
    if text == "💎 TON Income":
        context.user_data['ton_step'] = 'waiting_post_link'
        await message.reply_text("💎 **TON Income (One Click)**\n\n🔗 দয়া করে আপনার টেলিগ্রাম পোস্টের লিংক (Post Link) পাঠান:")
        return

    ton_step = context.user_data.get('ton_step')
    if ton_step == 'waiting_post_link':
        clean_post_link = clean_telegram_link(text)
        context.user_data['ton_post_link'] = clean_post_link
        context.user_data['ton_step'] = 'waiting_ton_reacts'
        await message.reply_text("❤️ আপনি এই পোস্টে কত রিঅ্যাকশন নিতে চান? (সংখ্যাটি লিখুন, যেমন: 500 বা 5000):")
        return

    elif ton_step == 'waiting_ton_reacts':
        post_link = context.user_data.pop('ton_post_link', '')
        context.user_data.pop('ton_step', None)
        
        reacts_count = text.strip()
        if not reacts_count.isdigit():
            await message.reply_text("❌ দয়া করে সঠিক সংখ্যা লিখুন (যেমন: 500)। আবার চেষ্টা করুন।")
            return

        r_qty = int(reacts_count)
        cost = int((r_qty / 1000) * 3000)

        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        urow = cursor.fetchone()
        user_coins = urow[0] if urow else 0

        if user_coins < cost:
            conn.close()
            await message.reply_text(f"⚠️ আপনার পর্যাপ্ত কয়েন নেই!\nআপনার আছে: {user_coins} Coins\nপ্রয়োজন: {cost} Coins\nদয়া করে টপ-আপ করুন।")
            return

        cursor.execute("UPDATE users SET coins = coins - ?, total_spent = total_spent + ? WHERE user_id = ?", (cost, cost, user_id))
        conn.commit()
        conn.close()

        order_data = {'service': 1936, 'link': post_link, 'quantity': r_qty}
        api_res = api_client.order(order_data)

        if isinstance(api_res, dict) and 'order' in api_res:
            order_id = str(api_res['order'])
            
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO orders (user_id, order_id, link, quantity, status) VALUES (?, ?, ?, ?, ?)",
                           (user_id, order_id, post_link, str(r_qty), "PENDING"))
            conn.commit()
            conn.close()

            await message.reply_text(
                f"✅ **TON Income অর্ডার সফলভাবে প্লেস হয়েছে!**\n\n"
                f"🆔 Order ID: `#{order_id}`\n"
                f"🔗 Link: {post_link}\n"
                f"❤️ Reacts: {r_qty}\n"
                f"🪙 খরচ হয়েছে: {cost} Coins",
                parse_mode="Markdown"
            )

            channel_text = f"ORDER UPDATE\n#{order_id}\nReacts|{r_qty}\nPENDING"
            try:
                await context.bot.send_message(chat_id=REQUIRED_CHANNEL, text=channel_text)
            except:
                pass
        else:
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (cost, user_id))
            conn.commit()
            conn.close()
            await message.reply_text(f"❌ এপিআই অর্ডার নিতে সমস্যা হয়েছে। আপনার কয়েন ফেরত দেওয়া হয়েছে।")
        return

    # ৫. অন্যান্য মেনু হ্যান্ডলার
    if text == "👤 Profile":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins, total_spent, active_projects, referrals, referral_income FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        c, ts, ap, ref, ref_inc = u if u else (0, 0, 0, 0, 0)
        await message.reply_text(f"👤 **User Profile**\n\n🆔 User ID: `{user_id}`\n💰 Coin Balance: {c}\n💸 Total Spent: {ts}\n🚀 Active Projects: {ap}", parse_mode="Markdown")
        return

    if text == "💳 Top-up":
        binance_uid = get_setting("binance_uid")
        context.user_data['waiting_for_proof'] = True
        await message.reply_text(f"💳 **Top-up Balance**\n\n📌 **Binance UID:** `{binance_uid}`\n\n📤 পেমেন্ট করে স্ক্রিনশট এখানে পাঠান।", parse_mode="Markdown")
        return

    if context.user_data.get('waiting_for_proof') or photo:
        if photo or context.user_data.get('waiting_for_proof'):
            context.user_data['waiting_for_proof'] = False
            admin_kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add / Enter Coins", callback_data=f"approve_pay_{user_id}")]])
            caption = f"🚨 **নতুন ডিপোজিট স্ক্রিনশট!**\n\n👤 ইউজার আইডি: `{user_id}`\n\n👇 কয়েন দিতে বাটনে চাপুন:"
            try:
                if photo:
                    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo[-1].file_id, caption=caption, reply_markup=admin_kb, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=ADMIN_ID, text=caption, reply_markup=admin_kb, parse_mode="Markdown")
                await message.reply_text("✅ স্ক্রিনশট এডমিনের কাছে পাঠানো হয়েছে।")
            except:
                pass
            return

    if user_id == ADMIN_ID and text == "👑 Admin Panel":
        is_prem = get_setting("is_premium") == "True"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Premium Mode: {'ON 👑' if is_prem else 'OFF ❌'}", callback_data="toggle_premium_mode")]
        ])
        await message.reply_text("👑 **Admin Control Panel**\n১-ক্লিকে প্রিমিয়াম বাটন অন/অফ করুন:", reply_markup=kb)
        return

    if text == "🎧 Support":
        await message.reply_text("🎧 যেকোনো সাহায্যে যোগাযোগ করুন: https://t.me/NIROB_GX")
        return

    if text == "👥 Refer & Earn":
        bot_username = (await context.bot.get_me()).username
        await message.reply_text(f"👥 **Refer & Earn**\nআপনার লিঙ্ক: `https://t.me/{bot_username}?start={user_id}`", parse_mode="Markdown")
        return

    if text == "📦 Order List":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, link, quantity, status FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        orders = cursor.fetchall()
        conn.close()

        if not orders:
            await message.reply_text("📦 আপনার কোনো অর্ডার হিস্ট্রি পাওয়া যায়নি।")
        else:
            msg = "📦 **Your Order List:**\n\n"
            for o in orders:
                msg += f"🆔 Order ID: `#{o[0]}`\n🔗 Link: {o[1]}\n📦 Qty: {o[2]} | Status: **{o[3]}**\n\n"
            await message.reply_text(msg, parse_mode="Markdown")
        return

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")
    if not API_KEY:
        logger.warning("PANEL_API_KEY is missing; paid orders will not be submitted")
    if not REACTION_SERVICE_ID or not VIEW_SERVICE_ID:
        logger.warning("Set REACTION_SERVICE_ID and VIEW_SERVICE_ID from your panel before enabling services")
    application = ApplicationBuilder().token(TOKEN).build()

    # ডেডিকেটেড কমান্ড এবং বাটন হ্যান্ডলার
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^⚙️ Setup$"), open_setup_menu))
    application.add_handler(MessageHandler(filters.Regex("^🛠️ Settings$"), open_settings_menu))
    
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_router))

    print("GX SMM Ultimate Fixed Bot is running successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
