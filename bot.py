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
# আপনার দেওয়া বাইনান্স ইউআইডি (Binance UID)
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
            coins INTEGER DEFAULT 1000
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rate_multiplier', '3')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('binance_uid', ?)", (DEFAULT_BINANCE_UID,))
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

# --- স্টার্টিং কমান্ড ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, coins) VALUES (?, ?)", (user_id, 1000))
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
    conn.close()
    coins = row[0] if row else 0

    keyboard = [
        [InlineKeyboardButton("🚀 Telegram Post Reaction (ID: 1936)", callback_data="order_1936")],
        [InlineKeyboardButton("👤 My Profile", callback_data="profile"),
         InlineKeyboardButton("🪙 Add Coins (Binance)", callback_data="add_coins")],
        [InlineKeyboardButton("📜 Order Channel", url=ORDER_CHANNEL_LINK)]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"🔥 **GX SMM PREMIUM PANEL** 🔥\n\n💰 আপনার বর্তমান কয়েন: **{coins} Coins**\nনিচের অপশন থেকে অটোমেটিক রিঅ্যাকশন অর্ডার করুন।"

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

    elif query.data == "profile":
        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        coins = row[0] if row else 0

        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
        await query.message.edit_text(
            f"👤 **User Profile**\n\n🆔 Telegram ID: `{user_id}`\n🪙 Coins: **{coins}**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "add_coins":
        binance_uid = get_setting("binance_uid")
        keyboard = [
            [InlineKeyboardButton("📤 Send Payment Screenshot", callback_data="send_payment_proof")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        await query.message.edit_text(
            f"💳 **Add Coins via Binance (USDT)**\n\n"
            f"আমাদের বাইনান্স ইউআইডি (Binance UID) তে পেমেন্ট করুন:\n\n"
            f"📌 **Binance UID:** `{binance_uid}`\n\n"
            f"টাকা পাঠানোর পর নিচের **'Send Payment Screenshot'** বাটনে ক্লিক করে পেমেন্টের স্ক্রিনশট ও ট্রানজাকশন ডিটেইলস পাঠান।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "send_payment_proof":
        context.user_data['waiting_for_payment_proof'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="add_coins")]]
        await query.message.edit_text(
            "📤 দয়া করে আপনার পেমেন্টের **স্ক্রিনশট (Photo)** এবং সাথে আপনার ইউজার আইডি বা বাইনান্স ডিটেইলস লিখে পাঠান। এটি সরাসরি এডমিনের কাছে চলে যাবে।",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "order_1936":
        context.user_data['selected_service'] = 1936
        context.user_data['waiting_for_link'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]
        await query.message.edit_text("🔗 আপনার **পোস্টের লিংক (Link)** দিন:\n(যে পোস্টে রিঅ্যাকশন ও ফ্রি ভিউ নিতে চান)", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "main_menu":
        await show_main_menu(update, context)

    elif query.data == "admin_panel":
        if user_id != ADMIN_ID:
            return
        
        api_bal = api_client.balance()
        balance_text = api_bal.get('balance', 'Unknown') if isinstance(api_bal, dict) else 'Check API'
        currency = api_bal.get('currency', 'USD') if isinstance(api_bal, dict) else ''

        keyboard = [
            [InlineKeyboardButton("🪙 Add Coins to User (Manual)", callback_data="adm_add_coins")],
            [InlineKeyboardButton("🎚️ Change Coin Rate", callback_data="adm_set_rate"),
             InlineKeyboardButton("🆔 Change Binance UID", callback_data="adm_set_binance")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        await query.message.edit_text(f"⚙️ **Admin Control Panel**\n\n🌐 1xPanel Balance: **{balance_text} {currency}**\n\nনিচের অপশন থেকে কন্ট্রোল করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_add_coins":
        context.user_data['waiting_for_admin_add_coins'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
        await query.message.reply_text("ইউজার আইডি এবং কত কয়েন দিবেন তা এভাবে লিখুন:\n(উদাহরণ: `123456789 5000`):", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "adm_set_rate":
        context.user_data['waiting_for_admin_rate'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
        await query.message.reply_text("নতুন কয়েন রেট দিন (যেমন: ১০০০ রিঅ্যাকশনের দাম কত কয়েন হবে):", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_set_binance":
        context.user_data['waiting_for_binance_uid_update'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
        await query.message.reply_text("নতুন বাইনান্স ইউআইডি (Binance UID) দিন:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- মেসেজ এবং পেমেন্ট প্রুফ হ্যান্ডলার ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    photo = update.message.photo

    # ১. ইউজার পেমেন্ট স্ক্রিনশট পাঠালে এডমিনের ইনবক্সে ফরোয়ার্ড করা
    if context.user_data.get('waiting_for_payment_proof'):
        context.user_data['waiting_for_payment_proof'] = False
        
        forward_text = f"🚨 **New USDT Payment Proof Received!**\n\n👤 From User ID: `{user_id}`\n💬 Details: {text if text else 'Attached Screenshot'}"
        try:
            if photo:
                await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo[-1].file_id, caption=forward_text, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=ADMIN_ID, text=forward_text, parse_mode="Markdown")
            
            await update.message.reply_text("✅ আপনার পেমেন্টের স্ক্রিনশট ও তথ্য এডমিনের কাছে সফলভাবে চলে গেছে! এডমিন চেক করে আপনার একাউন্টে কয়েন অ্যাড করে দিবেন।")
        except Exception as e:
            await update.message.reply_text("❌ পাঠাতে সমস্যা হয়েছে। দয়া করে সরাসরি এডমিনের সাথে যোগাযোগ করুন।")
        return

    # ২. এডমিন ম্যানুয়ালি ইউজারকে কয়েন অ্যাড করলে
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_admin_add_coins'):
        try:
            parts = text.split()
            target_user = int(parts[0])
            add_coins = int(parts[1])
            
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT coins FROM users WHERE user_id = ?", (target_user,))
            row = cursor.fetchone()
            
            if row:
                cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (add_coins, target_user))
            else:
                cursor.execute("INSERT INTO users (user_id, coins) VALUES (?, ?)", (target_user, add_coins))
            
            conn.commit()
            conn.close()
            
            context.user_data['waiting_for_admin_add_coins'] = False
            await update.message.reply_text(f"✅ সফলভাবে ইউজার `{target_user}` এর একাউন্টে `{add_coins}` কয়েন যোগ করা হয়েছে!")
            
            try:
                await context.bot.send_message(chat_id=target_user, text=f"🎉 অভিনন্দন! এডমিন আপনার একাউন্টে **{add_coins}** কয়েন যোগ করেছেন।", parse_mode="Markdown")
            except:
                pass
        except Exception as e:
            await update.message.reply_text("❌ সঠিক ফরম্যাটে লিখুন। উদাহরণ: `123456789 5000`", parse_mode="Markdown")
        return

    # ৩. এডমিন কয়েন রেট আপডেট করলে
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_admin_rate'):
        update_setting('rate_multiplier', text)
        context.user_data['waiting_for_admin_rate'] = False
        await update.message.reply_text(f"✅ কয়েন রেট সফলভাবে আপডেট করা হয়েছে: {text}")
        return

    # ৪. এডমিন বাইনান্স ইউআইডি আপডেট করলে
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_binance_uid_update'):
        update_setting('binance_uid', text)
        context.user_data['waiting_for_binance_uid_update'] = False
        await update.message.reply_text(f"✅ বাইনান্স ইউআইডি সফলভাবে আপডেট করা হয়েছে: {text}")
        return

    # ৫. ইউজার অর্ডার করার জন্য লিংক দিলে
    if context.user_data.get('waiting_for_link'):
        context.user_data['waiting_for_link'] = False
        service_id = context.user_data.get('selected_service', 1936)
        link = text

        quantity = 1000
        rate_multiplier = int(get_setting("rate_multiplier") or 3)
        required_coins = (quantity // 1000) * (3000 if rate_multiplier == 3 else rate_multiplier * 1000)

        api_bal = api_client.balance()
        if isinstance(api_bal, dict) and 'balance' in api_bal:
            try:
                if float(api_bal['balance']) <= 0:
                    await update.message.reply_text("⚠️ দুঃখিত, বর্তমানে প্যানেলে পর্যাপ্ত ব্যালেন্স না থাকায় অর্ডার সাময়িকভাবে বন্ধ রয়েছে।")
                    return
            except:
                pass

        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        user_coins = row[0] if row else 0

        if user_coins < required_coins:
            conn.close()
            await update.message.reply_text(f"❌ আপনার পর্যাপ্ত কয়েন নেই!\nআপনার আছে: **{user_coins}** কয়েন\nপ্রয়োজন: **{required_coins}** কয়েন (১০০০ রিঅ্যাকশন)")
            return

        cursor.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (required_coins, user_id))
        conn.commit()
        conn.close()

        order_data = {
            'service': service_id,
            'link': link,
            'quantity': quantity
        }
        api_response = api_client.order(order_data)

        if isinstance(api_response, dict) and 'order' in api_response:
            order_id = api_response['order']
            await update.message.reply_text(
                f"✅ **অর্ডার সফলভাবে প্লেস হয়েছে!**\n\n"
                f"📦 Service: Telegram Post Reaction + Free View (ID: 1936)\n"
                f"🆔 Order ID: `{order_id}`\n"
                f"🔗 Link: {link}\n"
                f"📌 Status: Pending\n"
                f"🪙 খরচ হয়েছে: **{required_coins}** কয়েন",
                parse_mode="Markdown"
            )
            
            try:
                channel_msg = (
                    f"🚀 **New SMM Order Completed!**\n\n"
                    f"👤 User ID: `{user_id}`\n"
                    f"🆔 Order ID: `{order_id}`\n"
                    f"📦 Service ID: `1936`\n"
                    f"🔗 Link: {link}\n"
                    f"⚡ Status: Processing"
                )
                await context.bot.send_message(chat_id=REQUIRED_CHANNEL, text=channel_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Channel notification error: {e}")
        else:
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (required_coins, user_id))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"❌ এপিআই অর্ডার নিতে সমস্যা হয়েছে। আপনার কেটে নেওয়া কয়েন ফেরত দেওয়া হয়েছে। Response: {api_response}")

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))

    print("SMM Bot with Binance UID 1122595327 is running successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
