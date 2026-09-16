import asyncpg
from datetime import datetime

DB_URL = "postgresql://neondb_owner:npg_xBvT6NX2ZDgi@ep-lively-sun-b4if6h55-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require"

async def get_conn():
    return await asyncpg.connect(DB_URL)

async def execute(query, *args):
    conn = await get_conn()
    try: return await conn.execute(query, *args)
    finally: await conn.close()

async def fetch(query, *args):
    conn = await get_conn()
    try: return await conn.fetch(query, *args)
    finally: await conn.close()

async def fetchrow(query, *args):
    conn = await get_conn()
    try: return await conn.fetchrow(query, *args)
    finally: await conn.close()

async def fetchval(query, *args):
    conn = await get_conn()
    try: return await conn.fetchval(query, *args)
    finally: await conn.close()


async def db_init():
    conn = await get_conn()
    try:
        await conn.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY, username TEXT, full_name TEXT)''')
        await conn.execute('''CREATE TABLE IF NOT EXISTS channels (
            channel_id BIGINT PRIMARY KEY, title TEXT, owner_id BIGINT, added_at TEXT)''')
        try:
            await conn.execute("ALTER TABLE channels ADD COLUMN auto_approve INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await conn.execute("ALTER TABLE states ADD COLUMN link TEXT")
        except Exception:
            pass
        await conn.execute('''CREATE TABLE IF NOT EXISTS ads (
            channel_id BIGINT PRIMARY KEY, photo_id TEXT, text TEXT, button_text TEXT, link TEXT, is_active INTEGER)''')
        await conn.execute('''CREATE TABLE IF NOT EXISTS stats (
            id SERIAL PRIMARY KEY, user_id BIGINT, channel_id BIGINT, action TEXT, timestamp TEXT)''')
        await conn.execute('''CREATE TABLE IF NOT EXISTS states (
            user_id BIGINT PRIMARY KEY, step TEXT, channel_id BIGINT, photo_id TEXT, text TEXT, button_text TEXT, link TEXT)''')
    finally:
        await conn.close()

async def db_add_user(uid, uname, fname):
    await execute("INSERT INTO users VALUES ($1,$2,$3,$4) ON CONFLICT(user_id) DO NOTHING",
                  uid, uname or "", fname or "", datetime.now().isoformat())

async def db_all_users():
    r = await fetch("SELECT user_id FROM users")
    return [x["user_id"] for x in r]

async def db_users_count():
    res = await fetchval("SELECT COUNT(*) FROM users")
    return res or 0

async def db_add_channel(ch_id, title, owner_id=0):
    await execute("""INSERT INTO channels (channel_id,title,owner_id,added_at) VALUES ($1,$2,$3,$4)
        ON CONFLICT(channel_id) DO UPDATE SET title=EXCLUDED.title, owner_id=EXCLUDED.owner_id""",
                  ch_id, title or str(ch_id), owner_id, datetime.now().isoformat())

async def db_get_channels_by_owner(owner_id):
    r = await fetch("SELECT channel_id,title,owner_id FROM channels WHERE owner_id=$1", owner_id)
    return [dict(x) for x in r]

async def db_get_all_channels():
    r = await fetch("SELECT channel_id,title,owner_id FROM channels")
    return [dict(x) for x in r]

async def db_get_channel(ch_id):
    r = await fetchrow("SELECT * FROM channels WHERE channel_id=$1", ch_id)
    return dict(r) if r else None

async def db_del_channel(ch_id):
    await execute("DELETE FROM channels WHERE channel_id=$1", ch_id)

async def db_set_ad(ch_id, text, link, btn_text, photo_id):
    await execute("""INSERT INTO ads (channel_id,text,link,button_text,photo_id,is_active,created_at)
        VALUES ($1,$2,$3,$4,$5,1,$6) ON CONFLICT(channel_id) DO UPDATE SET
        text=EXCLUDED.text, link=EXCLUDED.link, button_text=EXCLUDED.button_text,
        photo_id=EXCLUDED.photo_id, is_active=1, created_at=EXCLUDED.created_at""",
                  ch_id, text, link, btn_text, photo_id, datetime.now().isoformat())

async def db_get_ad(ch_id):
    r = await fetchrow("SELECT text,link,button_text,photo_id,is_active FROM ads WHERE channel_id=$1", ch_id)
    return dict(r) if r else None

async def db_toggle_ad(ch_id, active):
    await execute("UPDATE ads SET is_active=$1 WHERE channel_id=$2", 1 if active else 0, ch_id)

async def db_delete_ad(ch_id):
    await execute("DELETE FROM ads WHERE channel_id=$1", ch_id)

async def db_log_stat(uid, ch_id, action):
    await execute("INSERT INTO stats (user_id,channel_id,action,created_at) VALUES ($1,$2,$3,$4)",
                  uid, ch_id, action, datetime.now().isoformat())

async def db_stats_by_channel(ch_id):
    res = await fetchval("SELECT COUNT(*) FROM stats WHERE channel_id=$1 AND action='message_sent'", ch_id)
    return res or 0

async def db_total_sent():
    res = await fetchval("SELECT COUNT(*) FROM stats WHERE action='message_sent'")
    return res or 0

async def db_toggle_auto_approve(ch_id, active):
    await execute("UPDATE channels SET auto_approve=$1 WHERE channel_id=$2", 1 if active else 0, ch_id)

async def db_get_state(user_id):
    res = await fetchrow("SELECT * FROM states WHERE user_id=$1", user_id)
    return dict(res) if res else None

async def db_set_state(user_id, step, channel_id, photo_id=None, text=None, button_text=None, link=None):
    await execute("""
        INSERT INTO states (user_id, step, channel_id, photo_id, text, button_text, link) 
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (user_id) DO UPDATE SET 
        step=$2, channel_id=$3, photo_id=COALESCE($4, states.photo_id), text=COALESCE($5, states.text), button_text=COALESCE($6, states.button_text), link=COALESCE($7, states.link)
    """, user_id, step, channel_id, photo_id, text, button_text, link)

async def db_clear_state(user_id):
    await execute("DELETE FROM states WHERE user_id=$1", user_id)



