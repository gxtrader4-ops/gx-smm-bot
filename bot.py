import logging
import sqlite3
import requests
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
TOKEN = "9201048894:AAFmPupyT_zzzhICH4X2pylIwnrF4YCcMQ4"
ADMIN_ID = 8419760844
REQUIRED_CHANNEL = "-1003908562163"  # Force Join Group ID
ORDER_CHANNEL_LINK = "https://t.me/GX_SMM_PREMIUM_PANEL"
API_URL = "https://1xpanel.com/api/v2"
API_KEY = "e19e34d1e991b739cc18a9917e6d9144"
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
            views_count INTEGER DEFAULT 0,
            reacts_count INTEGER DEFAULT 0,
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

# --- ইউজার এবং এডমিন আলাদা কিবোর্ড ---
def get_user_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⚙️ Setup"), KeyboardButton("👤 Profile")],
        [KeyboardButton("🛠️ Settings"), KeyboardButton("💳 Top-up")],
        [KeyboardButton("📦 Order List"), KeyboardButton("🎧 Support")],
        [KeyboardButton("👥 Refer & Earn")]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👑 Admin Panel"), KeyboardButton("⚙️ Setup")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🛠️ Settings")],
        [KeyboardButton("💳 Top-up"), KeyboardButton("📦 Order List")],
        [KeyboardButton("🎧 Support"), KeyboardButton("👥 Refer & Earn")]
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
    ch_link, views, reacts = setup_row if setup_row else ('Not set', 0, 0)

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

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

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

    elif data == "toggle_react":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT react_service FROM user_setups WHERE user_id = ?", (user_id,))
        curr = cursor.fetchone()[0]
        new_val = "OFF" if curr == "ON" else "ON"
        cursor.execute("UPDATE user_setups SET react_service = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        conn.close()
        await render_settings_msg(query, user_id)

    elif data == "toggle_view":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT view_service FROM user_setups WHERE user_id = ?", (user_id,))
        curr = cursor.fetchone()[0]
        new_val = "OFF" if curr == "ON" else "ON"
        cursor.execute("UPDATE user_setups SET view_service = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        conn.close()
        await render_settings_msg(query, user_id)

    elif data == "edit_settings_btn":
        context.user_data['setup_step'] = 'waiting_channel'
        await query.message.reply_text("🔗 আপনার চ্যানেলের আসল ইউজারনেম বা লিংক দিন (যেমন: `@mychannel`):")

    elif data.startswith("approve_pay_"):
        target_uid = data.split("_")[2]
        context.user_data['target_user_for_coins'] = target_uid
        context.user_data['waiting_admin_coin_input'] = True
        await query.message.reply_text(
            f"👤 **ইউজার আইডি:** `{target_uid}`\n\n"
            f"✍️ **আপনি উনাকে কত কয়েন দিতে চান তা লিখুন:**",
            parse_mode="Markdown"
        )

    elif data == "toggle_premium_mode":
        curr = get_setting("is_premium") == "True"
        new_v = "False" if curr else "True"
        update_setting("is_premium", new_v)
        await query.answer(f"Premium Mode set to {new_v}", show_alert=True)

async def render_settings_msg(query, user_id):
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_link, react_service, view_service, reacts_count, views_count, emojis FROM user_setups WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    ch, r_s, v_s, r_c, v_c, emo = row if row else ("Not set", "ON", "OFF", 0, 0, "👍 ❤️ 🔥")
    ch_name = ch.split('/')[-1] if '/' in ch else ch

    r_btn = f"👍 React: {r_s} {'✅' if r_s=='ON' else '❌'}"
    v_btn = f"👁 Views: {v_s} {'✅' if v_s=='ON' else '❌'}"

    text = (
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

    await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- প্রধান মেসেজ হ্যান্ডলার ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    photo = update.message.photo

    # ১. গ্রুপ বা চ্যানেলে নতুন পোস্ট আসলে অটোমেটিক 1936 এ অর্ডার প্লেস হওয়া
    if update.message.chat.type in ["supergroup", "channel"]:
        if get_setting("global_orders") == "OFF":
            return
        
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        current_coins = user_row[0] if user_row else 0
        
        cursor.execute("SELECT reacts_count, views_count, react_service, view_service FROM user_setups WHERE user_id = ?", (user_id,))
        setup_row = cursor.fetchone()
        
        reacts_qty = int(setup_row[0]) if setup_row and str(setup_row[0]).isdigit() else 0
        views_qty = int(setup_row[1]) if setup_row and str(setup_row[1]).isdigit() else 0
        r_service = setup_row[2] if setup_row else "ON"
        v_service = setup_row[3] if setup_row else "OFF"

        # কয়েন হিসাব: ১০০০ রিঅ্যাকশন = ৩০০০ কয়েন, ১০০০ ভিউ = ২০০০ কয়েন
        react_cost = (reacts_qty * 3) if r_service == "ON" else 0
        view_cost = (views_qty * 2) if v_service == "ON" else 0
        total_cost_coins = react_cost + view_cost

        if current_coins < total_cost_coins or total_cost_coins == 0:
            try:
                await context.bot.send_message(
                    chat_id=user_id, 
                    text=f"⚠️ **অর্ডার ফেইলড!** আপনার পর্যাপ্ত কয়েন নেই বা সেটআপ করা হয়নি।\nআপনার বর্তমান ব্যালেন্স: **{current_coins} Coins**\nপ্রয়োজন: **{total_cost_coins} Coins**\nদয়া করে Top-up করে কয়েন অ্যাড করুন।"
                )
            except:
                pass
            conn.close()
            return

        # ব্যালেন্স থেকে কয়েন কাটা
        cursor.execute("UPDATE users SET coins = coins - ?, total_spent = total_spent + ? WHERE user_id = ?", (total_cost_coins, total_cost_coins, user_id))
        conn.commit()
        conn.close()

        post_link = f"https://t.me/{update.message.chat.username}/{update.message.message_id}" if update.message.chat.username else f"https://t.me/c/{str(update.message.chat.id).replace('-100', '')}/{update.message.message_id}"
        
        # 1936 এপিআই অর্ডার হিট
        order_data = {'service': 1936, 'link': post_link, 'quantity': reacts_qty}
        api_res = api_client.order(order_data)
        
        if isinstance(api_res, dict) and 'order' in api_res:
            order_id = str(api_res['order'])
            
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO orders (user_id, order_id, link, quantity, status) VALUES (?, ?, ?, ?, ?)",
                           (user_id, order_id, post_link, str(reacts_qty), "PENDING"))
            conn.commit()
            conn.close()

            # ইউজারের ইনবক্সে নোটিফিকেশন
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🚀 **অর্ডার পেন্ডিং আছে!**\n\n🆔 Order ID: `#{order_id}`\n❤️ Reacts: {reacts_qty}\n👀 Views: {views_qty}\n🔗 Link: {post_link}\n🪙 খরচ হয়েছে: {total_cost_coins} Coins",
                    parse_mode="Markdown"
                )
            except:
                pass

            # অর্ডার চ্যানেলে আপডেট
            channel_text = f"ORDER UPDATE\n#{order_id}\nReacts|{reacts_qty}\nPENDING"
            try:
                await context.bot.send_message(chat_id=REQUIRED_CHANNEL, text=channel_text)
            except Exception as e:
                logger.error(f"Error sending to order channel: {e}")
        return

    # ২. এডমিন কয়েন অনুমোদন
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

            await update.message.reply_text(f"✅ সফলভাবে ইউজার `{target_uid}` এর অ্যাকাউন্টে `{add_coins}` কয়েন জমা হয়েছে! বর্তমান ব্যালেন্স: {new_bal}", parse_mode="Markdown")
            try:
                await context.bot.send_message(chat_id=target_uid, text=f"🎉 পেমেন্ট কনফার্ম হয়েছে! অ্যাকাউন্টে **{add_coins} Coins** যোগ করা হয়েছে।\n💰 বর্তমান ব্যালেন্স: **{new_bal} Coins**", parse_mode="Markdown")
            except:
                pass
            return

    # ৩. Setup প্রসেস (ক্লিন ও সোজা ইউজারনেম ইনপুট)
    if text == "⚙️ Setup":
        context.user_data['setup_step'] = 'waiting_channel'
        await update.message.reply_text("🔗 আপনার চ্যানেলের ইউজারনেম বা লিংক দিন (যেমন: `@mychannel` বা চ্যানেল লিংক):")
        return

    setup_step = context.user_data.get('setup_step')
    if setup_step == 'waiting_channel':
        context.user_data['temp_channel'] = text
        context.user_data['setup_step'] = 'waiting_reacts'
        await update.message.reply_text("❤️ কত রিঅ্যাকশন নিতে চান? (সংখ্যাটি লিখুন, যেমন: 500 বা 50000):")
        return
    
    elif setup_step == 'waiting_reacts':
        context.user_data['temp_reacts'] = text
        context.user_data['setup_step'] = 'waiting_views'
        await update.message.reply_text("👀 কত ভিউ নিতে চান? (সংখ্যাটি লিখুন, যেমন: 500 বা 50000):")
        return

    elif setup_step == 'waiting_views':
        ch = context.user_data.pop('temp_channel', 'Not set')
        reacts = context.user_data.pop('temp_reacts', 0)
        views = text
        context.user_data.pop('setup_step', None)

        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_setups SET channel_link = ?, views_count = ?, reacts_count = ? WHERE user_id = ?", (ch, views, reacts, user_id))
        conn.commit()
        conn.close()

        keyboard = get_admin_keyboard() if user_id == ADMIN_ID else get_user_keyboard()
        await update.message.reply_text(f"✅ **সেটআপ সফলভাবে সেভ হয়েছে!**\n🔗 Link: {ch}\n❤️ Reacts: {reacts}\n👀 Views: {views}", reply_markup=keyboard, parse_mode="Markdown")
        return

    # ৪. Settings মেনু (প্রজেক্ট সেটিংস কার্ড)
    if text == "🛠️ Settings":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT channel_link, react_service, view_service, reacts_count, views_count, emojis FROM user_setups WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        ch, r_s, v_s, r_c, v_c, emo = row if row else ("Not set", "ON", "OFF", 0, 0, "👍 ❤️ 🔥")
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
        return

    # ৫. Order List (শুধু ইউজারের নিজের অর্ডার দেখাবে)
    if text == "📦 Order List":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, link, quantity, status FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        orders = cursor.fetchall()
        conn.close()

        if not orders:
            await update.message.reply_text("📦 আপনার কোনো অর্ডার হিস্ট্রি পাওয়া যায়নি।")
        else:
            msg = "📦 **Your Order List:**\n\n"
            for o in orders:
                msg += f"🆔 Order ID: `#{o[0]}`\n🔗 Link: {o[1]}\n📦 Qty: {o[2]} | Status: **{o[3]}**\n\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ৬. Profile, Top-up, Admin Panel
    if text == "👤 Profile":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins, total_spent, active_projects, referrals, referral_income FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        c, ts, ap, ref, ref_inc = u if u else (0, 0, 0, 0, 0)
        await update.message.reply_text(f"👤 **User Profile**\n\n🆔 User ID: `{user_id}`\n💰 Coin Balance: {c}\n💸 Total Spent: {ts}\n🚀 Active Projects: {ap}", parse_mode="Markdown")
        return

    if text == "💳 Top-up":
        binance_uid = get_setting("binance_uid")
        context.user_data['waiting_for_proof'] = True
        await update.message.reply_text(f"💳 **Top-up Balance**\n\n📌 **Binance UID:** `{binance_uid}`\n\n📤 পেমেন্ট করে স্ক্রিনশট এখানে পাঠান।", parse_mode="Markdown")
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
                await update.message.reply_text("✅ স্ক্রিনশট এডমিনের কাছে পাঠানো হয়েছে।")
            except:
                pass
            return

    if user_id == ADMIN_ID and text == "👑 Admin Panel":
        is_prem = get_setting("is_premium") == "True"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Premium Mode: {'ON 👑' if is_prem else 'OFF ❌'}", callback_data="toggle_premium_mode")]
        ])
        await update.message.reply_text("👑 **Admin Control Panel**\n১-ক্লিকে প্রিমিয়াম বাটন অন/অফ করুন:", reply_markup=kb)
        return

    if text == "🎧 Support":
        await update.message.reply_text("🎧 যেকোনো সাহায্যে যোগাযোগ করুন: https://t.me/NIROB_GX")
        return

    if text == "👥 Refer & Earn":
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(f"👥 **Refer & Earn**\nআপনার লিঙ্ক: `https://t.me/{bot_username}?start={user_id}`", parse_mode="Markdown")
        return

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))

    print("GX SMM Final Ultimate Bot is running successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
