import time
import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

TOKEN = "YOUR_BOT_TOKEN_HERE"
URL = "https://testcisia.it/calendario.php?tolc=cents&l=gb&lingua=inglese"

users = []
old_slots = []


async def fetch_page():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        try:
            await page.goto(URL, timeout=30000, wait_until="networkidle")
            await page.wait_for_selector("tr", timeout=15000)
            await asyncio.sleep(2)
            res = await page.content()
            # print(len(res))
            return res
        except Exception as e:
            print("Error:", e)
            return None
        finally:
            await b.close()


async def check(bot, hourly=False):
    global old_slots

    if len(users) == 0:
        return

    html = await fetch_page()
    if not html:
        if hourly:
            for u in users:
                try:
                    await bot.send_message(u, "⚠️ وضعیت ربات: فعال\nخطا در دریافت اطلاعات از سایت چیزیا در بررسی اخیر.")
                except:
                    pass
        return

    soup = BeautifulSoup(html, "html.parser")
    found_texts = []
    new_slots = []

    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue

        mode = tds[0].text.strip().upper()
        if not mode or "FORMAT" in mode:
            continue

        uni = tds[1].text.strip()
        city = tds[3].text.strip()
        seats = tds[5].text.strip()
        status = tds[6].text.strip().upper()
        date = tds[7].text.strip()

        # حواسمون باشه NOT AVAILABLE رو نگیره
        if "AVAILABLE" in status and "NOT" not in status:
            slot_id = f"{uni}_{city}_{mode}_{date}"
            new_slots.append(slot_id)

            txt = f"🏛 *{uni}* ({mode})\n   شهر: {city} | ظرفیت: {seats} | تاریخ: {date}"
            found_texts.append(txt)

            if slot_id not in old_slots:
                old_slots.append(slot_id)
                print(datetime.now().strftime("%H:%M:%S"), "NEW:", slot_id)

                alert = f"🚨 *ظرفیت جدید باز شد*\n\n{txt}"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("ورود به سایت چیزیا", url=URL)]])

                for u in users:
                    try:
                        await bot.send_message(u, alert, parse_mode="Markdown", reply_markup=kb)
                    except Exception as err:
                        print("Send err:", err)

    old_slots = new_slots
    print(datetime.now().strftime("%H:%M:%S"), f"Done -> open: {len(found_texts)}")

    if hourly:
        report = "🟢 *گزارش ساعتی وضعیت ظرفیت‌ها:*\n\n"
        if len(found_texts) > 0:
            report += "\n\n".join(found_texts)
        else:
            report += "در حال حاضر ظرفیت بازی ثبت نشده است."

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏹ توقف مانیتورینگ", callback_data="stop")]])
        for u in users:
            try:
                await bot.send_message(u, report, parse_mode="Markdown", reply_markup=kb)
            except:
                pass


async def loop_task(app):
    last_report = time.time()
    while True:
        if len(users) == 0:
            await asyncio.sleep(3)
            continue

        await asyncio.sleep(random.randint(30, 40))

        if len(users) == 0:
            continue

        is_hour = False
        if time.time() - last_report >= 3600:
            is_hour = True
            last_report = time.time()

        try:
            await check(app.bot, hourly=is_hour)
        except Exception as e:
            print("Loop error:", e)


async def start(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in users:
        users.append(chat_id)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏹ توقف مانیتورینگ", callback_data="stop")]])
    await update.message.reply_text(
        "مانیتورینگ چیزیا فعال شد.\n"
        "به محض باز شدن ظرفیت جدید اطلاع‌رسانی می‌شود و هر ۱ ساعت گزارش وضعیت ارسال خواهد شد.",
        reply_markup=kb
    )
    await check(context.bot, hourly=True)


async def btn_click(update, context):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id

    if q.data == "stop":
        if chat_id in users:
            users.remove(chat_id)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ شروع مجدد", callback_data="start")]])
        await q.message.edit_text("مانیتورینگ متوقف شد.", reply_markup=kb)

    elif q.data == "start":
        if chat_id not in users:
            users.append(chat_id)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏹ توقف مانیتورینگ", callback_data="stop")]])
        await q.message.edit_text("مانیتورینگ مجدداً فعال شد.", reply_markup=kb)
        await check(context.bot, hourly=True)


async def init_bot(app):
    asyncio.create_task(loop_task(app))


app = ApplicationBuilder().token(TOKEN).post_init(init_bot).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(btn_click))

print("Starting bot...")
app.run_polling()
