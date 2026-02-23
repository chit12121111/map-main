<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Check-in API</title>
    <style>
        body { font-family: 'Inter', sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #667eea; }
        .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 8px; }
        code { background: #333; color: #0f0; padding: 2px 8px; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Check-in API</h1>
    <p>API สำหรับระบบ Auto Check-in ด้วย Token และ Pipeline (places, emails)</p>
    <h2>Endpoints:</h2>
    <div class="endpoint"><strong>GET /health</strong><br>ตรวจสอบสถานะ API</div>
    <div class="endpoint"><strong>POST /checkin</strong><br>Check-in ด้วย token<br>Body: <code>{"token": "abc123"}</code></div>
    <div class="endpoint"><strong>POST /api/create-token</strong><br>สร้าง token ใหม่<br>Body: <code>{"email": "user@example.com"}</code></div>
    <div class="endpoint"><strong>GET /api/tokens</strong><br>ดู token ทั้งหมด</div>
    <div class="endpoint"><strong>GET /api/checkins</strong><br>ดูประวัติ check-in</div>
    <div class="endpoint"><strong>GET /api/stats</strong><br>สถิติ places, emails, discovered_urls</div>
    <div class="endpoint"><strong>GET /api/places</strong>, <strong>POST /api/places/import</strong>, <strong>POST /api/places/clear</strong></div>
    <div class="endpoint"><strong>GET /api/emails</strong>, <strong>POST /api/emails</strong>, <strong>POST /api/emails/bulk-delete</strong></div>
    <p>หน้า Check-in (ลิงก์ token): <a href="/index.html">/index.html</a></p>
</body>
</html>
