from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
import os

from database import init_db, get_db
from models import InviteToken, CheckIn
from utils import generate_token, get_client_ip

# สร้าง FastAPI app
app = FastAPI(
    title=os.getenv("API_TITLE", "Check-in API"),
    version=os.getenv("API_VERSION", "1.0.0"),
    description="Auto Check-in System with Token-based Authentication"
)

# CORS - อนุญาตทุก origin (แก้ตอน production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# สร้าง database tables เมื่อ app start
@app.on_event("startup")
def startup_event():
    init_db()
    print("[OK] Check-in API is running")

# ========== Pydantic Schemas ==========

class CheckInRequest(BaseModel):
    token: str

class CheckInResponse(BaseModel):
    message: str
    email: str
    status: str
    checked_in_at: str

class CreateTokenRequest(BaseModel):
    email: EmailStr
    expires_in_days: Optional[int] = None

class CreateTokenResponse(BaseModel):
    token: str
    email: str
    link: str
    expires_at: Optional[str] = None

# ========== API Endpoints ==========

@app.get("/index.html", response_class=HTMLResponse)
async def checkin_page():
    """หน้า Check-in (สำหรับ user คลิกลิงก์)"""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/", response_class=HTMLResponse)
async def root():
    """หน้าแรก - แสดงข้อมูล API"""
    return """
    <html>
        <head>
            <title>Check-in API</title>
            <style>
                body { font-family: 'Inter', sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                h1 { color: #667eea; }
                .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 8px; }
                code { background: #333; color: #0f0; padding: 2px 8px; border-radius: 4px; }
            </style>
        </head>
        <body>
            <h1>✅ Check-in API</h1>
            <p>API สำหรับระบบ Auto Check-in ด้วย Token</p>
            
            <h2>📍 Endpoints:</h2>
            <div class="endpoint">
                <strong>POST /checkin</strong><br>
                Check-in ด้วย token<br>
                Body: <code>{"token": "abc123"}</code>
            </div>
            
            <div class="endpoint">
                <strong>POST /api/create-token</strong><br>
                สร้าง token ใหม่<br>
                Body: <code>{"email": "user@example.com"}</code>
            </div>
            
            <div class="endpoint">
                <strong>GET /api/checkins</strong><br>
                ดูประวัติ check-in ทั้งหมด
            </div>
            
            <div class="endpoint">
                <strong>GET /health</strong><br>
                ตรวจสอบสถานะ API
            </div>
            
            <p>📚 Docs: <a href="/docs">/docs</a> | <a href="/redoc">/redoc</a></p>
        </body>
    </html>
    """

@app.post("/checkin", response_model=CheckInResponse)
async def check_in(
    data: CheckInRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    ✅ Check-in ด้วย token
    
    - รับ token จาก frontend
    - ตรวจสอบว่า token ถูกต้องและยังไม่ใช้
    - บันทึก check-in พร้อม IP, User-Agent
    - mark token เป็น used
    """
    # หา token ใน database
    invite = db.query(InviteToken).filter(
        InviteToken.token == data.token
    ).first()
    
    if not invite:
        raise HTTPException(
            status_code=404,
            detail="Token ไม่ถูกต้อง หรือไม่มีในระบบ"
        )
    
    # ถ้า token ถูกใช้ไปแล้ว ก็ยังให้ใช้งานได้ (แสดงหน้าเลือกปุ่ม)
    if invite.used_at:
        return CheckInResponse(
            message="ยินดีต้อนรับกลับมา",
            email=invite.email,
            status="already_used",
            checked_in_at=invite.used_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        )
    
    # ตรวจสอบว่า token หมดอายุหรือยัง
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail=f"Token หมดอายุแล้วเมื่อ {invite.expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
    
    # บันทึก check-in
    now = datetime.utcnow()
    checkin = CheckIn(
        token=data.token,
        email=invite.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "unknown"),
        referrer=request.headers.get("Referer"),
        created_at=now
    )
    db.add(checkin)
    
    # Mark token เป็น used
    invite.used_at = now
    
    # Commit ทั้งหมด
    db.commit()
    
    return CheckInResponse(
        message="Check-in สำเร็จ",
        email=invite.email,
        status="success",
        checked_in_at=now.strftime("%Y-%m-%d %H:%M:%S UTC")
    )

@app.post("/api/create-token", response_model=CreateTokenResponse)
async def create_token(
    data: CreateTokenRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    🔑 สร้าง token ใหม่สำหรับ email
    
    ใช้เฉพาะใน GUI (local) เพื่อสร้างลิงก์ส่งให้ user
    """
    # สร้าง token
    token = generate_token()
    
    # คำนวณเวลาหมดอายุ (ถ้ามี)
    expires_at = None
    if data.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)
    
    # บันทึกลง database
    invite = InviteToken(
        token=token,
        email=data.email,
        expires_at=expires_at,
        created_at=datetime.utcnow()
    )
    db.add(invite)
    db.commit()
    
    # สร้างลิงก์ check-in (ชี้ไปที่ index.html)
    base_url = str(request.base_url).rstrip("/")
    link = f"{base_url}/index.html?t={token}"
    
    return CreateTokenResponse(
        token=token,
        email=data.email,
        link=link,
        expires_at=expires_at.strftime("%Y-%m-%d %H:%M:%S UTC") if expires_at else None
    )

