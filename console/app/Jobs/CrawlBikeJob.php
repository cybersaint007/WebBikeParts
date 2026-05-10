<?php

namespace App\Jobs;

use App\Models\SyncRun;

class CrawlBikeJob extends RunPartsWatchJob
{
    public function __construct(int $syncRunId, public string $catalogKey)
    {
        parent::__construct($syncRunId);
    }

    public function handle(): void
    {
        // Ensure payload always carries catalog_key — guards against manually-dispatched
        // jobs where the SyncRun was created without it.
        $run = SyncRun::find($this->syncRunId);
        if ($run && empty($run->payload['catalog_key'] ?? null)) {
            $run->update(['payload' => array_merge($run->payload ?? [], ['catalog_key' => $this->catalogKey])]);
        }
        parent::handle();
    }

    protected function arguments(): array
    {
        return ['crawl', '--bike', $this->catalogKey];
    }
}
