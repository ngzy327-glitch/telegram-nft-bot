import asyncio
import os
import random
import string
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

logging.basicConfig(level=logging.INFO)

# ========== 环境变量 ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))       # 你的 TG 用户ID，用于管理命令
# =============================

if not BOT_TOKEN or not ADMIN_ID:
    print("❌ 缺少 BOT_TOKEN 或 ADMIN_ID")
    exit(1)

# 内存数据：{红包ID: {"total": 总额, "left": 剩余个数, "amounts": [], "claimed": {}, "answer": "xxx"}}
REDPACKETS = {}
RP_COUNTER = [0]  # 用列表模拟全局计数器

def gen_code(length=4):
    """生成随机验证码（大小写字母混合）"""
    return ''.join(random.choices(string.ascii_letters, k=length))

def gen_fake_codes(correct, count):
    """生成 count 个干扰码，跟正确答案不重复"""
    codes = {correct}
    while len(codes) < count:
        codes.add(gen_code(len(correct)))
    return list(codes)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("红包机器人已启动。管理员发送 /send 金额 个数 来发红包。")

async def send_rp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """管理员命令：/send 金额 个数"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ 只有管理员可以发红包。")
        return

    try:
        total = float(context.args[0])
        count = int(context.args[1])
        if total <= 0 or count <= 0:
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("格式：/send 金额 个数\n例如：/send 10 5")
        return

    # 生成随机金额（拼手气红包）
    amounts = []
    remaining = total
    for i in range(count - 1):
        # 每次随机取剩余金额的 0~剩余均值*2 之间
        avg = remaining / (count - i)
        m = round(random.uniform(0.01, avg * 2), 2)
        m = min(m, remaining - 0.01 * (count - i - 1))
        amounts.append(m)
        remaining -= m
    amounts.append(round(remaining, 2))
    random.shuffle(amounts)

    # 生成验证码和按钮
    answer = gen_code(4)
    fake_codes = gen_fake_codes(answer, random.randint(4, 8))
    random.shuffle(fake_codes)

    RP_COUNTER[0] += 1
    rp_id = RP_COUNTER[0]

    REDPACKETS[rp_id] = {
        "total": total,
        "left": count,
        "amounts": amounts,
        "claimed": {},   # user_id -> amount
        "answer": answer,
    }

    # 构建按钮键盘（每行2个按钮）
    keyboard = []
    row = []
    for code in fake_codes:
        row.append(InlineKeyboardButton(code, callback_data=f"rp:{rp_id}:{code}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    text = (
        f"🧧 红包来了！\n"
        f"总金额：{total} USDT\n"
        f"红包个数：{count}\n"
        f"请选择正确的验证码 <b>{answer}</b> 领取红包"
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮点击"""
    query = update.callback_query
    user = query.from_user

    try:
        _, rp_id_str, clicked_code = query.data.split(":", 2)
        rp_id = int(rp_id_str)
    except Exception:
        await query.answer("无效操作")
        return

    rp = REDPACKETS.get(rp_id)
    if not rp:
        await query.answer("红包不存在或已过期")
        return

    if user.id in rp["claimed"]:
        await query.answer(f"你已经领过了：{rp['claimed'][user.id]} USDT")
        return

    if rp["left"] <= 0:
        await query.answer("红包已被抢完")
        return

    # 判断验证码是否正确
    if clicked_code != rp["answer"]:
        await query.answer("❌ 验证码错误，再试一次")
        return

    # 领取
    amount = rp["amounts"].pop(0)
    rp["claimed"][user.id] = amount
    rp["left"] -= 1

    name = user.first_name or user.username or str(user.id)
    await query.answer(f"✅ 你领到了 {amount} USDT")
    await query.message.reply_text(
        f"🎉 {name} 领到了 {amount} USDT\n剩余红包：{rp['left']} 个"
    )

    if rp["left"] == 0:
        await query.message.reply_text(f"🧧 红包 {rp_id} 已抢完！")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send", send_rp))
    app.add_handler(CallbackQueryHandler(callback_handler, pattern=r"^rp:"))

    print("🤖 红包机器人已启动")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    # 保持运行
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())