@app.get("/api/checkins")
async def get_checkins(
    email: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    📊 ดูประวัติ check-in
    
    Query params:
    - email: กรองด้วยอีเมล (optional)
    - limit: จำนวนรายการสูงสุด (default: 100)
    """
    query = db.query(CheckIn)
    
    if email:
        query = query.filter(CheckIn.email == email)
    
    checkins = query.order_by(CheckIn.created_at.desc()).limit(limit).all()
    
    return {
        "total": len(checkins),
        "checkins": [
            {
                "email": c.email,
                "ip_address": c.ip_address,
                "user_agent": c.user_agent[:100] if c.user_agent else None,  # ตัดให้สั้น
                "checked_in_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            }
            for c in checkins
        ]
    }

@app.get("/api/tokens")
async def get_tokens(
    email: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """📋 ดู token ทั้งหมด"""
    query = db.query(InviteToken)
    
    if email:
        query = query.filter(InviteToken.email == email)
    
    tokens = query.order_by(InviteToken.created_at.desc()).all()
    
    return {
        "total": len(tokens),
        "tokens": [
            {
                "token": t.token,
                "email": t.email,
                "used": t.used_at is not None,
                "used_at": t.used_at.strftime("%Y-%m-%d %H:%M:%S UTC") if t.used_at else None,
                "expires_at": t.expires_at.strftime("%Y-%m-%d %H:%M:%S UTC") if t.expires_at else None,
                "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            }
            for t in tokens
        ]
    }

class ResponseRequest(BaseModel):
    token: str
    email: str
    response: str  # 'interested' or 'unsubscribe'

class ResponseResult(BaseModel):
    message: str
    email: str
    response: str

@app.post("/api/response", response_model=ResponseResult)
async def record_response(
    data: ResponseRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    บันทึกการตอบกลับของผู้ใช้ (สนใจ / ไม่รับ email อีก)
    """
    # บันทึกลงตาราง checkins เพิ่ม (หรือสร้างตารางใหม่ก็ได้)
    # ตอนนี้ใช้ CheckIn เก็บ response ไว้ใน user_agent field ก่อน
    checkin = CheckIn(
        token=data.token,
        email=data.email,
        ip_address=get_client_ip(request),
        user_agent=f"RESPONSE:{data.response}",  # เก็บ response type
        referrer=request.headers.get("Referer"),
        created_at=datetime.utcnow()
    )
    db.add(checkin)
    db.commit()
    
    return ResponseResult(
        message="บันทึกเรียบร้อยแล้ว",
        email=data.email,
        response=data.response
    )

@app.get("/api/responses")
async def get_responses(
    response_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    ดู response ทั้งหมด (interested / unsubscribe)
    """
    query = db.query(CheckIn).filter(
        CheckIn.user_agent.like("RESPONSE:%")
    )
    
    if response_type:
        query = query.filter(CheckIn.user_agent == f"RESPONSE:{response_type}")
    
    results = query.order_by(CheckIn.created_at.desc()).all()
    
    interested = []
    unsubscribed = []
    
    for r in results:
        resp_type = r.user_agent.replace("RESPONSE:", "")
        item = {
            "email": r.email,
            "response": resp_type,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        if resp_type == "interested":
            interested.append(item)
        else:
            unsubscribed.append(item)
    
    return {
        "total_interested": len(interested),
        "total_unsubscribed": len(unsubscribed),
        "interested": interested,
        "unsubscribed": unsubscribed
    }

@app.get("/health")
async def health_check():
    """🏥 Health check"""
    return {
        "status": "ok",
        "message": "API is running",
        "timestamp": datetime.utcnow().isoformat()
    }

# ========== Error Handlers ==========

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return HTMLResponse(
        content="<h1>404 Not Found</h1><p>Endpoint ที่คุณเรียกไม่มีในระบบ</p>",
        status_code=404
    )
