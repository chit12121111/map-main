<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class PipelineRunLog extends Model
{
    protected $table = 'pipeline_run_logs';

    protected $fillable = [
        'pipeline_run_id',
        'seq',
        'level',
        'line',
    ];

    protected $casts = [
        'pipeline_run_id' => 'integer',
        'seq' => 'integer',
    ];

    public function run(): BelongsTo
    {
        return $this->belongsTo(PipelineRun::class, 'pipeline_run_id', 'id');
    }
}
