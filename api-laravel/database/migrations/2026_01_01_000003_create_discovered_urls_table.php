<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('discovered_urls', function (Blueprint $table) {
            $table->id();
            $table->string('place_id', 255);
            $table->string('url', 2000);
            $table->string('url_type', 20);
            $table->string('found_by_stage', 20);
            $table->string('status', 20)->default('NEW');
            $table->timestamps();

            $table->foreign('place_id')->references('place_id')->on('places')->onDelete('cascade');
            $table->index('place_id');
            $table->index('status');
            $table->index('url_type');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('discovered_urls');
    }
};
