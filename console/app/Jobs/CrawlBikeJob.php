<?php

namespace App\Jobs;

class CrawlBikeJob extends RunPartsWatchJob
{
    public function __construct(int $syncRunId, public string $catalogKey)
    {
        parent::__construct($syncRunId);
    }

    protected function arguments(): array
    {
        return ['crawl', '--bike', $this->catalogKey];
    }
}
