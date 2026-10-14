import asyncio
import os
import random
import string
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)

logging.basicConfig(level=logging.INFO)

# ========== 环境变量 ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS_STR = os.environ.get("ADMIN_ID", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]
# =============================

if not BOT_TOKEN or not ADMIN_IDS:
    print("❌ 缺少 BOT_TOKEN 或 ADMIN_ID")
    exit(1)

REDPACKETS = {}
RP_COUNTER = [0]

# 币种映射：用户输入的简写 -> 显示名称
COIN_MAP = {
    'u': 'USDT',
    'usdt': 'USDT',
    'cny': 'CNY',
    'qq': 'QQ',
}

def gen_code(length=4):
    return ''.join(random.choices(string.ascii_letters, k=length))

def gen_fake_codes(correct, count):
    codes = {correct}
    while len(codes) < count:
        codes.add(gen_code(len(correct)))
    return list(codes)

def make_amounts(total, count):
    amounts = []
    remaining = total
    for i in range(count - 1):
        avg = remaining / (count - i)
        m = round(random.uniform(0.01, avg * 2), 2)
        m = min(m, remaining - 0.01 * (count - i - 1))
        amounts.append(m)
        remaining -= m
    amounts.append(round(remaining, 2))
    random.shuffle(amounts)
    return amounts

def parse_amount_coin_count(args):
    """
    解析参数：金额(带单位) 个数
    支持：100u 5 / 100cny 5 / 100qq 5 / 100USDT 5
    返回 (total, coin_display, count) 或 (None, None, None)
    """
    if len(args) < 2:
        return None, None, None
    try:
        amount_str = args[0].strip().lower()
        count = int(args[1])
        if count <= 0:
            return None, None, None

        # 匹配数字 + 可选单位
        m = re.match(r'^([\d.]+)\s*([a-z]*)$', amount_str)
        if not m:
            return None, None, None

        total = float(m.group(1))
        unit = m.group(2) or 'u'  # 默认 USDT

        if unit not in COIN_MAP:
            return None, None, None

        if total <= 0:
            return None, None, None

        return total, COIN_MAP[unit], count
    except (IndexError, ValueError):
        return None, None, None

# ================== 三种发红包方式 ==================

