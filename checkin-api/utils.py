import secrets
import string

def generate_token(length=32):
    """สร้าง token แบบสุ่มที่ปลอดภัย (cryptographically secure)"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_client_ip(request):
    """ดึง IP address จาก request (รองรับ proxy/load balancer)"""
    # ตรวจสอบ headers จาก proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For อาจมีหลาย IP (client, proxy1, proxy2)
        # เอา IP แรกซึ่งเป็น client จริง
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # fallback: ใช้ client.host
    return request.client.host if request.client else "unknown"
