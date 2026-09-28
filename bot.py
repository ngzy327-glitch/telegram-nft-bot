import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from portalsmp import search

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
PORTALS_AUTH = os.getenv("PORTALS_AUTH")

if not BOT_TOKEN:
    raise RuntimeError("请在 Railway Variables 中设置 TELEGRAM_BOT_TOKEN")
if not PORTALS_AUTH:
    raise RuntimeError("请在 Railway Variables 中设置 PORTALS_AUTH")

def is_allowed(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    return str(update.effective_user.id) == ALLOWED_USER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "👋 你好！我是 Fragment NFT 礼物价格查询机器人。\n\n"
        "📌 查询整体价格：\n"
        "`Plush Pepe`\n\n"
        "📌 查询特定款式/背景：\n"
        "`Plush Pepe Wizard`\n"
        "`Plush Pepe Black`\n\n"
        "📌 精确筛选：\n"
        "`Plush Pepe / Wizard / Black`"
    )

async def query_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_input = update.message.text.strip()
    if not user_input:
        return

    if "/" in user_input:
        parts = [p.strip() for p in user_input.split("/") if p.strip()]
    else:
        parts = user_input.split()

    if not parts:
        return

    processing_msg = await update.message.reply_text(f"🔍 正在查询 `{user_input}` ...")

    try:
        gift_name = parts[0]
        filters = parts[1:] if len(parts) > 1 else []

        if len(filters) >= 2:
            results = search(
                gift_name=gift_name,
                model=filters[0],
                backdrop=filters[1],
                limit=10,
                authData=PORTALS_AUTH
            )
        elif len(filters) == 1:
            results = search(
                gift_name=gift_name,
                model=filters[0],
                limit=10,
                authData=PORTALS_AUTH
            )
        else:
            results = search(
                gift_name=gift_name,
                limit=5,
                sort="price_asc",
                authData=PORTALS_AUTH
            )

        if not results:
            await processing_msg.edit_text(f"❌ 未找到名为 `{gift_name}` 的礼物，或没有匹配的款式/背景。")
            return

        reply = f"📊 *{gift_name}* 匹配结果（{len(results)} 条）：\n\n"
        for gift in results:
            name = gift.get("name", gift_name)
            price = gift.get("price", "N/A")
            floor = gift.get("floor_price", "N/A")

            attrs = gift.get("attributes", [])
            model_str = backdrop_str = symbol_str = ""
            for attr in attrs:
                t = attr.get("type", "")
                v = attr.get("value", "")
                r = attr.get("rarity_per_mille", "N/A")
                if t == "model":
                    model_str = f"  款式：{v} (稀有度 {r}‰)\n"
                elif t == "backdrop":
                    backdrop_str = f"  背景：{v} (稀有度 {r}‰)\n"
                elif t == "symbol":
                    symbol_str = f"  符号：{v} (稀有度 {r}‰)\n"

            reply += f"🎁 *{name}*\n"
            if model_str: reply += model_str
            if backdrop_str: reply += backdrop_str
            if symbol_str: reply += symbol_str
            reply += f"  💰 价格：{price} TON | 地板价：{floor} TON\n\n"

        await processing_msg.edit_text(reply, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"查询 {user_input} 时出错: {e}")
        await processing_msg.edit_text("❌ 查询过程中出现错误，请稍后再试。")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, query_gift))
    print("🤖 Bot 已启动，正在运行...")
    app.run_polling()

if __name__ == '__main__':
    main()
