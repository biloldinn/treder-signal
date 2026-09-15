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
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "YOUR_VERCEL_URL/api/webhook") # Replace with vercel URL later

bot = Bot(token=BOT_TOKEN_ENV, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(router)

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await db.db_init()
    # Webhook requires setting the URL. In Vercel, it's better to do this manually via browser once:
    # https://api.telegram.org/bot<TOKEN>/setWebhook?url=<URL>
    # But we can try setting it on startup if WEBHOOK_URL is configured
    try:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    except Exception as e:
        print("Failed to set webhook:", e)

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
