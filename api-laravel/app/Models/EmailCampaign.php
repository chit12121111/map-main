<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class EmailCampaign extends Model
{
    protected $table = 'email_campaigns';

    protected $fillable = [
        'subject',
        'body_text',
        'filters_json',
        'status',
        'requested_by',
        'total_recipients',
        'pending_count',
        'sent_count',
        'failed_count',
        'started_at',
        'finished_at',
        'last_error',
    ];

    protected $casts = [
        'filters_json' => 'array',
        'started_at' => 'datetime',
        'finished_at' => 'datetime',
    ];

    public function outbox(): HasMany
    {
        return $this->hasMany(EmailOutbox::class, 'campaign_id', 'id');
    }
}
