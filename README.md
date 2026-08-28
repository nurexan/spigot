# Telegram Business Spy & Monitoring Bot

Ushbu bot Telegram Business Chatbot API orqali ulangan foydalanuvchilarning barcha kiruvchi va chiquvchi yozishmalari, tahrirlangan va o'chirilgan xabarlari hamda media fayllarini (rasm, video, dumaloq video, ovozli xabar va o'chib ketuvchi medialar) real vaqt rejimida kuzatib, adminga uzatadi.

---

## 🚀 O'rnatish va Ishga tushirish

### 1. Talablar
* Python 3.9+
* Telegram Bot Token (@BotFather orqali olingan)

### 2. Virtual muhitni faollashtirish va kutubxonalarni o'rnatish
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Sozlamalar (`.env`)
`.env` faylida bot tokeni va admin ID larini ko'rsating:
```env
BOT_TOKEN=8751576357:AAHVuGYC8Ua3WnSKeRKI64oXRe7o6mM0_Ck
ADMIN_IDS=6476995106
CACHE_RETENTION_DAYS=7
```

### 4. Botni ishga tushirish
```bash
./venv/bin/python3 bot.py
```

---

## 🛠 Funksiyalar va Ishlash Tartibi

1. **Admin Panel:**
   - `➕ Kod yaratish`: Oddiy monitoring uchun bir martalik ulanish kodi yaratadi.
   - `➕ Maxsus kod (Kuzatuv)`: "MAXSUS KUZATUV" belgisi bilan xabarlarni ajratib ko'rsatuvchi maxsus kod yaratadi.
   - `👥 Foydalanuvchilar`: Barcha ulangan akkauntlar holati (🟢 Faol / 🔴 Nofaol) va statistikasi.
   - `💳 Faol kodlar`: Ishlatilmagan kodlarni ko'rish va boshqarish.

2. **Telegram Business Ulanish:**
   - Foydalanuvchi botga o'ziga berilgan ulanish kodini kiritadi.
   - Telegram ilovasida: `Sozlamalar (Settings)` -> `Telegram Business` -> `Chatbotlar (Chatbots)` bo'limiga kirib, ushbu botni tanlaydi.
   - Bot ulangach, barcha chatlardagi suhbatlar avtomatik adminga yuboriladi.

3. **Kuzatiladigan hodisalar:**
   - 📥 Kiruvchi xabarlar: `📍 Harakat: 📥 Qabul qildi (Kimdan: ...)`
   - 📤 Chiquvchi xabarlar: `📍 Harakat: 📤 Yubordi (Kimgacha: ...)`
   - ✏️ Tahrirlangan xabarlar (`edited_business_message`): Eski va yangi matn.
   - 🗑 O'chirilgan xabarlar (`deleted_business_messages`): O'chirilgan xabar matni/turi.
   - 📷 Barcha media turlari: Rasm, Video, Dumaloq video (Video note), Ovozli xabar (Voice), O'chib ketuvchi rasmlar.
