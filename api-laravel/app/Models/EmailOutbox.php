<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class EmailOutbox extends Model
{
    protected $table = 'email_outbox';

    protected $fillable = [
        'campaign_id',
        'place_id',
        'email',
        'source',
        'token',
        'status',
        'response_status',
        'retry_count',
        'last_error',
        'sent_at',
        'responded_at',
    ];

    protected $casts = [
        'sent_at' => 'datetime',
        'responded_at' => 'datetime',
    ];

    public function campaign(): BelongsTo
    {
        return $this->belongsTo(EmailCampaign::class, 'campaign_id', 'id');
    }
}
