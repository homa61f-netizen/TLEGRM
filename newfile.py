# -*- coding: utf-8 -*-
import os
import sys
import csv
import json
import asyncio
import random
import shutil
import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

from colorama import init, Fore, Style
from telethon import TelegramClient, functions, events, Button
from telethon.errors import (
    PeerFloodError, FloodWaitError, UserPrivacyRestrictedError,
    SessionPasswordNeededError, PhoneNumberInvalidError,
    PhoneCodeInvalidError, PhoneCodeExpiredError,
    UserNotMutualContactError, UserChannelsTooMuchError,
    UserAlreadyParticipantError, UserKickedError, ChatAdminRequiredError
)
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import (
    ImportChatInviteRequest, CheckChatInviteRequest
)
from telethon.tl.types import InputPeerUser

init(autoreset=True)

# ═══════════════════════════════════════════════════════════════
# ⚙️  قسم الإعدادات
# ═══════════════════════════════════════════════════════════════

class الاعدادات:
    API_ID = 22719912
    API_HASH = "de28bce3ac2f088204182fb17bca8b8e"
    TOKEN = "8967610616:AAFYTwMV6u1VlnOpMdpRwYMfiK7i112VU5g"
    
    المجلد_الرئيسي = Path(__file__).parent
    مجلد_الجلسات = المجلد_الرئيسي / "الجلسات"
    مجلد_الاعضاء = المجلد_الرئيسي / "الاعضاء_المستخرجين"
    مجلد_الاستثناءات = المجلد_الرئيسي / "قاعدة_الاستثناءات"
    مجلد_الاهداف = المجلد_الرئيسي / "الاهداف"
    مجلد_السجلات = المجلد_الرئيسي / "السجلات"
    مجلد_النسخ_الاحتياطية = المجلد_الرئيسي / "النسخ_الاحتياطية"
    
    اقل_تأخير = 3
    اقصى_تأخير = 7
    حد_الاضافة_اليومي = 50
    حد_البحث = 50
    هامش_الامان = 10
    
    حروف_عربية = "ابتثجحخدذرزسشصضطظعغفقكلمنهويىءآأؤإئ"
    ارقام_عربية = "٠١٢٣٤٥٦٧٨٩"
    حروف_انجليزية = "abcdefghijklmnopqrstuvwxyz"
    حروف_انجليزية_كبيرة = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ارقام_انجليزية = "0123456789"
    
    @classmethod
    def انشاء_المجلدات(cls):
        for مجلد in [cls.مجلد_الجلسات, cls.مجلد_الاعضاء,
                     cls.مجلد_الاستثناءات, cls.مجلد_الاهداف,
                     cls.مجلد_السجلات, cls.مجلد_النسخ_الاحتياطية]:
            مجلد.mkdir(parents=True, exist_ok=True)

class الالوان:
    اساسي = Fore.CYAN
    نجاح = Fore.GREEN
    خطأ = Fore.RED
    تحذير = Fore.YELLOW
    معلومة = Fore.BLUE
    تصفير = Style.RESET_ALL

# ═══════════════════════════════════════════════════════════════
# 📝  السجلات والدوال المساعدة
# ═══════════════════════════════════════════════════════════════

def تهيئة_السجل(اسم="البوت"):
    logger = logging.getLogger(اسم)
    if logger.handlers: return logger
    logger.setLevel(logging.INFO)
    تاريخ_اليوم = datetime.now().strftime("%Y-%m-%d")
    ملف_السجل = الاعدادات.مجلد_السجلات / f"{تاريخ_اليوم}.log"
    معالج_الملف = RotatingFileHandler(ملف_السجل, maxBytes=10*1024*1024, backupCount=10, encoding="utf-8")
    معالج_الملف.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(معالج_الملف)
    return logger

