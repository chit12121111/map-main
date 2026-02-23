<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('emails', function (Blueprint $table) {
            $table->id();
            $table->string('place_id', 255);
            $table->string('email', 255);
            $table->string('source', 50);
            $table->timestamps();

            $table->foreign('place_id')->references('place_id')->on('places')->onDelete('cascade');
            $table->unique(['place_id', 'email']);
        });

        Schema::table('emails', function (Blueprint $table) {
            $table->index('place_id');
            $table->index('email');
            $table->index('source');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('emails');
    }
};
