<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class DiscoveredUrl extends Model
{
    protected $table = 'discovered_urls';

    protected $fillable = [
        'place_id',
        'url',
        'url_type',
        'found_by_stage',
        'status',
    ];

    public function place(): BelongsTo
    {
        return $this->belongsTo(Place::class, 'place_id', 'place_id');
    }
}
