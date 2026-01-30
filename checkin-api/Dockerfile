# Check-in API บน Fly.io
# รันจากโฟลเดอร์ checkin-api (ที่มี main.py + requirements.txt)

FROM python:3.11-slim

WORKDIR /app

# ติดตั้ง dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ด
COPY . .

# Fly.io ส่ง PORT ผ่าน env (เช่น 8080)
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
