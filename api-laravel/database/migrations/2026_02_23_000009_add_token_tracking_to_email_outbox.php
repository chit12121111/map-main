<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('email_outbox', function (Blueprint $table) {
            if (! Schema::hasColumn('email_outbox', 'token')) {
                $table->string('token', 64)->nullable()->after('source');
            }
            if (! Schema::hasColumn('email_outbox', 'response_status')) {
                $table->string('response_status', 20)->default('PENDING')->after('status');
            }
            if (! Schema::hasColumn('email_outbox', 'responded_at')) {
                $table->timestamp('responded_at')->nullable()->after('sent_at');
            }
        });

        Schema::table('email_outbox', function (Blueprint $table) {
            $table->index('token');
            $table->index('response_status');
        });
    }

    public function down(): void
    {
        Schema::table('email_outbox', function (Blueprint $table) {
            $table->dropIndex(['token']);
            $table->dropIndex(['response_status']);
        });
    }
};
