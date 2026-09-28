import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from portalsmp import Client

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
# 确保环境变量 PORTALS_AUTH 已正确配置，且值以 "tma " 开头
PORTALS_AUTH = os.getenv("PORTALS_AUTH")

if not BOT_TOKEN:
    raise RuntimeError("请在 Railway Variables 中设置 TELEGRAM_BOT_TOKEN")

# 初始化 Portals 客户端
try:
    client = Client(authData=PORTALS_AUTH)
except Exception as e:
    raise RuntimeError(f"Portals 客户端初始化失败，请检查 PORTALS_AUTH 变量: {e}")

def is_allowed(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    user_id = str(update.effective_user.id)
    if user_id != ALLOWED_USER_ID:
        logging.warning(f"未授权用户尝试使用: {user_id}")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "👋 你好！我是 Fragment NFT 礼物价格查询机器人。\n\n"
        "📌 查询整体价格：\n"
        "直接发送礼物名称，例如：`Plush Pepe`\n\n"
        "📌 查询特定款式/背景：\n"
        "`Plush Pepe Wizard`\n"
        "`Plush Pepe Black`\n\n"
        "📌 精确筛选（用 / 分隔）：\n"
        "`Plush Pepe / Wizard / Black`"
    )

async def query_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_input = update.message.text.strip()
    if not user_input:
        return

    tokens = user_input.split()
    if not tokens:
        return

    processing_msg = await update.message.reply_text(f"🔍 正在查询 `{user_input}` ...")

    try:
        # 智能解析：尝试从长到短匹配礼物名
        gift_name = None
        extra_filters = []
        for i in range(len(tokens), 0, -1):
            candidate = " ".join(tokens[:i])
            # 用库提供的 search 方法探测是否存在该礼物
            try:
                test_results = client.search(gift_name=candidate, limit=1)
                if test_results:
                    gift_name = candidate
                    extra_filters = tokens[i:]
                    break
            except Exception:
                continue

        if not gift_name:
            await processing_msg.edit_text(f"❌ 未找到名为 `{user_input}` 的礼物。")
            return

        # 执行查询
        if len(extra_filters) >= 1:
            # 带筛选条件查询
            results = client.search(
                gift_name=gift_name,
                model=extra_filters[0] if len(extra_filters) >= 1 else None,
                backdrop=extra_filters[1] if len(extra_filters) >= 2 else None,
                limit=10
            )
        else:
            # 整体查询
            results = client.search(gift_name=gift_name, limit=5, sort="price_asc")

        if not results:
            await processing_msg.edit_text(
                f"❌ 在 `{gift_name}` 中未找到匹配的款式或背景。"
            )
            return

        # 格式化输出
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

        if len(results) >= 5 and len(extra_filters) == 0:
            reply += f"... 仅展示最低的 5 条结果"

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
