<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('pipeline_runs', function (Blueprint $table) {
            $table->id();
            $table->text('query');
            $table->string('status', 20)->default('RUNNING');
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->unsignedInteger('elapsed_ms')->nullable();
            $table->unsignedInteger('rows')->nullable();
            $table->string('report_path', 1000)->nullable();
            $table->string('source', 50)->nullable();
            $table->text('error')->nullable();
            $table->timestamps();
        });

        Schema::table('pipeline_runs', function (Blueprint $table) {
            $table->index('status');
            $table->index('started_at');
            $table->index('created_at');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('pipeline_runs');
    }
};
