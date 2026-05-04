<?php

namespace App\Jobs;

use App\Models\SyncRun;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Process;

/**
 * Base job for shelling out to the `parts-watch` Python CLI.
 * Subclasses define the argv they want to run.
 */
abstract class RunPartsWatchJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $timeout = 1800;     // 30 minutes
    public int $tries = 1;

    public function __construct(public int $syncRunId) {}

    abstract protected function arguments(): array;

    public function handle(): void
    {
        $run = SyncRun::find($this->syncRunId);
        if (!$run) return;

        $bin = config('crawler.bin');
        $cwd = config('crawler.cwd');

        if (!is_executable($bin)) {
            $run->markFailed("parts-watch binary not found or not executable at: {$bin}\n"
                . "Set WATCHER_PARTS_WATCH_BIN in console/.env to the venv's parts-watch path.");
            return;
        }

        $run->markRunning();

        // Override Laravel-inherited DB_* env vars so the Python subprocess connects
        // with the WATCHER_DB_* values (separate connection, watcher schema), not Laravel's
        // pgsql / console-schema config.
        $env = [
            'DATABASE_URL' => sprintf(
                'postgresql+psycopg://%s%s@%s:%s/%s',
                env('WATCHER_DB_USERNAME', env('DB_USERNAME', '')),
                env('WATCHER_DB_PASSWORD') ? ':' . env('WATCHER_DB_PASSWORD') : '',
                env('WATCHER_DB_HOST', env('DB_HOST', '127.0.0.1')),
                env('WATCHER_DB_PORT', env('DB_PORT', '5432')),
                env('WATCHER_DB_DATABASE', env('DB_DATABASE')),
            ),
            'DB_SCHEMA' => env('WATCHER_DB_SCHEMA', 'watcher'),
        ];

        $argv = array_merge([$bin], $this->arguments());
        $result = Process::path($cwd)
            ->env($env)
            ->timeout($this->timeout)
            ->run($argv);

        $output = $result->output() . "\n" . $result->errorOutput();

        if ($result->successful()) {
            $run->markSuccess($output);
        } else {
            $run->markFailed("Exit {$result->exitCode()}\n" . $output);
        }
    }

    public function failed(\Throwable $e): void
    {
        $run = SyncRun::find($this->syncRunId);
        $run?->markFailed("Job exception: " . $e->getMessage());
    }
}
