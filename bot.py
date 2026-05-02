import logging
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== НАСТРОЙКИ =====
TOKEN = "8668948538:AAH6NinNawBuQJs0PMVNSZ7nxvbv7OX1BgU"               # токен от BotFather
ADMIN_ID = 5735462741                    # ваш Telegram user ID

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ХРАНИЛИЩЕ КАРТОЧЕК =====
PACKS_DIR = "cards"
packs = {}
used_cards = {}
user_cards = {}
active_pack = "pack1"

def load_packs():
    global packs, used_cards
    packs.clear()
    used_cards.clear()
    for i in range(1, 5):
        pack_name = f"pack{i}"
        pack_dir = os.path.join(PACKS_DIR, pack_name)
        if not os.path.isdir(pack_dir):
            logger.error(f"Папка {pack_dir} не найдена!")
            continue
        images = sorted([
            os.path.join(pack_dir, f)
            for f in os.listdir(pack_dir)
            if f.lower().endswith('.png')
        ])
        if len(images) != 10:
            logger.warning(f"В паке {pack_name} ожидалось 10 PNG, загружено {len(images)}")
        packs[pack_name] = images
        used_cards[pack_name] = set()
    logger.info(f"Загружено паков: {list(packs.keys())}")

def reset_game_state():
    global user_cards
    for pack in used_cards:
        used_cards[pack].clear()
    user_cards.clear()
    logger.info("Состояние игры сброшено")

def is_admin(uid):
    return uid == ADMIN_ID

# ===== КОМАНДЫ АДМИНА =====
async def set_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав.")
        return
    try:
        num = int(context.args[0])
        if num < 1 or num > 4:
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /setpack 1-4")
        return
    global active_pack
    new_pack = f"pack{num}"
    if new_pack not in packs:
        await update.message.reply_text(f"Пак {new_pack} не загружен. Сначала /refresh.")
        return
    active_pack = new_pack
    reset_game_state()
    await update.message.reply_text(f"✅ Активный пак изменён на **{active_pack}**.\nВсе выданные карточки сброшены.", parse_mode="Markdown")

async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав.")
        return
    load_packs()
    reset_game_state()
    global active_pack
    if active_pack not in packs:
        active_pack = next(iter(packs.keys()), "pack1")
    await update.message.reply_text(f"🔄 Паки перезагружены. Активный пак: **{active_pack}**.", parse_mode="Markdown")

async def reset_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав.")
        return
    reset_game_state()
    await update.message.reply_text("✅ Все выданные карточки сброшены.")

async def admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав.")
        return
    avail = len(packs.get(active_pack, [])) - len(used_cards.get(active_pack, set()))
    await update.message.reply_text(f"📦 Пак: **{active_pack}**\n🃏 Осталось: {avail}/10", parse_mode="Markdown")

# ===== КОМАНДЫ ИГРОКОВ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = f"🎲 Привет, {update.effective_user.first_name}!\nСейчас активен пак: **{active_pack}**."
    if uid in user_cards:
        data = user_cards[uid]
        text += f"\n⚠️ Ты уже получил карточку из пака {data['pack']}."
        keyboard = None
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎴 Получить карточку", callback_data="get_card")]
        ])
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def mycard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_cards:
        data = user_cards[uid]
        with open(data['image_path'], 'rb') as photo:
            await update.message.reply_photo(photo, caption=f"Твоя карточка (пак {data['pack']})")
    else:
        await update.message.reply_text("У тебя ещё нет карточки. Нажми /start и получи её.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎲 *Бункер — карточки*\n"
        "• Администратор управляет активным паком.\n"
        "• Игроки получают по одной уникальной PNG‑картинке.\n\n"
        "Команды:\n"
        "/start – получить карточку\n"
        "/mycard – показать свою карточку\n"
        "/help – эта справка"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ===== ОБРАБОТКА КНОПКИ =====
async def get_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    if uid in user_cards:
        data = user_cards[uid]
        await query.edit_message_text(f"⚠️ Ты уже получил карточку из пака {data['pack']}.")
        return

    available = [img for img in packs.get(active_pack, []) if img not in used_cards[active_pack]]
    if not available:
        await query.edit_message_text("😔 Карточки в активном паке закончились.")
        return

    chosen = random.choice(available)
    used_cards[active_pack].add(chosen)
    user_cards[uid] = {"pack": active_pack, "image_path": chosen}

    with open(chosen, 'rb') as photo:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo,
            caption=f"🎴 Твоя карточка (пак *{active_pack}*)\n/mycard — показать снова.",
            parse_mode="Markdown"
        )
    await query.edit_message_text("✅ Карточка отправлена выше!")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)

# ===== ЗАПУСК =====
def main():
    load_packs()
    if not packs:
        logger.error("Не загружено ни одного пака. Проверьте папку 'cards' с подпапками pack1..4.")
        return

    global active_pack
    if active_pack not in packs:
        active_pack = next(iter(packs.keys()))

    # Без прокси — только если включён системный VPN
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("mycard", mycard))
    application.add_handler(CommandHandler("setpack", set_pack))
    application.add_handler(CommandHandler("refresh", refresh))
    application.add_handler(CommandHandler("resetgame", reset_game))
    application.add_handler(CommandHandler("status", admin_status))
    application.add_handler(CallbackQueryHandler(get_card_callback, pattern="^get_card$"))
    application.add_error_handler(error_handler)

    logger.info(f"Бот запущен. Активный пак: {active_pack}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()