async def send_yzm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """验证码红包：yzmhb 100u 5"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ 只有管理员可以发红包。")
        return
    total, coin, count = parse_amount_coin_count(context.args)
    if total is None:
        await update.message.reply_text(
            "格式：yzmhb 金额单位 个数\n"
            "示例：yzmhb 100u 5 / yzmhb 100cny 5 / yzmhb 100qq 5"
        )
        return

    amounts = make_amounts(total, count)
    answer = gen_code(4)
    fake_codes = gen_fake_codes(answer, random.randint(4, 8))
    random.shuffle(fake_codes)

    RP_COUNTER[0] += 1
    rp_id = RP_COUNTER[0]
    REDPACKETS[rp_id] = {
        "type": "yzm", "coin": coin,
        "total": total, "left": count,
        "amounts": amounts, "claimed": {},
        "answer": answer,
    }

    keyboard, row = [], []
    for code in fake_codes:
        row.append(InlineKeyboardButton(code, callback_data=f"rp:{rp_id}:{code}"))
        if len(row) == 2:
            keyboard.append(row); row = []
    if row: keyboard.append(row)

    await update.message.reply_text(
        f"🧧 验证码红包\n"
        f"总金额：{total} {coin}\n"
        f"红包个数：{count}\n"
        f"请选择正确的验证码 <b>{answer}</b> 领取红包",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def send_gk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """公开红包：gkhb 100u 5"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ 只有管理员可以发红包。")
        return
    total, coin, count = parse_amount_coin_count(context.args)
    if total is None:
        await update.message.reply_text(
            "格式：gkhb 金额单位 个数\n"
            "示例：gkhb 100u 5 / gkhb 100cny 5 / gkhb 100qq 5"
        )
        return

    amounts = make_amounts(total, count)
    RP_COUNTER[0] += 1
    rp_id = RP_COUNTER[0]
    REDPACKETS[rp_id] = {
        "type": "gk", "coin": coin,
        "total": total, "left": count,
        "amounts": amounts, "claimed": {},
    }

    keyboard = [[InlineKeyboardButton("领取红包🧧", callback_data=f"rp:{rp_id}:claim")]]

    await update.message.reply_text(
        f"🧧 公开红包\n"
        f"总金额：{total} {coin}\n"
        f"红包个数：{count}\n"
        f"点击下方按钮领取",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_zs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """专属红包：回复某人后发 hb 100u 5"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ 只有管理员可以发红包。")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("请先回复你要发红包的对象，再发送：hb 100u 5")
        return
    target = update.message.reply_to_message.from_user
    if not target:
        await update.message.reply_text("无法识别目标用户。")
        return

    total, coin, count = parse_amount_coin_count(context.args)
    if total is None:
        await update.message.reply_text(
            "格式：hb 金额单位 个数（需要回复某人的消息）\n"
            "示例：hb 100u 5 / hb 100cny 5 / hb 100qq 5"
        )
        return

    amounts = make_amounts(total, count)
    RP_COUNTER[0] += 1
    rp_id = RP_COUNTER[0]
    REDPACKETS[rp_id] = {
        "type": "zs", "coin": coin,
        "total": total, "left": count,
        "amounts": amounts, "claimed": {},
        "allowed_users": [target.id, update.effective_user.id],
    }

    keyboard = [[InlineKeyboardButton("领取红包🧧", callback_data=f"rp:{rp_id}:claim")]]

    await update.message.reply_text(
        f"🧧 专属红包\n"
        f"指定用户：{target.first_name or target.username or target.id}\n"
        f"总金额：{total} {coin}\n"
        f"红包个数：{count}\n"
        f"仅发送者和被指定者可领取",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== 回调处理 ==================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    try:
        _, rp_id_str, action = query.data.split(":", 2)
        rp_id = int(rp_id_str)
    except Exception:
        await query.answer("无效操作")
        return

    rp = REDPACKETS.get(rp_id)
    if not rp:
        await query.answer("红包不存在或已过期")
        return

    if user.id in rp["claimed"]:
        await query.answer(f"你已经领过了：{rp['claimed'][user.id]} {rp['coin']}")
        return

    if rp["left"] <= 0:
        await query.answer("红包已被抢完")
        return

    if rp["type"] == "yzm":
        if action != rp["answer"]:
            await query.answer("❌ 验证码错误，再试一次")
            return
    elif rp["type"] == "zs":
        if user.id not in rp["allowed_users"]:
            await query.answer("❌ 这个红包不属于你")
            return

    amount = rp["amounts"].pop(0)
    rp["claimed"][user.id] = amount
    rp["left"] -= 1

    name = user.first_name or user.username or str(user.id)
    await query.answer(f"✅ 你领到了 {amount} {rp['coin']}")
    await query.message.reply_text(
        f"🎉 {name} 领到了 {amount} {rp['coin']}\n剩余红包：{rp['left']} 个"
    )

    if rp["left"] == 0:
        await query.message.reply_text(f"🧧 红包 {rp_id} 已抢完！")

# ================== 指令路由 ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "红包机器人已启动。\n"
        "支持币种：u(USDT) / cny / qq\n\n"
        "管理员指令：\n"
        "• yzmhb 金额单位 个数 —— 验证码红包\n"
        "• gkhb 金额单位 个数 —— 公开红包\n"
        "• 回复某人后发 hb 金额单位 个数 —— 专属红包\n\n"
        "示例：\n"
        "• yzmhb 100u 5\n"
        "• gkhb 100cny 5\n"
        "• hb 100qq 5（回复某人消息）"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    parts = text.split()

    if parts and parts[0].lower() == "yzmhb":
        context.args = parts[1:]
        await send_yzm(update, context)
    elif parts and parts[0].lower() == "gkhb":
        context.args = parts[1:]
        await send_gk(update, context)
    elif parts and parts[0].lower() == "hb":
        context.args = parts[1:]
        await send_zs(update, context)

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send", send_yzm))  # 兼容 /send
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler, pattern=r"^rp:"))

    print(f"🤖 红包机器人已启动，管理员：{ADMIN_IDS}")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())