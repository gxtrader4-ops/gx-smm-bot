import logging
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
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
            coins INTEGER DEFAULT 200,
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
            views TEXT DEFAULT 'Not set',
            reacts TEXT DEFAULT 'Not set'
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rate_multiplier', '3')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('binance_uid', ?)", (DEFAULT_BINANCE_UID,))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_premium', 'False')")
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

# --- 1xPanel API ক্লাস (Service ID 1936) ---
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

    def balance(self):
        post = {'key': self.api_key, 'action': 'balance'}
        try:
            response = requests.post(self.api_url, data=post, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"API Balance Error: {e}")
            return {}

api_client = OneXPanelAPI(API_KEY)

# --- Force Join চেক ---
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

# --- স্টার্টিং কমান্ড ও মেইন মেনু ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, coins) VALUES (?, ?)", (user_id, 200))
    cursor.execute("INSERT OR IGNORE INTO user_setups (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    is_joined = await check_forced_join(update, context)
    if not is_joined:
        keyboard = [
            [InlineKeyboardButton("📢 Join Group/Channel", url=ORDER_CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Joined, Check Again", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ বট ব্যবহারের জন্য প্রথমে আমাদের অফিশিয়াল গ্রুপে জয়েন করতে হবে!\nদয়া করে লিংকে জয়েন করে নিচের বাটনে ক্লিক করুন।",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    cursor.execute("SELECT channel_link, views, reacts FROM user_setups WHERE user_id = ?", (user_id,))
    setup_row = cursor.fetchone()
    conn.close()

    coins = row[0] if row else 200
    ch_link, views, reacts = setup_row if setup_row else ('Not set', 'Not set', 'Not set')
    is_prem = get_setting("is_premium") == "True"
    prem_badge = "👑 [PREMIUM]" if is_prem else ""

    # স্ক্রিনশটের সাথে হুবহু মিল রেখে মেনু টেক্সট ও বাটন
    text = (
        f"Telegram Super Service {prem_badge}\n"
        f"110 monthly users\n\n"
        f"🔗 Channel: {ch_link}\n"
        f"👀 Views: {views}\n"
        f"❤️ Reacts: {reacts}\n\n"
        f"🔥 **GX SMM PREMIUM PANEL** 🔥\n"
        f"💰 আপনার বর্তমান ব্যালেন্স: **{coins} coins**"
    )

    keyboard = [
        [InlineKeyboardButton("⚙️ Setup", callback_data="menu_setup"),
         InlineKeyboardButton("👤 Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("🛠️ Settings", callback_data="menu_settings"),
         InlineKeyboardButton("💳 Top-up", callback_data="menu_topup")],
        [InlineKeyboardButton("📦 Order List", callback_data="menu_orders"),
         InlineKeyboardButton("🎧 Support", callback_data="menu_support")],
        [InlineKeyboardButton("👥 Refer & Earn", callback_data="menu_refer")]
    ]

    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Control Panel", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# --- কলারব্যাক হ্যান্ডলার ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "check_join":
        if await check_forced_join(update, context):
            await query.message.delete()
            await show_main_menu(update, context)
        else:
            await query.answer("❌ আপনি এখনো গ্রুপে জয়েন করেননি!", show_alert=True)

    elif query.data == "menu_setup":
        keyboard = [
            [InlineKeyboardButton("🔗 Channel Link", callback_data="set_ch"),
             InlineKeyboardButton("👀 Views", callback_data="set_views")],
            [InlineKeyboardButton("❤️ Reacts", callback_data="set_reacts"),
             InlineKeyboardButton("✅ Save Setup", callback_data="save_setup")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.message.edit_text("⚙️ **বট সেটআপ মেনু:**\nআপনার চ্যানেল এবং রিঅ্যাকশন/ভিউ অপশনগুলো কনফিগার করুন।", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "set_ch":
        context.user_data['waiting_for_setup'] = 'ch_link'
        await query.message.reply_text("দয়া করে আপনার চ্যানেলের লিংক (Channel Link) দিন:")

    elif query.data == "set_views":
        context.user_data['waiting_for_setup'] = 'views'
        await query.message.reply_text("ভিউ সংখ্যা লিখুন (যেমন: 1000, 5000):")

    elif query.data == "set_reacts":
        context.user_data['waiting_for_setup'] = 'reacts'
        await query.message.reply_text("রিঅ্যাকশন সংখ্যা লিখুন (যেমন: 1000):")

    elif query.data == "save_setup":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT channel_link, views, reacts FROM user_setups WHERE user_id = ?", (user_id,))
        sr = cursor.fetchone()
        conn.close()
        
        if not sr or sr[0] == 'Not set':
            await query.answer("⚠️ আগে চ্যানেল লিংক এবং ভিউ/রিঅ্যাক্ট সেটআপ করুন!", show_alert=True)
            return

        # সরাসরি সার্ভিস আইডি ১৯৩৬ এ অর্ডার হিট করা
        order_data = {
            'service': 1936,
            'link': sr[0],
            'quantity': int(sr[1]) if sr[1].isdigit() else 1000
        }
        api_res = api_client.order(order_data)
        
        if isinstance(api_res, dict) and 'order' in api_res:
            await query.message.reply_text(f"✅ সেটআপ সফল! অর্ডার প্লেস হয়েছে। Order ID: `{api_res['order']}`", parse_mode="Markdown")
        else:
            await query.message.reply_text(f"✅ সেটআপ সেভ হয়েছে! বট এখন অটোমেটিক কাজ করবে। Response: {api_res}")

    elif query.data == "menu_profile":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins, total_spent, active_projects, referrals, referral_income FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        
        c, ts, ap, ref, ref_inc = u if u else (200, 0, 0, 0, 0)
        text = (
            f"👤 **User Profile**\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"💰 Coin Balance: {c}\n"
            f"💸 Total Spent: {ts}\n"
            f"🚀 Active Projects: {ap}\n"
            f"👥 Total Referrals: {ref}\n"
            f"🎁 Referral Income: {ref_inc} coins"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "menu_topup":
        binance_uid = get_setting("binance_uid")
        keyboard = [
            [InlineKeyboardButton("📤 Send Payment Screenshot", callback_data="send_proof")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.message.edit_text(
            f"💳 **Top-up Balance**\n\n"
            f"বাইনান্স ইউআইডি (Binance UID) তে পেমেন্ট করুন:\n"
            f"📌 **Binance UID:** `{binance_uid}`\n\n"
            f"রেট: $1 = 65000 Coins\n\n"
            f"টাকা পাঠিয়ে নিচের বাটনে ক্লিক করে স্ক্রিনশট দিন।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "send_proof":
        context.user_data['waiting_for_proof'] = True
        await query.message.reply_text("📤 আপনার পেমেন্টের স্ক্রিনশট এবং ট্রানজাকশন ডিটেইলস পাঠান। এটি সরাসরি এডমিনের কাছে চলে যাবে।")

    elif query.data == "menu_settings":
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text("🛠️ **Settings**\nবটের নোটিফিকেশন ও অন্যান্য কনফিগারেশন এখানে পাওয়া যাবে।", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "menu_orders":
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text("📦 **Order List**\nআপনার সকল সাম্প্রতিক অর্ডার লিস্ট এখানে দেখাবে।", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "menu_support":
        keyboard = [[InlineKeyboardButton("💬 Contact Admin", url="https://t.me/NIROB_GX")],
                    [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text("🎧 **Support**\nযেকোনো সমস্যায় সরাসরি এডমিনের সাথে যোগাযোগ করুন:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "menu_refer":
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text(f"👥 **Refer & Earn**\nআপনার রেফারেল লিংক শেয়ার করে কয়েন উপার্জন করুন!\n\n🔗 `https://t.me/{(await context.bot.get_me()).username}?start={user_id}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "main_menu":
        await show_main_menu(update, context)

    elif query.data == "admin_panel":
        if user_id != ADMIN_ID:
            return
        
        is_prem = get_setting("is_premium") == "True"
        prem_status_text = "Disable Premium ❌" if is_prem else "Make Bot Premium 👑"

        keyboard = [
            [InlineKeyboardButton(prem_status_text, callback_data="toggle_premium")],
            [InlineKeyboardButton("🪙 Add Coins to User", callback_data="adm_add_coins"),
             InlineKeyboardButton("🎚️ Change Coin Rate", callback_data="adm_set_rate")],
            [InlineKeyboardButton("🆔 Change Binance UID", callback_data="adm_set_binance")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        await query.message.edit_text("👑 **Admin Control Panel**\nএক ক্লিকে বট প্রিমিয়াম করা এবং অন্যান্য ম্যানেজমেন্ট:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "toggle_premium":
        current = get_setting("is_premium") == "True"
        new_val = "False" if current else "True"
        update_setting("is_premium", new_val)
        await query.answer(f"✅ বট প্রিমিয়াম স্ট্যাটাস পরিবর্তন করে করা হয়েছে: {new_val}", show_alert=True)
        await show_main_menu(update, context)

    elif query.data == "adm_add_coins":
        context.user_data['adm_add'] = True
        await query.message.reply_text("ইউজার আইডি এবং কয়েন এভাবে লিখুন (উদাহরণ: `123456789 5000`):", parse_mode="Markdown")

    elif query.data == "adm_set_rate":
        context.user_data['adm_rate'] = True
        await query.message.reply_text("নতুন কয়েন রেট দিন:")

    elif query.data == "adm_set_binance":
        context.user_data['adm_binance'] = True
        await query.message.reply_text("নতুন বাইনান্স ইউআইডি দিন:")

# --- মেসেজ ও প্রুফ হ্যান্ডলার ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    photo = update.message.photo

    # সেটআপ প্রসেস
    if context.user_data.get('waiting_for_setup'):
        stype = context.user_data.pop('waiting_for_setup')
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        if stype == 'ch_link':
            cursor.execute("UPDATE user_setups SET channel_link = ? WHERE user_id = ?", (text, user_id))
        elif stype == 'views':
            cursor.execute("UPDATE user_setups SET views = ? WHERE user_id = ?", (text, user_id))
        elif stype == 'reacts':
            cursor.execute("UPDATE user_setups SET reacts = ? WHERE user_id = ?", (text, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ সফলভাবে সেভ হয়েছে! মেইন মেনুতে ফিরে যেতে /start লিখুন।")
        return

    # পেমেন্ট প্রুফ ফরোয়ার্ড
    if context.user_data.get('waiting_for_proof'):
        context.user_data['waiting_for_proof'] = False
        forward_text = f"🚨 **New USDT Payment Proof!**\n\n👤 User ID: `{user_id}`\n💬 Details: {text if text else 'Attached Screenshot'}"
        if photo:
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo[-1].file_id, caption=forward_text, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text=forward_text, parse_mode="Markdown")
        await update.message.reply_text("✅ স্ক্রিনশট এডমিনের কাছে পাঠানো হয়েছে। চেক করে কয়েন অ্যাড করা হবে।")
        return

    # এডমিন অ্যাকশন
    if user_id == ADMIN_ID and context.user_data.get('adm_add'):
        try:
            parts = text.split()
            t_user = int(parts[0])
            coins = int(parts[1])
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (coins, t_user))
            conn.commit()
            conn.close()
            context.user_data['adm_add'] = False
            await update.message.reply_text(f"✅ ইউজার `{t_user}` এর একাউন্টে `{coins}` কয়েন যোগ করা হয়েছে!")
            await context.bot.send_message(chat_id=t_user, text=f"🎉 অভিনন্দন! এডমিন আপনার একাউন্টে **{coins}** কয়েন যোগ করেছেন।", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ সঠিক ফরম্যাটে লিখুন। উদাহরণ: `123456789 5000`", parse_mode="Markdown")
        return

    if user_id == ADMIN_ID and context.user_data.get('adm_binance'):
        update_setting('binance_uid', text)
        context.user_data['adm_binance'] = False
        await update.message.reply_text(f"✅ বাইনান্স ইউআইডি আপডেট করা হয়েছে: {text}")
        return

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))

    print("GX SMM Panel Bot is running successfully...")
    application.run_polling()

if __name__ == "main()":
    main()

if __name__ == "__main__":
    main()
