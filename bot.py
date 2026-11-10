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
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('orders_status', 'ON')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('reacts_status', 'ON')")
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

    def balance(self):
        post = {'key': self.api_key, 'action': 'balance'}
        try:
            response = requests.post(self.api_url, data=post, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"API Balance Error: {e}")
            return {}

api_client = OneXPanelAPI(API_KEY)

# --- ফিক্সড রিপ্লাই কিবোর্ড (স্ক্রিনশটের মতো বাটন) ---
def get_main_keyboard(user_id):
    keyboard = [
        [KeyboardButton("⚙️ Setup"), KeyboardButton("👤 Profile")],
        [KeyboardButton("🛠️ Settings"), KeyboardButton("💳 Top-up")],
        [KeyboardButton("📦 Order List"), KeyboardButton("🎧 Support")],
        [KeyboardButton("👥 Refer & Earn")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton("👑 Admin Control Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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
    cursor.execute("INSERT OR IGNORE INTO users (user_id, coins) VALUES (?, ?)", (user_id, 200))
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
    cursor.execute("SELECT channel_link, views, reacts FROM user_setups WHERE user_id = ?", (user_id,))
    setup_row = cursor.fetchone()
    conn.close()

    coins = row[0] if row else 200
    ch_link, views, reacts = setup_row if setup_row else ('Not set', 'Not set', 'Not set')

    text = (
        f"Telegram Super Service\n"
        f"110 monthly users\n\n"
        f"🔗 Channel: {ch_link}\n"
        f"👀 Views: {views}\n"
        f"❤️ Reacts: {reacts}\n\n"
        f"🔥 **GX SMM PREMIUM PANEL** 🔥\n"
        f"💰 আপনার বর্তমান ব্যালেন্স: **{coins} coins**"
    )

    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

# --- কলারব্যাক হ্যান্ডলার ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "check_join":
        if await check_forced_join(update, context):
            await query.message.delete()
            await show_dashboard(update, context)
        else:
            await query.answer("❌ আপনি এখনো গ্রুপে জয়েন করেননি!", show_alert=True)

    elif data.startswith("approve_pay_"):
        target_uid = data.split("_")[2]
        context.user_data['target_user_for_coins'] = target_uid
        context.user_data['waiting_admin_coin_input'] = True
        await query.message.reply_text(
            f"👤 **ইউজার আইডি:** `{target_uid}`\n\n"
            f"✍️ **আপনি উনাকে কত কয়েন দিতে চান তা টাইপ করে লিখুন (যেমন: 50000):**",
            parse_mode="Markdown"
        )

# --- প্রধান মেসেজ হ্যান্ডলার ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    photo = update.message.photo

    # ১. এডমিন যখন স্ক্রিনশট পাওয়ার পর কয়েন লিখে কনফার্ম করবে
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

            await update.message.reply_text(
                f"✅ **সফলভাবে জমা হয়েছে!**\n\n"
                f"👤 ইউজার: `{target_uid}`\n"
                f"🪙 যোগ করা কয়েন: **{add_coins}**\n"
                f"💰 বর্তমান ব্যালেন্স: **{new_bal}**",
                parse_mode="Markdown"
            )

            # ইউজারের অ্যাকাউন্টে অটোমেটিক কনফার্মেশন মেসেজ
            try:
                await context.bot.send_message(
                    chat_id=target_uid,
                    text=f"🎉 **পেমেন্ট সফলভাবে কনফার্ম করা হয়েছে!**\n\n"
                         f"🪙 আপনার অ্যাকাউন্টে **{add_coins} Coins** যোগ করা হয়েছে।\n"
                         f"💰 বর্তমান ব্যালেন্স: **{new_bal} Coins**",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")
            return
        else:
            await update.message.reply_text("❌ সঠিক সংখ্যা (কয়েন) লিখুন।")
            return

    # ২. Admin Panel বাটন
    if user_id == ADMIN_ID and text == "👑 Admin Control Panel":
        o_status = get_setting("orders_status")
        r_status = get_setting("reacts_status")
        binance_uid = get_setting("binance_uid")
        
        adm_text = (
            f"👑 **Admin Control Panel**\n\n"
            f"🌐 Orders: **{o_status}**\n"
            f"❤️ Reacts/Views: **{r_status}**\n"
            f"📌 Binance UID: `{binance_uid}`"
        )
        await update.message.reply_text(adm_text, parse_mode="Markdown")
        return

    # ৩. Setup বাটন ও ফ্লো
    if text == "⚙️ Setup":
        context.user_data['setup_step'] = 'waiting_channel'
        await update.message.reply_text("🔗 আপনার চ্যানেলের আসল ইউজারনেম বা লিংক দিন (যেমন: `@mychannel`):")
        return

    setup_step = context.user_data.get('setup_step')
    if setup_step == 'waiting_channel':
        context.user_data['temp_channel'] = text
        context.user_data['setup_step'] = 'waiting_reacts'
        await update.message.reply_text("❤️ কত রিঅ্যাকশন নিতে চান? (মিনিমাম ৫০ হতে হবে, সংখ্যাটি লিখুন যেমন: 1000):")
        return
    
    elif setup_step == 'waiting_reacts':
        context.user_data['temp_reacts'] = text
        context.user_data['setup_step'] = 'waiting_views'
        await update.message.reply_text("👀 কত ভিউ নিতে চান? সংখ্যাটি লিখুন (যেমন: 1000):")
        return

    elif setup_step == 'waiting_views':
        ch = context.user_data.pop('temp_channel', 'Not set')
        reacts = context.user_data.pop('temp_reacts', 'Not set')
        views = text
        context.user_data.pop('setup_step', None)

        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_setups SET channel_link = ?, views = ?, reacts = ? WHERE user_id = ?", (ch, views, reacts, user_id))
        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"✅ **সেটআপ সফলভাবে সেভ হয়েছে!**\n\n"
            f"🔗 Channel: {ch}\n"
            f"❤️ Reacts: {reacts}\n"
            f"👀 Views: {views}",
            reply_markup=get_main_keyboard(user_id),
            parse_mode="Markdown"
        )
        return

    # ৪. Profile বাটন
    if text == "👤 Profile":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins, total_spent, active_projects, referrals, referral_income FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        c, ts, ap, ref, ref_inc = u if u else (200, 0, 0, 0, 0)
        
        profile_text = (
            f"👤 **User Profile**\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"💰 Coin Balance: {c}\n"
            f"💸 Total Spent: {ts}\n"
            f"🚀 Active Projects: {ap}\n"
            f"👥 Total Referrals: {ref}\n"
            f"🎁 Referral Income: {ref_inc} coins"
        )
        await update.message.reply_text(profile_text, parse_mode="Markdown")
        return

    # ৫. Settings বাটন
    if text == "🛠️ Settings":
        o_status = get_setting("orders_status")
        r_status = get_setting("reacts_status")
        await update.message.reply_text(
            f"🛠️ **Bot Settings**\n\n📦 Global Orders: **{o_status}**\n❤️ Reacts Engine: **{r_status}**",
            parse_mode="Markdown"
        )
        return

    # ৬. Top-up বাটন
    if text == "💳 Top-up":
        binance_uid = get_setting("binance_uid")
        topup_text = (
            f"💳 **Top-up Balance**\n\n"
            f"আমাদের বাইনান্স ইউআইডি (Binance UID) তে পেমেন্ট করুন:\n"
            f"📌 **Binance UID:** `{binance_uid}`\n\n"
            f"রেট: $1 = 65000 Coins\n\n"
            f"📤 **টাকা পাঠানোর পর এখন পেমেন্টের স্ক্রিনশট বা প্রুফ এখানে পাঠান।**"
        )
        context.user_data['waiting_for_proof'] = True
        await update.message.reply_text(topup_text, parse_mode="Markdown")
        return

    # ৭. ইউজার পেমেন্ট স্ক্রিনশট পাঠালে এডমিনের কাছে পাঠানো
    if context.user_data.get('waiting_for_proof') or photo:
        if photo or context.user_data.get('waiting_for_proof'):
            context.user_data['waiting_for_proof'] = False
            
            # এডমিনের কাছে বাটনসহ ইনবক্সে পাঠানো
            admin_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add / Enter Coins", callback_data=f"approve_pay_{user_id}")]
            ])
            
            caption = (
                f"🚨 **নতুন ডিপোজিট স্ক্রিনশট এসেছে!**\n\n"
                f"👤 ইউজার আইডি: `{user_id}`\n"
                f"💬 মেসেজ: {text if text else 'Photo attached'}\n\n"
                f"👇 **উনাকে কয়েন দিতে নিচের বাটনে ক্লিক করে সংখ্যা লিখুন:**"
            )
            
            try:
                if photo:
                    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo[-1].file_id, caption=caption, reply_markup=admin_kb, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=ADMIN_ID, text=caption, reply_markup=admin_kb, parse_mode="Markdown")
                
                await update.message.reply_text("✅ আপনার পেমেন্ট স্ক্রিনশট এডমিনের কাছে পৌঁছেছে। এডমিন চেক করে খুব শীঘ্রই কয়েন জমা করে দিবেন।")
            except Exception as e:
                logger.error(f"Failed to forward payment proof: {e}")
            return

    # ৮. Order List
    if text == "📦 Order List":
        await update.message.reply_text("📦 আপনার সাম্প্রতিক সকল অর্ডারের তালিকা এখানে সংরক্ষিত রয়েছে।")
        return

    # ৯. Support
    if text == "🎧 Support":
        await update.message.reply_text("🎧 যেকোনো সাহায্যের জন্য যোগাযোগ করুন: https://t.me/NIROB_GX")
        return

    # ১০. Refer & Earn
    if text == "👥 Refer & Earn":
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(f"👥 **Refer & Earn**\nআপনার লিঙ্ক: `https://t.me/{bot_username}?start={user_id}`", parse_mode="Markdown")
        return

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))

    print("GX SMM Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
