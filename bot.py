import os
import logging
import json
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
    if not data: return None
    links = data.get('links')
    if isinstance(links, dict):
        return links.get('webp') or links.get('png') or links.get('image')
    return data.get('image') or data.get('image_url')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text(
        "👋 你好！我是 Fragment NFT 礼物价格查询机器人。\n\n"
        "直接发送礼物名称即可查询整体价格，例如：\n"
        "`Artisan Brick`\n\n"
        "查询特定款式：\n"
        "`Artisan Brick Pro Gamer`\n\n"
        "查询特定背景：\n"
        "`Artisan Brick Black`\n\n"
        "🔍 查看底层数据：\n"
        "`DebugPlush Pepe`"
    )

async def query_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return

    user_input = update.message.text.strip()
    if not user_input: return

    # 调试功能
    if user_input.startswith("Debug"):
        gift_name = user_input[5:].strip()
        processing_msg = await update.message.reply_text(f"🔍 正在获取 `{gift_name}` 的底层数据...")
        try:
            info = gifts.get_gift(gift_name)
            if info:
                # 只展示关键字段，防止消息过长
                keys = list(info.keys())
                # 尝试寻找 models 和 backdrops
                models = info.get('models', [])
                backdrops = info.get('backdrops', [])
                
                msg = f"📊 `{gift_name}` 的底层字段：\n"
                msg += f"`{keys}`\n\n"
                msg += f"📦 找到的款式 (models) 数量：{len(models)}\n"
                if models:
                    msg += f"款式列表：\n"
                    for m in models[:5]: msg += f"  - {json.dumps(m, ensure_ascii=False)}\n"
                msg += f"\n🎨 找到的背景 (backdrops) 数量：{len(backdrops)}\n"
                if backdrops:
                    msg += f"背景列表：\n"
                    for b in backdrops[:5]: msg += f"  - {json.dumps(b, ensure_ascii=False)}\n"
                
                # 如果消息太长，截断
                if len(msg) > 4000:
                    msg = msg[:4000] + "\n...(截断)"
                
                await processing_msg.edit_text(msg, parse_mode='Markdown')
            else:
                await processing_msg.edit_text(f"❌ 未找到 `{gift_name}`。")
        except Exception as e:
            await processing_msg.edit_text(f"❌ 调试出错：{str(e)}")
        return

    tokens = user_input.split()
    if not tokens: return

    processing_msg = await update.message.reply_text(f"🔍 正在查询 `{user_input}` ...")

    try:
        gift_name = None
        extra_query = None

        for i in range(len(tokens), 0, -1):
            candidate_gift = " ".join(tokens[:i])
            candidate_extra = " ".join(tokens[i:]) if i < len(tokens) else None
            try:
                info = gifts.get_gift(candidate_gift)
            except Exception as e:
                logging.error(f"底层查询异常: {e}")
                raise CacheError("查询超时，请稍后重试")
            if info:
                gift_name = candidate_gift
                extra_query = candidate_extra
                break

        if not gift_name:
            await processing_msg.edit_text(f"❌ 未找到名为 `{user_input}` 的礼物。")
            return

        if not extra_query:
            info = gifts.get_gift(gift_name)
            full_name = info.get('full_name', gift_name)
            prices = info.get('prices', {})
            fragment_price = prices.get('fragment_price_ton')
            getgems_price = prices.get('getgems_price_ton')
            tgmrkt_price = prices.get('tgmrkt_price_ton')

            lines = [f"*{full_name}* 价格信息：\n"]
            if fragment_price is not None: lines.append(f"🔹 Fragment: `{fragment_price}` TON")
            if getgems_price is not None: lines.append(f"🔹 GetGems: `{getgems_price}` TON")
            if tgmrkt_price is not None: lines.append(f"🔹 TGMrkt: `{tgmrkt_price}` TON")

            if not any([fragment_price, getgems_price, tgmrkt_price]): lines.append("暂时没有找到该礼物的市场价格。")

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

        # 款式和背景查询保持不变
        gift_id = gift_name.lower().replace(" ", "_").replace("'", "")
        model = gifts.get_model_details(gift_id, extra_query)
        if model:
            model_name = model.get('name', extra_query)
            msg = f"*{model_name}* 款式价格：\n"
            msg += f"💰 价格：`{model.get('price_ton', 'N/A')}` TON\n"
            msg += f"🔹 稀有度：`{model.get('rarity', 'N/A')}`"
            await processing_msg.edit_text(msg, parse_mode='Markdown')
            image_url = get_image_url(model)
            if image_url:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url, caption=f"🎨 {gift_name} 款式：{model_name}")
            return

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
                        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url, caption=f"🎨 {gift_name} 背景：{bg_name}")
                    return

        await processing_msg.edit_text(
            f"❌ 在 `{gift_name}` 中未找到包含 `{extra_query}` 的款式或背景。\n"
            f"请尝试其他关键词，或直接发送 `{gift_name}` 查询整体价格。"
        )

    except CacheError:
        await processing_msg.edit_text("⏳ 查询超时了，请稍后再试一次！")
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
