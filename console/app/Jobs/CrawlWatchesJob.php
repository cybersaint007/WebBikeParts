<?php

namespace App\Jobs;

class CrawlWatchesJob extends RunPartsWatchJob
{
    protected function arguments(): array
    {
        return ['crawl-watches'];
    }
}
