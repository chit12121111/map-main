<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class CheckIn extends Model
{
    protected $table = 'checkins';

    protected $fillable = [
        'token',
        'email',
        'ip_address',
        'user_agent',
        'referrer',
    ];
}
