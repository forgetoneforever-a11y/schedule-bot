import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os

# Получаем данные из переменных окружения Render
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

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет! Твой Chat ID: `{message.chat.id}`.\n"
        "Вставь его в переменную ADMIN_CHAT_ID на Render, если он отличается!",
        parse_mode="Markdown"
    )

@app.post("/api/add_reminder")
async def add_reminder(item: ReminderItem):
    reminders.append(item.dict())
    job_id = f"{item.date}_{item.time}_{item.text}"
    dt = datetime.strptime(f"{item.date} {item.time}", "%Y-%m-%d %H:%M")
    
    scheduler.add_job(
        send_reminder_task,
        'date',
        run_date=dt,
        args=[item.chat_id, item.text],
        id=job_id,
        replace_existing=True
    )
    return {"status": "success", "message": "Напоминание добавлено!"}

async def send_reminder_task(chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, f"⏰ **Будильник / Заметка!**\n\n{text}", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")

async def main():
    scheduler.start()
    port = int(os.environ.get("PORT", 10000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        dp.start_polling(bot),
        server.serve()
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
