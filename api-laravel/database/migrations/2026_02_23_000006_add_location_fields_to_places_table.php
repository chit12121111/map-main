<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('places', function (Blueprint $table) {
            if (! Schema::hasColumn('places', 'province')) {
                $table->string('province', 255)->nullable()->after('address');
            }
            if (! Schema::hasColumn('places', 'district')) {
                $table->string('district', 255)->nullable()->after('province');
            }
            if (! Schema::hasColumn('places', 'normalized_category')) {
                $table->string('normalized_category', 255)->nullable()->after('category');
            }
        });

        Schema::table('places', function (Blueprint $table) {
            $table->index('province');
            $table->index('district');
            $table->index('normalized_category');
        });
    }

    public function down(): void
    {
        Schema::table('places', function (Blueprint $table) {
            $table->dropIndex(['province']);
            $table->dropIndex(['district']);
            $table->dropIndex(['normalized_category']);
        });
    }
};
