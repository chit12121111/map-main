<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ui_preferences', function (Blueprint $table) {
            $table->id();
            $table->string('pref_key', 100);
            $table->string('scope', 50)->default('global');
            $table->json('value');
            $table->timestamps();
        });

        Schema::table('ui_preferences', function (Blueprint $table) {
            $table->unique(['pref_key', 'scope']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ui_preferences');
    }
};