def استخراج_معرف_من_رابط(رابط):
    رابط = رابط.strip()
    if "t.me/+" in رابط: return رابط.split("t.me/+")[-1].split("/")[0].split("?")[0], "خاص"
    if "t.me/joinchat/" in رابط: return رابط.split("t.me/joinchat/")[-1].split("/")[0].split("?")[0], "خاص"
    if "t.me/" in رابط: return رابط.split("t.me/")[-1].split("/")[0].split("?")[0], "عام"
    if رابط.startswith("@"): return رابط[1:], "عام"
    return رابط, "عام"

async def الحصول_على_كيان(عميل, رابط):
    رابط = رابط.strip()
    if "t.me/+" in رابط or "joinchat" in رابط:
        هاش = رابط.split("+")[-1].split("/")[0].split("?")[0] if "t.me/+" in رابط else رابط.split("joinchat/")[-1].split("/")[0]
        try:
            نتيجة = await عميل(ImportChatInviteRequest(هاش))
            if نتيجة.chats: return نتيجة.chats[0], None
        except Exception as خطأ:
            if "already" in str(خطأ).lower():
                try:
                    نتيجة = await عميل(CheckChatInviteRequest(هاش))
                    if hasattr(نتيجة, "chat") and نتيجة.chat: return نتيجة.chat, None
                except Exception: pass
            return None, str(خطأ)
    
    معرف = رابط.split("t.me/")[-1].split("/")[0].split("?")[0].replace("@", "")
    try:
        return await عميل.get_entity(معرف), None
    except Exception as خطأ:
        return None, str(خطأ)

def عدد_اعضاء_الجلسة(اسم_الجلسة):
    مسار = الاعدادات.مجلد_الاعضاء / f"{اسم_الجلسة}.txt"
    if not مسار.exists(): return 0
    with open(مسار, "r", encoding="utf-8") as م:
        return sum(1 for سطر in م if ":" in سطر)

# ═══════════════════════════════════════════════════════════════
# 💾  قاعدة البيانات وإدارة الجلسات
# ═══════════════════════════════════════════════════════════════

