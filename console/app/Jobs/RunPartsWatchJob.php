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
        // Also forward adapter-enabled flags: console/.env doesn't carry these, so without
        // explicit forwarding the Python Settings class falls back to default=False for most
        // adapters and only ebay + manual_search (default=True) get enqueued.
        $env = [
            'DATABASE_URL' => sprintf(
                'postgresql+psycopg://%s%s@%s:%s/%s',
                env('WATCHER_DB_USERNAME', env('DB_USERNAME', '')),
                env('WATCHER_DB_PASSWORD') ? ':' . env('WATCHER_DB_PASSWORD') : '',
                env('WATCHER_DB_HOST', env('DB_HOST', '127.0.0.1')),
                env('WATCHER_DB_PORT', env('DB_PORT', '5432')),
                env('WATCHER_DB_DATABASE', env('DB_DATABASE')),
            ),
            'DB_SCHEMA'              => env('WATCHER_DB_SCHEMA', 'watcher'),
            'EBAY_ENABLED'           => env('EBAY_ENABLED', 'true'),
            'EBAY_CLIENT_ID'         => env('EBAY_CLIENT_ID', ''),
            'EBAY_CLIENT_SECRET'     => env('EBAY_CLIENT_SECRET', ''),
            'EBAY_MARKETPLACE_IDS'   => env('EBAY_MARKETPLACE_IDS', 'EBAY_US'),
            'BUYEE_ENABLED'          => env('BUYEE_ENABLED', 'true'),
            'WEBIKE_ENABLED'         => env('WEBIKE_ENABLED', 'true'),
            'WEBIKE_SEARCH_ENABLED'  => env('WEBIKE_SEARCH_ENABLED', 'false'),
            'WEBIKE_PROXY_URL'       => env('WEBIKE_PROXY_URL', ''),
            'WEBIKE_JP_ENABLED'      => env('WEBIKE_JP_ENABLED', 'false'),
            'YAHOO_AUCTIONS_ENABLED' => env('YAHOO_AUCTIONS_ENABLED', 'true'),
            'MONOTARO_ENABLED'       => env('MONOTARO_ENABLED', 'true'),
            'OLD_BIKE_BARN_ENABLED'  => env('OLD_BIKE_BARN_ENABLED', 'true'),
            'MERCARI_ENABLED'        => env('MERCARI_ENABLED', 'true'),
            'GOOBIKE_ENABLED'        => env('GOOBIKE_ENABLED', 'true'),
            'CROOOOBER_ENABLED'      => env('CROOOOBER_ENABLED', 'false'),
            'RAKUTEN_ENABLED'        => env('RAKUTEN_ENABLED', 'false'),
            'RAKUTEN_APP_ID'         => env('RAKUTEN_APP_ID', ''),
            'MANUAL_SEARCH_ENABLED'  => env('MANUAL_SEARCH_ENABLED', 'true'),
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
