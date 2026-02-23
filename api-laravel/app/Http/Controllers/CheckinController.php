<?php

namespace App\Http\Controllers;

use App\Models\CheckIn;
use App\Models\EmailOutbox;
use App\Models\InviteToken;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\View\View;

class CheckinController extends Controller
{
    public function checkinPage(): View
    {
        return view('checkin');
    }

    public function checkin(Request $request): JsonResponse
    {
        $data = $request->validate(['token' => 'required|string']);

        $invite = InviteToken::find($data['token']);

        if (! $invite) {
            return response()->json([
                'detail' => 'Token ไม่ถูกต้อง หรือไม่มีในระบบ',
            ], 404);
        }

        if ($invite->used_at) {
            return response()->json([
                'message' => 'ยินดีต้อนรับกลับมา',
                'email' => $invite->email,
                'status' => 'already_used',
                'checked_in_at' => $invite->used_at->format('Y-m-d H:i:s').' UTC',
            ]);
        }

        if ($invite->expires_at && $invite->expires_at->isPast()) {
            return response()->json([
                'detail' => 'Token หมดอายุแล้วเมื่อ '.$invite->expires_at->format('Y-m-d H:i:s').' UTC',
            ], 400);
        }

        $now = now();
        CheckIn::create([
            'token' => $invite->token,
            'email' => $invite->email,
            'ip_address' => $request->header('X-Forwarded-For') ? explode(',', $request->header('X-Forwarded-For'))[0] : $request->ip(),
            'user_agent' => $request->userAgent(),
            'referrer' => $request->header('Referer'),
        ]);

        $invite->update(['used_at' => $now]);

        return response()->json([
            'message' => 'Check-in สำเร็จ',
            'email' => $invite->email,
            'status' => 'success',
            'checked_in_at' => $now->format('Y-m-d H:i:s').' UTC',
        ]);
    }

    public function createToken(Request $request): JsonResponse
    {
        $data = $request->validate([
            'email' => 'required|email',
            'expires_in_days' => 'nullable|integer|min:1',
        ]);

        $token = Str::random(48);
        $expiresAt = isset($data['expires_in_days'])
            ? now()->addDays($data['expires_in_days'])
            : null;

        InviteToken::create([
            'token' => $token,
            'email' => $data['email'],
            'expires_at' => $expiresAt,
        ]);

        $baseUrl = $request->getSchemeAndHttpHost();
        $link = rtrim($baseUrl, '/').'/index.html?t='.$token;

        return response()->json([
            'token' => $token,
            'email' => $data['email'],
            'link' => $link,
            'expires_at' => $expiresAt?->format('Y-m-d H:i:s').' UTC',
        ]);
    }

    public function getTokens(Request $request): JsonResponse
    {
        $query = InviteToken::query()->orderByDesc('created_at');
        if ($request->filled('email')) {
            $query->where('email', $request->email);
        }
        $tokens = $query->get();

        return response()->json([
            'total' => $tokens->count(),
            'tokens' => $tokens->map(fn ($t) => [
                'token' => $t->token,
                'email' => $t->email,
                'used' => $t->used_at !== null,
                'used_at' => $t->used_at?->format('Y-m-d H:i:s').' UTC',
                'expires_at' => $t->expires_at?->format('Y-m-d H:i:s').' UTC',
                'created_at' => $t->created_at->format('Y-m-d H:i:s').' UTC',
            ]),
        ]);
    }

    public function getCheckins(Request $request): JsonResponse
    {
        $query = CheckIn::query()->orderByDesc('created_at');
        if ($request->filled('email')) {
            $query->where('email', $request->email);
        }
        $limit = (int) $request->get('limit', 100);
        $checkins = $query->limit($limit)->get();

        return response()->json([
            'total' => $checkins->count(),
            'checkins' => $checkins->map(fn ($c) => [
                'email' => $c->email,
                'ip_address' => $c->ip_address,
                'user_agent' => $c->user_agent ? substr($c->user_agent, 0, 100) : null,
                'checked_in_at' => $c->created_at->format('Y-m-d H:i:s').' UTC',
            ]),
        ]);
    }

    public function recordResponse(Request $request): JsonResponse
    {
        $data = $request->validate([
            'token' => 'required|string',
            'email' => 'required|email',
            'response' => 'required|string|in:interested,unsubscribe',
        ]);

        $ip = $request->header('X-Forwarded-For') ? explode(',', $request->header('X-Forwarded-For'))[0] : $request->ip();
        CheckIn::create([
            'token' => $data['token'],
            'email' => $data['email'],
            'ip_address' => $ip,
            'user_agent' => 'RESPONSE:'.$data['response'],
            'referrer' => $request->header('Referer'),
        ]);
        EmailOutbox::query()
            ->where('token', $data['token'])
            ->where('email', $data['email'])
            ->update([
                'response_status' => $data['response'] === 'interested' ? 'INTERESTED' : 'UNSUBSCRIBED',
                'responded_at' => now(),
            ]);

        return response()->json([
            'message' => 'บันทึกเรียบร้อยแล้ว',
            'email' => $data['email'],
            'response' => $data['response'],
        ]);
    }

    public function getResponses(Request $request): JsonResponse
    {
        $query = CheckIn::query()
            ->where('user_agent', 'like', 'RESPONSE:%')
            ->orderByDesc('created_at');
        if ($request->filled('response_type')) {
            $query->where('user_agent', 'RESPONSE:'.$request->response_type);
        }
        $results = $query->get();

        $interested = [];
        $unsubscribed = [];
        foreach ($results as $r) {
            $respType = str_replace('RESPONSE:', '', $r->user_agent);
            $item = [
                'email' => $r->email,
                'response' => $respType,
                'created_at' => $r->created_at->format('Y-m-d H:i:s').' UTC',
            ];
            if ($respType === 'interested') {
                $interested[] = $item;
            } else {
                $unsubscribed[] = $item;
            }
        }

        return response()->json([
            'total_interested' => count($interested),
            'total_unsubscribed' => count($unsubscribed),
            'interested' => $interested,
            'unsubscribed' => $unsubscribed,
        ]);
    }
}
