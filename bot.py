import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from portalsmp import search

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
# Portals 需要认证，请去 web.telegram.org 抓包获取 tma 开头的 token
PORTALS_AUTH = os.getenv("PORTALS_AUTH")

if not BOT_TOKEN:
    raise RuntimeError("请在 Railway Variables 中设置 TELEGRAM_BOT_TOKEN")

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

    # 解析输入：支持 "礼物名 属性" 或 "礼物名 / 属性1 / 属性2"
    if "/" in user_input:
        parts = [p.strip() for p in user_input.split("/") if p.strip()]
    else:
        tokens = user_input.split()
        # 智能拆分：从最长匹配开始尝试
        parts = []
        for i in range(len(tokens), 0, -1):
            candidate = " ".join(tokens[:i])
            # 先用候选名称试查一下
            try:
                test = search(gift_name=candidate, limit=1, authData=PORTALS_AUTH)
                if test:
                    parts = [candidate] + tokens[i:]
                    break
            except Exception:
                continue
        if not parts:
            parts = tokens

    if not parts:
        return

    processing_msg = await update.message.reply_text(f"🔍 正在查询 `{user_input}` ...")

    try:
        gift_name = parts[0]
        filters = parts[1:] if len(parts) > 1 else []

        # 构建搜索参数
        search_params = {
            "gift_name": gift_name,
            "limit": 20,
            "sort": "price_asc",
            "authData": PORTALS_AUTH,
        }

        # 如果有关键词，尝试匹配 model 或 backdrop
        if filters:
            # 这里简单处理：把第一个关键词当作 model 或 backdrop 搜索
            # 更精确的匹配可以在拿到结果后二次过滤
            search_params["model"] = filters[0] if len(filters) >= 1 else None
            search_params["backdrop"] = filters[1] if len(filters) >= 2 else None

        # 清理 None 值
        search_params = {k: v for k, v in search_params.items() if v is not None}

        results = search(**search_params)

        if not results:
            await processing_msg.edit_text(
                f"❌ 未找到名为 `{gift_name}` 的礼物，或没有匹配的款式/背景。"
            )
            return

        # 格式化输出
        reply = f"📊 *{gift_name}* 匹配结果（{len(results)} 条）：\n\n"
        for gift in results[:5]:
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

        if len(results) > 5:
            reply += f"... 还有 {len(results) - 5} 条结果"

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
  
