<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class InviteToken extends Model
{
    protected $table = 'invite_tokens';

    protected $primaryKey = 'token';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $fillable = [
        'token',
        'email',
        'used_at',
        'expires_at',
    ];

    protected $casts = [
        'used_at' => 'datetime',
        'expires_at' => 'datetime',
    ];
}
