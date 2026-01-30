# เตรียมขึ้น GitHub

โปรเจกต์พร้อม push ขึ้น GitHub แล้ว (มี git init + initial commit แล้ว)

## สิ่งที่ทำแล้ว

- สร้าง Git repository (`git init`)
- `.gitignore` กันไฟล์ลับและขยะแล้ว: `.env`, `*.db`, `__pycache__/`, `*.csv`, ฯลฯ
- มี `.env.example` ทั้ง root และ `checkin-api/` สำหรับตั้งค่าโดยไม่ใส่ secret จริง
- Commit แรกแล้ว (42 ไฟล์)

## ขั้นตอนขึ้น GitHub

### 1. สร้าง Repo บน GitHub

1. ไปที่ [github.com/new](https://github.com/new)
2. ตั้งชื่อ repo (เช่น `map-main` หรือชื่ออื่น)
3. เลือก **Public** หรือ **Private**
4. **อย่า** เลือก "Add a README" หรือ "Add .gitignore" (มีอยู่แล้วในโปรเจกต์)
5. กด **Create repository**

### 2. ผูก remote และ push

ในโฟลเดอร์โปรเจกต์ (PowerShell):

```powershell
cd C:\Users\0355\Desktop\map-main

# ใส่ URL repo ของคุณ (แทน YOUR_USERNAME และ YOUR_REPO)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# ส่งขึ้น GitHub (สาขา master)
git branch -M main
git push -u origin main
```

ถ้าใช้ SSH แทน HTTPS:

```powershell
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### 3. หลัง push

- ตั้งค่า **Secrets** ใน GitHub (Settings → Secrets and variables → Actions) ถ้ามี GitHub Actions
- ใส่ค่าใน `.env` บนเครื่อง/เซิร์ฟเวอร์จาก `.env.example` — **อย่า** commit ไฟล์ `.env` จริง

---

**หมายเหตุ:** ถ้ามี branch ชื่อ `master` อยู่แล้ว และอยากใช้ชื่อ `main` บน GitHub ให้รัน `git branch -M main` ก่อน `git push` ตามด้านบน
