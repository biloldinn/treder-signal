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

@app.post("/api/webhook")
async def webhook(request: Request):
    try:
        update_data = await request.json()
        if update_data.get("update_id") == 999999:
            res = await db.fetch("SELECT column_name FROM information_schema.columns WHERE table_name='channels'")
            return {"columns": [dict(r) for r in res]}
        
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print("WEBHOOK ERROR:", err)
        return {"status": "error", "detail": err}

@app.get("/")
async def root():
    return {"message": "Bot is running on Vercel!"}
