<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Place extends Model
{
    protected $table = 'places';

    protected $primaryKey = 'place_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $fillable = [
        'place_id',
        'name',
        'website',
        'phone',
        'google_maps_url',
        'address',
        'category',
        'normalized_category',
        'province',
        'district',
        'review_count',
        'review_rating',
        'latitude',
        'longitude',
        'raw_data',
        'status',
    ];

    protected $casts = [
        'review_count' => 'integer',
        'review_rating' => 'float',
        'latitude' => 'float',
        'longitude' => 'float',
    ];

    public function emails(): HasMany
    {
        return $this->hasMany(Email::class, 'place_id', 'place_id');
    }

    public function discoveredUrls(): HasMany
    {
        return $this->hasMany(DiscoveredUrl::class, 'place_id', 'place_id');
    }
}
