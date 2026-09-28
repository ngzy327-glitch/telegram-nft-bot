import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from TelegramGifts import TelegramGifts

# ==========================
# 日志配置
# ==========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==========================
# 环境变量
# ==========================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

if not BOT_TOKEN:
    raise RuntimeError("请在 Railway Variables 中设置 TELEGRAM_BOT_TOKEN")

# ==========================
# 初始化 TelegramGifts
# 【关键修改】：去掉了 cache_dir 参数，使用默认缓存目录
# 这样就不需要 Railway 的 Volume 也能运行
# ==========================
gifts = TelegramGifts()

# ==========================
# 权限检查
# ==========================
def is_allowed(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    user_id = str(update.effective_user.id)
    if user_id != ALLOWED_USER_ID:
        logging.warning(f"未授权用户尝试使用: {user_id}")
        return False
    return True

# ==========================
# 命令处理
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "👋 你好！我是 Fragment NFT 礼物价格查询机器人。\n\n"
        "直接发送礼物名称即可查询，例如：\n"
        "`Artisan Brick`\n"
        "`Khabib's Papakha`"
    )

async def query_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    gift_name = update.message.text.strip()
    if not gift_name:
        return

    processing_msg = await update.message.reply_text(
        f"🔍 正在查询 `{gift_name}` ..."
    )

    try:
        info = gifts.get_gift(gift_name)

        if not info:
            await processing_msg.edit_text(
                f"❌ 未找到名为 `{gift_name}` 的礼物。\n请检查名称是否正确。"
            )
            return

        full_name = info.get('full_name', gift_name)
        prices = info.get('prices', {})

        fragment_price = prices.get('fragment_price_ton')
        getgems_price = prices.get('getgems_price_ton')
        tgmrkt_price = prices.get('tgmrkt_price_ton')

        lines = [f"*{full_name}* 价格信息：\n"]

        if fragment_price is not None:
            lines.append(f"🔹 Fragment: `{fragment_price}` TON")
        if getgems_price is not None:
            lines.append(f"🔹 GetGems: `{getgems_price}` TON")
        if tgmrkt_price is not None:
            lines.append(f"🔹 TGMrkt: `{tgmrkt_price}` TON")

        if not any([fragment_price, getgems_price, tgmrkt_price]):
            lines.append("暂时没有找到该礼物的市场价格。")

        await processing_msg.edit_text("\n".join(lines), parse_mode='Markdown')

    except Exception as e:
        logging.error(f"查询礼物 {gift_name} 时出错: {e}")
        await processing_msg.edit_text("❌ 查询过程中出现错误，请稍后再试。")

# ==========================
# 启动
# ==========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, query_gift)
    )

    print("🤖 Bot 已启动，正在运行...")
    app.run_polling()

if __name__ == '__main__':
    main()
