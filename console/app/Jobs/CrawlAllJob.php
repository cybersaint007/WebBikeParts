<?php

namespace App\Jobs;

class CrawlAllJob extends RunPartsWatchJob
{
    protected function arguments(): array
    {
        return ['crawl-all'];
    }
}
