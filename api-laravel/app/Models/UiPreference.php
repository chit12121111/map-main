<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class UiPreference extends Model
{
    protected $table = 'ui_preferences';

    protected $fillable = [
        'pref_key',
        'scope',
        'value',
    ];

    protected $casts = [
        'value' => 'array',
    ];
}
