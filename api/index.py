import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import asyncio

import db
from bot import router

# Token in code or env
BOT_TOKEN_ENV = os.getenv("BOT_TOKEN", "8978385446:AAFA8yY_bbnehKBJDEDav_a1ctb2GBPZvpI")
WEBHOOK_URL = "https://treder-signal.vercel.app/api/webhook"

bot = Bot(token=BOT_TOKEN_ENV, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(router)

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await db.db_init()
    # Super adminlarga xabar yuborish
    try:
        from bot import SUPER_ADMINS
        for admin in SUPER_ADMINS:
            try:
                await bot.send_message(admin, "♻️ Bot yangilandi va ishga tushdi (Yoki server uyg'ondi)!")
            except Exception:
                pass
    except Exception:
        pass

@app.post("/api/webhook")
async def webhook(request: Request):
    update_data = await request.json()
    update = types.Update(**update_data)
    # Feed update to aiogram
    await dp.feed_update(bot, update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Bot is running on Vercel!"}
