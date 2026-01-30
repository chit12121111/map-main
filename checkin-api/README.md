# 🎫 Check-in API System

ระบบ Auto Check-in ด้วย Token-based Authentication สำหรับรันบน Cloud 24/7

## 📋 Features

- ✅ Auto check-in เมื่อคลิกลิงก์ (ไม่ต้อง login)
- 🔐 Token ใช้ครั้งเดียว (one-time use)
- 📊 บันทึก IP, User-Agent, Timestamp
- 🚀 Deploy ฟรีบน Render/Railway
- 💾 รองรับ SQLite (local) และ PostgreSQL (production)

---

## 🏗️ สถาปัตยกรรม

```
┌─────────────────────┐
│   GUI (Streamlit)   │  ← รันเฉพาะเวลาใช้งาน (local)
│   - สร้างลิงก์      │
│   - ส่งอีเมล        │
└─────────────────────┘
          │
          │ API calls
          ▼
┌─────────────────────┐
│ Check-in API        │ ← รันตลอด 24/7 (cloud)
│ (FastAPI)           │    https://yourapp.onrender.com
│  - รับ token        │
│  - บันทึก check-in  │
└─────────────────────┘
          │
          ▼
┌─────────────────────┐
│    Database         │
│  - invite_tokens    │
│  - checkins         │
└─────────────────────┘
```

---

## 🚀 Quick Start (Local)

### 1. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

### 2. สร้างไฟล์ .env

```bash
cp .env.example .env
```

แก้ไข `.env`:
```env
DATABASE_URL=sqlite:///./checkin.db
```

### 3. รัน API

```bash
uvicorn main:app --reload --port 8000
```

API จะรันที่: `http://localhost:8000`

### 4. ทดสอบ

เปิดเบราว์เซอร์:
- API Docs: http://localhost:8000/docs
- หน้าแรก: http://localhost:8000

สร้าง token:
```bash
curl -X POST "http://localhost:8000/api/create-token" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

ทดสอบ check-in:
```bash
# เอา token จากข้างบนมาใส่
curl -X POST "http://localhost:8000/checkin" \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_TOKEN_HERE"}'
```

---

## 📦 Deploy บน Render (ฟรี)

### ขั้นตอนที่ 1: Push โค้ดขึ้น GitHub

```bash
# ใน folder checkin-api
git init
git add .
git commit -m "Initial commit: Check-in API"

# สร้าง repo บน GitHub แล้ว push
git remote add origin https://github.com/YOUR_USERNAME/checkin-api.git
git branch -M main
git push -u origin main
```

### ขั้นตอนที่ 2: Deploy บน Render

1. ไปที่ [render.com](https://render.com) → Sign up (ฟรี)
2. คลิก **"New +"** → **"Web Service"**
3. เชื่อม GitHub repo ของคุณ
4. ตั้งค่า:
   - **Name**: `checkin-api` (หรือชื่ออะไรก็ได้)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`

5. คลิก **"Create Web Service"**

### ขั้นตอนที่ 3: เพิ่ม PostgreSQL Database (optional)

1. ใน Render Dashboard → **"New +"** → **"PostgreSQL"**
2. ตั้งชื่อ: `checkin-db`
3. Plan: **Free** (90 วัน)
4. คลิก **"Create Database"**

5. Copy **Internal Database URL**
6. ไปที่ Web Service → **Environment** → เพิ่ม:
   ```
   DATABASE_URL = postgresql://user:pass@host/db
   ```

### เสร็จแล้ว!

ได้ URL: `https://checkin-api-xxxxx.onrender.com`

---

## 📡 API Endpoints

### 1. สร้าง Token (ใช้ใน GUI)

```http
POST /api/create-token
Content-Type: application/json

{
  "email": "user@example.com",
  "expires_in_days": 7  // optional
}
```

Response:
```json
{
  "token": "abc123xyz789...",
  "email": "user@example.com",
  "link": "https://yourapp.onrender.com/checkin?t=abc123xyz789",
  "expires_at": "2024-01-15 10:30:00 UTC"
}
```

