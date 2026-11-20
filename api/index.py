import os
import sys
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from telethon.sessions import StringSession
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from pymongo import MongoClient

# إضافة مسار المجلد الأصلي للوصول لملف newfile.py
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import newfile

app = Flask(__name__)
CORS(app)

API_ID = int(os.getenv("API_ID", newfile.الاعدادات.API_ID))
API_HASH = os.getenv("API_HASH", newfile.الاعدادات.API_HASH)
MONGODB_URI = os.getenv("MONGODB_URI")

# ─── إدارة قاعدة البيانات ───
def get_db():
    client = MongoClient(MONGODB_URI)
    return client["telegram_bot"]

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# متغيرات مؤقتة لحفظ الجلسة أثناء التسجيل
temp_client = None
temp_phone = None
temp_hash = None

# ─── 1. التحقق من الجلسة ───
@app.route('/api/check-session', methods=['GET'])
def check_session():
    try:
        db = get_db()
        doc = db.tg_session.find_one({"_id": "main"})
        if not doc:
            return jsonify({"loggedIn": False})

        async def check():
            client = TelegramClient(StringSession(doc["sessionString"]), API_ID, API_HASH)
            await client.connect()
            auth = await client.is_user_authorized()
            name = ""
            if auth:
                me = await client.get_me()
                name = me.first_name
            await client.disconnect()
            return auth, name

        auth, name = run_async(check())
        return jsonify({"loggedIn": auth, "name": name})
    except Exception as e:
        return jsonify({"loggedIn": False, "error": str(e)})

# ─── 2. إرسال كود التحقق ───
@app.route('/api/send-code', methods=['POST'])
def send_code():
    global temp_client, temp_phone, temp_hash
    data = request.json
    phone = data.get('phone')
    
    try:
        async def start():
            global temp_client, temp_phone, temp_hash
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp_client.connect()
            sent = await temp_client.send_code_request(phone)
            temp_phone = phone
            temp_hash = sent.phone_code_hash
            return True

        run_async(start())
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ─── 3. تأكيد الكود وحفظ الجلسة ───
@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    global temp_client, temp_phone, temp_hash
    data = request.json
    code = data.get('code')
    
    if not temp_client:
        return jsonify({"success": False, "error": "لم يتم طلب كود أولاً"})

    try:
        async def verify():
            global temp_client, temp_phone, temp_hash
            try:
                await temp_client.sign_in(temp_phone, code, phone_code_hash=temp_hash)
            except SessionPasswordNeededError:
                return "need_password"
            
            session_str = temp_client.session.save()
            db = get_db()
            db.tg_session.update_one(
                {"_id": "main"},
                {"$set": {"sessionString": session_str, "phone": temp_phone}},
                upsert=True
            )
            await temp_client.disconnect()
            return "done"

        result = run_async(verify())
        if result == "need_password":
            return jsonify({"success": False, "error": "الحساب يحتاج كلمة مرور 2FA"})
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ─── دالة للحصول على عميل نشط ───
async def get_active_client():
    db = get_db()
    doc = db.tg_session.find_one({"_id": "main"})
    if not doc:
        raise Exception("يرجى تسجيل الدخول أولاً")
    client = TelegramClient(StringSession(doc["sessionString"]), API_ID, API_HASH)
    await client.connect()
    return client

# ─── 4. الاستخراج ───
@app.route('/api/extract', methods=['POST'])
def extract():
    data = request.json
    link = data.get('link')
    limit = int(data.get('limit', 50)) if data.get('limit') else None

    try:
        async def process():
            client = await get_active_client()
            كيان, خطأ = await newfile.الحصول_على_كيان(client, link)
            if not كيان:
                raise Exception(خطأ)

            users = []
            async for u in client.iter_participants(كيان, limit=limit):
                if not u.bot and not u.deleted:
                    users.append(f"{u.id}:{u.access_hash}")

            db = get_db()
            db.members.delete_many({})
            if users:
                db.members.insert_many([{"data": u} for u in users])

            await client.disconnect()
            return len(users)

        count = run_async(process())
        return jsonify({"success": True, "message": f"تم استخراج {count} عضو وحفظهم"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── 5. الإضافة ───
@app.route('/api/add', methods=['POST'])
def add_members():
    data = request.json
    link = data.get('link')
    limit = int(data.get('limit', 50))

    try:
        async def process():
            client = await get_active_client()
            كيان, خطأ = await newfile.الحصول_على_كيان(client, link)
            if not كيان:
                raise Exception(خطأ)

            db = get_db()
            members = list(db.members.find().limit(limit))
            if not members:
                raise Exception("لا يوجد أعضاء في قاعدة البيانات. قم بالاستخراج أولاً.")

            success_count = 0
            for m in members:
                try:
                    id, hash = m["data"].split(":")
                    peer = newfile.InputPeerUser(int(id), int(hash))
                    await client(newfile.InviteToChannelRequest(كيان, [peer]))
                    success_count += 1
                    await asyncio.sleep(5) # تأخير 5 ثواني
                except Exception:
                    pass
            
            await client.disconnect()
            return success_count

        count = run_async(process())
        return jsonify({"success": True, "message": f"تم إضافة {count} عضو بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# مطلوب لـ Vercel
handler = app