class قاعدة_البيانات:
    def __init__(self): self.سجل = تهيئة_السجل("قاعدة_البيانات")
    def مسار_الاستثناء(self, معرف): return الاعدادات.مجلد_الاستثناءات / f"استثناء_{معرف}.csv"
    
    def تحميل_المستثنيين(self, معرف):
        مسار = self.مسار_الاستثناء(معرف)
        مستثنيين = set()
        if not مسار.exists(): return مستثنيين
        with open(مسار, "r", encoding="utf-8") as م:
            for صف in csv.DictReader(م):
                if صف.get("معرف_العضو"): مستثنيين.add(صف["معرف_العضو"])
        return مستثنيين
    
    def اضافة_استثناء(self, معرف_المجموعة, معرف_العضو, السبب, اسم_الجلسة):
        مسار = self.مسار_الاستثناء(معرف_المجموعة)
        with open(مسار, "a", newline="", encoding="utf-8") as م:
            csv.writer(م).writerow([str(معرف_العضو), السبب, اسم_الجلسة, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    
    def احصائيات_الاستثناء(self, معرف):
        مسار = self.مسار_الاستثناء(معرف)
        احصائيات = {}
        if not مسار.exists(): return احصائيات
        with open(مسار, "r", encoding="utf-8") as م:
            for صف in csv.DictReader(م):
                سبب = صف.get("السبب", "غير_معروف")
                احصائيات[سبب] = احصائيات.get(سبب, 0) + 1
        return احصائيات
    
    def كل_الاستثناءات(self):
        نتيجة = []
        for ملف in الاعدادات.مجلد_الاستثناءات.glob("استثناء_*.csv"):
            معرف = ملف.stem.replace("استثناء_", "")
            with open(ملف, "r", encoding="utf-8") as م:
                صفوف = list(csv.DictReader(م))
            نتيجة.append({"معرف_المجموعة": معرف, "الاجمالي": len(صفوف), "احصائيات": self.احصائيات_الاستثناء(معرف)})
        return نتيجة

class مدير_الجلسات:
    def __init__(self):
        self.مجلد_الجلسات = الاعدادات.مجلد_الجلسات
        self.سجل = تهيئة_السجل("مدير_الجلسات")

    def عرض_الجلسات(self):
        return sorted([ملف.name.replace(".session", "") for ملف in self.مجلد_الجلسات.iterdir() if ملف.name.endswith(".session")])
    def الجلسة_موجودة(self, الاسم): return (self.مجلد_الجلسات / f"{الاسم}.session").exists()
    def مسار_الجلسة(self, الاسم): return self.مجلد_الجلسات / الاسم
    
    def معلومات_الجلسة(self, الاسم):
        ملف = self.مجلد_الجلسات / f"{الاسم}_معلومات.txt"
        معلومات = {}
        if ملف.exists():
            with open(ملف, "r", encoding="utf-8") as م:
                for سطر in م:
                    if "=" in سطر and not سطر.startswith("#"):
                        k, v = سطر.strip().split("=", 1)
                        معلومات[k] = v
        return معلومات
    
    def حفظ_معلومات_الجلسة_الكاملة(self, الاسم, انا, كامل):
        with open(self.مجلد_الجلسات / f"{الاسم}_معلومات.txt", "w", encoding="utf-8") as م:
            م.write(f"الاسم={انا.first_name or ''}\nالمعرف={انا.id}\nالهاتف={انا.phone or 'لا_يوجد'}\nتاريخ_التسجيل={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    async def الحصول_على_عميل(self, اسم_الجلسة):
        if not self.الجلسة_موجودة(اسم_الجلسة): return None
        try:
            عميل = TelegramClient(str(self.مسار_الجلسة(اسم_الجلسة)), الاعدادات.API_ID, الاعدادات.API_HASH)
            await عميل.connect()
            if not await عميل.is_user_authorized():
                await عميل.disconnect()
                return None
            return عميل
        except Exception: return None

# ═══════════════════════════════════════════════════════════════
# 🔍  وحدات الاستخراج والبحث والإضافة
# ═══════════════════════════════════════════════════════════════

class وحدة_الاستخراج:
    def __init__(self):
        self.مدير = مدير_الجلسات()
        self.سجل = تهيئة_السجل("الاستخراج")

    async def _استخراج_بجلسة(self, اسم_الجلسة, رابط, حد):
        نتيجة = {"جديد": 0, "اجمالي": 0, "حالة": "نجح"}
        عميل = await self.مدير.الحصول_على_عميل(اسم_الجلسة)
        if not عميل: return {"جديد": 0, "حالة": "فشل الاتصال"}
        try:
            كيان, خطأ = await الحصول_على_كيان(عميل, رابط)
            if not كيان: return {"جديد": 0, "حالة": "فشل الوصول"}
            
            اعضاء = []
            async for عضو in عميل.iter_participants(كيان, limit=حد):
                if not عضو.bot and not عضو.deleted:
                    اعضاء.append(f"{عضو.id}:{عضو.access_hash}")
            
            نتيجة["اجمالي"] = len(اعضاء)
            نتيجة["جديد"] = self._حفظ_الاعضاء(اسم_الجلسة, اعضاء)
        except Exception as e:
            نتيجة["حالة"] = str(e)
        finally:
            await عميل.disconnect()
        return نتيجة

    def _حفظ_الاعضاء(self, اسم_الجلسة, اعضاء):
        مسار = الاعدادات.مجلد_الاعضاء / f"{اسم_الجلسة}.txt"
        موجودين = set()
        if مسار.exists():
            with open(مسار, "r", encoding="utf-8") as م:
                موجودين = set(سطر.strip().split(":")[0] for سطر in م if ":" in سطر)
        
        جديد = [عضو for عضو in اعضاء if عضو.split(":")[0] not in موجودين]
        if جديد:
            with open(مسار, "a", encoding="utf-8") as م:
                if مسار.stat().st_size > 0: م.write("\n")
                م.write("\n".join(جديد))
        return len(جديد)

class وحدة_البحث:
    def __init__(self):
        self.مدير = مدير_الجلسات()
        self.سجل = تهيئة_السجل("البحث")

    async def _بحث_بجلسة(self, اسم_الجلسة, كلمات, حد):
        نتيجة = {"جديد": 0, "حالة": "نجح"}
        عميل = await self.مدير.الحصول_على_عميل(اسم_الجلسة)
        if not عميل: return {"جديد": 0, "حالة": "فشل الاتصال"}
        
        try:
            موجودين = set()
            مسار = الاعدادات.مجلد_الاعضاء / f"{اسم_الجلسة}.txt"
            if مسار.exists():
                with open(مسار, "r", encoding="utf-8") as م:
                    موجودين = set(سطر.split(":")[0] for سطر in م if ":" in سطر)
            
            كل_النتائج = []
            for كلمة in كلمات:
                res = await عميل(functions.contacts.SearchRequest(q=كلمة, limit=حد))
                for مستخدم in res.users:
                    معرف = str(مستخدم.id)
                    if not مستخدم.bot and not مستخدم.deleted and معرف not in موجودين:
                        كل_النتائج.append(f"{مستخدم.id}:{مستخدم.access_hash}")
                        موجودين.add(معرف)
                await asyncio.sleep(random.uniform(3, 5))
            
            if كل_النتائج:
                with open(مسار, "a", encoding="utf-8") as م:
                    if مسار.stat().st_size > 0: م.write("\n")
                    م.write("\n".join(كل_النتائج))
                نتيجة["جديد"] = len(كل_النتائج)
        except Exception as e:
            نتيجة["حالة"] = str(e)
        finally:
            await عميل.disconnect()
        return نتيجة

class وحدة_الاضافة:
    def __init__(self):
        self.مدير = مدير_الجلسات()
        self.قاعدة = قاعدة_البيانات()
        self.سجل = تهيئة_السجل("الاضافة")

    async def _معالجة_جلسة(self, اسم_الجلسة, رابط, معرف_نصي, حد):
        نتيجة = {"نجاح": 0, "فشل": 0, "تخطي": 0, "محظورة": False}
        مسار = الاعدادات.مجلد_الاعضاء / f"{اسم_الجلسة}.txt"
        if not مسار.exists(): return نتيجة
        
        with open(مسار, "r", encoding="utf-8") as م:
            مستخدمين = [سطر.strip() for سطر in م if ":" in سطر]
            
        عميل = await self.مدير.الحصول_على_عميل(اسم_الجلسة)
        if not عميل: return {**نتيجة, "محظورة": True}

        try:
            كيان, _ = await الحصول_على_كيان(عميل, رابط)
            if not كيان: return {**نتيجة, "محظورة": True}
            
            معرف_القاعدة = str(getattr(كيان, "id", معرف_نصي))
            مستثنيين = self.قاعدة.تحميل_المستثنيين(معرف_القاعدة)

            for سطر in مستخدمين:
                if نتيجة["محظورة"] or نتيجة["نجاح"] >= حد: break
                معرف, هاش = سطر.split(":")
                if معرف in مستثنيين:
                    نتيجة["تخطي"] += 1
                    continue
                
                try:
                    await عميل(InviteToChannelRequest(كيان, [InputPeerUser(int(معرف), int(هاش))]))
                    نتيجة["نجاح"] += 1
                    self.قاعدة.اضافة_استثناء(معرف_القاعدة, معرف, "نجاح", اسم_الجلسة)
                    await asyncio.sleep(random.uniform(الاعدادات.اقل_تأخير, الاعدادات.اقصى_تأخير))
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds + 10)
                except PeerFloodError:
                    نتيجة["محظورة"] = True
                    break
                except Exception as e:
                    نتيجة["فشل"] += 1
                    self.قاعدة.اضافة_استثناء(معرف_القاعدة, معرف, str(e)[:20], اسم_الجلسة)
        finally:
            await عميل.disconnect()
        return نتيجة

# ═══════════════════════════════════════════════════════════════
# 🤖 بوت التليجرام بالأزرار
# ═══════════════════════════════════════════════════════════════

class بوت_التليجرام:
    def __init__(self):
        self.مدير = مدير_الجلسات()
        self.استخراج = وحدة_الاستخراج()
        self.بحث = وحدة_البحث()
        self.اضافة = وحدة_الاضافة()
        self.قاعدة = قاعدة_البيانات()
        self.حالات = {}
        self.بوت = None

    async def تشغيل(self):
        self.بوت = TelegramClient("بوت_الادارة", الاعدادات.API_ID, الاعدادات.API_HASH)
        await self.بوت.start(bot_token=الاعدادات.TOKEN)
        print(f"✅ البوت يعمل بنجاح!")
        self._تسجيل_المعالجات()
        await self.بوت.run_until_disconnected()

    def _تسجيل_المعالجات(self):
        @self.بوت.on(events.NewMessage(pattern=r'^/start$'))
        async def بداية(event):
            await event.respond("🚀 **بوت إدارة الحسابات**\nاختر من القائمة:", buttons=self._ازرار_رئيسية())

        @self.بوت.on(events.CallbackQuery())
        async def ازرار(event):
            await self._معالجة_الازرار(event)

        @self.بوت.on(events.NewMessage(func=lambda e: e.is_private and not e.raw_text.startswith('/')))
        async def رسائل(event):
            await self._معالجة_الرسائل(event)

    def _ازرار_رئيسية(self):
        return [
            [Button.inline("👤 تسجيل حساب", b"new_acc"), Button.inline("📋 الجلسات", b"sessions")],
            [Button.inline("🔗 استخراج", b"extract"), Button.inline("🔎 بحث", b"search")],
            [Button.inline("➕ إضافة أعضاء", b"add"), Button.inline("📊 إحصائيات", b"stats")]
        ]

    async def _معالجة_الازرار(self, event):
        data = event.data.decode()
        await event.answer()
        
        if data == "main":
            await event.edit("🚀 **القائمة الرئيسية**", buttons=self._ازرار_رئيسية())
        elif data == "sessions":
            جلسات = self.مدير.عرض_الجلسات()
            ازرار = [[Button.inline(f"📱 {ج}", f"sess_{ج}".encode())] for ج in جلسات]
            ازرار.append([Button.inline("🔙 رجوع", b"main")])
            await event.edit("📋 **جلساتك:**", buttons=ازرار)
        elif data == "new_acc":
            self.حالات[event.sender_id] = "wait_phone"
            await event.edit("📱 أرسل رقم الهاتف (مثال: 201012345678):", buttons=[[Button.inline("❌ إلغاء", b"main")]])
        elif data == "extract":
            self.حالات[event.sender_id] = "wait_extract_link"
            await event.edit("🔗 أرسل رابط المجموعة للاستخراج:", buttons=[[Button.inline("❌ إلغاء", b"main")]])
        elif data == "search":
            self.حالات[event.sender_id] = "wait_search_word"
            await event.edit("🔎 أرسل الكلمة المراد البحث عنها:", buttons=[[Button.inline("❌ إلغاء", b"main")]])
        elif data == "add":
            self.حالات[event.sender_id] = "wait_add_link"
            await event.edit("➕ أرسل رابط المجموعة الهدف:", buttons=[[Button.inline("❌ إلغاء", b"main")]])
        elif data == "stats":
            جلسات = self.مدير.عرض_الجلسات()
            نص = f"📊 **الإحصائيات**\nعدد الجلسات: {len(جلسات)}\n"
            for ج in جلسات:
                نص += f"- `{ج}`: {عدد_اعضاء_الجلسة(ج)} عضو\n"
            await event.edit(نص, buttons=[[Button.inline("🔙 رجوع", b"main")]])

    async def _معالجة_الرسائل(self, event):
        state = self.حالات.get(event.sender_id)
        if not state:
            await event.respond("استخدم /start للبدء")
            return

        if state == "wait_phone":
            رقم = ''.join(filter(str.isdigit, event.raw_text))
            await event.respond("⏳ جاري إرسال الكود...")
            try:
                client = TelegramClient(str(self.مدير.مسار_الجلسة(رقم)), الاعدادات.API_ID, الاعدادات.API_HASH)
                await client.connect()
                sent = await client.send_code_request(f"+{رقم}")
                self.حالات[event.sender_id] = {"step": "wait_code", "phone": f"+{رقم}", "client": client, "hash": sent.phone_code_hash}
                await event.respond("🔢 أرسل كود التحقق:")
            except Exception as e:
                await event.respond(f"❌ خطأ: {e}")
                self.حالات[event.sender_id] = None

        elif isinstance(state, dict) and state.get("step") == "wait_code":
            try:
                await state["client"].sign_in(state["phone"], event.raw_text, phone_code_hash=state["hash"])
                me = await state["client"].get_me()
                self.مدير.حفظ_معلومات_الجلسة_الكاملة(state["phone"].replace("+",""), me, None)
                await event.respond(f"✅ تم التسجيل بنجاح!\nID: {me.id}", buttons=[[Button.inline("🔙 القائمة", b"main")]])
                await state["client"].disconnect()
            except SessionPasswordNeededError:
                self.حالات[event.sender_id]["step"] = "wait_2fa"
                await event.respond("🔐 الحساب محمي بكلمة مرور (2FA)، أرسلها:")
            except Exception as e:
                await event.respond(f"❌ خطأ: {e}")
                self.حالات[event.sender_id] = None
                
        elif isinstance(state, dict) and state.get("step") == "wait_2fa":
            try:
                await state["client"].sign_in(password=event.raw_text)
                me = await state["client"].get_me()
                self.مدير.حفظ_معلومات_الجلسة_الكاملة(state["phone"].replace("+",""), me, None)
                await event.respond(f"✅ تم التسجيل بنجاح!\nID: {me.id}", buttons=[[Button.inline("🔙 القائمة", b"main")]])
                await state["client"].disconnect()
            except Exception as e:
                await event.respond(f"❌ خطأ: {e}")
            self.حالات[event.sender_id] = None

        elif state == "wait_extract_link":
            await event.respond("⏳ جاري الاستخراج...")
            جلسات = self.مدير.عرض_الجلسات()
            مجموع = 0
            for ج in جلسات:
                res = await self.استخراج._استخراج_بجلسة(ج, event.raw_text, None)
                مجموع += res["جديد"]
            await event.respond(f"✅ تم الاستخراج! إجمالي الجديد: {مجموع}", buttons=[[Button.inline("🔙 القائمة", b"main")]])
            self.حالات[event.sender_id] = None

        elif state == "wait_search_word":
            await event.respond("⏳ جاري البحث في كل الجلسات...")
            جلسات = self.مدير.عرض_الجلسات()
            مجموع = 0
            for ج in جلسات:
                res = await self.بحث._بحث_بجلسة(ج, [event.raw_text], الاعدادات.حد_البحث)
                مجموع += res["جديد"]
            await event.respond(f"✅ تم البحث! إجمالي الجديد: {مجموع}", buttons=[[Button.inline("🔙 القائمة", b"main")]])
            self.حالات[event.sender_id] = None
            
        elif state == "wait_add_link":
            await event.respond("⏳ جاري الإضافة من كل الجلسات...")
            جلسات = self.مدير.عرض_الجلسات()
            مجموع = 0
            for ج in جلسات:
                res = await self.اضافة._معالجة_جلسة(ج, event.raw_text, "0", الاعدادات.حد_الاضافة_اليومي)
                مجموع += res["نجاح"]
            await event.respond(f"✅ تمت الإضافة! إجمالي النجاح: {مجموع}", buttons=[[Button.inline("🔙 القائمة", b"main")]])
            self.حالات[event.sender_id] = None

# ═══════════════════════════════════════════════════════════════
# 🚀 التشغيل الرئيسي
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    الاعدادات.انشاء_المجلدات()
    بوت = بوت_التليجرام()
    asyncio.run(بوت.تشغيل())
