#!/usr/bin/env python3
"""
4-Stage Pipeline GUI with Streamlit
รัน Pipeline: Stage 1 → Stage 2 (Website + FB URLs) → Stage 3 (Facebook + Web URLs) → Stage 4 (Cross-Ref)
🆕 รองรับ Parallel execution สำหรับ Stage 2&3
"""
import streamlit as st
import subprocess
import sqlite3
import pandas as pd
import requests
from pathlib import Path
import time
import sys
import os
import threading
import re
from contextlib import contextmanager
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
try:
    from keyword_generator import KeywordGenerator
except ImportError:
    KeywordGenerator = None  # e.g. google-generativeai not installed
from dotenv import load_dotenv
import json

# โหลด API key จาก .env file
load_dotenv()

# ตัวแปร env ที่ให้ตั้งค่าใน GUI ได้ (จะเขียนลง .env)
ENV_EDITABLE_KEYS = [
    "CHECKIN_API_URL",
    "GOOGLE_REDIRECT_URI",
    "GEMINI_API_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
]
def _get_env_file():
    return Path(__file__).resolve().parent / ".env"


def _read_env_to_dict():
    """อ่าน .env เป็น dict (key -> value) ไม่รวม comment และบรรทัดว่าง"""
    env_path = _get_env_file()
    result = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _write_env_from_dict(data: dict):
    """เขียน dict ลง .env (อัปเดตเฉพาะ key ใน data ที่อยู่ใน ENV_EDITABLE_KEYS, key อื่นคงเดิม)"""
    env_path = _get_env_file()
    existing = _read_env_to_dict()
    for k, v in data.items():
        if k in ENV_EDITABLE_KEYS and v is not None and str(v).strip():
            existing[k] = str(v).strip()
    lines = []
    for k in ENV_EDITABLE_KEYS:
        if k in existing:
            v = existing[k]
            if "\n" in v or (" " in v and not v.startswith("http")) or "#" in v:
                v = f'"{v}"'
            lines.append(f"{k}={v}")
    other_keys = [k for k in existing if k not in ENV_EDITABLE_KEYS]
    for k in other_keys:
        v = existing[k]
        if "\n" in v or (" " in v and not v.startswith("http")) or "#" in v:
            v = f'"{v}"'
        lines.append(f"{k}={v}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for k in existing:
        os.environ[k] = str(existing[k])


# ========== Configuration ==========

# โฟลเดอร์โปรเจกต์ (ที่อยู่ของ gui_app.py) — ใช้เป็น cwd ตอนรัน subprocess
PROJECT_ROOT = Path(__file__).resolve().parent

DB_FILE = "pipeline.db"
QUERIES_FILE = "config/queries.txt"
RESULTS_CSV = "output/results.csv"

TH_LOCATIONS_FILE = "data/th_locations.json"

# Google OAuth (เข้าสู่ระบบด้วย Google เลือกบัญชี)
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
OAUTH_TOKEN_FILE = ".gmail_oauth.json"


def _save_gmail_oauth_to_file(token_info: dict, email: str):
    """เก็บ OAuth token ลงไฟล์ เพื่อไม่ต้องล็อกอินใหม่ทุกครั้ง"""
    try:
        data = {"email": email, "token_info": dict(token_info)}
        if data["token_info"].get("expiry") is not None:
            from datetime import datetime
            e = data["token_info"]["expiry"]
            data["token_info"]["expiry"] = e.isoformat() if hasattr(e, "isoformat") else str(e)
        with open(OAUTH_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
    except Exception:
        pass


def _load_gmail_oauth_from_file():
    """โหลด OAuth token จากไฟล์ คืน (token_info, email) หรือ (None, None)"""
    try:
        if not Path(OAUTH_TOKEN_FILE).exists():
            return None, None
        with open(OAUTH_TOKEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        token_info = data.get("token_info") or {}
        email = (data.get("email") or "").strip()
        if not token_info or not email:
            return None, None
        token_info.setdefault("scopes", GOOGLE_OAUTH_SCOPES)
        token_info["expiry"] = None  # ให้ Gmail API ใช้ refresh_token อัปเดตเอง
        return token_info, email
    except Exception:
        return None, None


def _get_google_oauth_url():
    """สร้าง URL สำหรับไปหน้าเลือกบัญชี Google (OAuth)"""
    import urllib.parse
    import secrets
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        return None
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8502/")
    state = secrets.token_urlsafe(32)
    if "oauth_state" not in st.session_state:
        st.session_state.oauth_state = state
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": st.session_state.oauth_state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def _exchange_oauth_code_for_credentials(code: str):
    """แลก code จาก Google เป็น credentials แล้วได้ email ด้วย"""
    try:
        from google_auth_oauthlib.flow import Flow
        from google.oauth2.credentials import Credentials
        import urllib.request
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8502/")
        if not client_id or not client_secret:
            return None, None
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=GOOGLE_OAUTH_SCOPES,
            redirect_uri=redirect_uri,
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        # เก็บ credentials เป็น dict สำหรับ session_state (ไม่เก็บ object โดยตรง)
        token_info = {
            "token": creds.token,
            "refresh_token": getattr(creds, "refresh_token", None) or "",
            "expiry": getattr(creds, "expiry", None),
            "scopes": creds.scopes or GOOGLE_OAUTH_SCOPES,
        }
        # ดึง email จาก token (id_token ถ้ามี) หรือใช้ People API
        email = None
        if hasattr(creds, "id_token") and creds.id_token:
            import base64
            try:
                payload = creds.id_token.split(".")[1]
                payload += "=" * (4 - len(payload) % 4)
                data = json.loads(base64.urlsafe_b64decode(payload))
                email = data.get("email")
            except Exception:
                pass
        if not email and creds.token:
            try:
                req = urllib.request.Request(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {creds.token}"},
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode())
                    email = data.get("email")
            except Exception:
                pass
        return token_info, email
    except Exception:
        return None, None


def _send_email_via_gmail_api(token_info: dict, from_email: str, to_addr: str, subject: str, body: str) -> tuple[bool, str | None]:
    """ส่งอีเมลด้วย Gmail API (ใช้เมื่อล็อกอินด้วย OAuth) คืน (สำเร็จหรือไม่, ข้อความ error ถ้ามี)"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import base64
        from email.mime.text import MIMEText
        creds = Credentials(
            token=token_info.get("token"),
            refresh_token=token_info.get("refresh_token") or None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=token_info.get("scopes"),
        )
        if getattr(creds, "expired", True) and getattr(creds, "refresh_token", None):
            creds.refresh(Request())
        service = build("gmail", "v1", credentials=creds)
        message = MIMEText(body, "plain", "utf-8")
        message["to"] = to_addr
        message["from"] = from_email
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, None
    except Exception as e:
        return False, str(e)


# ========== Helper Functions ==========

def check_docker():
    """ตรวจสอบว่า Docker และ Docker daemon ทำงานหรือไม่"""
    try:
        # เช็คว่า docker CLI มีอยู่หรือไม่
        result = subprocess.run(
            ['docker', '--version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False

        # เช็คว่า daemon ต่อได้จริงหรือไม่
        info = subprocess.run(
            ['docker', 'info'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return info.returncode == 0
    except Exception:
        return False


def get_statistics(db_path):
    """ดึง statistics จาก database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Total places
        cursor.execute("SELECT COUNT(*) FROM places")
        total_places = cursor.fetchone()[0]
        
        # Status breakdown
        cursor.execute("SELECT status, COUNT(*) FROM places GROUP BY status")
        status_breakdown = dict(cursor.fetchall())
        
        # Total emails
        cursor.execute("SELECT COUNT(*) FROM emails")
        total_emails = cursor.fetchone()[0]
        
        # Source breakdown
        cursor.execute("SELECT source, COUNT(*) FROM emails GROUP BY source")
        source_breakdown = dict(cursor.fetchall())
        
        # 🆕 Discovered URLs
        try:
            cursor.execute("SELECT COUNT(*) FROM discovered_urls")
            total_discovered = cursor.fetchone()[0]
            
            cursor.execute("SELECT status, COUNT(*) FROM discovered_urls GROUP BY status")
            discovered_breakdown = dict(cursor.fetchall())
            
            cursor.execute("SELECT url_type, COUNT(*) FROM discovered_urls GROUP BY url_type")
            discovered_types = dict(cursor.fetchall())
        except:
            total_discovered = 0
            discovered_breakdown = {}
            discovered_types = {}
        
        conn.close()
        
        return {
            'total_places': total_places,
            'status_breakdown': status_breakdown,
            'total_emails': total_emails,
            'source_breakdown': source_breakdown,
            'total_discovered': total_discovered,
            'discovered_breakdown': discovered_breakdown,
            'discovered_types': discovered_types
        }
    except Exception as e:
        return None


def _is_valid_email(s):
    """ตรวจว่า string เป็นรูปแบบอีเมลที่ถูกต้องหรือไม่"""
    if pd.isna(s) or not str(s).strip():
        return False
    s = str(s).strip()
    import re
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", s))


def get_emails_dataframe(db_path):
    """ดึงข้อมูลอีเมลเป็น DataFrame"""
    try:
        conn = sqlite3.connect(db_path)
        query = """
            SELECT 
                e.id,
                p.name AS place_name,
                p.category,
                p.phone,
                p.website,
                p.address,
                e.email,
                e.source,
                datetime(e.created_at, 'unixepoch') AS found_at
            FROM emails e
            JOIN places p ON e.place_id = p.place_id
            ORDER BY e.created_at DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # แยกจังหวัดจาก address (รองรับทั้งภาษาไทยและอังกฤษ)
        def extract_province(addr):
            if not addr or pd.isna(addr):
                return ""
            addr = str(addr).strip()
            
            # Mapping ภาษาอังกฤษ → ภาษาไทย
            province_map = {
                # ภาษาอังกฤษ
                "Bangkok": "กรุงเทพมหานคร",
                "Krabi": "กระบี่",
                "Kanchanaburi": "กาญจนบุรี",
                "Kalasin": "กาฬสินธุ์",
                "Kamphaeng Phet": "กำแพงเพชร",
                "Khon Kaen": "ขอนแก่น",
                "Chanthaburi": "จันทบุรี",
                "Chachoengsao": "ฉะเชิงเทรา",
                "Chonburi": "ชลบุรี", "Chon Buri": "ชลบุรี",
                "Chai Nat": "ชัยนาท",
                "Chaiyaphum": "ชัยภูมิ",
                "Chumphon": "ชุมพร",
                "Chiang Rai": "เชียงราย",
                "Chiang Mai": "เชียงใหม่",
                "Trang": "ตรัง",
                "Trat": "ตราด",
                "Tak": "ตาก",
                "Nakhon Nayok": "นครนายก",
                "Nakhon Pathom": "นครปฐม",
                "Nakhon Phanom": "นครพนม",
                "Nakhon Ratchasima": "นครราชสีมา", "Korat": "นครราชสีมา",
                "Nakhon Si Thammarat": "นครศรีธรรมราช",
                "Nakhon Sawan": "นครสวรรค์",
                "Nonthaburi": "นนทบุรี",
                "Narathiwat": "นราธิวาส",
                "Nan": "น่าน",
                "Bueng Kan": "บึงกาฬ",
                "Buriram": "บุรีรัมย์", "Buri Ram": "บุรีรัมย์",
                "Pathum Thani": "ปทุมธานี",
                "Prachuap Khiri Khan": "ประจวบคีรีขันธ์",
                "Prachinburi": "ปราจีนบุรี", "Prachin Buri": "ปราจีนบุรี",
                "Pattani": "ปัตตานี",
                "Phra Nakhon Si Ayutthaya": "พระนครศรีอยุธยา", "Ayutthaya": "พระนครศรีอยุธยา",
                "Phangnga": "พังงา", "Phang Nga": "พังงา",
                "Phatthalung": "พัทลุง",
                "Phichit": "พิจิตร",
                "Phitsanulok": "พิษณุโลก",
                "Phetchaburi": "เพชรบุรี",
                "Phetchabun": "เพชรบูรณ์",
                "Phrae": "แพร่",
                "Phayao": "พะเยา",
                "Phuket": "ภูเก็ต",
                "Maha Sarakham": "มหาสารคาม",
                "Mukdahan": "มุกดาหาร",
                "Mae Hong Son": "แม่ฮ่องสอน",
                "Yasothon": "ยโสธร",
                "Yala": "ยะลา",
                "Roi Et": "ร้อยเอ็ด",
                "Ranong": "ระนอง",
                "Rayong": "ระยอง",
                "Ratchaburi": "ราชบุรี",
                "Lopburi": "ลพบุรี", "Lop Buri": "ลพบุรี",
                "Lampang": "ลำปาง",
                "Lamphun": "ลำพูน",
                "Loei": "เลย",
                "Si Sa Ket": "ศรีสะเกษ", "Sisaket": "ศรีสะเกษ",
                "Sakon Nakhon": "สกลนคร",
                "Songkhla": "สงขลา",
                "Satun": "สตูล",
                "Samut Prakan": "สมุทรปราการ",
                "Samut Songkhram": "สมุทรสงคราม",
                "Samut Sakhon": "สมุทรสาคร",
                "Sa Kaeo": "สระแก้ว",
                "Saraburi": "สระบุรี", "Sara Buri": "สระบุรี",
                "Sing Buri": "สิงห์บุรี",
                "Sukhothai": "สุโขทัย",
                "Suphan Buri": "สุพรรณบุรี", "Suphanburi": "สุพรรณบุรี",
                "Surat Thani": "สุราษฎร์ธานี",
                "Surin": "สุรินทร์",
                "Nong Khai": "หนองคาย",
                "Nong Bua Lam Phu": "หนองบัวลำภู", "Nong Bua Lamphu": "หนองบัวลำภู",
                "Ang Thong": "อ่างทอง",
                "Udon Thani": "อุดรธานี",
                "Uthai Thani": "อุทัยธานี",
                "Uttaradit": "อุตรดิตถ์",
                "Ubon Ratchathani": "อุบลราชธานี",
                "Amnat Charoen": "อำนาจเจริญ",
                # ภาษาไทยแบบย่อ
                "กรุงเทพฯ": "กรุงเทพมหานคร", "กทม": "กรุงเทพมหานคร", "กทม.": "กรุงเทพมหานคร",
            }
            
            # รายชื่อจังหวัดภาษาไทย (เต็ม)
            thai_provinces = [
                "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น",
                "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ",
                "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก",
                "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช",
                "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ",
                "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี", "ปัตตานี",
                "พระนครศรีอยุธยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก",
                "เพชรบุรี", "เพชรบูรณ์", "แพร่", "พะเยา", "ภูเก็ต",
                "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา",
                "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี",
                "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร",
                "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร",
                "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี",
                "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู",
                "อ่างทอง", "อุดรธานี", "อุทัยธานี", "อุตรดิตถ์", "อุบลราชธานี", "อำนาจเจริญ"
            ]
            
            # ค้นหาจังหวัดภาษาอังกฤษก่อน (case-insensitive)
            addr_lower = addr.lower()
            for eng, thai in province_map.items():
                if eng.lower() in addr_lower:
                    return thai
            
            # ค้นหาจังหวัดภาษาไทย (รวม จ. และ จังหวัด)
            for prov in thai_provinces:
                if prov in addr or f"จ.{prov}" in addr or f"จ. {prov}" in addr or f"จังหวัด{prov}" in addr:
                    return prov
            
            return ""
        
        df["province"] = df["address"].apply(extract_province)
        return df
    except Exception as e:
        return None


def run_subprocess_with_live_output(cmd, placeholder, cwd=None):
    """รัน subprocess และแสดง live output (Windows-compatible)
    ใช้ cwd=PROJECT_ROOT เพื่อให้ path อย่าง output/results.csv, scripts/ ถูกต้อง
    """
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd if cwd is not None else str(PROJECT_ROOT),
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1,
            universal_newlines=True
        )
        
        output_lines = []
        
        # อ่าน output แบบ real-time
        for line in iter(process.stdout.readline, ''):
            if line:
                decoded = line.rstrip()
                output_lines.append(decoded)
                
                # แสดง output ล่าสุด 30 บรรทัด
                display_lines = output_lines[-30:]
                placeholder.code('\n'.join(display_lines))
        
        # รอให้ process เสร็จ
        process.wait()
        
        return process.returncode, output_lines
    except Exception as e:
        return 1, [f"Error: {str(e)}"]


def get_docker_host_path_for_app_mount(container_mount_path: str = "/app") -> str | None:
    """
    When running *inside* the Streamlit container, Docker volume bind mounts in `docker run -v`
    must use a host path (as seen by the Docker daemon), not the container path (e.g. `/app`).

    This attempts to discover the host-side source path for the container mount at `/app`
    by inspecting the current container.
    """
    def _normalize_bind_source_for_linux_docker_cli(src: str) -> str:
        # If the Docker daemon reports a Windows path (e.g. C:\Users\...),
        # the Linux docker CLI inside this container can't parse it due to the drive colon.
        # Convert to Docker Desktop's host mount path that the Linux CLI can use.
        m = re.match(r"^([A-Za-z]):[\\/](.*)$", (src or "").strip())
        if m:
            drive = m.group(1).lower()
            rest = m.group(2).replace("\\", "/")
            return f"/run/desktop/mnt/host/{drive}/{rest}"
        return src

    try:
        container_id = os.getenv("HOSTNAME")  # default to container id in Docker
        if not container_id:
            return None

        result = subprocess.run(
            ["docker", "inspect", container_id],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout:
            return None

        info = json.loads(result.stdout)
        if not info or not isinstance(info, list):
            return None

        mounts = info[0].get("Mounts", []) or []
        for m in mounts:
            if m.get("Destination") == container_mount_path and m.get("Type") == "bind":
                src = m.get("Source")
                if src:
                    return _normalize_bind_source_for_linux_docker_cli(src)
        return None
    except Exception:
        return None


@st.cache_data
def load_th_locations(path: str = TH_LOCATIONS_FILE):
    """Load consolidated Thai locations mapping: region -> province -> [amphoe/district]."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_location_suffix_required(region: str, province: str, amphoe_or_district: str) -> str:
    """Require location down to amphoe/district; return '' if not fully selected."""
    region = (region or "").strip()
    province = (province or "").strip()
    amphoe_or_district = (amphoe_or_district or "").strip()
    if not region or region == "—":
        return ""
    if not province or province == "—":
        return ""
    if not amphoe_or_district or amphoe_or_district == "—":
        return ""
    # Query suffix: prefer most specific first
    return f"{amphoe_or_district} {province}".strip()


# ========== Streamlit App ==========

MODERN_VIVID_CSS = """
<style>
  /* Modern Vivid (B3) - light dashboard look */
  /* Streamlit has a fixed header; add extra top padding to prevent clipping */
  .block-container { padding-top: 3.25rem; padding-bottom: 2rem; }
  .mv-header {
    display:flex; align-items:flex-start; justify-content:space-between;
    gap: 1rem; margin-bottom: .75rem;
  }
  .mv-title { font-size: 1.55rem; font-weight: 750; color: #0F172A; line-height: 1.1; }
  .mv-subtitle { color: #475569; margin-top: .25rem; }
  .mv-badges { display:flex; gap: .5rem; flex-wrap:wrap; justify-content:flex-end; }
  .mv-badge {
    display:inline-flex; align-items:center; gap:.35rem;
    padding: .25rem .55rem; border-radius: 999px;
    font-size: .85rem; font-weight: 650;
    border: 1px solid #E2E8F0; background: #FFFFFF;
  }
  .mv-badge.ok { color:#166534; background:#ECFDF5; border-color:#BBF7D0; }
  .mv-badge.warn { color:#92400E; background:#FFFBEB; border-color:#FDE68A; }
  .mv-badge.bad { color:#991B1B; background:#FEF2F2; border-color:#FECACA; }
  .mv-badge.info { color:#075985; background:#ECFEFF; border-color:#A5F3FC; }
  .mv-card-title { font-size: 1.05rem; font-weight: 750; color:#0F172A; margin-bottom: .15rem; }
  .mv-card-help { color:#64748B; margin-bottom: .5rem; }
  .mv-kpi-label { color:#475569; font-weight:650; }
  .mv-muted { color:#64748B; }
  .mv-divider { height: 1px; background: #E2E8F0; margin: .75rem 0; }

  /* Gmail login button - ใช้ :has() เพราะปุ่มไม่อยู่ใน div เดียวกับ marker ใน Streamlit */
  div[data-testid="stMainBlockContainer"]:has(#gmail-login-section) [data-testid="stButton"] button {
    width: 100% !important;
    max-width: 320px !important;
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    color: #1f2937 !important;
    border: 1.5px solid #d1d5db !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 0.6rem 1rem !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0.6rem !important;
    box-shadow: none !important;
  }
  div[data-testid="stMainBlockContainer"]:has(#gmail-login-section) [data-testid="stButton"] button:hover,
  div[data-testid="stMainBlockContainer"]:has(#gmail-login-section) [data-testid="stButton"] button:focus,
  div[data-testid="stMainBlockContainer"]:has(#gmail-login-section) [data-testid="stButton"] button:active {
    background: #f9fafb !important;
    background-color: #f9fafb !important;
    border-color: #9ca3af !important;
    color: #111827 !important;
  }
</style>
"""


def inject_modern_vivid_css():
    st.markdown(MODERN_VIVID_CSS, unsafe_allow_html=True)


def _badge(label: str, state: str):
    cls = state if state in {"ok", "warn", "bad", "info"} else "info"
    st.markdown(f"<span class='mv-badge {cls}'>{label}</span>", unsafe_allow_html=True)


def page_header(title: str, subtitle: str, badges: list[tuple[str, str]]):
    badge_html = "".join([f"<span class='mv-badge {s}'>{t}</span>" for (t, s) in badges])
    st.markdown(
        f"""
        <div class="mv-header">
          <div>
            <div class="mv-title">{title}</div>
            <div class="mv-subtitle">{subtitle}</div>
          </div>
          <div class="mv-badges">{badge_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def card(title: str, icon: str = "", help_text: str | None = None):
    with st.container(border=True):
        st.markdown(f"<div class='mv-card-title'>{icon} {title}</div>", unsafe_allow_html=True)
        if help_text:
            st.markdown(f"<div class='mv-card-help'>{help_text}</div>", unsafe_allow_html=True)
        yield


def _nav_set(page_value: str):
    """Set pending navigation - will be applied on next rerun"""
    st.session_state._pending_nav = page_value
    st.rerun()


def render_sidebar_nav(docker_ok: bool, db_exists: bool, loc_ok: bool):
    # Check for pending navigation (must be before widget creation)
    if "_pending_nav" in st.session_state:
        pending = st.session_state._pending_nav
        del st.session_state._pending_nav
        st.session_state.nav_page = pending
    
    with st.sidebar:
        st.markdown("### 🧭 Navigation")
        page = st.radio(
            "ไปที่หน้า",
            ["🏠 Dashboard", "🚀 Pipeline Runner", "📊 Results", "📬 Emails", "🎫 Check-in", "🧰 Tools & Settings", "🔐 Login Gmail"],
            key="nav_page",
            label_visibility="collapsed",
        )

        gmail_ok = bool(
            st.session_state.get("gmail_logged_in")
            and (st.session_state.get("smtp_user") or st.session_state.get("gmail_oauth_credentials"))
        )
        _badge(f"📧 Gmail: {'ล็อกอินแล้ว' if gmail_ok else 'ยังไม่ล็อกอิน'}", "ok" if gmail_ok else "warn")

        st.markdown("### ✅ Status")
        _badge(f"🐳 Docker: {'Running' if docker_ok else 'Down'}", "ok" if docker_ok else "bad")
        _badge(f"💾 DB: {'Ready' if db_exists else 'Empty'}", "ok" if db_exists else "warn")
        _badge(f"🧭 Dataset: {'OK' if loc_ok else 'Missing'}", "ok" if loc_ok else "warn")

        st.markdown("### ⚡ Quick")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Run", width="stretch"):
                _nav_set("🚀 Pipeline Runner")
        with col2:
            if st.button("📊 Results", width="stretch"):
                _nav_set("📊 Results")

        st.markdown("<div class='mv-divider'></div>", unsafe_allow_html=True)
        with st.expander("🔎 Debug", expanded=False):
            try:
                st.caption("Running file:")
                st.code(str(Path(__file__).resolve()))
            except Exception:
                st.caption("Running file: (unknown)")
            st.write({"TH_LOCATIONS_FILE": TH_LOCATIONS_FILE, "exists": Path(TH_LOCATIONS_FILE).exists()})
    return page


def render_login_gmail(docker_ok: bool, db_exists: bool, loc_ok: bool):
    """หน้า Login Gmail แยกต่างหาก — ใส่อีเมล + App Password แล้วใช้ส่งอีเมลจากหน้า Results ได้"""
    st.markdown("<div class='page-login-gmail'>", unsafe_allow_html=True)
    badges = [
        (f"📧 Gmail: {'ล็อกอินแล้ว' if st.session_state.get('gmail_logged_in') else 'ยังไม่ล็อกอิน'}", "ok" if st.session_state.get("gmail_logged_in") else "warn"),
    ]
    page_header("🔐 Login Gmail", "ล็อกอินด้วย Google (OAuth) เพื่อใช้ส่งอีเมลไปยังรายการที่เลือก", badges)

    logged_in = st.session_state.get("gmail_logged_in") and (
        st.session_state.get("smtp_user") or st.session_state.get("gmail_oauth_credentials")
    )
    if logged_in:
        with card("✅ สถานะล็อกอิน", help_text="คุณล็อกอินแล้ว — ไปที่ Results Explorer → Emails → ส่งข้อความไปยังอีเมลที่เลือก ได้เลย"):
            email_display = st.session_state.get("smtp_user") or st.session_state.get("gmail_oauth_email") or ""
            mode = "OAuth (เลือกบัญชี Google)" if st.session_state.get("gmail_oauth_credentials") else "อีเมล + App Password"
            st.success(f"ล็อกอินเป็น: **{email_display}** ({mode})")
            st.caption("ข้อมูลเก็บใน session และไฟล์ .gmail_oauth.json — ปิดแอปแล้วเปิดใหม่ไม่ต้องล็อกอินใหม่")
            if st.button("🚪 ออกจากระบบ (Logout)", type="secondary", key="btn_gmail_logout"):
                for k in ("gmail_logged_in", "smtp_user", "smtp_password", "gmail_oauth_credentials", "gmail_oauth_email", "oauth_state"):
                    if k in st.session_state:
                        del st.session_state[k]
                try:
                    if Path(OAUTH_TOKEN_FILE).exists():
                        Path(OAUTH_TOKEN_FILE).unlink()
                except Exception:
                    pass
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    with card("🔐 ล็อกอิน Gmail", help_text="ใช้บัญชี Gmail ที่ต้องการส่งอีเมล — ล็อกอินด้วย Google (OAuth) เท่านั้น"):
        st.markdown("<span id='gmail-login-section' style='display:none' aria-hidden='true'></span>", unsafe_allow_html=True)

        oauth_url = _get_google_oauth_url()
        if oauth_url:
            st.markdown("**▶ เลือกบัญชี Google**")
            st.link_button("🔐 ลงชื่อเข้าใช้ด้วย Google — เลือกบัญชี", url=oauth_url, type="primary")
            st.caption("กดปุ่มด้านบน → ไปหน้า Google เลือกบัญชี → กลับมาที่แอปอัตโนมัติ")
        else:
            st.warning("ตั้งค่า **GOOGLE_CLIENT_ID** และ **GOOGLE_CLIENT_SECRET** ใน `.env` เพื่อใช้ปุ่มลงชื่อเข้าใช้ด้วย Google (ดู README)")

    st.markdown("</div>", unsafe_allow_html=True)


def render_query_builder(loc_ok: bool):
    # Location dataset
    if not loc_ok:
        th_locations = {}
    else:
        th_locations = load_th_locations(TH_LOCATIONS_FILE)

    region_options = ["—"] + (sorted(th_locations.keys()) if th_locations else [])
    region = st.selectbox("ภาค", region_options, key="loc_region_dd")

    province_options = []
    if region != "—" and region in th_locations:
        province_options = sorted(th_locations[region].keys())
    province = st.selectbox("จังหวัด", ["—"] + province_options, key="loc_province_dd", disabled=(region == "—"))

    amphoe_label = "เขต/อำเภอ"
    amphoe_options = []
    if region != "—" and province != "—":
        if region == "กรุงเทพมหานคร" or province == "กรุงเทพมหานคร":
            amphoe_label = "เขต"
        else:
            amphoe_label = "อำเภอ"
        amphoe_options = th_locations.get(region, {}).get(province, [])

    amphoe_or_district = st.selectbox(
        amphoe_label,
        ["—"] + amphoe_options,
        key="loc_amphoe_dd",
        disabled=(province == "—"),
    )

    loc_suffix = build_location_suffix_required(region, province, amphoe_or_district)
    st.session_state.loc_suffix = loc_suffix

    want_text = st.text_input(
        "สิ่งที่ต้องการค้นหา (เช่น ร้านอาหาร/โรงแรม/โรงเรียน)",
        placeholder="พิมพ์ประเภทสถานที่ที่ต้องการ",
        key="want_text",
        disabled=(not loc_suffix),
    )

    built_query = ""
    if want_text and loc_suffix:
        built_query = f"{want_text.strip()} {loc_suffix}".strip()
    st.session_state.built_query = built_query
    return loc_suffix, built_query


def render_dashboard(docker_ok: bool, db_exists: bool, loc_ok: bool):
    badges = [
        (f"🐳 Docker: {'Running' if docker_ok else 'Down'}", "ok" if docker_ok else "bad"),
        (f"💾 DB: {'Ready' if db_exists else 'Empty'}", "ok" if db_exists else "warn"),
        (f"🧭 Dataset: {'OK' if loc_ok else 'Missing'}", "ok" if loc_ok else "warn"),
    ]
    page_header("🏠 Dashboard", "ภาพรวมสถานะระบบ + ผลลัพธ์ล่าสุด", badges)

    stats = get_statistics(DB_FILE) if db_exists else None
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Places", (stats or {}).get("total_places", 0))
    with col2:
        st.metric("Emails", (stats or {}).get("total_emails", 0))
    with col3:
        st.metric("Discovered URLs", (stats or {}).get("total_discovered", 0))
    with col4:
        success_rate = 0.0
        if stats and stats.get("total_places", 0) > 0:
            done = stats.get("status_breakdown", {}).get("DONE", 0)
            success_rate = (done / stats["total_places"]) * 100
        st.metric("Success Rate", f"{success_rate:.1f}%")

    c1, c2 = st.columns([2, 1])
    with c1:
        with card("🚀 Quick start", help_text="เริ่มจาก Runner แล้วค่อยไปดูผลใน Results"):
            colA, colB = st.columns(2)
            with colA:
                if st.button("ไปหน้า 🚀 Pipeline Runner", type="primary", width="stretch"):
                    _nav_set("🚀 Pipeline Runner")
            with colB:
                if st.button("ไปหน้า 📊 Results", width="stretch"):
                    _nav_set("📊 Results")
            st.markdown("<div class='mv-divider'></div>", unsafe_allow_html=True)
            st.caption("Last query:")
            st.code(st.session_state.get("built_query", "") or "(ยังไม่มี)")

    with c2:
        with card("⚠️ Health & warnings", help_text="ถ้าขึ้นเตือน แนะนำแก้ก่อนเริ่มรัน"):
            if not docker_ok:
                st.error("Docker ไม่ทำงาน — กรุณาเปิด Docker Desktop")
            if not loc_ok:
                st.warning(f"ไม่พบไฟล์พื้นที่: `{TH_LOCATIONS_FILE}`")
                st.caption("ให้แน่ใจว่ามีไฟล์ `data/th_locations.json` ในโปรเจกต์")
            if not db_exists:
                st.info("ยังไม่มีฐานข้อมูล `pipeline.db` — ให้เริ่มรัน Stage 1 ก่อน")


def render_runner(docker_ok: bool, db_exists: bool, loc_ok: bool):
    badges = [
        (f"🐳 Docker: {'Running' if docker_ok else 'Down'}", "ok" if docker_ok else "bad"),
        (f"💾 DB: {'Ready' if db_exists else 'Empty'}", "ok" if db_exists else "warn"),
    ]
    page_header("🚀 Pipeline Runner", "ตั้งค่า Query → เลือก Stages → รันแบบ live log", badges)

    left, right = st.columns([2.2, 1])
    with left:
        with card("🧭 Query Builder", help_text="ต้องเลือกถึงเขต/อำเภอ แล้วใส่ประเภทสถานที่"):
            if not loc_ok:
                st.error(f"ไม่พบไฟล์พื้นที่: `{TH_LOCATIONS_FILE}`")
                st.info("ให้แน่ใจว่ามีไฟล์ `data/th_locations.json` ในโปรเจกต์")
            loc_suffix, built_query = render_query_builder(loc_ok)
            if built_query:
                st.success(f"Query ที่จะใช้: {built_query}")
            else:
                st.warning("กรุณาเลือกพื้นที่และใส่สิ่งที่ต้องการค้นหา")

        with card("⚙️ Runner Settings", help_text="ค่าเหล่านี้ใช้ตอนรัน Stage 1–4"):
            st.info("🐳 ใช้ Docker (gosom) Scraper เป็นค่าเริ่มต้น")
            depth = st.selectbox(
                "Search Depth",
                options=[1, 2, 3, 4, 5],
                index=1,
                key="runner_depth",
                help="Depth 2 แนะนำสำหรับเริ่มต้น",
            )
            # Force sequential execution (more stable on Windows)
            run_parallel = False
            st.session_state["runner_parallel"] = False
            st.caption("โหมดการรัน: **Sequential (บังคับใช้เพื่อความเสถียร)**")
            st.caption("รัน **Stage 1–4 ครบทุกครั้ง** (ไม่มีการเลือก stage)")

        # บังคับรันครบ 4 stages ทุกครั้ง
        run_stage1 = run_stage2 = run_stage3 = run_stage4 = True

        disable_start = (not docker_ok) or (not st.session_state.get("built_query"))
        if not docker_ok:
            st.error("Docker ไม่ทำงาน — กรุณาเปิด Docker Desktop ก่อน")

        if st.button("▶️ START PIPELINE", type="primary", width="stretch", disabled=disable_start):
            built_query = st.session_state.get("built_query", "")
            try:
                with open(QUERIES_FILE, "w", encoding="utf-8") as f:
                    f.write(built_query)
                st.info(f"📝 ใช้ Query: **{built_query}**")
            except Exception as e:
                st.error(f"❌ Error creating queries file: {e}")
                st.stop()

            # ========== Stage 1 ==========
            if run_stage1:
                st.info(
                    "⏳ **Stage 1 ครั้งแรก:** ถ้าขึ้น log `Downloading driver path=/opt` ให้รอ **5–15 นาที** "
                    "(ดาวน์โหลด Chrome ใน container) ครั้งถัดไปจะเร็วขึ้นมาก — อย่าปิดหรือหยุดรัน"
                )
                with st.status("🔄 Stage 1: Google Maps Scraper (Docker)", expanded=True) as status:
                    output_placeholder = st.empty()

                    host_project_dir = get_docker_host_path_for_app_mount("/app")
                    cwd_str = host_project_dir or str(PROJECT_ROOT)

                    results_path = Path(RESULTS_CSV)
                    results_path.parent.mkdir(parents=True, exist_ok=True)
                    if not results_path.exists():
                        results_path.touch()

                    cmd = [
                        "docker",
                        "run",
                        "--rm",
                        "-v",
                        f"{cwd_str}:/work",
                        "gosom/google-maps-scraper",
                        "-input",
                        f"/work/{QUERIES_FILE}",
                        "-results",
                        f"/work/{RESULTS_CSV}",
                        "-depth",
                        str(depth),
                        "-exit-on-inactivity",
                        "3m",
                    ]

                    returncode, _output = run_subprocess_with_live_output(cmd, output_placeholder)
                    if returncode == 0:
                        status.update(label="✅ Stage 1: Scraping สำเร็จ", state="complete")
                        st.success(f"✅ Scraping สำเร็จ → {RESULTS_CSV}")
                    else:
                        status.update(label="❌ Stage 1: Scraping ล้มเหลว", state="error")
                        st.error("❌ Scraping ล้มเหลว")
                        st.stop()

                with st.status("🔄 Stage 1: CSV → SQLite", expanded=False) as status:
                    output_placeholder = st.empty()
                    cmd = ["python", "scripts/csv_to_sqlite.py", str(PROJECT_ROOT / RESULTS_CSV), str(PROJECT_ROOT / DB_FILE)]
                    returncode, _output = run_subprocess_with_live_output(cmd, output_placeholder)
                    if returncode == 0:
                        status.update(label="✅ CSV → SQLite สำเร็จ", state="complete")
                        st.success(f"✅ แปลงสำเร็จ → {DB_FILE}")
                    else:
                        status.update(label="❌ CSV → SQLite ล้มเหลว", state="error")
                        st.error("❌ แปลงล้มเหลว")
                        st.stop()

            # ========== Stage 2 & 3 ==========
            if run_stage2 or run_stage3:
                st.markdown("<div class='mv-divider'></div>", unsafe_allow_html=True)
                if run_parallel and run_stage2 and run_stage3:
                    with st.status("⚡ Stage 2 & 3: Parallel execution", expanded=True) as status:
                        cmd = ["python", "scripts/run_parallel.py"]
                        returncode, _output = run_subprocess_with_live_output(cmd, st.empty())
                        if returncode == 0:
                            status.update(label="✅ Parallel execution สำเร็จ", state="complete")
                            st.success("✅ Parallel execution สำเร็จ")
                        else:
                            status.update(label="❌ Parallel execution ล้มเหลว", state="error")
                            st.error("❌ Parallel execution ล้มเหลว")
                            st.stop()
                else:
                    if run_stage2:
                        with st.status("🌐 Stage 2: Website Email Finder", expanded=True) as status:
                            output_placeholder = st.empty()
                            cmd = ["python", "stage2_email_finder.py", "--db", str(PROJECT_ROOT / DB_FILE), "--verbose"]
                            returncode, _output = run_subprocess_with_live_output(cmd, output_placeholder)
                            if returncode == 0:
                                status.update(label="✅ Stage 2 สำเร็จ", state="complete")
                            else:
                                status.update(label="❌ Stage 2 ล้มเหลว", state="error")
                                st.stop()

                    if run_stage3:
                        with st.status("📘 Stage 3: Facebook Scraper", expanded=True) as status:
                            output_placeholder = st.empty()
                            cmd = ["python", "facebook_about_scraper.py", "--db", str(PROJECT_ROOT / DB_FILE), "--verbose"]
                            returncode, _output = run_subprocess_with_live_output(cmd, output_placeholder)
                            if returncode == 0:
                                status.update(label="✅ Stage 3 สำเร็จ", state="complete")
                            else:
                                status.update(label="❌ Stage 3 ล้มเหลว", state="error")
                                st.stop()

            # ========== Stage 4 ==========
            if run_stage4:
                with st.status("🔗 Stage 4: Cross-Reference Scraper", expanded=True) as status:
                    output_placeholder = st.empty()
                    cmd = ["python", "stage4_crossref_scraper.py", "--db", str(PROJECT_ROOT / DB_FILE), "--verbose"]
                    returncode, _output = run_subprocess_with_live_output(cmd, output_placeholder)
                    if returncode == 0:
                        status.update(label="✅ Stage 4 สำเร็จ", state="complete")
                    else:
                        status.update(label="❌ Stage 4 ล้มเหลว", state="error")

            # ========== กรองอีเมลไม่ถูกต้องทิ้ง ==========
            with st.status("🧹 กรองอีเมลไม่ถูกต้องทิ้ง", expanded=False) as status:
                try:
                    conn = sqlite3.connect(str(PROJECT_ROOT / DB_FILE))
                    cursor = conn.execute("SELECT id, email FROM emails")
                    rows = cursor.fetchall()
                    deleted = 0
                    for row in rows:
                        eid, email = row[0], (row[1] or "").strip()
                        if not _is_valid_email(email):
                            conn.execute("DELETE FROM emails WHERE id = ?", (eid,))
                            deleted += 1
                    conn.commit()
                    conn.close()
                    if deleted > 0:
                        status.update(label=f"✅ กรองอีเมลไม่ถูกต้องทิ้งแล้ว {deleted} รายการ", state="complete")
                        st.caption(f"ลบอีเมลรูปแบบไม่ถูกต้องออกจาก DB แล้ว {deleted} รายการ")
                    else:
                        status.update(label="✅ ไม่มีอีเมลที่ไม่ถูกต้อง", state="complete")
                except Exception as e:
                    status.update(label="⚠️ กรองอีเมลข้าม", state="complete")
                    st.caption(f"ข้ามขั้นตอนกรอง: {e}")

            st.success("🎉 Pipeline เสร็จสิ้น! ไปดูผลต่อได้ที่หน้า Results Explorer")
            st.balloons()

    with right:
        with card("💡 Tips", help_text="เริ่มง่าย ๆ ก่อนแล้วค่อยเพิ่มความลึก"):
            st.caption("- เริ่มที่ Depth 2")
            st.caption("- รันแบบ Sequential ถูกบังคับใช้เพื่อความเสถียร")
            st.caption("- ให้แน่ใจว่ามีไฟล์ `data/th_locations.json` ในโปรเจกต์")


def render_emails(docker_ok: bool, db_exists: bool, loc_ok: bool):
    """หน้า Emails แยกต่างหาก - เลือก/กรอง/ส่งอีเมล"""
    badges = [
        (f"💾 DB: {'Ready' if db_exists else 'Empty'}", "ok" if db_exists else "warn"),
    ]
    page_header("📬 Emails", "เลือกรายการอีเมล + กรอง + Export + ส่งข้อความ", badges)
    
    if not db_exists:
        with card("🧾 Empty state", help_text="ยังไม่มีฐานข้อมูล — รัน Stage 1 ก่อน"):
            st.info("ℹ️ ยังไม่มีข้อมูล - กรุณารัน Pipeline ก่อน")
        return
    
    # แสดง metrics
    stats = get_statistics(DB_FILE)
    if stats:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Emails ทั้งหมด", stats["total_emails"])
        with col2:
            selected_count = len(st.session_state.get("selected_email_ids", set()))
            st.metric("เลือกแล้ว", selected_count)
        with col3:
            st.caption("เลือก email แล้วไปหน้า 🎫 Check-in")
    
    with card("📬 รายการ Emails", help_text="เลือกรายการอีเมลที่ต้องการ แล้ว Export หรือส่งข้อความได้"):
        df = get_emails_dataframe(DB_FILE)
        if df is None or len(df) == 0:
            st.info("ยังไม่มีอีเมลในฐานข้อมูล")
        else:
            # ดึงรายการ email ที่ส่งแล้ว, เข้าดู, blocked, interested (สำหรับ filter)
            sent_emails_for_filter = set()
            viewed_emails_for_filter = set()  # กดลิงก์เข้ามาดูแต่ไม่ตอบ
            blocked_emails_for_filter = set()
            interested_emails_for_filter = set()
            try:
                # ดึง tokens (ส่งแล้ว + เข้าดู)
                r = requests.get(f"{get_checkin_api_url()}/api/tokens", timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    tokens_list = data.get("tokens", []) if isinstance(data, dict) else data
                    sent_emails_for_filter = set(t.get("email", "").lower() for t in tokens_list if t.get("email"))
                    # เข้าดู = token ถูกใช้แล้ว (used=true)
                    viewed_emails_for_filter = set(t.get("email", "").lower() for t in tokens_list if t.get("email") and t.get("used"))
                
                # ดึง responses (interested/unsubscribed)
                r2 = requests.get(f"{get_checkin_api_url()}/api/responses", timeout=3)
                if r2.status_code == 200:
                    resp_data = r2.json()
                    # Blocked = unsubscribed
                    unsubscribed_list = resp_data.get("unsubscribed", [])
                    blocked_emails_for_filter = set(u.get("email", "").lower() for u in unsubscribed_list if u.get("email"))
                    # Interested
                    interested_list = resp_data.get("interested", [])
                    interested_emails_for_filter = set(i.get("email", "").lower() for i in interested_list if i.get("email"))
            except:
                pass
            
            # ฟิลเตอร์
            st.markdown("**🔍 ฟิลเตอร์**")
            f1, f2, f3, f4, f5, f6 = st.columns(6)
            with f1:
                search_emails = st.text_input("ค้นหา", key="emails_filter_search_page", placeholder="ชื่อ/อีเมล...")
            with f2:
                provinces = ["All"] + sorted([p for p in df["province"].dropna().unique().tolist() if p])
                filter_province = st.selectbox("จังหวัด", provinces, key="emails_filter_province_page")
            with f3:
                categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
                filter_category = st.selectbox("Category", categories, key="emails_filter_category_page")
            with f4:
                sources = ["All"] + sorted(df["source"].dropna().unique().tolist())
                filter_source = st.selectbox("Source", sources, key="emails_filter_source_page")
            with f5:
                filter_valid = st.selectbox(
                    "อีเมล",
                    ["All", "ถูกต้อง", "ไม่ถูกต้อง"],
                    key="emails_filter_valid_page",
                )
            with f6:
                filter_sent = st.selectbox(
                    "สถานะ",
                    ["All", "ยังไม่ส่ง", "ส่งแล้ว", "เข้าดู", "สนใจ", "Blocked"],
                    key="emails_filter_sent_page",
                )

            filtered_df = df.copy()
            if search_emails and search_emails.strip():
                q = search_emails.strip().lower()
                mask = (
                    filtered_df["place_name"].astype(str).str.lower().str.contains(q, na=False)
                    | filtered_df["email"].astype(str).str.lower().str.contains(q, na=False)
                    | filtered_df["category"].astype(str).str.lower().str.contains(q, na=False)
                    | filtered_df["address"].astype(str).str.lower().str.contains(q, na=False)
                )
                filtered_df = filtered_df[mask]
            if filter_province != "All":
                filtered_df = filtered_df[filtered_df["province"] == filter_province]
            if filter_source != "All":
                filtered_df = filtered_df[filtered_df["source"] == filter_source]
            if filter_category != "All":
                filtered_df = filtered_df[filtered_df["category"] == filter_category]
            if filter_valid == "ถูกต้อง":
                filtered_df = filtered_df[filtered_df["email"].apply(_is_valid_email)]
            elif filter_valid == "ไม่ถูกต้อง":
                filtered_df = filtered_df[~filtered_df["email"].apply(_is_valid_email)]
            
            # Filter by sent/blocked status
            if filter_sent == "ส่งแล้ว":
                filtered_df = filtered_df[filtered_df["email"].str.lower().isin(sent_emails_for_filter)]
            elif filter_sent == "ยังไม่ส่ง":
                filtered_df = filtered_df[~filtered_df["email"].str.lower().isin(sent_emails_for_filter)]
            elif filter_sent == "เข้าดู":
                # เข้าดู = กดลิงก์แล้วแต่ยังไม่ตอบ (ไม่ใช่ interested หรือ blocked)
                viewed_only = viewed_emails_for_filter - interested_emails_for_filter - blocked_emails_for_filter
                filtered_df = filtered_df[filtered_df["email"].str.lower().isin(viewed_only)]
            elif filter_sent == "สนใจ":
                filtered_df = filtered_df[filtered_df["email"].str.lower().isin(interested_emails_for_filter)]
            elif filter_sent == "Blocked":
                filtered_df = filtered_df[filtered_df["email"].str.lower().isin(blocked_emails_for_filter)]

            invalid_count = (~df["email"].apply(_is_valid_email)).sum()
            st.caption(f"แสดง **{len(filtered_df)}** จาก **{len(df)}** รายการ" + (f" · อีเมลไม่ถูกต้อง **{invalid_count}** รายการ" if invalid_count > 0 else ""))
            
            # สร้าง key ที่เปลี่ยนตามฟิลเตอร์
            filter_key = f"{search_emails}_{filter_province}_{filter_source}_{filter_category}_{filter_valid}_{filter_sent}_{len(filtered_df)}"
            
            # ========== AgGrid (เร็วกว่า data_editor) ==========
            # ใช้ข้อมูลที่ดึงมาแล้วด้านบน
            sent_emails = sent_emails_for_filter
            viewed_emails = viewed_emails_for_filter
            blocked_emails = blocked_emails_for_filter
            interested_emails = interested_emails_for_filter
            display_df = filtered_df[["id", "place_name", "phone", "email", "category", "province", "source", "website"]].copy()
            display_df = display_df.reset_index(drop=True)  # Reset index ให้เลขต่อเนื่อง
            display_df.insert(0, "ลำดับ", range(1, len(display_df) + 1))  # เพิ่มเลขลำดับ 1, 2, 3...
            
            # รวม Source + Link เป็นคอลัมน์เดียว (เช่น "WEBSITE 🔗" หรือ "FACEBOOK 🔗")
            def combine_source_link(row):
                source = str(row["source"]) if row["source"] and not pd.isna(row["source"]) else ""
                website = str(row["website"]) if row["website"] and not pd.isna(row["website"]) else ""
                if website.strip():
                    return f"{source} 🔗"
                return source
            
            display_df["แหล่งที่มา"] = display_df.apply(combine_source_link, axis=1)
            # เก็บ website ไว้ใน _website สำหรับใช้เปิดลิงก์ (ซ่อน)
            display_df["_website"] = filtered_df["website"].values
            
            # เพิ่มคอลัมน์สถานะ (Blocked > สนใจ > เข้าดู > ส่งแล้ว)
            def get_status(email):
                email_lower = str(email).lower()
                if email_lower in blocked_emails:
                    return "🚫 Blocked"
                elif email_lower in interested_emails:
                    return "💚 สนใจ"
                elif email_lower in viewed_emails:
                    return "👁️ เข้าดู"
                elif email_lower in sent_emails:
                    return "✅ ส่งแล้ว"
                return ""
            
            display_df["สถานะ"] = display_df["email"].apply(get_status)
            
            # สร้าง GridOptions
            gb = GridOptionsBuilder.from_dataframe(display_df)
            gb.configure_default_column(resizable=True, filterable=True, sortable=True, editable=True)
            gb.configure_column("ลำดับ", headerName="#", width=45, editable=False)
            gb.configure_column("id", headerName="ID", width=50, editable=False)
            gb.configure_column("place_name", headerName="ชื่อสถานที่", width=140, editable=True)
            gb.configure_column("phone", headerName="เบอร์โทร", width=100, editable=True)
            gb.configure_column("email", headerName="Email", width=160, editable=True)
            gb.configure_column("category", headerName="Category", width=85, editable=True)
            gb.configure_column("province", headerName="จังหวัด", width=75, editable=False)
            gb.configure_column("source", hide=True)  # ซ่อน
            gb.configure_column("website", hide=True)  # ซ่อน
            gb.configure_column("_website", hide=True)  # ซ่อน
            # แสดงข้อความ "WEBSITE 🔗" ธรรมดา (ไม่ใช้ HTML ใน cell เพราะ streamlit-aggrid แสดงเป็นข้อความ)
            gb.configure_column("แหล่งที่มา", headerName="แหล่งที่มา", width=90, editable=False)
            gb.configure_column("สถานะ", headerName="สถานะ", width=75, editable=False)
            gb.configure_selection(
                selection_mode="multiple",
                use_checkbox=True,
                header_checkbox=True,  # checkbox ที่ header เพื่อเลือกทั้งหมด
            )
            gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=50)
            grid_options = gb.build()
            # คลิกที่เซลล์ "แหล่งที่มา" → เปิด URL ในแท็บใหม่ (streamlit-aggrid ไม่ render HTML ใน cell จึงใช้ onCellClicked แทน)
            grid_options["onCellClicked"] = JsCode("""
                function(event) {
                    if (event.colDef && event.colDef.field === 'แหล่งที่มา' && event.data && event.data._website) {
                        var url = String(event.data._website).trim();
                        if (url) window.open(url, '_blank', 'noopener');
                    }
                }
            """)

            # แสดง AgGrid
            grid_response = AgGrid(
                display_df,
                gridOptions=grid_options,
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                update_mode=GridUpdateMode.MODEL_CHANGED,
                fit_columns_on_grid_load=True,
                theme="streamlit",
                height=400,
                allow_unsafe_jscode=True,
                key=f"emails_aggrid_{hash(filter_key)}",
                reload_data=True,
            )
            
            # ดึงแถวที่เลือก
            # ดึงข้อมูลที่แก้ไขแล้ว
            edited_data = grid_response.get("data", None)
            if edited_data is not None:
                if isinstance(edited_data, pd.DataFrame):
                    edited_df = edited_data
                else:
                    edited_df = pd.DataFrame(edited_data)
            else:
                edited_df = display_df
            
            selected_rows = grid_response.get("selected_rows", None)
            if selected_rows is not None and len(selected_rows) > 0:
                if isinstance(selected_rows, pd.DataFrame):
                    selected_df = selected_rows
                else:
                    selected_df = pd.DataFrame(selected_rows)
                selected_count = len(selected_df)
                selected_emails = selected_df["email"].dropna().unique().tolist()
                all_selected_df = selected_df
                
                # แสดงลิงก์ website ของแถวที่เลือก (ดึงจาก filtered_df ที่มี URL เต็ม)
                selected_ids = selected_df["id"].tolist()
                selected_with_links = filtered_df[filtered_df["id"].isin(selected_ids)][["place_name", "website", "source"]].dropna(subset=["website"])
                selected_with_links = selected_with_links[selected_with_links["website"].str.strip() != ""]
                if len(selected_with_links) > 0:
                    with st.expander(f"🔗 เปิดเว็บไซต์ ({len(selected_with_links)} ลิงก์)", expanded=True):
                        for _, row in selected_with_links.iterrows():
                            source = row.get('source', '')
                            st.markdown(f"[{source} 🔗 {row['place_name']}]({row['website']})")
            else:
                selected_count = 0
                selected_emails = []
                all_selected_df = pd.DataFrame()
            
            # ========== ปุ่มบันทึกการแก้ไข ==========
            save_col1, save_col2 = st.columns([1, 3])
            with save_col1:
                if st.button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True, key="save_edits_btn"):
                    try:
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        updated_count = 0
                        for _, row in edited_df.iterrows():
                            row_id = int(row["id"])
                            # อัพเดท email ในตาราง emails
                            cursor.execute("""
                                UPDATE emails SET email = ? WHERE id = ?
                            """, (row["email"], row_id))
                            # อัพเดท place_name, phone และ category ในตาราง places
                            cursor.execute("""
                                UPDATE places 
                                SET name = ?, phone = ?, category = ?
                                WHERE place_id = (SELECT place_id FROM emails WHERE id = ?)
                            """, (row["place_name"], row.get("phone", ""), row["category"], row_id))
                            updated_count += 1
                        conn.commit()
                        conn.close()
                        st.success(f"บันทึกสำเร็จ {updated_count} รายการ")
                        st.rerun()
                    except Exception as e:
                        st.error(f"บันทึกไม่สำเร็จ: {e}")
            with save_col2:
                st.caption(f"เลือกแล้ว **{selected_count}** รายการ (อีเมลไม่ซ้ำ **{len(selected_emails)}** ที่อยู่)")

            # Export buttons
            col_export1, col_export2, col_export3 = st.columns(3)
            with col_export1:
                csv_all = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="⬇️ Download ทั้งหมด",
                    data=csv_all,
                    file_name="emails_all.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_export2:
                csv_filtered = filtered_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="⬇️ Download ที่แสดง",
                    data=csv_filtered,
                    file_name="emails_filtered.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_emails_filtered_page",
                )
            with col_export3:
                if selected_count > 0:
                    csv_sel = all_selected_df.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        label=f"⬇️ ที่เลือก ({selected_count})",
                        data=csv_sel,
                        file_name="emails_selected.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="dl_selected_emails_page",
                    )

            if selected_count > 0:
                st.session_state.selected_emails_for_send = selected_emails
                
                st.markdown("---")
                
                # Action buttons
                col_action1, col_action2 = st.columns(2)
                st.markdown("---")
                
                # ========== ส่งอีเมลพร้อมลิงก์ Check-in อัตโนมัติ ==========
                with st.expander("📤 ส่งอีเมลพร้อมลิงก์ Check-in อัตโนมัติ", expanded=True):
                    oauth_creds = st.session_state.get("gmail_oauth_credentials")
                    smtp_user = st.session_state.get("smtp_user") or st.session_state.get("gmail_oauth_email") or os.getenv("SMTP_USER")
                    smtp_pass = st.session_state.get("smtp_password") or os.getenv("SMTP_PASSWORD")
                    can_send = oauth_creds or (smtp_user and smtp_pass)
                    
                    if not can_send:
                        st.warning("กรุณาไปที่เมนู **🔐 Login Gmail** เพื่อล็อกอินก่อน")
                    else:
                        st.caption(f"ส่งจากบัญชี: **{smtp_user}**")
                    
                    # Check-in API status
                    api_ok = False
                    try:
                        r = requests.get(f"{get_checkin_api_url()}/health", timeout=2)
                        api_ok = r.status_code == 200
                    except:
                        api_ok = False
                    
                    if api_ok:
                        st.success(f"✅ Check-in API พร้อมใช้งาน ({get_checkin_api_url()})")
                    else:
                        st.error(f"❌ Check-in API ไม่พร้อม - ลิงก์จะไม่ถูกสร้าง")
                        st.caption("รัน Check-in API ก่อน: `cd map-main/checkin-api && python -m uvicorn main:app --port 8000`")
                    
                    send_subject = st.text_input(
                        "หัวข้ออีเมล (Subject)", 
                        key="send_email_subject_page", 
                        placeholder="เช่น แจ้งข่าวโปรโมชัน"
                    )
                    
                    # Default body template
                    default_body = """สวัสดีครับ/ค่ะ

ขอเสนอบริการ SCADA Linker Box สำหรับโรงงานของท่าน

หากสนใจ กรุณากดลิงก์ด้านล่าง:
{checkin_link}

ขอบคุณครับ/ค่ะ"""
                    
                    send_body = st.text_area(
                        "เนื้อความ (Body)", 
                        value=default_body if "send_email_body_page" not in st.session_state else st.session_state.get("send_email_body_page_val", default_body),
                        key="send_email_body_page", 
                        placeholder="ใช้ {checkin_link} เพื่อใส่ลิงก์อัตโนมัติ",
                        height=180
                    )
                    
                    # Save body value
                    st.session_state["send_email_body_page_val"] = send_body
                    
                    has_placeholder = "{checkin_link}" in send_body
                    if has_placeholder:
                        st.info("💡 ระบบจะสร้างลิงก์ Check-in เฉพาะสำหรับแต่ละ email อัตโนมัติ")
                    else:
                        st.warning("⚠️ ไม่พบ `{checkin_link}` ในเนื้อความ - จะส่งโดยไม่มีลิงก์ Check-in")
                    
                    # แสดงรายการ email ที่จะส่ง (ไม่ซ้ำ)
                    emails_to_send = st.session_state.get("selected_emails_for_send", [])
                    n = len(emails_to_send)
                    
                    if n > 0:
                        with st.expander(f"📋 รายการ Email ที่จะส่ง ({n} ที่อยู่)", expanded=False):
                            for i, em in enumerate(emails_to_send, 1):
                                st.text(f"{i}. {em}")
                            if selected_count > n:
                                st.caption(f"⚠️ เลือก {selected_count} แถว แต่มี email ซ้ำกัน → ส่งจริง {n} ที่อยู่")
                    
                    if st.button(f"📤 ส่งอีเมลไปยัง {n} ที่อยู่", type="primary", key="btn_send_selected_page", use_container_width=True):
                        if n == 0:
                            st.warning("ไม่มีอีเมลที่เลือก")
                        elif not send_subject.strip() or not send_body.strip():
                            st.warning("กรุณากรอกหัวข้อและเนื้อความ")
                        else:
                            from_email = st.session_state.get("smtp_user") or st.session_state.get("gmail_oauth_email")
                            
                            # Progress
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            ok, fail, tokens_created = 0, 0, 0
                            
                            for i, to_addr in enumerate(emails_to_send):
                                status_text.text(f"กำลังส่ง {i+1}/{n}: {to_addr}...")
                                
                                # สร้างลิงก์ Check-in ถ้ามี placeholder
                                final_body = send_body.strip()
                                if has_placeholder and api_ok:
                                    try:
                                        r = requests.post(
                                            f"{get_checkin_api_url()}/api/create-token",
                                            json={"email": to_addr},
                                            timeout=5
                                        )
                                        if r.status_code == 200:
                                            link = r.json().get("link", "")
                                            final_body = final_body.replace("{checkin_link}", link)
                                            tokens_created += 1
                                        else:
                                            final_body = final_body.replace("{checkin_link}", "(ลิงก์ไม่พร้อม)")
                                    except Exception as e:
                                        final_body = final_body.replace("{checkin_link}", "(ลิงก์ไม่พร้อม)")
                                
                                # ส่งอีเมล
                                if st.session_state.get("gmail_oauth_credentials"):
                                    success, err_msg = _send_email_via_gmail_api(
                                        st.session_state["gmail_oauth_credentials"],
                                        from_email,
                                        to_addr,
                                        send_subject.strip(),
                                        final_body,
                                    )
                                    if success:
                                        ok += 1
                                    else:
                                        fail += 1
                                        st.caption(f"❌ {to_addr}: {err_msg or 'ไม่ทราบสาเหตุ'}")
                                else:
                                    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
                                    smtp_port = int(os.getenv("SMTP_PORT", "587"))
                                    smtp_user_env = st.session_state.get("smtp_user") or os.getenv("SMTP_USER")
                                    smtp_pass_env = st.session_state.get("smtp_password") or os.getenv("SMTP_PASSWORD")
                                    if smtp_user_env and smtp_pass_env:
                                        try:
                                            import smtplib
                                            from email.mime.text import MIMEText
                                            from email.mime.multipart import MIMEMultipart
                                            msg = MIMEMultipart()
                                            msg["Subject"] = send_subject.strip()
                                            msg["From"] = smtp_user_env
                                            msg["To"] = to_addr
                                            msg.attach(MIMEText(final_body, "plain", "utf-8"))
                                            with smtplib.SMTP(smtp_host, smtp_port) as s:
                                                s.starttls()
                                                s.login(smtp_user_env, smtp_pass_env)
                                                s.sendmail(smtp_user_env, to_addr, msg.as_string())
                                            ok += 1
                                        except Exception as e:
                                            fail += 1
                                            st.caption(f"❌ {to_addr}: {e}")
                                    else:
                                        fail += 1
                                        st.caption(f"❌ {to_addr}: ไม่มีข้อมูล SMTP")
                                
                                progress_bar.progress((i + 1) / n)
                            
                            status_text.empty()
                            progress_bar.empty()
                            
                            # แสดงผลสรุป
                            if ok > 0:
                                st.success(f"✅ ส่งสำเร็จ {ok} รายการ" + (f" (สร้างลิงก์ {tokens_created} ลิงก์)" if tokens_created > 0 else ""))
                            if fail > 0:
                                st.error(f"❌ ล้มเหลว {fail} รายการ")
                            
                            st.balloons()
            else:
                st.info("ติ๊กเลือก email จากตารางด้านบน แล้วกดส่งได้เลย")


def render_results(docker_ok: bool, db_exists: bool, loc_ok: bool):
    badges = [
        (f"💾 DB: {'Ready' if db_exists else 'Empty'}", "ok" if db_exists else "warn"),
        (f"🐳 Docker: {'Running' if docker_ok else 'Down'}", "ok" if docker_ok else "bad"),
    ]
    page_header("📊 Results", "ดูสถิติ + Places สำเร็จ/ล้มเหลว", badges)

    if not db_exists:
        with card("🧾 Empty state", help_text="ยังไม่มีฐานข้อมูล — รัน Stage 1 ก่อน แล้วกลับมาดูผล"):
            st.info("ℹ️ ยังไม่มีข้อมูล - กรุณารัน Pipeline ก่อน")
        return

    stats = get_statistics(DB_FILE)
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Places", stats["total_places"])
        with col2:
            st.metric("Emails", stats["total_emails"])
        with col3:
            st.metric("Discovered URLs", stats["total_discovered"])
        with col4:
            sr = 0.0
            if stats["total_places"] > 0:
                done = stats.get("status_breakdown", {}).get("DONE", 0)
                sr = (done / stats["total_places"]) * 100
            st.metric("Success Rate", f"{sr:.1f}%")

    t1, t2, t3 = st.tabs(["📈 Stats", "✅ Success", "❌ Failed"])

    with t1:
        with card("📈 Statistics", help_text="ภาพรวมสถานะ + แหล่งที่มาของอีเมล"):
            if stats:
                c1, c2, c3 = st.columns(3)
                with c1:
                    status_df = pd.DataFrame(list(stats["status_breakdown"].items()), columns=["Status", "Count"])
                    st.dataframe(status_df, use_container_width=True, hide_index=True)
                with c2:
                    if stats["source_breakdown"]:
                        source_df = pd.DataFrame(list(stats["source_breakdown"].items()), columns=["Source", "Count"])
                        st.dataframe(source_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("ไม่มีข้อมูลอีเมล")
                with c3:
                    if stats["discovered_types"]:
                        discovered_df = pd.DataFrame(list(stats["discovered_types"].items()), columns=["Type", "Count"])
                        st.dataframe(discovered_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("ไม่มี Discovered URLs")
            else:
                st.error("❌ ไม่สามารถอ่านข้อมูลจาก database")
        
        # Quick link to Emails page
        st.caption("💡 ไปที่เมนู 📬 Emails เพื่อดูรายละเอียด")

    with t2:
        with card("✅ Success places", help_text="Places ที่เจออีเมล → ไปดูรายละเอียดที่หน้า 📬 Emails"):
            try:
                conn = sqlite3.connect(DB_FILE)
                query = """
                    SELECT DISTINCT
                        p.place_id,
                        p.name AS place_name,
                        p.category,
                        p.phone,
                        p.website,
                        GROUP_CONCAT(DISTINCT e.email) AS emails,
                        GROUP_CONCAT(DISTINCT e.source) AS sources,
                        COUNT(DISTINCT e.id) AS email_count,
                        p.status,
                        datetime(p.updated_at, 'unixepoch') AS updated_at
                    FROM places p
                    JOIN emails e ON p.place_id = e.place_id
                    GROUP BY p.place_id
                    ORDER BY p.updated_at DESC
                """
                df = pd.read_sql_query(query, conn)
                conn.close()
                if len(df) == 0:
                    st.info("ℹ️ ยังไม่มี places ที่สำเร็จ - กรุณารัน Pipeline ก่อน")
                else:
                    f1, f2, f3 = st.columns(3)
                    with f1:
                        sources = ["All"] + ["WEBSITE", "FACEBOOK_PLAYWRIGHT", "CROSSREF_FB", "CROSSREF_WEB"]
                        selected_source = st.selectbox("Filter by Source", sources, key="success_source")
                    with f2:
                        categories = ["All"] + list(df["category"].dropna().unique())
                        selected_category = st.selectbox("Filter by Category", categories, key="success_category")
                    with f3:
                        search = st.text_input("Search (name, email)", key="success_search")

                    filtered_df = df.copy()
                    if selected_source != "All":
                        filtered_df = filtered_df[filtered_df["sources"].str.contains(selected_source, na=False)]
                    if selected_category != "All":
                        filtered_df = filtered_df[filtered_df["category"] == selected_category]
                    if search:
                        mask = (
                            filtered_df["place_name"].str.contains(search, case=False, na=False)
                            | filtered_df["emails"].str.contains(search, case=False, na=False)
                        )
                        filtered_df = filtered_df[mask]

                    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
                    csv = filtered_df.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        label="⬇️ Download Success Places CSV",
                        data=csv,
                        file_name="success_places_export.csv",
                        mime="text/csv",
                        width="stretch",
                    )
            except Exception as e:
                st.error(f"❌ Error: {e}")

    with t3:
        with card("❌ Failed places", help_text="Places ที่ยังไม่เจออีเมล + กรอง + export"):
            try:
                conn = sqlite3.connect(DB_FILE)
                query = """
                    SELECT 
                        p.place_id,
                        p.name AS place_name,
                        p.category,
                        p.phone,
                        p.website,
                        p.status,
                        CASE 
                            WHEN p.status = 'FAILED' THEN 'ไม่เจออีเมล'
                            WHEN p.status = 'NEW' THEN 'ยังไม่ได้รัน'
                            WHEN p.status = 'PROCESSING' THEN 'กำลังประมวลผล'
                            ELSE 'ไม่ทราบสาเหตุ'
                        END AS failure_reason,
                        CASE
                            WHEN p.website IS NULL OR p.website = '' THEN 'ไม่มีเว็บไซต์'
                            WHEN p.website LIKE '%facebook.com%' THEN 'มีแต่ Facebook'
                            ELSE 'มีเว็บไซต์'
                        END AS website_status,
                        datetime(p.updated_at, 'unixepoch') AS updated_at
                    FROM places p
                    LEFT JOIN emails e ON p.place_id = e.place_id
                    WHERE e.place_id IS NULL
                    ORDER BY p.updated_at DESC
                """
                df = pd.read_sql_query(query, conn)
                conn.close()
                if len(df) == 0:
                    st.success("🎉 ไม่มี Failed Places - เจออีเมลครบทุก place แล้ว!")
                else:
                    f1, f2, f3 = st.columns(3)
                    with f1:
                        statuses = ["All"] + list(df["status"].unique())
                        selected_status = st.selectbox("Filter by Status", statuses, key="failed_status")
                    with f2:
                        website_statuses = ["All"] + list(df["website_status"].unique())
                        selected_web_status = st.selectbox("Filter by Website", website_statuses, key="failed_web_status")
                    with f3:
                        search = st.text_input("Search (name, website)", key="failed_search")

                    filtered_df = df.copy()
                    if selected_status != "All":
                        filtered_df = filtered_df[filtered_df["status"] == selected_status]
                    if selected_web_status != "All":
                        filtered_df = filtered_df[filtered_df["website_status"] == selected_web_status]
                    if search:
                        mask = (
                            filtered_df["place_name"].str.contains(search, case=False, na=False)
                            | filtered_df["website"].str.contains(search, case=False, na=False)
                        )
                        filtered_df = filtered_df[mask]

                    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
                    csv = filtered_df.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        label="⬇️ Download Failed Places CSV",
                        data=csv,
                        file_name="failed_places_export.csv",
                        mime="text/csv",
                        width="stretch",
                    )
            except Exception as e:
                st.error(f"❌ Error: {e}")


def render_tools(docker_ok: bool, db_exists: bool, loc_ok: bool):
    badges = [
        (f"🐳 Docker: {'Running' if docker_ok else 'Down'}", "ok" if docker_ok else "bad"),
        (f"💾 DB: {'Ready' if db_exists else 'Empty'}", "ok" if db_exists else "warn"),
    ]
    page_header("🧰 Tools & Settings", "เครื่องมือเสริม + บำรุงรักษา DB + Debug", badges)

    tabs = st.tabs(["🤖 AI Keywords", "🧹 Database", "⚙️ Environment", "🔎 Debug"])

    with tabs[0]:
        with card("🤖 AI Keyword Generator", help_text="สร้าง query variations ด้วย Gemini แล้วบันทึกลง `config/queries.txt`"):
            # Ensure session state
            if "ai_variations" not in st.session_state:
                st.session_state.ai_variations = []
            if "ai_selected" not in st.session_state:
                st.session_state.ai_selected = []
            if "ai_generator_input" not in st.session_state:
                st.session_state.ai_generator_input = ""

            ai_input = st.text_input(
                "พิมพ์คำค้นหา",
                value=st.session_state.ai_generator_input,
                placeholder="เช่น: ร้านอาหาร สายไหม",
                key="ai_input_field",
            )
            if ai_input != st.session_state.ai_generator_input:
                st.session_state.ai_generator_input = ai_input

            num_variations = st.slider("จำนวน variations", 5, 20, 10, key="ai_num_variations")

            loc_suffix = st.session_state.get("loc_suffix", "")
            use_loc = st.toggle("แนบพื้นที่ (จาก Runner) อัตโนมัติ", value=bool(loc_suffix), disabled=not bool(loc_suffix))
            if use_loc and loc_suffix:
                st.caption(f"จะต่อท้ายด้วย: **{loc_suffix}**")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔍 Generate Variations", type="primary", width="stretch", disabled=not ai_input):
                    try:
                        if KeywordGenerator is None:
                            st.error("❌ ฟีเจอร์ AI Keywords ใช้ไม่ได้: ไม่พบ google-generativeai (pip install google-generativeai)")
                        else:
                            with st.spinner("🤖 AI กำลังสร้าง keywords..."):
                                api_key = os.getenv("GEMINI_API_KEY")
                                if not api_key or api_key == "YOUR_API_KEY_HERE":
                                    st.error("❌ ไม่พบ GEMINI_API_KEY! กรุณาตั้งค่า env var ก่อน")
                                else:
                                    ai_prompt = ai_input.strip()
                                    if use_loc and loc_suffix and loc_suffix not in ai_prompt:
                                        ai_prompt = f"{ai_prompt} {loc_suffix}".strip()
                                    generator = KeywordGenerator(api_key=api_key)
                                    variations = generator.generate_variations(
                                        ai_prompt,
                                        num_variations=num_variations - 1,
                                        include_original=True,
                                    )
                                    st.session_state.ai_variations = variations
                                    st.session_state.ai_selected = [True] * len(variations)
                                    st.success(f"✅ สร้าง {len(variations)} variations สำเร็จ!")
                                    st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
            with c2:
                if st.button("🗑️ Clear", width="stretch", disabled=len(st.session_state.ai_variations) == 0):
                    st.session_state.ai_variations = []
                    st.session_state.ai_selected = []
                    st.session_state.ai_generator_input = ""
                    st.rerun()

            if st.session_state.ai_variations:
                st.markdown("<div class='mv-divider'></div>", unsafe_allow_html=True)
                st.caption(f"📋 เลือก queries ที่ต้องการ ({len(st.session_state.ai_variations)} variations)")
                for i, variation in enumerate(st.session_state.ai_variations):
                    if i >= len(st.session_state.ai_selected):
                        st.session_state.ai_selected.append(True)
                    st.session_state.ai_selected[i] = st.checkbox(
                        variation,
                        value=st.session_state.ai_selected[i],
                        key=f"variation_{i}",
                    )

                selected_count = sum(st.session_state.ai_selected)
                if st.button(
                    f"💾 บันทึก {selected_count} queries ที่เลือกลง {QUERIES_FILE}",
                    width="stretch",
                    type="primary",
                    disabled=selected_count == 0,
                ):
                    selected_queries = [
                        q for i, q in enumerate(st.session_state.ai_variations) if st.session_state.ai_selected[i]
                    ]
                    if use_loc and loc_suffix:
                        selected_queries = [
                            (q if loc_suffix in (q or "") else f"{(q or '').strip()} {loc_suffix}".strip())
                            for q in selected_queries
                            if (q or "").strip()
                        ]
                    with open(QUERIES_FILE, "w", encoding="utf-8") as f:
                        f.write("\n".join(selected_queries))
                    st.success(f"✅ บันทึก {len(selected_queries)} queries สำเร็จ!")

    with tabs[1]:
        with card("🧹 Database maintenance", help_text="ดูสถิติ + ลบข้อมูลทั้งหมด (ย้อนกลับไม่ได้)"):
            if not Path(DB_FILE).exists():
                st.info(f"ℹ️ ยังไม่มี {DB_FILE}")
            else:
                stats = get_statistics(DB_FILE) or {}
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Places", stats.get("total_places", 0))
                with col2:
                    st.metric("Emails", stats.get("total_emails", 0))
                with col3:
                    st.metric("Discovered URLs", stats.get("total_discovered", 0))

                if "confirm_clear_all_data" not in st.session_state:
                    st.session_state.confirm_clear_all_data = False

                if not st.session_state.confirm_clear_all_data:
                    if st.button("🗑️ Clear All Data", width="stretch", type="primary"):
                        st.session_state.confirm_clear_all_data = True
                        st.rerun()
                else:
                    st.warning("⚠️ คำเตือน: จะลบข้อมูลทั้งหมด และย้อนกลับไม่ได้")
                    colA, colB = st.columns(2)
                    with colA:
                        if st.button("✅ ยืนยันลบทั้งหมด", width="stretch"):
                            try:
                                conn = sqlite3.connect(DB_FILE)
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM emails")
                                cursor.execute("DELETE FROM discovered_urls")
                                cursor.execute("DELETE FROM places")
                                cursor.execute("DELETE FROM sqlite_sequence WHERE name='places'")
                                cursor.execute("DELETE FROM sqlite_sequence WHERE name='emails'")
                                cursor.execute("DELETE FROM sqlite_sequence WHERE name='discovered_urls'")
                                conn.commit()
                                conn.close()
                                st.session_state.confirm_clear_all_data = False
                                st.success("✅ ลบข้อมูลทั้งหมดสำเร็จ!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                    with colB:
                        if st.button("❌ ยกเลิก", width="stretch"):
                            st.session_state.confirm_clear_all_data = False
                            st.rerun()

    with tabs[2]:
        with card("⚙️ ตั้งค่า Environment (.env)", help_text="แก้ไขตัวแปรที่ใช้ใน GUI — บันทึกลงไฟล์ .env ที่ root ของโปรเจกต์"):
            env_path = _get_env_file()
            current = _read_env_to_dict()
            st.caption(f"ไฟล์: `{env_path}`")

            show_secrets = st.toggle("👁️ แสดงค่า (รหัสผ่าน)", value=False, key="env_show_secrets")

            checkin_url = st.text_input(
                "CHECKIN_API_URL",
                value=current.get("CHECKIN_API_URL") or os.getenv("CHECKIN_API_URL", "http://localhost:8000"),
                placeholder="http://localhost:8000",
                help="URL ของ Check-in API — รันบนเครื่องใช้ localhost",
            )
            redirect_uri = st.text_input(
                "GOOGLE_REDIRECT_URI",
                value=current.get("GOOGLE_REDIRECT_URI") or os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8502/"),
                placeholder="http://localhost:8502/",
                help="Redirect URI หลังล็อกอิน Google — ต้องตรงกับที่ตั้งใน Google Console",
            )
            _pwd_type = "default" if show_secrets else "password"
            _gemini_val = (current.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or "") if show_secrets else ""
            gemini_key = st.text_input(
                "GEMINI_API_KEY",
                value=_gemini_val,
                type=_pwd_type,
                placeholder="(ตั้งค่าแล้ว)" if (current.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")) and not show_secrets else "(ยังไม่ตั้ง)",
                help="API key สำหรับ AI Keyword Generator — เปิด 'แสดงค่า' เพื่อดูค่าปัจจุบัน",
            )
            google_client_id = st.text_input(
                "GOOGLE_CLIENT_ID",
                value=current.get("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID", ""),
                placeholder="xxx.apps.googleusercontent.com",
                help="OAuth Client ID จาก Google Cloud Console",
            )
            _secret_val = (current.get("GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET") or "") if show_secrets else ""
            google_client_secret = st.text_input(
                "GOOGLE_CLIENT_SECRET",
                value=_secret_val,
                type=_pwd_type,
                placeholder="(ตั้งค่าแล้ว)" if (current.get("GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET")) and not show_secrets else "(ยังไม่ตั้ง)",
                help="OAuth Client Secret — เปิด 'แสดงค่า' เพื่อดูค่าปัจจุบัน",
            )

            if st.button("💾 บันทึกลง .env", type="primary"):
                data = {
                    "CHECKIN_API_URL": checkin_url.strip() or None,
                    "GOOGLE_REDIRECT_URI": redirect_uri.strip() or None,
                    "GEMINI_API_KEY": gemini_key.strip() if gemini_key else (current.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")),
                    "GOOGLE_CLIENT_ID": google_client_id.strip() or None,
                    "GOOGLE_CLIENT_SECRET": google_client_secret.strip() if google_client_secret else (current.get("GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET")),
                }
                try:
                    _write_env_from_dict(data)
                    st.success("✅ บันทึกลง .env แล้ว — ค่าจะมีผลทันที (Check-in API URL ใช้ได้ในหน้าถัดไป)")
                except Exception as e:
                    st.error(f"❌ บันทึกไม่สำเร็จ: {e}")

    with tabs[3]:
        with card("🔎 Debug info", help_text="ช่วยตรวจสภาพแวดล้อมเวลาแก้ปัญหา"):
            st.write(
                {
                    "cwd": str(Path.cwd()),
                    "DB_FILE_exists": Path(DB_FILE).exists(),
                    "TH_LOCATIONS_FILE_exists": Path(TH_LOCATIONS_FILE).exists(),
                    "built_query": st.session_state.get("built_query", ""),
                    "loc_suffix": st.session_state.get("loc_suffix", ""),
                }
            )


# ========== Check-in API Integration ==========

def get_checkin_api_url():
    """อ่าน CHECKIN_API_URL จาก env (อัปเดตเมื่อ user เปลี่ยนใน Settings)"""
    return os.getenv("CHECKIN_API_URL", "http://localhost:8000")

def render_checkin(docker_ok: bool, db_exists: bool, loc_ok: bool):
    """หน้าดู Check-in responses และสร้าง token"""
    badges = [
        ("🎫 Check-in API", "info"),
    ]
    page_header("🎫 Check-in Dashboard", "ดู response จากลิงก์ check-in + สร้าง token ใหม่", badges)
    checkin_url = get_checkin_api_url()
    # ตรวจสอบว่า API ทำงานหรือไม่
    api_ok = False
    try:
        r = requests.get(f"{checkin_url}/health", timeout=3)
        api_ok = r.status_code == 200
    except:
        api_ok = False

    if not api_ok:
        st.error(f"❌ ไม่สามารถเชื่อมต่อ Check-in API ที่ {checkin_url}")
        st.info("กรุณารัน Check-in API ก่อน หรือตั้งค่า CHECKIN_API_URL ใน Tools & Settings → Environment")
        st.code("cd C:\\Users\\0355\\Desktop\\map-main\\checkin-api\npython -m uvicorn main:app --reload --port 8000")
        return

    st.success(f"✅ เชื่อมต่อ Check-in API สำเร็จ ({checkin_url})")
    
    tabs = st.tabs(["📊 สรุป Response", "📋 Token ทั้งหมด", "➕ สร้าง Token ใหม่"])
    
    with tabs[0]:
        with card("📊 สรุป Response", help_text="ดูสถานะทั้งหมด: สนใจ, blocked, เข้าดู, ส่งแล้ว"):
            try:
                # ดึงข้อมูล tokens
                r_tokens = requests.get(f"{checkin_url}/api/tokens", timeout=10)
                tokens_data = r_tokens.json()
                tokens_list = tokens_data.get("tokens", [])
                
                # ดึงข้อมูล responses
                r_resp = requests.get(f"{checkin_url}/api/responses", timeout=10)
                resp_data = r_resp.json()
                
                # คำนวณสถานะต่างๆ
                all_sent_emails = set(t.get("email", "").lower() for t in tokens_list if t.get("email"))
                viewed_emails = set(t.get("email", "").lower() for t in tokens_list if t.get("email") and t.get("used"))
                interested_emails = set(i.get("email", "").lower() for i in resp_data.get("interested", []) if i.get("email"))
                blocked_emails = set(u.get("email", "").lower() for u in resp_data.get("unsubscribed", []) if u.get("email"))
                
                # เข้าดูแต่ไม่ตอบ = viewed - interested - blocked
                viewed_only_emails = viewed_emails - interested_emails - blocked_emails
                # ส่งแล้วแต่ยังไม่เปิด = sent - viewed
                sent_not_opened_emails = all_sent_emails - viewed_emails
                
                # แสดง metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("💚 สนใจ", len(interested_emails))
                with col2:
                    st.metric("🚫 Blocked", len(blocked_emails))
                with col3:
                    st.metric("👁️ เข้าดู", len(viewed_only_emails))
                with col4:
                    st.metric("✅ ส่งแล้ว", len(sent_not_opened_emails))
                
                st.caption(f"รวมส่งทั้งหมด **{len(all_sent_emails)}** emails")
                st.markdown("---")
                
                # แสดงรายการแต่ละสถานะ
                status_tabs = st.tabs(["💚 สนใจ", "🚫 Blocked", "👁️ เข้าดู", "✅ ส่งแล้ว"])
                
                with status_tabs[0]:
                    if resp_data.get("interested"):
                        interested_df = pd.DataFrame(resp_data["interested"])
                        st.dataframe(interested_df, use_container_width=True, hide_index=True)
                        csv = interested_df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button("⬇️ Download CSV", data=csv, file_name="interested.csv", mime="text/csv", key="dl_interested")
                    else:
                        st.info("ยังไม่มี")
                
                with status_tabs[1]:
                    if resp_data.get("unsubscribed"):
                        blocked_df = pd.DataFrame(resp_data["unsubscribed"])
                        st.dataframe(blocked_df, use_container_width=True, hide_index=True)
                        csv = blocked_df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button("⬇️ Download CSV", data=csv, file_name="blocked.csv", mime="text/csv", key="dl_blocked")
                    else:
                        st.info("ยังไม่มี")
                
                with status_tabs[2]:
                    if viewed_only_emails:
                        viewed_list = [{"email": e} for e in sorted(viewed_only_emails)]
                        viewed_df = pd.DataFrame(viewed_list)
                        st.dataframe(viewed_df, use_container_width=True, hide_index=True)
                        csv = viewed_df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button("⬇️ Download CSV", data=csv, file_name="viewed.csv", mime="text/csv", key="dl_viewed")
                    else:
                        st.info("ยังไม่มี")
                
                with status_tabs[3]:
                    if sent_not_opened_emails:
                        sent_list = [{"email": e} for e in sorted(sent_not_opened_emails)]
                        sent_df = pd.DataFrame(sent_list)
                        st.dataframe(sent_df, use_container_width=True, hide_index=True)
                        csv = sent_df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button("⬇️ Download CSV", data=csv, file_name="sent_not_opened.csv", mime="text/csv", key="dl_sent")
                    else:
                        st.info("ยังไม่มี")
                    
            except Exception as e:
                st.error(f"❌ Error: {e}")
    
    with tabs[1]:
        with card("📋 Token ทั้งหมด", help_text="ดู token ที่สร้างไว้ และสถานะการใช้งาน"):
            try:
                r = requests.get(f"{checkin_url}/api/tokens", timeout=10)
                data = r.json()
                
                tokens = data.get("tokens", [])
                if not tokens:
                    st.info("ยังไม่มี token ในระบบ — สร้างได้ที่แท็บ 'สร้าง Token ใหม่'")
                else:
                    st.caption(f"ทั้งหมด **{len(tokens)}** tokens")
                    
                    # Filter
                    filter_used = st.selectbox("กรอง", ["All", "ใช้แล้ว", "ยังไม่ใช้"], key="token_filter")
                    
                    filtered = tokens
                    if filter_used == "ใช้แล้ว":
                        filtered = [t for t in tokens if t.get("used")]
                    elif filter_used == "ยังไม่ใช้":
                        filtered = [t for t in tokens if not t.get("used")]
                    
                    # แสดงตาราง
                    df = pd.DataFrame(filtered)
                    if "token" in df.columns:
                        # ย่อ token ให้สั้น
                        df["token_short"] = df["token"].str[:12] + "..."
                        df["link"] = df["token"].apply(lambda t: f"{checkin_url}/index.html?t={t}")
                    
                    display_cols = ["email", "token_short", "used", "used_at", "created_at"]
                    display_cols = [c for c in display_cols if c in df.columns]
                    
                    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
                    
                    # Export
                    csv = df.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        "⬇️ Download Tokens CSV",
                        data=csv,
                        file_name="checkin_tokens.csv",
                        mime="text/csv",
                    )
                    
            except Exception as e:
                st.error(f"❌ Error: {e}")
    
    with tabs[2]:
        with card("➕ สร้าง Token ใหม่", help_text="สร้างลิงก์ check-in สำหรับส่งให้ user"):
            # วิธีที่ 1: กรอก email เดียว
            st.markdown("**วิธีที่ 1: กรอก email เดียว**")
            single_email = st.text_input("Email", placeholder="user@example.com", key="single_email_input")
            
            if st.button("🔗 สร้างลิงก์", type="primary", disabled=not single_email):
                try:
                    r = requests.post(
                        f"{checkin_url}/api/create-token",
                        json={"email": single_email.strip()},
                        timeout=10
                    )
                    if r.status_code == 200:
                        data = r.json()
                        st.success("✅ สร้างสำเร็จ!")
                        st.code(data.get("link", ""), language=None)
                        st.caption("คัดลอกลิงก์นี้ส่งให้ user ได้เลย")
                    else:
                        st.error(f"❌ Error: {r.text}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
            
            st.markdown("---")
            
            # วิธีที่ 2: สร้างจาก email ที่เลือกใน Results
            st.markdown("**วิธีที่ 2: สร้างจาก email ที่เลือกใน Results Explorer**")
            selected_emails = st.session_state.get("selected_emails_for_send", [])
            
            if selected_emails:
                st.caption(f"มี {len(selected_emails)} email ที่เลือกไว้")
                if st.button(f"🔗 สร้างลิงก์ให้ {len(selected_emails)} emails", type="primary"):
                    created = []
                    failed = []
                    progress = st.progress(0)
                    for i, email in enumerate(selected_emails):
                        try:
                            r = requests.post(
                                f"{checkin_url}/api/create-token",
                                json={"email": email},
                                timeout=10
                            )
                            if r.status_code == 200:
                                data = r.json()
                                created.append({"email": email, "link": data.get("link", "")})
                            else:
                                failed.append(email)
                        except:
                            failed.append(email)
                        progress.progress((i + 1) / len(selected_emails))
                    
                    if created:
                        st.success(f"✅ สร้างสำเร็จ {len(created)} ลิงก์")
                        links_df = pd.DataFrame(created)
                        st.dataframe(links_df, use_container_width=True, hide_index=True)
                        
                        # Download
                        csv = links_df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button(
                            "⬇️ Download Links CSV",
                            data=csv,
                            file_name="checkin_links.csv",
                            mime="text/csv",
                        )
                    
                    if failed:
                        st.warning(f"⚠️ สร้างไม่สำเร็จ {len(failed)} emails")
            else:
                st.info("ไปที่เมนู 📬 Emails → เลือก email → กลับมาสร้างลิงก์ได้ที่นี่")


def main():
    st.set_page_config(page_title="Google Maps Email Pipeline", page_icon="📧", layout="wide")
    inject_modern_vivid_css()

    # OAuth callback: หลังเลือกบัญชี Google จะ redirect กลับมาพร้อม ?code=...
    qp = getattr(st, "query_params", None)
    if qp is not None:
        code = qp.get("code")
        if isinstance(code, list):
            code = code[0] if code else None
    else:
        code = (st.experimental_get_query_params().get("code") or [None])[0]
    if code and os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
        token_info, email = _exchange_oauth_code_for_credentials(code)
        if token_info and email:
            st.session_state.gmail_oauth_credentials = token_info
            st.session_state.gmail_oauth_email = email
            st.session_state.gmail_logged_in = True
            st.session_state.smtp_user = email
            _save_gmail_oauth_to_file(token_info, email)
            if hasattr(qp, "clear"):
                qp.clear()
            st.rerun()

    # โหลด Gmail OAuth จากไฟล์ (ไม่ต้องล็อกอินใหม่ทุกครั้ง)
    if not st.session_state.get("gmail_oauth_credentials") and Path(OAUTH_TOKEN_FILE).exists():
        token_info, email = _load_gmail_oauth_from_file()
        if token_info and email:
            st.session_state.gmail_oauth_credentials = token_info
            st.session_state.gmail_oauth_email = email
            st.session_state.gmail_logged_in = True
            st.session_state.smtp_user = email

    # Ensure session state flags (kept for backward-compat with old UI)
    for k, v in {
        "confirm_delete_all_emails": False,
        "confirm_delete_filtered_emails": False,
        "confirm_delete_all_urls": False,
        "confirm_delete_filtered_urls": False,
        "confirm_clear_all_data": False,
        "ai_variations": [],
        "ai_selected": [],
        "ai_generator_input": "",
        "built_query": st.session_state.get("built_query", ""),
        "loc_suffix": st.session_state.get("loc_suffix", ""),
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    docker_ok = check_docker()
    db_exists = Path(DB_FILE).exists()
    loc_ok = Path(TH_LOCATIONS_FILE).exists()

    page = render_sidebar_nav(docker_ok=docker_ok, db_exists=db_exists, loc_ok=loc_ok)

    if page == "🏠 Dashboard":
        render_dashboard(docker_ok=docker_ok, db_exists=db_exists, loc_ok=loc_ok)
    elif page == "🚀 Pipeline Runner":
        render_runner(docker_ok=docker_ok, db_exists=db_exists, loc_ok=loc_ok)
    elif page == "📊 Results":
        render_results(docker_ok=docker_ok, db_exists=db_exists, loc_ok=loc_ok)
    elif page == "📬 Emails":
        render_emails(docker_ok=docker_ok, db_exists=db_exists, loc_ok=loc_ok)
    elif page == "🎫 Check-in":
        render_checkin(docker_ok=docker_ok, db_exists=db_exists, loc_ok=loc_ok)
    elif page == "🔐 Login Gmail":
        render_login_gmail(docker_ok=docker_ok, db_exists=db_exists, loc_ok=loc_ok)
    else:
        render_tools(docker_ok=docker_ok, db_exists=db_exists, loc_ok=loc_ok)


if __name__ == "__main__":
    main()
