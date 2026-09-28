import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from portalsmp import search_gifts

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

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
        "`Plush Pepe Black`\n"
        "`Plush Pepe Gold`\n\n"
        "📌 精确筛选（用 / 分隔）：\n"
        "`Plush Pepe / Wizard / Black`\n"
        "`Plush Pepe / Gold / Blue`"
    )

def format_gift(gift: dict) -> str:
    """格式化单个礼物信息"""
    name = gift.get('name', '未知')
    price = gift.get('price', 'N/A')
    floor = gift.get('floor_price', 'N/A')
    
    attrs = gift.get('attributes', [])
    model = backdrop = symbol = None
    for attr in attrs:
        t = attr.get('type', '')
        if t == 'model':
            model = f"{attr.get('value')} (稀有度 {attr.get('rarity_per_mille', 'N/A')}‰)"
        elif t == 'backdrop':
            backdrop = f"{attr.get('value')} (稀有度 {attr.get('rarity_per_mille', 'N/A')}‰)"
        elif t == 'symbol':
            symbol = f"{attr.get('value')} (稀有度 {attr.get('rarity_per_mille', 'N/A')}‰)"
    
    lines = [f"🎁 *{name}*"]
    if model:
        lines.append(f"  款式：{model}")
    if backdrop:
        lines.append(f"  背景：{backdrop}")
    if symbol:
        lines.append(f"  符号：{symbol}")
    lines.append(f"  💰 价格：{price} TON | 地板价：{floor} TON")
    return "\n".join(lines)

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
        parts = tokens

    if not parts:
        return

    processing_msg = await update.message.reply_text(f"🔍 正在查询 `{user_input}` ...")

    try:
        # 用礼物名搜索
        gift_name = parts[0]
        results = search_gifts(gift_name)

        if not results:
            await processing_msg.edit_text(f"❌ 未找到名为 `{gift_name}` 的礼物。")
            return

        # 如果有属性筛选条件
        if len(parts) > 1:
            filters = parts[1:]
            matched = []

            for gift in results:
                attrs = gift.get('attributes', [])
                attr_values = {a.get('type'): a.get('value', '').lower() for a in attrs}

                # 检查所有筛选条件是否都匹配
                all_match = True
                for f in filters:
                    f_lower = f.lower()
                    # 在所有属性值中查找
                    if not any(f_lower in v for v in attr_values.values()):
                        all_match = False
                        break

                if all_match:
                    matched.append(gift)

            if matched:
                reply = f"📊 *{gift_name}* 匹配结果（{len(matched)} 条）：\n\n"
                for g in matched[:5]:  # 最多显示5条
                    reply += format_gift(g) + "\n\n"
                if len(matched) > 5:
                    reply += f"... 还有 {len(matched) - 5} 条结果"
                await processing_msg.edit_text(reply, parse_mode='Markdown')
            else:
                await processing_msg.edit_text(
                    f"❌ 在 `{gift_name}` 中未找到包含 `{' '.join(filters)}` 的款式或背景。\n"
                    f"请尝试其他关键词，或直接发送 `{gift_name}` 查询整体价格。"
                )
        else:
            # 只查礼物名，显示最便宜的几条
            sorted_results = sorted(results, key=lambda x: float(x.get('price', 0) or 0))
            reply = f"📊 *{gift_name}* 价格信息（最低价）：\n\n"
            for g in sorted_results[:5]:
                reply += format_gift(g) + "\n\n"
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