### 2. Check-in (เรียกจาก Frontend)

```http
POST /checkin
Content-Type: application/json

{
  "token": "abc123xyz789"
}
```

Response (สำเร็จ):
```json
{
  "message": "Check-in สำเร็จ",
  "email": "user@example.com",
  "status": "success",
  "checked_in_at": "2024-01-08 14:30:00 UTC"
}
```

Response (ล้มเหลว):
```json
{
  "detail": "Token นี้ถูกใช้ไปแล้ว..."
}
```

### 3. ดูประวัติ Check-in

```http
GET /api/checkins?email=user@example.com&limit=50
```

### 4. ดู Token ทั้งหมด

```http
GET /api/tokens?email=user@example.com
```

---

## 🔗 การใช้งานจาก GUI

ใน Streamlit GUI ของคุณ เรียก API แบบนี้:

```python
import requests

# สร้าง token
response = requests.post(
    "https://yourapp.onrender.com/api/create-token",
    json={"email": "user@example.com"}
)
data = response.json()
link = data["link"]

# ส่งลิงก์ไปทาง email (ใช้ Gmail OAuth ที่มีอยู่แล้ว)
# link จะเป็น: https://yourapp.onrender.com/checkin?t=abc123
```

---

## 🗄️ Database Schema

### Table: invite_tokens

| Column     | Type     | Description                    |
|------------|----------|--------------------------------|
| token      | VARCHAR  | Primary key, unique token      |
| email      | VARCHAR  | Email ของผู้ใช้                |
| used_at    | DATETIME | เวลาที่ใช้ token (null = ยังไม่ใช้) |
| expires_at | DATETIME | เวลาหมดอายุ (optional)          |
| created_at | DATETIME | เวลาสร้าง token                |

### Table: checkins

| Column      | Type     | Description           |
|-------------|----------|-----------------------|
| id          | INTEGER  | Primary key           |
| token       | VARCHAR  | Token ที่ใช้ check-in |
| email       | VARCHAR  | Email ของผู้ใช้       |
| ip_address  | VARCHAR  | IP address            |
| user_agent  | TEXT     | Browser/Device info   |
| referrer    | VARCHAR  | มาจากไหน              |
| created_at  | DATETIME | เวลา check-in         |

---

## 🔐 Security

- ✅ Token สุ่มด้วย `secrets` module (cryptographically secure)
- ✅ Token ใช้ได้ครั้งเดียว (mark `used_at` หลัง check-in)
- ✅ รองรับ Token Expiration
- ✅ บันทึก IP และ User-Agent สำหรับ audit
- ✅ CORS configured (ต้องแก้ `ALLOWED_ORIGINS` ตอน production)

---

## 📊 Monitoring

ดูสถิติ check-in:
```bash
curl "https://yourapp.onrender.com/api/checkins?limit=10"
```

Health check:
```bash
curl "https://yourapp.onrender.com/health"
```

---

## 🆘 Troubleshooting

### API Sleep (Render Free)
- Render free tier จะ sleep หลัง 15 นาที
- ครั้งแรกที่เปิดจะช้า 10-30 วินาที
- **Solution**: ใช้ Railway ($5/เดือน) หรือ Cloudflare Workers (ฟรี)

### Database หมดอายุ (Render PostgreSQL)
- PostgreSQL ฟรีได้ 90 วัน
- **Solution**: 
  1. ใช้ SQLite (เก็บไว้ใน repo) สำหรับ data น้อยๆ
  2. ย้ายไป Railway/Supabase (PostgreSQL ฟรีตลอดกาล)

### CORS Error
- แก้ `ALLOWED_ORIGINS` ใน `.env` หรือ `main.py`
- ตัวอย่าง: `ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com`

---

## 📝 License

MIT License - ใช้ฟรี แก้ไขได้ตามต้องการ

---

## 🙏 Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Render](https://render.com/)
