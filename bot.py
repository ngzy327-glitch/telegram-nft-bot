import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from TelegramGifts import TelegramGifts
from TelegramGifts.exceptions import CacheError

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

if not BOT_TOKEN:
    raise RuntimeError("请在 Railway Variables 中设置 TELEGRAM_BOT_TOKEN")

gifts = TelegramGifts()

def is_allowed(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    user_id = str(update.effective_user.id)
    if user_id != ALLOWED_USER_ID:
        logging.warning(f"未授权用户尝试使用: {user_id}")
        return False
    return True

def get_image_url(data: dict) -> str | None:
    """从库返回的数据中安全地提取图片链接"""
    if not data:
        return None
    links = data.get('links')
    if isinstance(links, dict):
        return links.get('webp') or links.get('png') or links.get('image')
    return data.get('image') or data.get('image_url')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "👋 你好！我是 Fragment NFT 礼物价格查询机器人。\n\n"
        "直接发送礼物名称即可查询整体价格，例如：\n"
        "`Artisan Brick`\n\n"
        "查询特定款式：\n"
        "`Artisan Brick Pro Gamer`\n\n"
        "查询特定背景：\n"
        "`Artisan Brick Black`"
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
        # === 智能解析 ===
        gift_name = None
        extra_query = None

        for i in range(len(tokens), 0, -1):
            candidate_gift = " ".join(tokens[:i])
            candidate_extra = " ".join(tokens[i:]) if i < len(tokens) else None

            try:
                info = gifts.get_gift(candidate_gift)
            except Exception as e:
                # 捕获底层网络异常，避免误报“未找到”
                logging.error(f"底层查询异常: {e}")
                raise CacheError("查询超时，请稍后重试")

            if info:
                gift_name = candidate_gift
                extra_query = candidate_extra
                break

        if not gift_name:
            await processing_msg.edit_text(f"❌ 未找到名为 `{user_input}` 的礼物。")
            return

        # 1. 整体查询
        if not extra_query:
            info = gifts.get_gift(gift_name)
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

            image_url = get_image_url(info)
            if image_url:
                try:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=image_url,
                        caption=f"🎨 {full_name}"
                    )
                except Exception as img_err:
                    logging.warning(f"发送图片失败: {img_err}")
            return

        # 2. 款式/背景查询
        gift_id = gift_name.lower().replace(" ", "_").replace("'", "")

        # 尝试按款式查询
        model = gifts.get_model_details(gift_id, extra_query)
        if model:
            model_name = model.get('name', extra_query)
            msg = f"*{model_name}* 款式价格：\n"
            msg += f"💰 价格：`{model.get('price_ton', 'N/A')}` TON\n"
            msg += f"🔹 稀有度：`{model.get('rarity', 'N/A')}`"
            await processing_msg.edit_text(msg, parse_mode='Markdown')

            image_url = get_image_url(model)
            if image_url:
                try:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=image_url,
                        caption=f"🎨 {gift_name}\n款式：{model_name}\n价格：{model.get('price_ton', 'N/A')} TON"
                    )
                except Exception as img_err:
                    logging.warning(f"发送款式图片失败: {img_err}")
            return

        # 尝试按背景查询
        info = gifts.get_gift(gift_name)
        if info:
            backdrops = info.get('backdrops', [])
            for bg in backdrops:
                bg_name = bg.get('name', '')
                if extra_query.lower() in bg_name.lower():
                    msg = f"*{bg_name}* 背景价格：\n"
                    msg += f"💰 价格：`{bg.get('price_ton', 'N/A')}` TON\n"
                    msg += f"🔹 稀有度：`{bg.get('rarity', 'N/A')}`"
                    await processing_msg.edit_text(msg, parse_mode='Markdown')

                    image_url = get_image_url(bg)
                    if image_url:
                        try:
                            await context.bot.send_photo(
                                chat_id=update.effective_chat.id,
                                photo=image_url,
                                caption=f"🎨 {gift_name}\n背景：{bg_name}\n价格：{bg.get('price_ton', 'N/A')} TON"
                            )
                        except Exception as img_err:
                            logging.warning(f"发送背景图片失败: {img_err}")
                    return

        await processing_msg.edit_text(
            f"❌ 在 `{gift_name}` 中未找到包含 `{extra_query}` 的款式或背景。\n"
            f"请尝试其他关键词，或直接发送 `{gift_name}` 查询整体价格。"
        )

    except CacheError:
        await processing_msg.edit_text(
            "⏳ 查询超时了，这通常是因为网络波动或数据正在同步。\n请稍后再试一次！"
        )
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
