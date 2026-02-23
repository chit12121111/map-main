#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run full pipeline (all stages) from CLI and print report.
Usage from map-main: python scripts/run_pipeline_test.py
"""
import os
import sys
import subprocess
import urllib.parse
import urllib.request
import json
import csv
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# โฟลเดอร์โปรเจกต์ = โฟลเดอร์ที่มี gui_app.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

# โหลด .env
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        # Keep externally provided env vars (from Laravel runner) higher priority.
        os.environ.setdefault(k.strip(), v)

CHECKIN_API_URL = os.environ.get("CHECKIN_API_URL", "http://localhost:8000")
QUERIES_FILE = PROJECT_ROOT / "config" / "queries.txt"
RESULTS_CSV = PROJECT_ROOT / "output" / "results.csv"
DB_FILE = PROJECT_ROOT / "pipeline.db"
PIPELINE_CONCURRENCY = max(1, int(os.environ.get("PIPELINE_CONCURRENCY", "2")))
PIPELINE_LANG = os.environ.get("PIPELINE_LANG", "th")
PIPELINE_INACTIVITY = os.environ.get("PIPELINE_INACTIVITY", "3m")
PIPELINE_RADIUS = max(1000, int(os.environ.get("PIPELINE_RADIUS", "7000")))
PIPELINE_DEPTH = max(1, int(os.environ.get("PIPELINE_DEPTH", "2")))
TH_LOCATIONS_FILE = PROJECT_ROOT / "data" / "th_locations.json"

def _load_th_locations():
    try:
        if not TH_LOCATIONS_FILE.exists():
            return {}
        return json.loads(TH_LOCATIONS_FILE.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}

TH_LOCATIONS = _load_th_locations()

def import_stage1_csv_to_api(csv_path: Path):
    try:
        import api_client
    except Exception as e:
        return False, f"cannot import api_client: {e}"

    if not csv_path.exists():
        return False, "results.csv not found"
    try:
        text = csv_path.read_text(encoding="utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) <= 1:
            return True, "no rows to import"
        reader = csv.DictReader(lines)
        payload = []
        for row in reader:
            payload.append(
                {
                    "place_id": row.get("place_id") or row.get("cid") or "",
                    "cid": row.get("cid") or "",
                    "title": row.get("title") or "",
                    "name": row.get("title") or "",
                    "website": row.get("website") or "",
                    "phone": row.get("phone") or "",
                    "address": row.get("address") or "",
                    "category": row.get("category") or "",
                    "review_count": row.get("review_count") or None,
                    "review_rating": row.get("review_rating") or None,
                    "latitude": row.get("latitude") or None,
                    "longitude": row.get("longitude") or None,
                    "url": row.get("link") or row.get("website") or "",
                    "raw_data": json.dumps(row, ensure_ascii=False),
                }
            )
        resp, err = api_client.import_places(payload)
        if err:
            return False, err
        created = (resp or {}).get("created", 0)
        updated = (resp or {}).get("updated", 0)
        return True, f"created={created}, updated={updated}, total={len(payload)}"
    except Exception as e:
        return False, str(e)

def get_stage1_binary():
    raw = os.environ.get("GOOGLE_MAPS_SCRAPER_BIN", "").strip()
    if raw:
        for base in (PROJECT_ROOT, Path.cwd()):
            p = base / raw
            if p.is_file():
                return p
    default = "google-maps-scraper.exe" if sys.platform == "win32" else "google-maps-scraper"
    for base in (PROJECT_ROOT, Path.cwd()):
        p = base / "tools" / default
        if p.is_file():
            return p
    return None

def run_cmd(cmd, env=None, cwd=None, timeout_sec=300):
    env = env or os.environ.copy()
    cwd = cwd or str(PROJECT_ROOT)
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            env=env,
            timeout=timeout_sec,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out
    except subprocess.TimeoutExpired as e:
        return -1, (e.stdout or "") + (e.stderr or "") + "\n[TIMEOUT] " + str(e)
    except Exception as e:
        return -1, str(e)


def _quote_cmd_arg(s):
    s = str(s)
    if " " in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def run_stage1_windows(cmd, env=None, cwd=None, timeout_sec=300):
    """Run Stage 1 on Windows via cmd.exe without opening extra console."""
    env = env or os.environ.copy()
    cwd = cwd or str(PROJECT_ROOT)
    try:
        cmd_str = "cd /d " + _quote_cmd_arg(cwd) + " && " + " ".join(
            _quote_cmd_arg(a) for a in cmd
        )
        p = subprocess.Popen(
            ["cmd.exe", "/c", cmd_str],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out, _ = p.communicate(timeout=timeout_sec)
        return p.returncode, out or ""
    except subprocess.TimeoutExpired:
        p.kill()
        return -1, "[TIMEOUT] Stage 1 timed out"
    except Exception as e:
        return -1, str(e)

def main():
    report = []
    report_path = PROJECT_ROOT / "output" / "pipeline_test_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("", encoding="utf-8")
    def log(msg):
        print(msg)
        report.append(msg)
        try:
            with report_path.open("a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    log("=" * 60)
    log("Pipeline Runner - Test all stages")
    log("=" * 60)
    log(f"PROJECT_ROOT: {PROJECT_ROOT}")
    log(f"CHECKIN_API_URL: {CHECKIN_API_URL}")
    log("")

    env = os.environ.copy()
    env.setdefault("CHECKIN_API_URL", CHECKIN_API_URL)

    def geocode_query_center(query: str):
        if not query.strip():
            return None

        def try_geocode(q: str):
            try:
                params = urllib.parse.urlencode(
                    {
                        "q": q,
                        "format": "json",
                        "limit": 1,
                        "countrycodes": "th",
                        "accept-language": "th,en",
                    },
                    quote_via=urllib.parse.quote,
                )
                url = f"https://nominatim.openstreetmap.org/search?{params}"
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "mapping-pipeline-runner/1.1"},
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                arr = json.loads(raw)
                if not arr:
                    return None
                lat = float(arr[0]["lat"])
                lon = float(arr[0]["lon"])
                return lat, lon
            except Exception:
                return None

        candidates = []
        q = " ".join(query.split())
        if q:
            candidates.append(q)
            candidates.append(f"{q}, Thailand")

        # Heuristic: strip business keyword and geocode location-only phrase
        location_hint = q
        low = q.lower()
        for kw in ["restaurant", "hotel", "cafe", "coffee", "clinic", "pharmacy", "ร้านอาหาร", "โรงแรม", "ร้านกาแฟ", "คลินิก"]:
            if low.startswith(kw + " "):
                location_hint = q[len(kw):].strip()
                break
        if location_hint and location_hint != q:
            candidates.append(location_hint)
            candidates.append(f"{location_hint}, Thailand")

            # If location hint has many tokens, try splitting into district/province.
            toks = location_hint.split()
            if len(toks) >= 4:
                candidates.append(f"{' '.join(toks[:2])}, {' '.join(toks[2:])}, Thailand")
                if len(toks) >= 5:
                    candidates.append(f"{' '.join(toks[:3])}, {' '.join(toks[3:])}, Thailand")

        # Use province/district hints from local data to improve geocoding hit-rate.
        province_hit = None
        district_hit = None
        for region_map in TH_LOCATIONS.values() if isinstance(TH_LOCATIONS, dict) else []:
            if not isinstance(region_map, dict):
                continue
            for province_name, districts in region_map.items():
                if province_name in q:
                    province_hit = province_name
                    if isinstance(districts, list):
                        for d in districts:
                            if d and d in q:
                                district_hit = d
                                break
                    break
            if province_hit:
                break

        if district_hit and province_hit:
            candidates.append(f"{district_hit}, {province_hit}, Thailand")
            candidates.append(f"{province_hit}, {district_hit}, Thailand")
        elif province_hit:
            candidates.append(f"{province_hit}, Thailand")

        # De-duplicate while preserving order
        seen = set()
        ordered_candidates = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                ordered_candidates.append(c)

        for c in ordered_candidates:
            geo = try_geocode(c)
            if geo:
                return geo[0], geo[1], c
        return None

    # ---------- Stage 1 ----------
    log("--- Stage 1: Google Maps Scraper (gosom) ---")
    bin_path = get_stage1_binary()
    if not bin_path:
        log("Result: SKIP (no binary in tools/)")
        log("")
    else:
        RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
        if not RESULTS_CSV.exists():
            RESULTS_CSV.touch()
        if not QUERIES_FILE.exists():
            QUERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
            QUERIES_FILE.write_text("โรงแรม คลองสาน กรุงเทพมหานคร", encoding="utf-8")
        query_for_geo = QUERIES_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
        geo = geocode_query_center(query_for_geo)
        if geo:
            lat, lon, matched = geo
            log(f"Geo center: {lat:.6f},{lon:.6f} (from: {matched})")
        else:
            # Keep Stage 1 reliable on Windows by always using fast-mode + geo
            # even when geocoding service is unavailable.
            lat, lon = 13.756331, 100.501762  # Bangkok fallback
            log("Geo center: not found (fallback to Bangkok 13.756331,100.501762)")

        # Reset results file each run to avoid stale rows
        RESULTS_CSV.write_text("", encoding="utf-8")

        cmd = [
            str(bin_path),
            "-input", str(QUERIES_FILE),
            "-results", str(RESULTS_CSV),
            "-depth", str(PIPELINE_DEPTH),
            "-c", str(PIPELINE_CONCURRENCY),
            "-lang", PIPELINE_LANG,
            "-exit-on-inactivity", PIPELINE_INACTIVITY,
        ]
        cmd.extend(
            [
                "-fast-mode",
                "-geo", f"{lat:.6f},{lon:.6f}",
                "-radius", str(PIPELINE_RADIUS),
            ]
        )
        if sys.platform == "win32":
            code, out = run_stage1_windows(cmd, env=env, timeout_sec=600)
        else:
            code, out = run_cmd(cmd, env=env, timeout_sec=600)
        tail = "\n".join(out.strip().split("\n")[-25:]) if out else ""
        if code == 0:
            log("Result: OK")
            approx_rows = 0
            if RESULTS_CSV.exists():
                lines = len(RESULTS_CSV.read_text(encoding="utf-8", errors="replace").strip().split("\n")) - 1
                approx_rows = max(0, lines)
                log(f"      CSV rows (approx): {approx_rows}")
            if approx_rows > 0:
                ok, msg = import_stage1_csv_to_api(RESULTS_CSV)
                log(f"      CSV -> API: {'OK' if ok else 'FAILED'} ({msg})")
        else:
            log(f"Result: FAILED (return code {code})")
            if tail:
                log("Last output:")
                for line in tail.split("\n"):
                    log("  " + line)
        log("")

    # ---------- Stage 2 ----------
    log("--- Stage 2: Website Email Finder ---")
    cmd = [sys.executable, "stage2_email_finder.py", "--db", str(DB_FILE), "--api", "--verbose"]
    code, out = run_cmd(cmd, env=env, timeout_sec=900)
    tail = "\n".join(out.strip().split("\n")[-20:]) if out else ""
    if code == 0:
        log("Result: OK")
    else:
        log(f"Result: FAILED (return code {code})")
        if tail:
            log("Last output:")
            for line in tail.split("\n"):
                log("  " + line)
    log("")

    # ---------- Stage 3 ----------
    log("--- Stage 3: Facebook Scraper ---")
    cmd = [sys.executable, "facebook_about_scraper.py", "--db", str(DB_FILE), "--verbose"]
    code, out = run_cmd(cmd, env=env, timeout_sec=900)
    tail = "\n".join(out.strip().split("\n")[-20:]) if out else ""
    if code == 0:
        log("Result: OK")
    else:
        log(f"Result: FAILED (return code {code})")
        if tail:
            log("Last output:")
            for line in tail.split("\n"):
                log("  " + line)
    log("")

    # ---------- Stage 4 ----------
    log("--- Stage 4: Cross-Reference Scraper ---")
    cmd = [sys.executable, "stage4_crossref_scraper.py", "--db", str(DB_FILE), "--verbose"]
    code, out = run_cmd(cmd, env=env, timeout_sec=900)
    tail = "\n".join(out.strip().split("\n")[-20:]) if out else ""
    if code == 0:
        log("Result: OK")
    else:
        log(f"Result: FAILED (return code {code})")
        if tail:
            log("Last output:")
            for line in tail.split("\n"):
                log("  " + line)
    log("")

    log("=" * 60)
    log("Summary: see above")
    log("=" * 60)

    log(f"\nReport saved: {report_path}")

if __name__ == "__main__":
    main()
