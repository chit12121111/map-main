from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class InviteToken(Base):
    """ตาราง token สำหรับลิงก์ check-in"""
    __tablename__ = "invite_tokens"
    
    token = Column(String(64), primary_key=True, unique=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # optional: กำหนดเวลาหมดอายุ
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class CheckIn(Base):
    """ตารางเก็บประวัติ check-in"""
    __tablename__ = "checkins"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    user_agent = Column(Text, nullable=True)
    referrer = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
