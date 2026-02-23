<?php

namespace App\Jobs;

use App\Models\EmailCampaign;
use App\Models\EmailOutbox;
use App\Models\InviteToken;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Str;

class SendEmailCampaignJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function __construct(public int $campaignId)
    {
    }

    public function handle(): void
    {
        $campaign = EmailCampaign::query()->find($this->campaignId);
        if (! $campaign) {
            return;
        }

        if ($campaign->status === 'COMPLETED' || $campaign->status === 'CANCELLED') {
            return;
        }

        if (! $campaign->started_at) {
            $campaign->update([
                'status' => 'SENDING',
                'started_at' => now(),
            ]);
        } elseif ($campaign->status === 'QUEUED') {
            $campaign->update(['status' => 'SENDING']);
        }

        $batchSize = max(1, min(500, (int) env('EMAIL_CAMPAIGN_BATCH_SIZE', 50)));

        $rows = EmailOutbox::query()
            ->where('campaign_id', $campaign->id)
            ->where('status', 'PENDING')
            ->orderBy('id')
            ->limit($batchSize)
            ->get();

        foreach ($rows as $row) {
            try {
                $token = $row->token;
                if (! $token) {
                    $token = Str::random(48);
                    InviteToken::query()->updateOrCreate(
                        ['token' => $token],
                        [
                            'email' => $row->email,
                            'used_at' => null,
                            'expires_at' => now()->addDays((int) env('EMAIL_TOKEN_EXPIRES_DAYS', 30)),
                        ]
                    );
                    $row->update(['token' => $token]);
                }

                $baseUrl = rtrim((string) env('APP_URL', 'http://127.0.0.1:8000'), '/');
                $checkinLink = $baseUrl.'/index.html?t='.$token;
                $body = str_replace(
                    ['{{checkin_link}}', '{{email}}', '{{token}}'],
                    [$checkinLink, $row->email, $token],
                    $campaign->body_text
                );

                Mail::raw($body, function ($message) use ($campaign, $row) {
                    $message->to($row->email);
                    $message->subject($campaign->subject);
                });

                $row->update([
                    'status' => 'SENT',
                    'sent_at' => now(),
                    'response_status' => 'PENDING',
                    'last_error' => null,
                ]);
            } catch (\Throwable $e) {
                $row->update([
                    'status' => 'FAILED',
                    'retry_count' => (int) $row->retry_count + 1,
                    'last_error' => mb_substr($e->getMessage(), 0, 1000),
                ]);
                Log::warning('Email campaign send failed', [
                    'campaign_id' => $campaign->id,
                    'outbox_id' => $row->id,
                    'email' => $row->email,
                    'error' => $e->getMessage(),
                ]);
            }
        }

        $stats = EmailOutbox::query()
            ->where('campaign_id', $campaign->id)
            ->selectRaw("SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_count")
            ->selectRaw("SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) AS sent_count")
            ->selectRaw("SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_count")
            ->first();

        $pending = (int) ($stats->pending_count ?? 0);
        $sent = (int) ($stats->sent_count ?? 0);
        $failed = (int) ($stats->failed_count ?? 0);

        $campaign->update([
            'pending_count' => $pending,
            'sent_count' => $sent,
            'failed_count' => $failed,
            'status' => $pending > 0 ? 'SENDING' : 'COMPLETED',
            'finished_at' => $pending > 0 ? null : now(),
        ]);

        if ($pending > 0) {
            self::dispatch($campaign->id);
        }
    }
}
