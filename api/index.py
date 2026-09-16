import os
from fastapi import FastAPI, Request, Response
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

LAST_ERROR = "No errors yet"

@app.post("/api/webhook")
async def webhook(request: Request):
    global LAST_ERROR
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        LAST_ERROR = err
        print("WEBHOOK ERROR:", err)
        return Response(content="Error", status_code=500)

@app.get("/api/lasterror")
async def get_last_error():
    global LAST_ERROR
    return {"error": LAST_ERROR}

@app.get("/")
async def root():
    return {"message": "Bot is running on Vercel!"}
