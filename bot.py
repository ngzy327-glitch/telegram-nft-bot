import asyncio
import os
import random
import string
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)

logging.basicConfig(level=logging.INFO)

# ========== 环境变量 ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# 多个管理员用逗号分隔
ADMIN_IDS_STR = os.environ.get("ADMIN_ID", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]
# =============================

if not BOT_TOKEN or not ADMIN_IDS:
    print("❌ 缺少 BOT_TOKEN 或 ADMIN_ID")
    exit(1)

REDPACKETS = {}
RP_COUNTER = [0]

def gen_code(length=4):
    return ''.join(random.choices(string.ascii_letters, k=length))

def gen_fake_codes(correct, count):
    codes = {correct}
    while len(codes) < count:
        codes.add(gen_code(len(correct)))
    return list(codes)

def make_amounts(total, count):
    """拼手气金额分配"""
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

def parse_amount_count(context):
    """解析 /send 类指令的金额和个数"""
    try:
        total = float(context.args[0])
        count = int(context.args[1])
        if total <= 0 or count <= 0:
            raise ValueError
        return total, count
    except (IndexError, ValueError):
        return None, None

# ================== 三种发红包方式 ==================

async def send_yzm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """验证码红包：yzmhb 金额 个数"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ 只有管理员可以发红包。")
        return
    total, count = parse_amount_count(context)
    if total is None:
        await update.message.reply_text("格式：yzmhb 金额 个数\n例如：yzmhb 10 5")
        return

    amounts = make_amounts(total, count)
    answer = gen_code(4)
    fake_codes = gen_fake_codes(answer, random.randint(4, 8))
    random.shuffle(fake_codes)

    RP_COUNTER[0] += 1
    rp_id = RP_COUNTER[0]
    REDPACKETS[rp_id] = {
        "type": "yzm",
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
        f"总金额：{total} USDT\n"
        f"红包个数：{count}\n"
        f"请选择正确的验证码 <b>{answer}</b> 领取红包",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def send_gk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """公开红包：gkhb 金额 个数（无需验证码）"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ 只有管理员可以发红包。")
        return
    total, count = parse_amount_count(context)
    if total is None:
        await update.message.reply_text("格式：gkhb 金额 个数\n例如：gkhb 10 5")
        return

    amounts = make_amounts(total, count)
    RP_COUNTER[0] += 1
    rp_id = RP_COUNTER[0]
    REDPACKETS[rp_id] = {
        "type": "gk",
        "total": total, "left": count,
        "amounts": amounts, "claimed": {},
    }

    keyboard = [[InlineKeyboardButton("领取红包🧧", callback_data=f"rp:{rp_id}:claim")]]

    await update.message.reply_text(
        f"🧧 公开红包\n"
        f"总金额：{total} USDT\n"
        f"红包个数：{count}\n"
        f"点击下方按钮领取",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_zs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """专属红包：回复某人的消息，发送 hb 金额 个数"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ 只有管理员可以发红包。")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("请先回复你要发红包的对象，再发送：hb 金额 个数")
        return
    target = update.message.reply_to_message.from_user
    if not target:
        await update.message.reply_text("无法识别目标用户。")
        return

    total, count = parse_amount_count(context)
    if total is None:
        await update.message.reply_text("格式：hb 金额 个数（需要回复某人的消息）")
        return

    amounts = make_amounts(total, count)
    RP_COUNTER[0] += 1
    rp_id = RP_COUNTER[0]
    REDPACKETS[rp_id] = {
        "type": "zs",
        "total": total, "left": count,
        "amounts": amounts, "claimed": {},
        "allowed_users": [target.id, update.effective_user.id],
    }

    keyboard = [[InlineKeyboardButton("领取红包🧧", callback_data=f"rp:{rp_id}:claim")]]

    await update.message.reply_text(
        f"🧧 专属红包\n"
        f"指定用户：{target.first_name or target.username or target.id}\n"
        f"总金额：{total} USDT\n"
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
        await query.answer(f"你已经领过了：{rp['claimed'][user.id]} USDT")
        return

    if rp["left"] <= 0:
        await query.answer("红包已被抢完")
        return

    # 根据红包类型做验证
    if rp["type"] == "yzm":
        if action != rp["answer"]:
            await query.answer("❌ 验证码错误，再试一次")
            return
    elif rp["type"] == "zs":
        if user.id not in rp["allowed_users"]:
            await query.answer("❌ 这个红包不属于你")
            return
    # gk 类型无需验证

    # 发放
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

# ================== 指令路由 ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "红包机器人已启动。\n"
        "管理员指令：\n"
        "• /send 金额 个数 —— 验证码红包\n"
        "• yzmhb 金额 个数 —— 验证码红包\n"
        "• gkhb 金额 个数 —— 公开红包（无需验证码）\n"
        "• 回复某人后发 hb 金额 个数 —— 专属红包"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理不带 / 的指令"""
    text = (update.message.text or "").strip()

    # 去掉可能的参数拆分
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
    app.add_handler(CommandHandler("send", send_yzm))   # /send 保持兼容
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