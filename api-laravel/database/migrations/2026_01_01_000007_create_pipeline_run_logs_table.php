<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('pipeline_run_logs', function (Blueprint $table) {
            $table->id();
            $table->foreignId('pipeline_run_id')->constrained('pipeline_runs')->cascadeOnDelete();
            $table->unsignedInteger('seq');
            $table->string('level', 20)->default('info');
            $table->text('line');
            $table->timestamps();
        });

        Schema::table('pipeline_run_logs', function (Blueprint $table) {
            $table->unique(['pipeline_run_id', 'seq']);
            $table->index(['pipeline_run_id', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('pipeline_run_logs');
    }
};
