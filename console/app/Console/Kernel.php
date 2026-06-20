<?php

namespace App\Console;

use App\Jobs\CleanseListingsJob;
use App\Jobs\CrawlAllJob;
use App\Jobs\CrawlWatchesJob;
use App\Models\SyncRun;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Foundation\Console\Kernel as ConsoleKernel;

class Kernel extends ConsoleKernel
{
    /**
     * Define the application's command schedule.
     *
     * @param  \Illuminate\Console\Scheduling\Schedule  $schedule
     * @return void
     */
    protected function schedule(Schedule $schedule)
    {
        // Hourly bike sweep: every active bike × every enabled adapter.
        // Skipped if a prior crawl-all is still queued/running, so a slow
        // sweep doesn't pile up duplicates the next hour.
        $schedule->call(fn () => $this->dispatchSweep(SyncRun::KIND_CRAWL_ALL, CrawlAllJob::class))
            ->hourly()
            ->name('crawl-all')
            ->onOneServer();

        // Hourly watch-list sweep: only is_high_priority=true rows.
        // Cheaper than crawl-all and the reason the watch-list exists.
        $schedule->call(fn () => $this->dispatchSweep(SyncRun::KIND_CRAWL_WATCHES, CrawlWatchesJob::class))
            ->hourly()
            ->name('crawl-watches')
            ->onOneServer();

        // Daily cleanse: hard-delete listings unseen by a crawl in 14 days
        // (expired auctions, sold-out parts). A per-source freshness guard in
        // the CLI skips sources with no recent activity so a crawler outage
        // can't wipe still-live listings.
        $schedule->call(fn () => $this->dispatchSweep(SyncRun::KIND_CLEANSE_LISTINGS, CleanseListingsJob::class))
            ->daily()
            ->name('cleanse-listings')
            ->onOneServer();
    }

    private function dispatchSweep(string $kind, string $jobClass): void
    {
        $inFlight = SyncRun::where('kind', $kind)
            ->whereIn('status', [SyncRun::STATUS_QUEUED, SyncRun::STATUS_RUNNING])
            ->exists();
        if ($inFlight) {
            return;
        }
        $run = SyncRun::create([
            'kind' => $kind,
            'status' => SyncRun::STATUS_QUEUED,
            'triggered_by' => null,
            'payload' => ['source' => 'scheduler'],
        ]);
        $jobClass::dispatch($run->id)->onQueue('sync');
    }

    /**
     * Register the commands for the application.
     *
     * @return void
     */
    protected function commands()
    {
        $this->load(__DIR__.'/Commands');

        require base_path('routes/console.php');
    }
}
