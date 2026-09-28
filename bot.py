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
        "`Artisan Brick`\n\n"
        "如果要查询特定款式或背景，可以发送：\n"
        "`Artisan Brick Pro Gamer`\n"
        "`Artisan Brick Black`"
    )

async def query_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_input = update.message.text.strip()
    if not user_input:
        return

    # 解析输入：拆分为基础礼物名和附加属性（款式/背景）
    parts = user_input.split()
    if not parts:
        return

    base_name = parts[0]
    extra_query = " ".join(parts[1:]).lower() if len(parts) > 1 else None

    processing_msg = await update.message.reply_text(
        f"🔍 正在查询 `{user_input}` ..."
    )

    try:
        # 1. 先尝试用完整输入查询，如果失败，再用基础名查询
        info = gifts.get_gift(user_input)
        if not info:
            info = gifts.get_gift(base_name)

        if not info:
            await processing_msg.edit_text(
                f"❌ 未找到名为 `{user_input}` 的礼物。\n请检查名称拼写是否正确。"
            )
            return

        full_name = info.get('full_name', base_name)

        # 2. 如果用户没有指定具体属性，直接显示整体价格
        if not extra_query:
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
            return

        # 3. 如果用户指定了属性（比如 Pro Gamer 或 Black），则尝试过滤
        # 注意：不同版本的 TelegramGifts 库返回的数据结构可能略有不同，
        # 以下代码兼容了 'models' 和 'backdrops' 字段的解析。
        matched_lines = []
        
        # 尝试遍历所有模型
        models = info.get('models', [])
        for model in models:
            model_name = model.get('name', '').lower()
            if extra_query in model_name:
                price = model.get('price_ton', 'N/A')
                matched_lines.append(f"🔸 模型 [{model.get('name')}]：`{price}` TON")

        # 尝试遍历所有背景
        backdrops = info.get('backdrops', [])
        for bg in backdrops:
            bg_name = bg.get('name', '').lower()
            if extra_query in bg_name:
                price = bg.get('price_ton', 'N/A')
                matched_lines.append(f"🎨 背景 [{bg.get('name')}]：`{price}` TON")

        if matched_lines:
            reply_text = f"*{full_name}* 中的匹配结果：\n\n" + "\n".join(matched_lines)
            await processing_msg.edit_text(reply_text, parse_mode='Markdown')
        else:
            await processing_msg.edit_text(
                f"❌ 在 `{full_name}` 中未找到包含 `{extra_query}` 的模型或背景。\n"
                f"请尝试其他关键词，或直接发送 `{base_name}` 查询整体价格。"
            )

    except Exception as e:
        logging.error(f"查询礼物 {user_input} 时出错: {e}")
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
