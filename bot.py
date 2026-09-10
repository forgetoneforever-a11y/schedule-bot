python
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os

Данные из переменных окружения Render
TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler()

reminders = []

class ReminderItem(BaseModel):
    date: str
    time: str
    text: str
    chat_id: int = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID else 0

===== Главное меню =====
def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏰ Добавить напоминание")],
            [KeyboardButton(text="📋 Список напоминаний"),
             KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True
    )

def countdown_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 мин", callback_data="cd_1")],
        [InlineKeyboardButton(text="5 мин", callback_data="cd_5")],
        [InlineKeyboardButton(text="30 мин", callback_data="cd_30")],
        [InlineKeyboardButton(text="1 час", callback_data="cd_60")],
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет! Твой Chat ID: {message.chat.id}.\n"
        f"Если он отличается от ADMIN_CHAT_ID — обнови на Render.\n\n"
        "Выбери действие ниже 👇",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )

===== Reply-кнопки =====
@dp.message(F.text == "⏰ Добавить напоминание")
async def add_reminder_prompt(msg: types.Message):
    await msg.answer(
        "Пример: 2026-09-10 19:00 Текст напоминания\n"
        "Или выбери таймер ниже 👇",
        reply_markup=countdown_kb()
    )

@dp.message(F.text == "📋 Список напоминаний")
async def show_list(msg: types.Message):
    if not reminders:
        await msg.answer("Напоминаний пока нет.")
        return
    text = "\n".join(f"{i+1}. {r['date']} {r['time']} — {r['text']}" for i, r in enumerate(reminders))
    await msg.answer(f"📋 Твои напоминания:\n\n{text}")

@dp.message(F.text == "❓ Помощь")
async def show_help(msg: types.Message):
    await msg.answer(
        "⏰ Добавить напоминание — дата/время/текст или таймер.\n"
        "📋 Список напоминаний — все активные.\n"
        "Формат: ГГГГ-ММ-ДД ЧЧ:ММ текст (например: 2026-09-10 19:00 Позвонить маме)"
    )

===== Приём даты от пользователя =====
@dp.message(F.text)
async def parse_reminder(msg: types.Message):
    parts = msg.text.split()
    if len(parts) >= 3:
        try:
            date_str, time_str = parts[0], parts[1]
text = " ".join(parts[2:])
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            job_id = f"{msg.chat.id}_{date_str}_{time_str}"
            scheduler.add_job(
                send_reminder_task,
                'date',
                run_date=dt,
                args=[msg.chat.id, text],
                id=job_id,
                replace_existing=True
            )
            reminders.append({"date": date_str, "time": time_str, "text": text, "chat_id": msg.chat.id})
            await msg.answer(f"✅ Напоминание на {dt.strftime('%d.%m %H:%M')}: {text}")
        except ValueError:
            await msg.answer("Формат неправильный: ГГГГ-ММ-ДД ЧЧ:ММ текст")

===== Inline-кнопки (таймер) =====
@dp.callback_query(lambda c: c.data and c.data.startswith("cd"))
async def set_timer(cb: types.CallbackQuery):
    minutes = int(cb.data.split("_")[1])
    dt = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=minutes)
    job_id = f"{cb.from_user.id}_{minutes}min"
    scheduler.add_job(
        send_reminder_task,
        'date',
        run_date=dt,
        args=[cb.from_user.id, f"Таймер {minutes} мин истек"],
        id=job_id,
        replace_existing=True
    )
    await cb.answer()
    await cb.message.answer(f"Таймер на {minutes} мин! Сработает в {dt.strftime('%H:%M')}")

===== Отправка =====
async def send_reminder_task(chat_id, text):
    try:
        await bot.send_message(chat_id, f"⏰ Будильник / Заметка!\n\n{text}")
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")

===== FastAPI =====
@app.post("/api/add_reminder")
async def api_add_reminder(item: ReminderItem):
    reminders.append(item.dict())
    dt = datetime.strptime(f"{item.date} {item.time}", "%Y-%m-%d %H:%M")
    job_id = f"{item.date}_{item.time}_{item.text}"
    scheduler.add_job(
        send_reminder_task,
        'date',
        run_date=dt,
        args=[item.chat_id, item.text],
        id=job_id,
        replace_existing=True
    )
    return {"status": "success", "message": "Напоминание добавлено!"}

===== Запуск =====
async def main():
    scheduler.start()
    port = int(os.environ.get("PORT", 10000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(
        dp.start_polling(bot),
        server.serve()
    )

if name == "main":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
