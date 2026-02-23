<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('places', function (Blueprint $table) {
            $table->string('place_id', 255)->primary();
            $table->string('name');
            $table->string('website', 500)->nullable();
            $table->string('phone', 50)->nullable();
            $table->string('google_maps_url', 1000);
            $table->text('address')->nullable();
            $table->string('category', 255)->nullable();
            $table->unsignedInteger('review_count')->nullable();
            $table->decimal('review_rating', 3, 2)->nullable();
            $table->decimal('latitude', 10, 8)->nullable();
            $table->decimal('longitude', 11, 8)->nullable();
            $table->longText('raw_data');
            $table->string('status', 20)->default('NEW');
            $table->timestamps();
        });

        Schema::table('places', function (Blueprint $table) {
            $table->index('status');
            $table->index('name');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('places');
    }
};
