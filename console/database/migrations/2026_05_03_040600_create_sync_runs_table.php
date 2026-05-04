<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('sync_runs', function (Blueprint $table) {
            $table->bigIncrements('id');
            $table->string('kind', 40);
            $table->string('status', 20);
            $table->foreignId('triggered_by')->nullable()->constrained('users')->nullOnDelete();
            $table->jsonb('payload')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->text('output_excerpt')->nullable();
            $table->timestamps();

            $table->index(['kind', 'status']);
            $table->index('created_at');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('sync_runs');
    }
};
