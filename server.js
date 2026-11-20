const express = require('express');
const cors = require('cors');
const { TelegramClient, Api } = require("telegram");
const { StringSession } = require("telegram/sessions");
const { MongoClient } = require('mongodb');

const app = express();
app.use(cors());
app.use(express.json());

// جلب الإعدادات
const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;
const MONGODB_URI = process.env.MONGODB_URI;
const DB_NAME = "telegram_bot";

// ─── إدارة قاعدة البيانات ───
let dbClient = null;
async function getDB() {
    if (!dbClient) {
        dbClient = new MongoClient(MONGODB_URI);
        await dbClient.connect();
    }
    return dbClient.db(DB_NAME);
}

// ─── التحقق من الجلسة ───
app.get('/api/check-session', async (req, res) => {
    try {
        const db = await getDB();
        const doc = await db.collection("tg_session").findOne({ _id: "main" });
        
        if (!doc || !doc.sessionString) {
            return res.json({ loggedIn: false });
        }

        // اختبار سريع للجلسة
        const client = new TelegramClient(new StringSession(doc.sessionString), apiId, apiHash, { connectionRetries: 1 });
        await client.connect();
        const authorized = await client.isUserAuthorized();
        await client.disconnect();
        
        res.json({ loggedIn: authorized });
    } catch (error) {
        res.json({ loggedIn: false });
    }
});

// ─── إرسال كود التحقق ───
app.post('/api/send-code', async (req, res) => {
    const { phone } = req.body;
    try {
        const client = new TelegramClient(new StringSession(""), apiId, apiHash, { connectionRetries: 3 });
        await client.connect();
        
        // إرسال الكود
        const result = await client.sendCode({ apiId, apiHash }, phone);
        
        // حفظ بيانات الجلسة المؤقتة في قاعدة البيانات
        const db = await getDB();
        await db.collection("temp_login").updateOne(
            { _id: "temp" },
            { $set: { 
                phone: phone, 
                phoneCodeHash: result.phoneCodeHash,
                sessionString: client.session.save() 
            }},
            { upsert: true }
        );

        await client.disconnect();
        res.json({ success: true, message: "تم إرسال الكود بنجاح، تحقق من تليجرام" });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// ─── تأكيد الكود ───
app.post('/api/verify-code', async (req, res) => {
    const { code } = req.body;
    try {
        const db = await getDB();
        const tempData = await db.collection("temp_login").findOne({ _id: "temp" });
        
        if (!tempData) return res.status(400).json({ success: false, error: "انتهت الجلسة المؤقتة، أعد إرسال الكود" });

        const client = new TelegramClient(new StringSession(tempData.sessionString), apiId, apiHash, { connectionRetries: 3 });
        await client.connect();
        
        await client.invoke(new Api.auth.SignIn({
            phoneNumber: tempData.phone, 
            phoneCodeHash: tempData.phoneCodeHash, 
            phoneCode: code
        }));

        const sessionString = client.session.save();
        
        // حفظ الجلسة النهائية
        await db.collection("tg_session").updateOne(
            { _id: "main" },
            { $set: { sessionString: sessionString, phone: tempData.phone, updatedAt: new Date() } },
            { upsert: true }
        );

        await db.collection("temp_login").deleteOne({ _id: "temp" });
        await client.disconnect();

        res.json({ success: true });
    } catch (error) {
        if (error.message.includes("SESSION_PASSWORD_NEEDED")) {
            return res.status(400).json({ success: false, error: "الحساب محمي بكلمة مرور (2FA) غير مدعومة حالياً" });
        }
        res.status(500).json({ success: false, error: error.message });
    }
});

// ─── العمليات (استخراج وإضافة) ───
async function getClient() {
    const db = await getDB();
    const doc = await db.collection("tg_session").findOne({ _id: "main" });
    if (!doc || !doc.sessionString) throw new Error("يرجى تسجيل الدخول أولاً");
    
    const client = new TelegramClient(new StringSession(doc.sessionString), apiId, apiHash, { connectionRetries: 3 });
    await client.connect();
    return client;
}

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

app.post('/api/add', async (req, res) => {
    try {
        const client = await getClient();
        await client.disconnect();
        res.json({ success: true, message: "تم الاتصال بالجلسة بنجاح (العملية قيد التطوير)" });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 Server running on ${PORT}`));
module.exports = app;
