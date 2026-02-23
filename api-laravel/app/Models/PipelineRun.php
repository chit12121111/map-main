<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class PipelineRun extends Model
{
    protected $table = 'pipeline_runs';

    protected $fillable = [
        'query',
        'status',
        'started_at',
        'finished_at',
        'elapsed_ms',
        'rows',
        'report_path',
        'source',
        'error',
    ];

    protected $casts = [
        'started_at' => 'datetime',
        'finished_at' => 'datetime',
        'elapsed_ms' => 'integer',
        'rows' => 'integer',
    ];

    public function logs(): HasMany
    {
        return $this->hasMany(PipelineRunLog::class, 'pipeline_run_id', 'id')->orderBy('seq');
    }
}
