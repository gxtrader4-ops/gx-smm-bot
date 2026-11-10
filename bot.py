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
            coins INTEGER DEFAULT 100
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rate_multiplier', '5')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('binance_id', 'USDT_TRC20_OR_BINANCE_ID')")
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

# --- 1xPanel API ক্লাস ---
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

    def services(self):
        post = {'key': self.api_key, 'action': 'services'}
        try:
            response = requests.post(self.api_url, data=post, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"API Services Error: {e}")
            return []

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
    cursor.execute("INSERT OR IGNORE INTO users (user_id, coins) VALUES (?, ?)", (user_id, 100))
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
        [InlineKeyboardButton("🛒 New Order (Reaction/View)", callback_data="new_order")],
        [InlineKeyboardButton("👤 My Profile", callback_data="profile"),
         InlineKeyboardButton("🪙 Add Coins", callback_data="add_coins")],
        [InlineKeyboardButton("📜 Order Channel", url=ORDER_CHANNEL_LINK)]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"🔥 **GX SMM PREMIUM PANEL** 🔥\n\n💰 আপনার বর্তমান কয়েন: **{coins} Coins**\nনিচের অপশন থেকে আপনার প্রয়োজনীয় সার্ভিস বেছে নিন।"

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
        binance_id = get_setting("binance_id")
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
        await query.message.edit_text(
            f"💳 **Add Coins via Binance/Bkash**\n\nনিচের বাইনান্স আইডি বা পেমেন্ট মাধ্যমে টাকা পাঠিয়ে স্ক্রিনশট এডমিনকে দিন:\n\n📌 **Binance ID:** `{binance_id}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "new_order":
        services = api_client.services()
        if not services or isinstance(services, dict) and 'error' in services:
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
            await query.message.edit_text("⚠️ সার্ভিস লোড করতে সমস্যা হচ্ছে। পরে চেষ্টা করুন।", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = []
        for s in services[:10]:
            keyboard.append([InlineKeyboardButton(f"{s['name'][:30]} (Rate: {s['rate']})", callback_data=f"srv_{s['service']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
        
        await query.message.edit_text("📋 **একটি সার্ভিস সিলেক্ট করুন:**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("srv_"):
        service_id = query.data.split("_")[1]
        context.user_data['selected_service'] = service_id
        context.user_data['waiting_for_link'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]
        await query.message.edit_text("🔗 এখন আপনার **পোস্টের লিংক (Link)** দিন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "main_menu":
        await show_main_menu(update, context)

    elif query.data == "admin_panel":
        if user_id != ADMIN_ID:
            return
        keyboard = [
            [InlineKeyboardButton("🪙 Set User Coins", callback_data="adm_set_user_coins"),
             InlineKeyboardButton("🎚️ Change Coin Rate", callback_data="adm_set_rate")],
            [InlineKeyboardButton("🆔 Change Binance ID", callback_data="adm_set_binance")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        await query.message.edit_text("⚙️ **Admin Control Panel**\nএডমিন প্যানেল থেকে যেকোনো সেটিংস পরিবর্তন করতে পারেন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_set_rate":
        context.user_data['waiting_for_admin_rate'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
        await query.message.reply_text("দয়া করে নতুন কয়েন রেট দিন (যেমন: ১০০০ রিঅ্যাকশনের জন্য কত কয়েন কাটবে):", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_set_user_coins":
        context.user_data['waiting_for_user_coin_update'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
        await query.message.reply_text("ইউজার আইডি এবং কয়েন এভাবে দিন (উদাহরণ: `123456789 500`):", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "adm_set_binance":
        context.user_data['waiting_for_binance_update'] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
        await query.message.reply_text("নতুন বাইনান্স আইডি বা পেমেন্ট ওয়ালেট দিন:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- মেসেজ এবং অর্ডার এক্সিকিউশন হ্যান্ডলার ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id == ADMIN_ID and context.user_data.get('waiting_for_admin_rate'):
        update_setting('rate_multiplier', text)
        context.user_data['waiting_for_admin_rate'] = False
        await update.message.reply_text(f"✅ কয়েন রেট সফলভাবে আপডেট করা হয়েছে: {text}")
        return

    if user_id == ADMIN_ID and context.user_data.get('waiting_for_user_coin_update'):
        try:
            parts = text.split()
            target_user = int(parts[0])
            new_coins = int(parts[1])
            
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO users (user_id, coins) VALUES (?, ?)", (target_user, new_coins))
            conn.commit()
            conn.close()
            
            context.user_data['waiting_for_user_coin_update'] = False
            await update.message.reply_text(f"✅ ইউজার `{target_user}` এর কয়েন সফলভাবে `{new_coins}` করা হয়েছে!")
        except Exception as e:
            await update.message.reply_text("❌ সঠিক ফরম্যাটে লিখুন। উদাহরণ: `123456789 500`", parse_mode="Markdown")
        return

    if user_id == ADMIN_ID and context.user_data.get('waiting_for_binance_update'):
        update_setting('binance_id', text)
        context.user_data['waiting_for_binance_update'] = False
        await update.message.reply_text(f"✅ বাইনান্স আইডি সফলভাবে আপডেট করা হয়েছে: {text}")
        return

    if context.user_data.get('waiting_for_link'):
        context.user_data['waiting_for_link'] = False
        service_id = context.user_data.get('selected_service')
        link = text

        quantity = 1000
        rate_multiplier = int(get_setting("rate_multiplier") or 5)
        required_coins = quantity * rate_multiplier

        conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        user_coins = row[0] if row else 0

        if user_coins < required_coins:
            conn.close()
            await update.message.reply_text(f"❌ আপনার পর্যাপ্ত কয়েন নেই! আপনার আছে **{user_coins}** কয়েন, প্রয়োজন **{required_coins}** কয়েন।")
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
            await update.message.reply_text(f"✅ **অর্ডার সফলভাবে প্লেস হয়েছে!**\n\n🆔 Order ID: `{order_id}`\n📌 Status: Pending\n🪙 খরচ হয়েছে: **{required_coins}** কয়েন", parse_mode="Markdown")
            
            try:
                channel_msg = f"🚀 **New SMM Order Placed!**\n\n👤 User ID: `{user_id}`\n🆔 Order ID: `{order_id}`\n🔗 Link: {link}\n📦 Quantity: {quantity}"
                await context.bot.send_message(chat_id=REQUIRED_CHANNEL, text=channel_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Channel notification error: {e}")
        else:
            conn = sqlite3.connect("smm_bot.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (required_coins, user_id))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"❌ এপিআই অর্ডার নিতে সমস্যা হয়েছে। আপনার কয়েন ফেরত দেওয়া হয়েছে। Response: {api_response}")

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("SMM Bot is running successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
