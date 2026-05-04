<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('user_bikes', function (Blueprint $table) {
            $table->bigIncrements('id');
            $table->foreignId('user_id')->constrained('users')->cascadeOnDelete();
            $table->integer('bike_catalog_id'); // soft FK to watcher.bike_catalog (cross-schema, app-validated)
            $table->string('nickname', 120)->nullable();
            $table->timestamp('created_at')->useCurrent();

            $table->unique(['user_id', 'bike_catalog_id']);
            $table->index('bike_catalog_id');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('user_bikes');
    }
};
