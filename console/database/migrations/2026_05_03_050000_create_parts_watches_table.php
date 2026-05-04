<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('parts_watches', function (Blueprint $table) {
            $table->bigIncrements('id');
            $table->foreignId('user_id')->constrained('users')->cascadeOnDelete();
            $table->integer('bike_catalog_id')->nullable(); // null = applies to all of user's bikes
            $table->string('query', 200);
            $table->boolean('is_high_priority')->default(true);
            $table->timestamp('priority_revoked_at')->nullable();
            $table->timestamp('last_crawled_at')->nullable();
            $table->integer('match_count')->default(0);
            $table->timestamps();

            $table->unique(['user_id', 'bike_catalog_id', 'query'], 'uq_parts_watches_user_bike_query');
            $table->index(['is_high_priority', 'last_crawled_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('parts_watches');
    }
};
