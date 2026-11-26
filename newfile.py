# -*- coding: utf-8 -*-
import os, sys, csv, asyncio, random, logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

from telethon import TelegramClient, functions, events, Button
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, PeerFloodError
)
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.tl.types import InputPeerUser

# ═══════════════════════════════════════════════
# ⚙️ الإعدادات
# ═══════════════════════════════════════════════
class الاعدادات:
    API_ID = 22719912
    API_HASH = "de28bce3ac2f088204182fb17bca8b8e"
    TOKEN = "8808268157:AAEVEd2VVi0PcZF7hpggdCeV-uyoRcUGTV8"
    المدير_ID = None  # اختياري: حط ID حسابك عشان محدش يتحكم غيرك

    المجلد_الرئيسي = Path(__file__).parent
    مجلد_الجلسات = المجلد_الرئيسي / "الجلسات"
    مجلد_الاعضاء = المجلد_الرئيسي / "الاعضاء_المستخرجين"
    مجلد_الاستثناءات = المجلد_الرئيسي / "قاعدة_الاستثناءات"
    مجلد_السجلات = المجلد_الرئيسي / "السجلات"

    اقل_تأخير = 3
    اقصى_تأخير = 7
    حد_الاضافة_اليومي = 50
    حد_البحث = 50

    @classmethod
    def انشاء_المجلدات(cls):
        for m in [cls.مجلد_الجلسات, cls.مجلد_الاعضاء,
                  cls.مجلد_الاستثناءات, cls.مجلد_السجلات]:
            m.mkdir(parents=True, exist_ok=True)

الاعدادات.انشاء_المجلدات()

