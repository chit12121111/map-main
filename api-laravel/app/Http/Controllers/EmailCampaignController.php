<?php

namespace App\Http\Controllers;

use App\Jobs\SendEmailCampaignJob;
use App\Models\CheckIn;
use App\Models\Email;
use App\Models\EmailCampaign;
use App\Models\EmailOutbox;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class EmailCampaignController extends Controller
{
    private function normalizeEmail(string $email): string
    {
        return mb_strtolower(trim($email), 'UTF-8');
    }

    private function getUnsubscribedSet(): array
    {
        $rows = CheckIn::query()
            ->where('user_agent', 'RESPONSE:unsubscribe')
            ->pluck('email')
            ->all();

        $set = [];
        foreach ($rows as $email) {
            if (! is_string($email)) {
                continue;
            }
            $normalized = $this->normalizeEmail($email);
            if ($normalized !== '') {
                $set[$normalized] = true;
            }
        }

        return $set;
    }

    private function buildRecipientRows(array $filters): array
    {
        $query = Email::query()
            ->select(['emails.id', 'emails.email', 'emails.place_id', 'emails.source'])
            ->join('places', 'places.place_id', '=', 'emails.place_id')
            ->orderByDesc('emails.id');

        if (! empty($filters['status'])) {
            $query->where('places.status', $filters['status']);
        }
        if (! empty($filters['province'])) {
            $query->where('places.province', $filters['province']);
        }
        if (! empty($filters['district'])) {
            $query->where('places.district', $filters['district']);
        }
        if (! empty($filters['category'])) {
            $query->where('places.category', $filters['category']);
        }
        if (! empty($filters['normalized_category'])) {
            $query->where('places.normalized_category', $filters['normalized_category']);
        }
        if (! empty($filters['source'])) {
            $query->where('emails.source', $filters['source']);
        }

        $rows = $query->limit(max(1, min(10000, (int) ($filters['limit'] ?? 3000))))->get();
        $unsubscribed = $this->getUnsubscribedSet();

        $deduped = [];
        foreach ($rows as $row) {
            $normalizedEmail = $this->normalizeEmail((string) $row->email);
            if ($normalizedEmail === '') {
                continue;
            }
            if (isset($unsubscribed[$normalizedEmail])) {
                continue;
            }
            if (isset($deduped[$normalizedEmail])) {
                continue;
            }
            $deduped[$normalizedEmail] = [
                'email' => $normalizedEmail,
                'place_id' => $row->place_id,
                'source' => $row->source,
            ];
        }

        return array_values($deduped);
    }

    private function computeResponseStatus(string $token): string
    {
        if ($token === '') {
            return 'PENDING';
        }
        $latest = CheckIn::query()
            ->where('token', $token)
            ->where('user_agent', 'like', 'RESPONSE:%')
            ->orderByDesc('id')
            ->value('user_agent');
        if (! is_string($latest) || $latest === '') {
            return 'PENDING';
        }
        $type = str_replace('RESPONSE:', '', $latest);
        if ($type === 'interested') {
            return 'INTERESTED';
        }
        if ($type === 'unsubscribe') {
            return 'UNSUBSCRIBED';
        }

        return 'PENDING';
    }

    public function preview(Request $request): JsonResponse
    {
        $filters = $request->validate([
            'status' => 'nullable|string|max:30',
            'province' => 'nullable|string|max:255',
            'district' => 'nullable|string|max:255',
            'category' => 'nullable|string|max:255',
            'normalized_category' => 'nullable|string|max:255',
            'source' => 'nullable|string|max:50',
            'limit' => 'nullable|integer|min:1|max:10000',
            'selected_emails' => 'nullable|array',
            'selected_emails.*' => 'string|email',
        ]);

        $recipients = $this->buildRecipientRows($filters);
        if (! empty($filters['selected_emails']) && is_array($filters['selected_emails'])) {
            $picked = array_map(fn ($e) => $this->normalizeEmail((string) $e), $filters['selected_emails']);
            $pickedMap = array_fill_keys(array_filter($picked), true);
            $recipients = array_values(array_filter($recipients, fn (array $r) => isset($pickedMap[$r['email']])));
        }

        return response()->json([
            'count' => count($recipients),
            'recipients' => array_slice($recipients, 0, 200),
            'filters' => $filters,
        ]);
    }

    public function send(Request $request): JsonResponse
    {
        $data = $request->validate([
            'subject' => 'required|string|max:255',
            'body_text' => 'required|string|min:3',
            'status' => 'nullable|string|max:30',
            'province' => 'nullable|string|max:255',
            'district' => 'nullable|string|max:255',
            'category' => 'nullable|string|max:255',
            'normalized_category' => 'nullable|string|max:255',
            'source' => 'nullable|string|max:50',
            'limit' => 'nullable|integer|min:1|max:10000',
            'selected_emails' => 'nullable|array',
            'selected_emails.*' => 'string|email',
            'dry_run' => 'nullable|boolean',
        ]);

        $filters = [
            'status' => $data['status'] ?? null,
            'province' => $data['province'] ?? null,
            'district' => $data['district'] ?? null,
            'category' => $data['category'] ?? null,
            'normalized_category' => $data['normalized_category'] ?? null,
            'source' => $data['source'] ?? null,
            'limit' => $data['limit'] ?? null,
            'selected_emails' => $data['selected_emails'] ?? null,
        ];

        $recipients = $this->buildRecipientRows($filters);
        if (! empty($data['selected_emails']) && is_array($data['selected_emails'])) {
            $picked = array_map(fn ($e) => $this->normalizeEmail((string) $e), $data['selected_emails']);
            $pickedMap = array_fill_keys(array_filter($picked), true);
            $recipients = array_values(array_filter($recipients, fn (array $r) => isset($pickedMap[$r['email']])));
        }
        if (! empty($data['dry_run'])) {
            return response()->json([
                'dry_run' => true,
                'count' => count($recipients),
                'recipients' => array_slice($recipients, 0, 200),
                'filters' => $filters,
            ]);
        }

        if (empty($recipients)) {
            return response()->json([
                'message' => 'No recipients matched filters',
                'count' => 0,
            ], 422);
        }

        $campaign = EmailCampaign::query()->create([
            'subject' => $data['subject'],
            'body_text' => $data['body_text'],
            'filters_json' => $filters,
            'status' => 'QUEUED',
            'requested_by' => $request->ip(),
            'total_recipients' => count($recipients),
            'pending_count' => count($recipients),
            'sent_count' => 0,
            'failed_count' => 0,
        ]);

        $now = now();
        $rows = array_map(fn (array $item) => [
            'campaign_id' => $campaign->id,
            'place_id' => $item['place_id'],
            'email' => $item['email'],
            'source' => $item['source'],
            'token' => null,
            'status' => 'PENDING',
            'response_status' => 'PENDING',
            'retry_count' => 0,
            'last_error' => null,
            'sent_at' => null,
            'responded_at' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ], $recipients);

        foreach (array_chunk($rows, 500) as $chunk) {
            EmailOutbox::query()->insert($chunk);
        }

        SendEmailCampaignJob::dispatch($campaign->id);

        return response()->json([
            'message' => 'Campaign queued',
            'campaign_id' => $campaign->id,
            'count' => count($recipients),
        ], 201);
    }

    public function index(Request $request): JsonResponse
    {
        $limit = max(1, min(100, (int) $request->get('limit', 30)));
        $rows = EmailCampaign::query()->orderByDesc('id')->limit($limit)->get();

        return response()->json([
            'total' => $rows->count(),
            'campaigns' => $rows,
        ]);
    }

    public function show(string $id): JsonResponse
    {
        $campaign = EmailCampaign::query()->findOrFail((int) $id);

        $recent = EmailOutbox::query()
            ->where('campaign_id', $campaign->id)
            ->orderByDesc('id')
            ->limit(100)
            ->get(['id', 'email', 'place_id', 'source', 'token', 'status', 'response_status', 'retry_count', 'last_error', 'sent_at', 'responded_at', 'created_at']);

        $interested = 0;
        $unsubscribed = 0;
        $pending = 0;
        foreach ($recent as $row) {
            $resp = $this->computeResponseStatus((string) ($row->token ?? ''));
            if ($resp !== $row->response_status) {
                $row->response_status = $resp;
                $row->responded_at = $resp === 'PENDING' ? null : now();
                $row->save();
            }
            if ($resp === 'INTERESTED') {
                $interested++;
            } elseif ($resp === 'UNSUBSCRIBED') {
                $unsubscribed++;
            } else {
                $pending++;
            }
        }

        return response()->json([
            'campaign' => $campaign,
            'response_summary' => [
                'INTERESTED' => $interested,
                'UNSUBSCRIBED' => $unsubscribed,
                'PENDING' => $pending,
            ],
            'outbox' => $recent,
        ]);
    }
}
