# Mapping Pipeline (React + Laravel + Python Stages)

Production-ready local pipeline for scraping Google Maps places, finding emails/URLs, and viewing results in a React dashboard backed by Laravel API + MySQL.

## Architecture

- `web-ui-react/` - React + TypeScript frontend (Vite, React Query, Recharts)
- `api-laravel/` - Laravel API (MySQL storage, pipeline trigger endpoints)
- `scripts/run_pipeline_test.py` - Orchestrates Stage 1-4
- `stage2_email_finder.py` - Website email extraction
- `facebook_about_scraper.py` - Facebook about scraping
- `stage4_crossref_scraper.py` - Cross-reference URL scraping
- `tools/google-maps-scraper.exe` - Stage 1 gosom binary (Windows)
- `data/th_locations.json` - Thailand province/district list for UI selection

## One-Click Setup and Run

### 1) Install everything (first time)

Run:

```bat
one_click_install.bat
```

This script installs:
- Python dependencies (`requirements.txt`, `requirements_stage2.txt`)
- Playwright Chromium
- Laravel dependencies (`composer install`, key generate, migrate, cache clear)
- Web dependencies (`npm install` in `web-ui-react`)

Install log file:
- `logs/one_click_install_YYYYMMDD_HHMMSS.log`

### 2) Start the full stack

Run:

```bat
one_click_start.bat
```

This script starts/validates:
- Laravel API public worker: `http://127.0.0.1:8000`
- Laravel internal pipeline worker: `http://127.0.0.1:8010`
- React web app: `http://localhost:5173`

It opens the browser automatically and writes logs to:
- `logs/one_click_YYYYMMDD_HHMMSS.log`
- `logs/api_8000_*.log`
- `logs/api_8010_*.log`
- `logs/web_5173_*.log`

## Runtime Flow

1. User starts run from Dashboard (keyword + province + district + language + depth)
2. API endpoint `POST /api/pipeline/run` writes query and launches Python runner
3. Stage 1 runs gosom in fast-mode + geo
4. Stage 1 CSV is imported to API automatically (`CSV -> API`)
5. Stage 2/3/4 continue on API data
6. Logs and status can be monitored from `/logs` menu

## Key API Endpoints

- `GET /health`
- `GET /api/stats`
- `POST /api/pipeline/run`
- `GET /api/pipeline/status`
- `GET /api/places`
- `POST /api/places/import`

## Environment Notes

### `api-laravel/.env`

Important values:
- `DB_CONNECTION=mysql`
- `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`
- `CHECKIN_API_URL=http://127.0.0.1:8010`
- `PIPELINE_INTERNAL_API_URL=http://127.0.0.1:8010`
- `CORS_ALLOWED_ORIGINS` includes `http://localhost:5173`

### Root `.env` / `.env.example`

- `GOOGLE_MAPS_SCRAPER_BIN` (optional override for Stage 1 binary path)
- Optional Google/Gemini keys if needed by related flows

## Common Troubleshooting

- **API Offline in UI**
  - Ensure API is running on `8000`
  - Verify CORS allows `http://localhost:5173`
- **Stage 1 rows = 0**
  - Check query quality (keyword + province + district)
  - Check geocode line in pipeline output
  - Confirm binary exists in `tools/`
- **Pipeline says OK but dashboard empty**
  - Check Stage 1 line `CSV -> API: OK (...)`
  - Check `GET /api/stats`
- **Install fails**
  - Open install log in `logs/`
  - Fix reported step (Python/PHP/Composer/Node), then re-run `one_click_install.bat`

## Manual Commands (optional)

If you do not use one-click scripts:

```bat
:: API
cd api-laravel
php artisan serve --host=127.0.0.1 --port=8000

:: Internal API worker (second terminal)
cd api-laravel
php artisan serve --host=127.0.0.1 --port=8010

:: Web
cd web-ui-react
npx vite --host=localhost --port=5173
```

## Status

- Web UI, API, and pipeline are integrated
- Logs page is available and polls run status/output
- Pipeline imports Stage 1 results to API automatically