# ═══════════════════════════════════════════════
# 📝 السجلات
# ═══════════════════════════════════════════════
def تهيئة_السجل(اسم="البوت"):
    logger = logging.getLogger(اسم)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    f = الاعدادات.مجلد_السجلات / f"{datetime.now():%Y-%m-%d}.log"
    h = RotatingFileHandler(f, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(h)
    return logger

# ═══════════════════════════════════════════════
# 🛠️ دوال مساعدة
# ═══════════════════════════════════════════════
async def الحصول_على_كيان(عميل, رابط):
    رابط = رابط.strip()
    try:
        if "t.me/+" in رابط or "joinchat" in رابط:
            هاش = رابط.split("+")[-1].split("/")[0].split("?")[0] if "t.me/+" in رابط else رابط.split("joinchat/")[-1].split("/")[0]
            try:
                res = await عميل(ImportChatInviteRequest(هاش))
                if res.chats: return res.chats[0], None
            except Exception as e:
                if "already" in str(e).lower():
                    r = await عميل(CheckChatInviteRequest(هاش))
                    if hasattr(r, "chat") and r.chat: return r.chat, None
                return None, str(e)
        معرف = رابط.split("t.me/")[-1].split("/")[0].split("?")[0].replace("@", "")
        return await عميل.get_entity(معرف), None
    except Exception as e:
        return None, str(e)

def عدد_اعضاء_الجلسة(اسم):
    p = الاعدادات.مجلد_الاعضاء / f"{اسم}.txt"
    if not p.exists(): return 0
    return sum(1 for s in open(p, encoding="utf-8") if ":" in s)

# ═══════════════════════════════════════════════
# 💾 قاعدة البيانات
# ═══════════════════════════════════════════════
class قاعدة_البيانات:
    def __init__(self): self.سجل = تهيئة_السجل("DB")

    def مسار_الاستثناء(self, معرف):
        return الاعدادات.مجلد_الاستثناءات / f"استثناء_{معرف}.csv"

    def تحميل_المستثنيين(self, معرف):
        p = self.مسار_الاستثناء(معرف)
        if not p.exists(): return set()
        with open(p, encoding="utf-8") as f:
            return {r["معرف_العضو"] for r in csv.DictReader(f) if r.get("معرف_العضو")}

    def اضافة_استثناء(self, gid, uid, سبب, جلسة):
        p = self.مسار_الاستثناء(gid)
        with open(p, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([str(uid), سبب, جلسة, f"{datetime.now():%Y-%m-%d %H:%M:%S}"])

# ═══════════════════════════════════════════════
# 🗂️ مدير الجلسات
# ═══════════════════════════════════════════════
class مدير_الجلسات:
    def __init__(self):
        self.مجلد = الاعدادات.مجلد_الجلسات

    def عرض_الجلسات(self):
        return sorted(f.stem for f in self.مجلد.glob("*.session")
                      if not f.stem.startswith("بوت_"))

    def موجودة(self, اسم): return (self.مجلد / f"{اسم}.session").exists()
    def مسار(self, اسم): return str(self.مجلد / اسم)

    async def الحصول_على_عميل(self, اسم):
        if not self.موجودة(اسم): return None
        try:
            c = TelegramClient(self.مسار(اسم), الاعدادات.API_ID, الاعدادات.API_HASH)
            await c.connect()
            if not await c.is_user_authorized():
                await c.disconnect(); return None
            return c
        except Exception:
            return None

# ═══════════════════════════════════════════════
# 🔍 وحدات التشغيل
# ═══════════════════════════════════════════════
class وحدة_الاستخراج:
    def __init__(self): self.مدير = مدير_الجلسات()

    async def تشغيل(self, اسم, رابط, حد):
        op = await self.مدير.الحصول_على_عميل(اسم)
        if not op: return {"جديد": 0, "حالة": "فشل الاتصال"}
        try:
            كيان, _ = await الحصول_على_كيان(op, رابط)
            if not كيان: return {"جديد": 0, "حالة": "فشل الوصول"}
            اعضاء = []
            async for m in op.iter_participants(كيان, limit=حد):
                if not m.bot and not m.deleted:
                    اعضاء.append(f"{m.id}:{m.access_hash}")
            return {"جديد": self._حفظ(اسم, اعضاء), "حالة": "نجح"}
        except Exception as e:
            return {"جديد": 0, "حالة": str(e)[:50]}
        finally:
            await op.disconnect()

    def _حفظ(self, اسم, اعضاء):
        p = الاعدادات.مجلد_الاعضاء / f"{اسم}.txt"
        موجود = set()
        if p.exists():
            موجود = {l.split(":")[0] for l in open(p, encoding="utf-8") if ":" in l}
        جديد = [a for a in اعضاء if a.split(":")[0] not in موجود]
        if جديد:
            with open(p, "a", encoding="utf-8") as f:
                if p.stat().st_size: f.write("\n")
                f.write("\n".join(جديد))
        return len(جديد)

class وحدة_البحث:
    def __init__(self): self.مدير = مدير_الجلسات()

    async def تشغيل(self, اسم, كلمة, حد):
        op = await self.مدير.الحصول_على_عميل(اسم)
        if not op: return {"جديد": 0, "حالة": "فشل الاتصال"}
        try:
            p = الاعدادات.مجلد_الاعضاء / f"{اسم}.txt"
            موجود = set()
            if p.exists():
                موجود = {l.split(":")[0] for l in open(p, encoding="utf-8") if ":" in l}
            res = await op(functions.contacts.SearchRequest(q=كلمة, limit=حد))
            جديد = []
            for u in res.users:
                if not u.bot and not u.deleted and str(u.id) not in موجود:
                    جديد.append(f"{u.id}:{u.access_hash}")
            if جديد:
                with open(p, "a", encoding="utf-8") as f:
                    if p.stat().st_size: f.write("\n")
                    f.write("\n".join(جديد))
            return {"جديد": len(جديد), "حالة": "نجح"}
        except Exception as e:
            return {"جديد": 0, "حالة": str(e)[:50]}
        finally:
            await op.disconnect()

class وحدة_الاضافة:
    def __init__(self):
        self.مدير = مدير_الجلسات()
        self.قاعدة = قاعدة_البيانات()

    async def تشغيل(self, اسم, رابط, حد):
        p = الاعدادات.مجلد_الاعضاء / f"{اسم}.txt"
        if not p.exists(): return {"نجاح": 0, "فشل": 0, "محظورة": True}
        users = [l.strip() for l in open(p, encoding="utf-8") if ":" in l]
        op = await self.مدير.الحصول_على_عميل(اسم)
        if not op: return {"نجاح": 0, "فشل": 0, "محظورة": True}
        res = {"نجاح": 0, "فشل": 0, "محظورة": False}
        try:
            كيان, _ = await الحصول_على_كيان(op, رابط)
            if not كيان: return {**res, "محظورة": True}
            gid = str(getattr(كيان, "id", "0"))
            مستثنى = self.قاعدة.تحميل_المستثنيين(gid)
            for u in users:
                if res["محظورة"] or res["نجاح"] >= حد: break
                uid, h = u.split(":")
                if uid in مستثنى: continue
                try:
                    await op(InviteToChannelRequest(كيان, [InputPeerUser(int(uid), int(h))]))
                    res["نجاح"] += 1
                    self.قاعدة.اضافة_استثناء(gid, uid, "نجاح", اسم)
                    await asyncio.sleep(random.uniform(الاعدادات.اقل_تأخير, الاعدادات.اقصى_تأخير))
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds + 5)
                except PeerFloodError:
                    res["محظورة"] = True; break
                except Exception as e:
                    res["فشل"] += 1
                    self.قاعدة.اضافة_استثناء(gid, uid, str(e)[:20], اسم)
        finally:
            await op.disconnect()
        return res

# ═══════════════════════════════════════════════
# 🤖 البوت
# ═══════════════════════════════════════════════
class بوت_التليجرام:
    def __init__(self):
        self.مدير = مدير_الجلسات()
        self.استخراج = وحدة_الاستخراج()
        self.بحث = وحدة_البحث()
        self.اضافة = وحدة_الاضافة()
        self.حالات = {}
        self.بوت = None

    async def تشغيل(self):
        self.بوت = TelegramClient("بوت_الادارة", الاعدادات.API_ID, الاعدادات.API_HASH)
        await self.بوت.start(bot_token=الاعدادات.TOKEN)
        print("✅ البوت يعمل!")
        self._تسجيل()
        await self.بوت.run_until_disconnected()

    def _مسموح(self, uid):
        return الاعدادات.المدير_ID is None or uid == الاعدادات.المدير_ID

    def _ازرار_رئيسية(self):
        return [
            [Button.inline("👤 تسجيل حساب", b"new_acc"), Button.inline("📋 الجلسات", b"sessions")],
            [Button.inline("🔗 استخراج", b"extract"), Button.inline("🔎 بحث", b"search")],
            [Button.inline("➕ إضافة أعضاء", b"add"), Button.inline("📊 إحصائيات", b"stats")],
        ]

    def _تسجيل(self):
        @self.بوت.on(events.NewMessage(pattern=r'^/start$'))
        async def start(ev):
            if not self._مسموح(ev.sender_id): return
            await ev.respond("🚀 **بوت إدارة الحسابات**\nاختر:", buttons=self._ازرار_رئيسية())

        @self.بوت.on(events.CallbackQuery())
        async def cb(ev):
            if not self._مسموح(ev.sender_id): return await ev.answer("غير مصرح", alert=True)
            await self._معالجة_ازرار(ev)

        @self.بوت.on(events.NewMessage(func=lambda e: e.is_private and not e.raw_text.startswith('/')))
        async def msg(ev):
            if not self._مسموح(ev.sender_id): return
            await self._معالجة_رسائل(ev)

    async def _معالجة_ازرار(self, ev):
        d = ev.data.decode()
        await ev.answer()
        uid = ev.sender_id
        if d == "main":
            await ev.edit("🚀 **القائمة الرئيسية**", buttons=self._ازرار_رئيسية())
        elif d == "sessions":
            js = self.مدير.عرض_الجلسات()
            if not js:
                return await ev.edit("❌ لا توجد جلسات", buttons=[[Button.inline("🔙 رجوع", b"main")]])
            az = [[Button.inline(f"📱 {j}", f"sess_{j}".encode())] for j in js]
            az.append([Button.inline("🔙 رجوع", b"main")])
            await ev.edit("📋 **جلساتك:**", buttons=az)
        elif d.startswith("sess_"):
            اسم = d[5:]
            info = f"📱 `{اسم}`\n👥 الأعضاء المستخرجون: {عدد_اعضاء_الجلسة(اسم)}"
            await ev.edit(info, buttons=[[Button.inline("🔙 رجوع", b"sessions")]])
        elif d == "new_acc":
            self.حالات[uid] = "wait_phone"
            await ev.edit("📱 أرسل رقم الهاتف (مثال: 201012345678):",
                          buttons=[[Button.inline("❌ إلغاء", b"main")]])
        elif d == "extract":
            self.حالات[uid] = "wait_extract_link"
            await ev.edit("🔗 أرسل رابط المجموعة:",
                          buttons=[[Button.inline("❌ إلغاء", b"main")]])
        elif d == "search":
            self.حالات[uid] = "wait_search_word"
            await ev.edit("🔎 أرسل الكلمة:",
                          buttons=[[Button.inline("❌ إلغاء", b"main")]])
        elif d == "add":
            self.حالات[uid] = "wait_add_link"
            await ev.edit("➕ أرسل رابط المجموعة الهدف:",
                          buttons=[[Button.inline("❌ إلغاء", b"main")]])
        elif d == "stats":
            js = self.مدير.عرض_الجلسات()
            txt = f"📊 **الإحصائيات**\nعدد الجلسات: {len(js)}\n\n"
            for j in js:
                txt += f"- `{j}`: {عدد_اعضاء_الجلسة(j)} عضو\n"
            await ev.edit(txt, buttons=[[Button.inline("🔙 رجوع", b"main")]])

    async def _معالجة_رسائل(self, ev):
        uid = ev.sender_id
        st = self.حالات.get(uid)
        if not st:
            return await ev.respond("استخدم /start")

        # تسجيل حساب جديد
        if st == "wait_phone":
            رقم = ''.join(filter(str.isdigit, ev.raw_text))
            if len(رقم) < 10: return await ev.respond("❌ رقم غير صحيح")
            await ev.respond("⏳ جاري إرسال الكود...")
            try:
                c = TelegramClient(self.مدير.مسار(رقم), الاعدادات.API_ID, الاعدادات.API_HASH)
                await c.connect()
                sent = await c.send_code_request(f"+{رقم}")
                self.حالات[uid] = {"step": "wait_code", "phone": f"+{رقم}",
                                   "client": c, "hash": sent.phone_code_hash}
                await ev.respond("🔢 أرسل كود التحقق:")
            except Exception as e:
                self.حالات[uid] = None
                await ev.respond(f"❌ خطأ: {e}")
        elif isinstance(st, dict) and st.get("step") == "wait_code":
            try:
                await st["client"].sign_in(st["phone"], ev.raw_text, phone_code_hash=st["hash"])
                me = await st["client"].get_me()
                await ev.respond(f"✅ تم التسجيل!\nID: {me.id}",
                                 buttons=[[Button.inline("🔙 القائمة", b"main")]])
                await st["client"].disconnect()
                self.حالات[uid] = None
            except SessionPasswordNeededError:
                st["step"] = "wait_2fa"
                await ev.respond("🔐 الحساب محمي بكلمة مرور (2FA)، أرسلها:")
            except Exception as e:
                self.حالات[uid] = None
                await ev.respond(f"❌ خطأ: {e}")
        elif isinstance(st, dict) and st.get("step") == "wait_2fa":
            try:
                await st["client"].sign_in(password=ev.raw_text)
                me = await st["client"].get_me()
                await ev.respond(f"✅ تم التسجيل!\nID: {me.id}",
                                 buttons=[[Button.inline("🔙 القائمة", b"main")]])
                await st["client"].disconnect()
                self.حالات[uid] = None
            except Exception as e:
                self.حالات[uid] = None
                await ev.respond(f"❌ خطأ: {e}")
        # استخراج
        elif st == "wait_extract_link":
            self.حالات[uid] = None
            js = self.مدير.عرض_الجلسات()
            if not js: return await ev.respond("❌ لا توجد جلسات")
            m = await ev.respond("⏳ جاري الاستخراج...")
            total = 0
            for j in js:
                r = await self.استخراج.تشغيل(j, ev.raw_text, None)
                total += r["جديد"]
            await m.edit(f"✅ تم! إجمالي الجديد: {total}",
                         buttons=[[Button.inline("🔙 القائمة", b"main")]])
        # بحث
        elif st == "wait_search_word":
            self.حالات[uid] = None
            js = self.مدير.عرض_الجلسات()
            if not js: return await ev.respond("❌ لا توجد جلسات")
            m = await ev.respond("⏳ جاري البحث...")
            total = 0
            for j in js:
                r = await self.بحث.تشغيل(j, ev.raw_text, الاعدادات.حد_البحث)
                total += r["جديد"]
            await m.edit(f"✅ تم! إجمالي الجديد: {total}",
                         buttons=[[Button.inline("🔙 القائمة", b"main")]])
        # إضافة
        elif st == "wait_add_link":
            self.حالات[uid] = None
            js = self.مدير.عرض_الجلسات()
            if not js: return await ev.respond("❌ لا توجد جلسات")
            m = await ev.respond("⏳ جاري الإضافة...")
            total = 0
            for j in js:
                r = await self.اضافة.تشغيل(j, ev.raw_text, الاعدادات.حد_الاضافة_اليومي)
                total += r["نجاح"]
            await m.edit(f"✅ تم! إجمالي النجاح: {total}",
                         buttons=[[Button.inline("🔙 القائمة", b"main")]])

# ═══════════════════════════════════════════════
# 🚀 التشغيل
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    asyncio.run(بوت_التليجرام().تشغيل())
