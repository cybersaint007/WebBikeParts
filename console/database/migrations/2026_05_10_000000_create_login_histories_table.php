<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('login_histories', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->nullable()->constrained()->nullOnDelete();
            $table->string('email', 255)->nullable();
            $table->string('ip_address', 45)->nullable();
            $table->text('user_agent')->nullable();
            $table->boolean('success')->default(true);
            $table->timestamp('login_at');
            $table->timestamp('logout_at')->nullable();
            $table->index(['user_id', 'login_at']);
            $table->index('login_at');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('login_histories');
    }
};
