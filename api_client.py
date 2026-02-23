# -*- coding: utf-8 -*-
"""
API client for Laravel Pipeline + Check-in API.
ใช้แทนการเชื่อม SQLite โดยตรง — ทุกการอ่าน/เขียนข้อมูลผ่าน HTTP ไปที่ API.
"""
import os
import requests
from typing import Optional, Any
from pathlib import Path

# Base URL จาก env (ชี้ไปที่ Laravel API)
def get_api_base_url() -> str:
    url = os.getenv("CHECKIN_API_URL") or os.getenv("API_BASE_URL") or "http://localhost:8000"
    return url.rstrip("/")

def _req(method: str, path: str, **kwargs) -> requests.Response:
    base = get_api_base_url()
    url = path if path.startswith("http") else f"{base}{path}"
    # API on local Windows can intermittently respond slowly while multiple stages run.
    timeout = kwargs.pop("timeout", 60)
    return requests.request(method, url, timeout=timeout, **kwargs)

# ---------- Stats ----------
def get_stats() -> Optional[dict]:
    """ดึงสถิติรวม (total_places, status_breakdown, total_emails, source_breakdown, total_discovered, ...)"""
    r = _req("GET", "/api/stats")
    if r.status_code != 200:
        return None
    return r.json()

# ---------- Places ----------
def get_places(status: Optional[str] = None, per_page: int = 500, page: Optional[int] = None) -> Optional[dict]:
    """GET /api/places. Returns { data: [...], total, per_page, current_page }"""
    params = {"per_page": per_page}
    if status:
        params["status"] = status
    if page:
        params["page"] = page
    r = _req("GET", "/api/places", params=params)
    if r.status_code != 200:
        return None
    return r.json()

def get_place(place_id: str) -> Optional[dict]:
    r = _req("GET", f"/api/places/{place_id}")
    if r.status_code != 200:
        return None
    return r.json()

def update_place(place_id: str, data: dict) -> Optional[dict]:
    r = _req("PATCH", f"/api/places/{place_id}", json=data)
    if r.status_code != 200:
        return None
    return r.json()

def import_places(payload: list) -> tuple[Optional[dict], Optional[str]]:
    """POST /api/places/import. Returns (result_dict, error_message). result_dict is None on failure."""
    try:
        r = _req("POST", "/api/places/import", json={"places": payload})
        if r.status_code in (200, 201):
            return (r.json(), None)
        try:
            err = r.json()
            msg = err.get("message", err.get("error", r.text)) if isinstance(err, dict) else r.text
        except Exception:
            msg = r.text or f"HTTP {r.status_code}"
        return (None, msg)
    except Exception as e:
        return (None, str(e))

def clear_all() -> Optional[dict]:
    """POST /api/places/clear — ล้าง places, emails, discovered_urls"""
    r = _req("POST", "/api/places/clear")
    if r.status_code != 200:
        return None
    return r.json()

# ---------- Emails ----------
def get_emails(place_id: Optional[str] = None, source: Optional[str] = None, per_page: int = 2000, include_place: bool = False) -> Optional[dict]:
    """GET /api/emails. Returns { data: [...], total, ... }. If include_place=True, each item has 'place'."""
    params = {"per_page": per_page}
    if place_id:
        params["place_id"] = place_id
    if source:
        params["source"] = source
    if include_place:
        params["include_place"] = "1"
    r = _req("GET", "/api/emails", params=params)
    if r.status_code != 200:
        return None
    return r.json()

def create_email(place_id: str, email: str, source: str) -> Optional[dict]:
    r = _req("POST", "/api/emails", json={"place_id": place_id, "email": email, "source": source})
    if r.status_code not in (200, 201):
        return None
    return r.json()

def update_email(email_id: int, data: dict) -> Optional[dict]:
    r = _req("PATCH", f"/api/emails/{email_id}", json=data)
    if r.status_code != 200:
        return None
    return r.json()

def delete_email(email_id: int) -> bool:
    r = _req("DELETE", f"/api/emails/{email_id}")
    return r.status_code == 200

def bulk_delete_emails(ids: list) -> Optional[dict]:
    r = _req("POST", "/api/emails/bulk-delete", json={"ids": ids})
    if r.status_code != 200:
        return None
    return r.json()

# ---------- Discovered URLs ----------
def get_discovered_urls(
    status: Optional[str] = None,
    place_id: Optional[str] = None,
    url_type: Optional[str] = None,
    per_page: int = 500,
    page: Optional[int] = None,
) -> Optional[dict]:
    params = {"per_page": per_page}
    if status:
        params["status"] = status
    if place_id:
        params["place_id"] = place_id
    if url_type:
        params["url_type"] = url_type
    if page:
        params["page"] = page
    r = _req("GET", "/api/discovered-urls", params=params)
    if r.status_code != 200:
        return None
    return r.json()

def create_discovered_url(place_id: str, url: str, url_type: str, found_by_stage: str) -> Optional[dict]:
    r = _req("POST", "/api/discovered-urls", json={
        "place_id": place_id, "url": url, "url_type": url_type, "found_by_stage": found_by_stage
    })
    if r.status_code not in (200, 201):
        return None
    return r.json()

def update_discovered_url(id: int, status: str) -> Optional[dict]:
    r = _req("PATCH", f"/api/discovered-urls/{id}", json={"status": status})
    if r.status_code != 200:
        return None
    return r.json()

# ---------- Check-in (existing) ----------
def health_check() -> Optional[dict]:
    r = _req("GET", "/health", timeout=5)
    if r.status_code != 200:
        return None
    return r.json()

def create_token(email: str, expires_in_days: Optional[int] = None) -> Optional[dict]:
    body = {"email": email}
    if expires_in_days is not None:
        body["expires_in_days"] = expires_in_days
    r = _req("POST", "/api/create-token", json=body)
    if r.status_code not in (200, 201):
        return None
    return r.json()

def get_tokens(email: Optional[str] = None) -> Optional[dict]:
    params = {}
    if email:
        params["email"] = email
    r = _req("GET", "/api/tokens", params=params)
    if r.status_code != 200:
        return None
    return r.json()

def get_responses(response_type: Optional[str] = None) -> Optional[dict]:
    params = {}
    if response_type:
        params["response_type"] = response_type
    r = _req("GET", "/api/responses", params=params)
    if r.status_code != 200:
        return None
    return r.json()

# ---------- Helpers for GUI (DataFrame-compatible) ----------
def get_emails_dataframe_from_api():
    """
    ดึงข้อมูลอีเมลรวม place เป็นชุดที่เหมาะสำหรับสร้าง DataFrame
    (เหมือน get_emails_dataframe ที่อ่านจาก SQLite)
    Returns DataFrame or None on error.
    """
    import pandas as pd
    emails_resp = get_emails(per_page=5000, include_place=True)
    if not emails_resp or "data" not in emails_resp:
        return None
    emails = emails_resp["data"]
    if not emails:
        return pd.DataFrame()

    rows = []
    for e in emails:
        p = e.get("place") or {}
        rows.append({
            "id": e.get("id"),
            "place_id": e.get("place_id", ""),
            "place_name": p.get("name", ""),
            "category": p.get("category"),
            "phone": p.get("phone"),
            "website": p.get("website"),
            "address": p.get("address"),
            "email": e.get("email", ""),
            "source": e.get("source", ""),
            "found_at": e.get("created_at", ""),
        })
    return pd.DataFrame(rows)
