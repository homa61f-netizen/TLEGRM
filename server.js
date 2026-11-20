const express = require('express');
const cors = require('cors');
const { TelegramClient, Api } = require("telegram");
const { StringSession } = require("telegram/sessions");
const { MongoClient } = require('mongodb');

const app = express();
app.use(cors());
app.use(express.json());

// جلب الإعدادات من Vercel
const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;
const MONGODB_URI = process.env.MONGODB_URI;
const DB_NAME = "telegram_bot";

// الاتصال بقاعدة البيانات
async function getDB() {
    const client = new MongoClient(MONGODB_URI);
    await client.connect();
    return client.db(DB_NAME);
}

// جلب الجلسة المحفوظة
async function getSavedSessionString() {
    try {
        const db = await getDB();
        const doc = await db.collection("tg_session").findOne({ _id: "main" });
        return doc ? doc.sessionString : null;
    } catch (e) {
        return null;
    }
}

// 1. التحقق من حالة الجلسة
app.get('/api/check-session', async (req, res) => {
    try {
        const sessionStr = await getSavedSessionString();
        if (sessionStr) {
            const client = new TelegramClient(new StringSession(sessionStr), apiId, apiHash, { connectionRetries: 1 });
            await client.connect();
            const authorized = await client.isUserAuthorized();
            await client.disconnect();
            return res.json({ loggedIn: authorized });
        }
        res.json({ loggedIn: false });
    } catch (error) {
        res.json({ loggedIn: false });
    }
});

// 2. إرسال كود التحقق
app.post('/api/send-code', async (req, res) => {
    const { phone } = req.body;
    try {
        const client = new TelegramClient(new StringSession(""), apiId, apiHash, { connectionRetries: 3 });
        await client.connect();
        const result = await client.sendCode({ apiId, apiHash }, phone);
        
        global.tempClient = client;
        global.tempPhone = phone;
        global.tempHash = result.phoneCodeHash;

        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// 3. تأكيد الكود وحفظ الجلسة
app.post('/api/verify-code', async (req, res) => {
    const { code } = req.body;
    if (!global.tempClient) return res.status(400).json({ success: false, error: "انتهت الجلسة المؤقتة، أعد المحاولة" });

    try {
        const { tempClient, tempPhone, tempHash } = global;
        await tempClient.invoke(new Api.auth.SignIn({
            phoneNumber: tempPhone, phoneCodeHash: tempHash, phoneCode: code
        }));

        const sessionString = tempClient.session.save();
        
        const db = await getDB();
        await db.collection("tg_session").updateOne(
            { _id: "main" },
            { $set: { sessionString: sessionString, phone: tempPhone, updatedAt: new Date() } },
            { upsert: true }
        );

        await tempClient.disconnect();
        global.tempClient = null;

        res.json({ success: true });
    } catch (error) {
        if (error.message.includes("SESSION_PASSWORD_NEEDED")) {
            return res.status(400).json({ success: false, error: "الحساب محمي بكلمة مرور (2FA) غير مدعومة حالياً" });
        }
        res.status(500).json({ success: false, error: error.message });
    }
});

// دالة مساعدة للعمليات
async function getClient() {
    const sessionString = await getSavedSessionString();
    if (!sessionString) throw new Error("يرجى تسجيل الدخول أولاً");
    const client = new TelegramClient(new StringSession(sessionString), apiId, apiHash, { connectionRetries: 3 });
    await client.connect();
    return client;
}

// 4. مسار الاستخراج
app.post('/api/extract', async (req, res) => {
    const { link, limit } = req.body;
    try {
        const client = await getClient();
        let entity;
        try { entity = await client.getEntity(link); } 
        catch (e) {
            if (link.includes('+')) {
                const hash = link.split('+')[1];
                const result = await client.invoke(new Api.messages.ImportChatInvite({ hash }));
                entity = result.chats[0];
            } else throw new Error("لا يمكن الوصول للرابط");
        }
        const participants = await client.getParticipants(entity, { limit: parseInt(limit) || 50 });
        await client.disconnect();
        res.json({ success: true, message: `تم استخراج ${participants.length} عضو بنجاح` });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// 5. مسار الإضافة
app.post('/api/add', async (req, res) => {
    const { link, limit } = req.body;
    try {
        const client = await getClient();
        let entity;
        try { entity = await client.getEntity(link); } 
        catch (e) { throw new Error("لا يمكن الوصول للمجموعة"); }

        // كود الإضافة هنا (يحتاج قائمة أعضاء)
        await client.disconnect();
        res.json({ success: true, message: `تم الدخول للمجموعة: ${entity.title || entity.username} (العملية قيد التطوير)` });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// تشغيل السيرفر
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 Server running on ${PORT}`));
module.exports = app;
